"""Admin / field-ops API (X-API-Key protected).

Used by:
  * the field agent's price-entry tool (or ops entering on their behalf),
  * the ops KPI dashboard (metrics),
  * SOS monitoring and resolution,
  * broadcast announcements (e.g. cyclone warnings, service notices).
"""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin_key
from app.config import get_settings
from app.database import get_db
from app.enums import MessageType
from app.models import User, Village
from app.schemas import (
    BroadcastRequest,
    PriceBulkRequest,
    PriceResponse,
    ResolveSOSRequest,
    SOSAlertResponse,
)
from app.seeds import resolve_species
from app.services import metrics_service, price_service, sos_service, user_service
from app.services.messenger import send_message
from app.services.sos_service import maps_link

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin_key)])


def _today_ist() -> date:
    return datetime.now(ZoneInfo(get_settings().timezone)).date()


@router.post("/prices", response_model=list[PriceResponse])
async def submit_prices(
    request: PriceBulkRequest, db: AsyncSession = Depends(get_db)
) -> list[PriceResponse]:
    responses: list[PriceResponse] = []
    for entry in request.prices:
        center = await price_service.get_landing_center(db, entry.landing_center)
        if center is None:
            raise HTTPException(422, f"Unknown landing center: {entry.landing_center!r}")
        species = resolve_species(entry.species)
        if species is None:
            raise HTTPException(422, f"Unknown species: {entry.species!r}")
        price = await price_service.record_price(
            db,
            landing_center=center,
            species=species,
            price_per_kg=entry.price_per_kg,
            price_date=entry.price_date or _today_ist(),
            source=entry.source,
            reported_by_phone=request.reported_by_phone,
        )
        responses.append(
            PriceResponse(
                landing_center=center.name,
                species=price.species,
                price_per_kg=price.price_per_kg,
                price_date=price.price_date,
                source=price.source,
            )
        )
    return responses


@router.get("/prices", response_model=list[PriceResponse])
async def list_prices(
    day: date | None = None, db: AsyncSession = Depends(get_db)
) -> list[PriceResponse]:
    target = day or await price_service.get_latest_price_day(db, _today_ist())
    if target is None:
        return []
    prices = await price_service.get_prices_for_day(db, target)
    return [
        PriceResponse(
            landing_center=p.landing_center.name,
            species=p.species,
            price_per_kg=p.price_per_kg,
            price_date=p.price_date,
            source=p.source,
        )
        for p in prices
    ]


@router.get("/metrics")
async def metrics(db: AsyncSession = Depends(get_db)) -> dict:
    return await metrics_service.collect_metrics(db, _today_ist())


@router.get("/sos", response_model=list[SOSAlertResponse])
async def active_sos_alerts(db: AsyncSession = Depends(get_db)) -> list[SOSAlertResponse]:
    alerts = await sos_service.all_active_alerts(db)
    return [
        SOSAlertResponse(
            id=a.id,
            user_phone=a.user.phone,
            user_name=a.user.name,
            village=a.user.village.name if a.user.village else None,
            status=a.status.value,
            activated_at=a.activated_at,
            last_latitude=a.last_latitude,
            last_longitude=a.last_longitude,
            last_location_at=a.last_location_at,
            maps_link=maps_link(a.last_latitude, a.last_longitude)
            if a.last_latitude is not None else None,
        )
        for a in alerts
    ]


@router.post("/sos/{alert_id}/resolve")
async def resolve_sos(
    alert_id: int, request: ResolveSOSRequest, db: AsyncSession = Depends(get_db)
) -> dict:
    alert = await sos_service.resolve(db, alert_id, request.notes)
    if alert is None:
        raise HTTPException(404, "No active alert with that id")
    return {"status": "resolved", "alert_id": alert.id}


@router.post("/broadcast")
async def broadcast(request: BroadcastRequest, db: AsyncSession = Depends(get_db)) -> dict:
    users = await user_service.registered_users_for_push(db)
    if request.village:
        village = (
            await db.execute(select(Village).where(Village.name.ilike(request.village)))
        ).scalar_one_or_none()
        if village is None:
            raise HTTPException(422, f"Unknown village: {request.village!r}")
        users = [u for u in users if u.village_id == village.id]

    sent = 0
    for user in users:
        await send_message(
            db, phone=user.phone, text=request.text,
            user_id=user.id, message_type=MessageType.GENERIC,
        )
        sent += 1
    return {"status": "ok", "sent": sent}


@router.post("/users/{phone}/make-field-agent")
async def make_field_agent(phone: str, db: AsyncSession = Depends(get_db)) -> dict:
    """Grant a user the field-agent role so they can submit PRICE commands."""
    from app.enums import UserRole

    user = await user_service.get_user_by_phone(db, phone)
    if user is None:
        raise HTTPException(404, "User not found (they must message the bot first)")
    user.role = UserRole.FIELD_AGENT
    await db.commit()
    return {"status": "ok", "phone": user.phone, "role": user.role.value}


@router.post("/jobs/morning-push")
async def trigger_morning_push() -> dict:
    """Manually trigger the 3:30 AM push (ops testing / recovery)."""
    from app.scheduler import push_morning_forecasts

    sent = await push_morning_forecasts()
    return {"status": "ok", "sent": sent}


@router.post("/jobs/price-push")
async def trigger_price_push() -> dict:
    from app.scheduler import push_price_digests

    sent = await push_price_digests()
    return {"status": "ok", "sent": sent}
