"""SOS distress service.

Flow (execution plan Feature 3):
  * "SOS" → alert created, Coast Guard 1554 surfaced, emergency contacts
    notified over WhatsApp, location-sharing loop starts (5-min pings).
  * Fisherman shares WhatsApp location → recorded against the active alert,
    contacts get the updated position.
  * "CANCEL" → alert deactivated, contacts stood down.

Regulatory note (execution plan §10): messages always state that this is
supplementary to — never a replacement for — calling Coast Guard 1554.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.enums import SOSStatus
from app.models import SOSAlert, SOSLocationPing, User

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def maps_link(latitude: float, longitude: float) -> str:
    return f"https://maps.google.com/?q={latitude:.5f},{longitude:.5f}"


async def get_active_alert(session: AsyncSession, user: User) -> SOSAlert | None:
    result = await session.execute(
        select(SOSAlert)
        .where(SOSAlert.user_id == user.id, SOSAlert.status == SOSStatus.ACTIVE)
        .order_by(SOSAlert.activated_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def activate(
    session: AsyncSession,
    user: User,
    latitude: float | None = None,
    longitude: float | None = None,
) -> tuple[SOSAlert, bool]:
    """Activate SOS for a user. Returns (alert, newly_created).

    Idempotent: a second "SOS" while an alert is active reuses it (and updates
    the location if one came with the message).
    """
    alert = await get_active_alert(session, user)
    created = False
    if alert is None:
        alert = SOSAlert(user_id=user.id, contacts_notified=len(user.emergency_contacts))
        session.add(alert)
        created = True
        logger.warning("SOS ACTIVATED for user %s (%s)", user.id, user.phone)

    if latitude is not None and longitude is not None:
        await _record_ping(session, alert, latitude, longitude)

    await session.commit()
    await session.refresh(alert)
    return alert, created


async def record_location(
    session: AsyncSession, user: User, latitude: float, longitude: float
) -> SOSAlert | None:
    """Attach a location ping to the user's active alert, if any."""
    alert = await get_active_alert(session, user)
    if alert is None:
        return None
    await _record_ping(session, alert, latitude, longitude)
    await session.commit()
    await session.refresh(alert)
    return alert


async def _record_ping(
    session: AsyncSession, alert: SOSAlert, latitude: float, longitude: float
) -> None:
    now = _utcnow()
    session.add(SOSLocationPing(alert=alert, latitude=latitude,
                                longitude=longitude, recorded_at=now))
    alert.last_latitude = latitude
    alert.last_longitude = longitude
    alert.last_location_at = now


async def cancel(session: AsyncSession, user: User) -> SOSAlert | None:
    alert = await get_active_alert(session, user)
    if alert is None:
        return None
    alert.status = SOSStatus.CANCELLED
    alert.closed_at = _utcnow()
    await session.commit()
    logger.info("SOS cancelled by user %s (alert %s)", user.id, alert.id)
    return alert


async def resolve(session: AsyncSession, alert_id: int, notes: str | None = None) -> SOSAlert | None:
    """Ops closes an alert after Coast Guard follow-up."""
    alert = (
        await session.execute(select(SOSAlert).where(SOSAlert.id == alert_id))
    ).scalar_one_or_none()
    if alert is None or alert.status != SOSStatus.ACTIVE:
        return None
    alert.status = SOSStatus.RESOLVED
    alert.closed_at = _utcnow()
    if notes:
        alert.notes = notes
    await session.commit()
    return alert


async def all_active_alerts(session: AsyncSession) -> list[SOSAlert]:
    result = await session.execute(
        select(SOSAlert)
        .where(SOSAlert.status == SOSStatus.ACTIVE)
        .options(
            selectinload(SOSAlert.user).selectinload(User.emergency_contacts),
            selectinload(SOSAlert.user).selectinload(User.village),
        )
        .order_by(SOSAlert.activated_at)
    )
    return list(result.scalars().all())
