"""Scheduled jobs (all times IST — Asia/Kolkata):

  03:30  Morning forecast auto-push to every registered, subscribed user
         (execution plan Feature 1: "before he leaves the shore").
  04:30  Best-effort FMPIS price ingestion.
  05:00  Price digest auto-push (Feature 2).
  */5m   SOS follow-up: remind active-alert users to share location and
         relay the latest position to their emergency contacts.
"""

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.bot import composer
from app.config import get_settings
from app.database import get_session_factory
from app.enums import MessageType
from app.localization.strings import t
from app.services import price_service, sos_service, user_service, weather_service
from app.services.messenger import send_message

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


def _now_ist() -> datetime:
    return datetime.now(ZoneInfo(get_settings().timezone))


async def push_morning_forecasts() -> int:
    """Fetch fresh forecasts per village and push to each subscribed user.
    Returns the number of messages sent."""
    sent = 0
    async with get_session_factory()() as session:
        users = await user_service.registered_users_for_push(session)
        if not users:
            logger.info("Morning push: no subscribed users")
            return 0

        now = _now_ist()
        forecast_cache: dict[int, object] = {}
        for user in users:
            village = user.village or await user_service.default_village(session)
            if village is None:
                continue
            try:
                if village.id not in forecast_cache:
                    forecast_cache[village.id] = await weather_service.refresh_forecast(
                        session, village, now.date()
                    )
                forecast = forecast_cache[village.id]
            except Exception:
                logger.exception("Morning push: forecast failed for %s", village.name)
                continue
            await send_message(
                session,
                phone=user.phone,
                text=composer.morning_forecast(user, forecast, now),
                user_id=user.id,
                message_type=MessageType.MORNING_FORECAST,
            )
            sent += 1
    logger.info("Morning push: sent %d forecasts", sent)
    return sent


async def push_price_digests() -> int:
    """5 AM price digest to subscribed users. Skips silently if the field
    agent hasn't reported yet (fishermen can still pull with PRICES)."""
    sent = 0
    async with get_session_factory()() as session:
        today = _now_ist().date()
        latest_day = await price_service.get_latest_price_day(session, today)
        if latest_day is None:
            logger.info("Price push: no prices recorded yet, skipping")
            return 0
        prices = await price_service.get_prices_for_day(session, latest_day)
        if not prices:
            return 0
        by_center: dict[str, list] = {}
        for price in prices:
            by_center.setdefault(price.landing_center.name, []).append(price)
        tip = price_service.best_market_tip(prices)

        for user in await user_service.registered_users_for_push(session):
            text = composer.price_digest(user.language, by_center, tip, latest_day)
            await send_message(
                session, phone=user.phone, text=text,
                user_id=user.id, message_type=MessageType.PRICE_DIGEST,
            )
            sent += 1
    logger.info("Price push: sent %d digests", sent)
    return sent


async def fetch_market_prices() -> int:
    async with get_session_factory()() as session:
        return await price_service.fetch_fmpis_prices(session, _now_ist().date())


async def sos_follow_up() -> int:
    """Every 5 minutes: nudge active-SOS users for a location and relay the
    latest known position to their emergency contacts."""
    handled = 0
    async with get_session_factory()() as session:
        for alert in await sos_service.all_active_alerts(session):
            user = alert.user
            await send_message(
                session, phone=user.phone, text=t("sos_reminder", user.language),
                user_id=user.id, message_type=MessageType.SOS,
            )
            if alert.last_latitude is not None and alert.last_location_at is not None:
                update = composer.sos_contact_location_update(
                    user, alert.last_latitude, alert.last_longitude, alert.last_location_at
                )
                for contact in user.emergency_contacts:
                    await send_message(
                        session, phone=contact.phone, text=update,
                        user_id=user.id, message_type=MessageType.SOS,
                    )
            handled += 1
    if handled:
        logger.info("SOS follow-up: handled %d active alerts", handled)
    return handled


def start_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    settings = get_settings()
    tz = ZoneInfo(settings.timezone)
    scheduler = AsyncIOScheduler(timezone=tz)

    scheduler.add_job(
        push_morning_forecasts,
        CronTrigger(hour=settings.morning_forecast_hour,
                    minute=settings.morning_forecast_minute, timezone=tz),
        id="morning_forecast_push",
        name="3:30 AM morning forecast push",
        misfire_grace_time=3600,
    )
    scheduler.add_job(
        fetch_market_prices,
        CronTrigger(hour=settings.price_fetch_hour,
                    minute=settings.price_fetch_minute, timezone=tz),
        id="market_price_fetch",
        name="FMPIS price ingestion",
        misfire_grace_time=3600,
    )
    scheduler.add_job(
        push_price_digests,
        CronTrigger(hour=settings.price_push_hour,
                    minute=settings.price_push_minute, timezone=tz),
        id="price_digest_push",
        name="5 AM price digest push",
        misfire_grace_time=3600,
    )
    scheduler.add_job(
        sos_follow_up,
        IntervalTrigger(minutes=settings.sos_ping_interval_minutes, timezone=tz),
        id="sos_follow_up",
        name="SOS location follow-up",
        misfire_grace_time=60,
    )

    scheduler.start()
    _scheduler = scheduler
    logger.info("Scheduler started (timezone %s)", settings.timezone)
    return scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
