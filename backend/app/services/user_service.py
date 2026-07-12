"""User management: lookup/registration helpers and village matching."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.enums import OnboardingState
from app.models import EmergencyContact, User, Village


def normalize_phone(raw: str) -> str:
    """Normalize to digits-only E.164 without '+' (Gupshup's format).

    '+91 98765 43210' -> '919876543210'; bare 10-digit Indian numbers get '91'.
    """
    digits = "".join(ch for ch in raw if ch.isdigit())
    if len(digits) == 10:
        digits = "91" + digits
    return digits


async def get_user_by_phone(session: AsyncSession, phone: str) -> User | None:
    result = await session.execute(
        select(User)
        .where(User.phone == normalize_phone(phone))
        .options(selectinload(User.village), selectinload(User.emergency_contacts))
    )
    return result.scalar_one_or_none()


async def get_or_create_user(session: AsyncSession, phone: str) -> tuple[User, bool]:
    """Return (user, created). New users start in onboarding state NEW."""
    user = await get_user_by_phone(session, phone)
    if user is not None:
        return user, False
    user = User(
        phone=normalize_phone(phone),
        trial_started_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    session.add(user)
    await session.commit()
    # re-select so relationship collections are loaded
    user = await get_user_by_phone(session, phone)
    assert user is not None
    return user, True


async def touch_last_active(session: AsyncSession, user: User, commit: bool = True) -> None:
    user.last_active_at = datetime.now(timezone.utc).replace(tzinfo=None)
    if commit:
        await session.commit()


async def match_village(session: AsyncSession, raw_name: str) -> Village | None:
    """Match free-text village input; exact first, then prefix/substring."""
    needle = raw_name.strip().lower()
    if not needle:
        return None
    villages = (await session.execute(select(Village).where(Village.is_active))).scalars().all()
    for village in villages:
        if village.name.lower() == needle:
            return village
    candidates = [
        v for v in villages
        if v.name.lower().startswith(needle) or needle in v.name.lower()
    ]
    return candidates[0] if len(candidates) >= 1 else None


async def default_village(session: AsyncSession) -> Village | None:
    """Betul is the pilot village and the fallback forecast point."""
    result = await session.execute(select(Village).where(Village.name == "Betul"))
    village = result.scalar_one_or_none()
    if village is None:
        village = (await session.execute(select(Village).limit(1))).scalar_one_or_none()
    return village


async def registered_users_for_push(session: AsyncSession) -> list[User]:
    """Everyone who should receive scheduled pushes (registered + subscribed)."""
    result = await session.execute(
        select(User)
        .where(
            User.onboarding_state == OnboardingState.REGISTERED,
            User.subscribed.is_(True),
        )
        .options(selectinload(User.village))
    )
    return list(result.scalars().all())


async def add_emergency_contact(
    session: AsyncSession, user: User, name: str, phone: str
) -> EmergencyContact:
    contact = EmergencyContact(user_id=user.id, name=name.strip(), phone=normalize_phone(phone))
    session.add(contact)
    await session.commit()
    return contact
