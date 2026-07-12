"""KPI metrics for the ops team — mirrors execution plan §9 targets."""

from datetime import date, datetime, time, timedelta

from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import (
    MessageDirection,
    MessageType,
    OnboardingState,
    SOSStatus,
    SubscriptionStatus,
)
from app.models import MessageLog, SOSAlert, User


async def collect_metrics(session: AsyncSession, day: date | None = None) -> dict:
    day = day or date.today()
    day_start = datetime.combine(day, time.min)
    day_end = day_start + timedelta(days=1)

    registered = (
        await session.execute(
            select(func.count(User.id)).where(
                User.onboarding_state == OnboardingState.REGISTERED
            )
        )
    ).scalar_one()

    subscribed = (
        await session.execute(
            select(func.count(User.id)).where(
                User.onboarding_state == OnboardingState.REGISTERED,
                User.subscribed.is_(True),
            )
        )
    ).scalar_one()

    paying = (
        await session.execute(
            select(func.count(User.id)).where(
                User.subscription_status == SubscriptionStatus.ACTIVE
            )
        )
    ).scalar_one()

    # DAU proxy: distinct phones that sent us an inbound message today.
    dau = (
        await session.execute(
            select(func.count(distinct(MessageLog.phone))).where(
                MessageLog.direction == MessageDirection.INBOUND,
                MessageLog.created_at >= day_start,
                MessageLog.created_at < day_end,
            )
        )
    ).scalar_one()

    forecasts_delivered = (
        await session.execute(
            select(func.count(MessageLog.id)).where(
                MessageLog.direction == MessageDirection.OUTBOUND,
                MessageLog.message_type == MessageType.MORNING_FORECAST,
                MessageLog.created_at >= day_start,
                MessageLog.created_at < day_end,
            )
        )
    ).scalar_one()

    sos_active = (
        await session.execute(
            select(func.count(SOSAlert.id)).where(SOSAlert.status == SOSStatus.ACTIVE)
        )
    ).scalar_one()

    sos_total = (
        await session.execute(select(func.count(SOSAlert.id)))
    ).scalar_one()

    return {
        "date": day.isoformat(),
        "registered_users": registered,
        "registered_target": 500,
        "subscribed_users": subscribed,
        "paying_users": paying,
        "dau": dau,
        "dau_pct_of_registered": round(dau / registered * 100, 1) if registered else 0.0,
        "dau_target_pct": 60,
        "morning_forecasts_delivered_today": forecasts_delivered,
        "sos_alerts_active": sos_active,
        "sos_alerts_total": sos_total,
    }
