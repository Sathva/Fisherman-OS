"""Market price service.

Prices arrive from three sources (execution plan §3):
  1. Field agents — via the admin API or a WhatsApp "PRICE ..." command,
     daily by 5 AM (primary for the MVP).
  2. FMPIS (NFDB) — automated ingestion attempt (best-effort stub for now;
     FMPIS has no stable public API, scraping target documented below).
  3. CMFRI Fish Watch — same, Phase 1.5.

The service also computes the "💡 TIP" line — the biggest same-species price
spread across centers — which drives the MVP's key economic KPI (20% of users
switching markets).
"""

import logging
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.enums import PriceSource
from app.models import FishPrice, LandingCenter

logger = logging.getLogger(__name__)


class UnknownLandingCenter(Exception):
    pass


async def get_landing_center(session: AsyncSession, name: str) -> LandingCenter | None:
    """Match a landing center loosely: 'betul' matches 'Betul Landing'."""
    needle = name.strip().lower()
    centers = (await session.execute(select(LandingCenter))).scalars().all()
    for center in centers:
        if center.name.lower() == needle:
            return center
    for center in centers:
        if needle and (needle in center.name.lower() or center.name.lower().split()[0] == needle):
            return center
    return None


async def record_price(
    session: AsyncSession,
    *,
    landing_center: LandingCenter,
    species: str,
    price_per_kg: float,
    price_date: date,
    source: PriceSource = PriceSource.FIELD_AGENT,
    reported_by_phone: str | None = None,
) -> FishPrice:
    """Upsert a price for (center, species, day); latest report wins."""
    existing = (
        await session.execute(
            select(FishPrice).where(
                FishPrice.landing_center_id == landing_center.id,
                FishPrice.species == species,
                FishPrice.price_date == price_date,
            )
        )
    ).scalar_one_or_none()

    if existing is not None:
        existing.price_per_kg = price_per_kg
        existing.source = source
        existing.reported_by_phone = reported_by_phone
        price = existing
    else:
        price = FishPrice(
            landing_center_id=landing_center.id,
            species=species,
            price_per_kg=price_per_kg,
            price_date=price_date,
            source=source,
            reported_by_phone=reported_by_phone,
        )
        session.add(price)

    await session.commit()
    await session.refresh(price)
    return price


async def get_prices_for_day(session: AsyncSession, day: date) -> list[FishPrice]:
    result = await session.execute(
        select(FishPrice)
        .where(FishPrice.price_date == day)
        .options(selectinload(FishPrice.landing_center))
        .order_by(FishPrice.landing_center_id, FishPrice.species)
    )
    return list(result.scalars().all())


async def get_latest_price_day(session: AsyncSession, on_or_before: date) -> date | None:
    """Most recent day with any prices (the 5 AM digest shows yesterday's closing)."""
    result = await session.execute(
        select(FishPrice.price_date)
        .where(FishPrice.price_date <= on_or_before)
        .order_by(FishPrice.price_date.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


@dataclass(frozen=True)
class MarketTip:
    species: str
    best_center: str
    worst_center: str
    best_price: float
    worst_price: float

    @property
    def uplift_pct(self) -> int:
        return round((self.best_price - self.worst_price) / self.worst_price * 100)


def best_market_tip(prices: list[FishPrice]) -> MarketTip | None:
    """Largest same-species % spread across centers (needs >= 2 centers quoting)."""
    by_species: dict[str, list[FishPrice]] = {}
    for price in prices:
        by_species.setdefault(price.species, []).append(price)

    best: MarketTip | None = None
    for species, quotes in by_species.items():
        if len({q.landing_center_id for q in quotes}) < 2:
            continue
        high = max(quotes, key=lambda q: q.price_per_kg)
        low = min(quotes, key=lambda q: q.price_per_kg)
        if low.price_per_kg <= 0 or high.price_per_kg <= low.price_per_kg:
            continue
        tip = MarketTip(
            species=species,
            best_center=high.landing_center.name,
            worst_center=low.landing_center.name,
            best_price=high.price_per_kg,
            worst_price=low.price_per_kg,
        )
        if best is None or tip.uplift_pct > best.uplift_pct:
            best = tip
    if best is not None and best.uplift_pct < 5:
        return None  # not worth a fuel-burning detour
    return best


async def fetch_fmpis_prices(session: AsyncSession, day: date) -> int:
    """Best-effort FMPIS (NFDB) ingestion.

    FMPIS (https://fmpis.nfdb.gov.in) exposes prices through an interactive
    dashboard without a stable public API; NFDB MoU/API access is on the
    partnership roadmap (execution plan §10). Until that lands, field-agent
    entry is the source of truth and this job is a no-op that logs its skip.
    Returns the number of prices ingested.
    """
    logger.info("FMPIS ingestion skipped for %s (awaiting NFDB API access)", day)
    return 0
