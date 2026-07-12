"""Bot conversation router — every inbound WhatsApp message lands here.

Flow priority:
  1. SOS keywords and location shares — always handled first, in any state.
     A fisherman mid-onboarding in distress still gets the SOS flow.
  2. Onboarding state machine (execution plan: "Hi" -> language -> name ->
     village -> boat type -> first forecast immediately).
  3. Registered-user commands: 1, 2/PRICES, HELP, STOP/START, LANG,
     VILLAGE, CONTACT, PRICE (field agents).
"""

import logging
import re
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import composer
from app.config import get_settings
from app.enums import (
    BoatType,
    Language,
    MessageDirection,
    MessageType,
    OnboardingState,
    UserRole,
)
from app.localization.strings import t
from app.models import User
from app.providers.whatsapp.base import InboundMessage
from app.seeds import resolve_species, species_display_name
from app.services import price_service, sos_service, user_service, weather_service
from app.services.message_log import log_message
from app.services.messenger import send_message
from app.services.price_service import PriceSource

logger = logging.getLogger(__name__)

SOS_KEYWORDS = {"SOS", "EMERGENCY", "HELP ME", "MADAT", "APOTKAL", "BACHAO"}
CANCEL_KEYWORDS = {"CANCEL", "RADD"}
GREETING_KEYWORDS = {
    "HI", "HELLO", "HELO", "HII", "HIII", "HEY", "NAMASKAR", "NAMASTE",
    "DEV BOREM KORUM", "JOIN",
}
PRICE_KEYWORDS = {"2", "PRICE", "PRICES", "MOL", "DAM", "RATES", "RATE"}
HELP_KEYWORDS = {"HELP", "MENU", "?"}

_LANGUAGE_CHOICES = {
    "1": Language.ENGLISH,
    "2": Language.KONKANI,
    "3": Language.HINDI,
    "4": Language.MARATHI,
}
_BOAT_CHOICES = {
    "1": BoatType.CANOE,
    "2": BoatType.MOTORIZED_CANOE,
    "3": BoatType.RAMPON,
    "4": BoatType.TRAWLER,
    "5": BoatType.OTHER,
}


def _now_ist() -> datetime:
    return datetime.now(ZoneInfo(get_settings().timezone))


async def _reply(
    session: AsyncSession,
    user: User,
    text: str,
    message_type: MessageType = MessageType.GENERIC,
) -> str:
    await send_message(
        session, phone=user.phone, text=text, user_id=user.id, message_type=message_type
    )
    return text


async def handle_inbound(session: AsyncSession, inbound: InboundMessage) -> list[str]:
    """Process one inbound message; returns the reply texts sent to the sender."""
    user, created = await user_service.get_or_create_user(session, inbound.phone)
    await log_message(
        session,
        phone=user.phone,
        direction=MessageDirection.INBOUND,
        content=inbound.text if not inbound.has_location
        else f"[location {inbound.latitude:.5f},{inbound.longitude:.5f}]",
        user_id=user.id,
        message_type=MessageType.GENERIC,
        provider_message_id=inbound.provider_message_id,
    )
    await user_service.touch_last_active(session, user)

    command = inbound.text.strip()
    upper = command.upper()

    # --- 1. Safety first: SOS / location / cancel, regardless of state -------
    if inbound.has_location:
        return await _handle_location(session, user, inbound)
    if upper in SOS_KEYWORDS:
        return await _handle_sos(session, user)
    if upper in CANCEL_KEYWORDS:
        return await _handle_cancel(session, user)

    # --- 2. Onboarding state machine -----------------------------------------
    if user.onboarding_state != OnboardingState.REGISTERED:
        return await _handle_onboarding(session, user, command, created)

    # --- 3. Registered-user commands ------------------------------------------
    if upper == "1":
        return await _send_detailed_forecast(session, user)
    if upper in PRICE_KEYWORDS:
        return await _send_price_digest(session, user)
    if upper == "STOP":
        user.subscribed = False
        await session.commit()
        return [await _reply(session, user, t("stopped", user.language))]
    if upper in {"START", "RESUME"}:
        user.subscribed = True
        await session.commit()
        return [await _reply(session, user, t("started", user.language))]
    if upper in HELP_KEYWORDS or upper in GREETING_KEYWORDS:
        return [await _reply(session, user, t("help", user.language), MessageType.HELP)]
    if upper in {"LANG", "LANGUAGE", "BHAS"}:
        user.onboarding_state = OnboardingState.AWAITING_LANGUAGE
        await session.commit()
        return [await _reply(session, user, t("language_menu", user.language))]
    if upper.startswith("VILLAGE"):
        return await _handle_village_change(session, user, command)
    if upper.startswith("CONTACT"):
        return await _handle_contact(session, user, command)
    if upper.startswith("PRICE "):
        return await _handle_price_entry(session, user, command)

    return [await _reply(session, user, t("unknown_command", user.language), MessageType.HELP)]


# --- SOS ---------------------------------------------------------------------


async def _handle_sos(session: AsyncSession, user: User) -> list[str]:
    settings = get_settings()
    alert, _created = await sos_service.activate(session, user)
    reply = await _reply(
        session, user, composer.sos_activated(user, alert, settings.coast_guard_number),
        MessageType.SOS,
    )
    for contact in user.emergency_contacts:
        await send_message(
            session,
            phone=contact.phone,
            text=composer.sos_contact_alert(user, alert, settings.coast_guard_number),
            user_id=user.id,
            message_type=MessageType.SOS,
        )
    return [reply]


async def _handle_location(
    session: AsyncSession, user: User, inbound: InboundMessage
) -> list[str]:
    alert = await sos_service.record_location(
        session, user, inbound.latitude, inbound.longitude
    )
    if alert is None:
        return []  # location share outside an emergency — nothing to do (MVP)
    reply = await _reply(
        session, user,
        composer.sos_location_received(user, inbound.latitude, inbound.longitude),
        MessageType.SOS,
    )
    update = composer.sos_contact_location_update(
        user, inbound.latitude, inbound.longitude, _now_ist()
    )
    for contact in user.emergency_contacts:
        await send_message(
            session, phone=contact.phone, text=update,
            user_id=user.id, message_type=MessageType.SOS,
        )
    return [reply]


async def _handle_cancel(session: AsyncSession, user: User) -> list[str]:
    alert = await sos_service.cancel(session, user)
    if alert is None:
        return [await _reply(session, user, t("sos_none_active", user.language), MessageType.SOS)]
    reply = await _reply(session, user, composer.sos_cancelled(user), MessageType.SOS)
    stand_down = composer.sos_contact_stand_down(user)
    for contact in user.emergency_contacts:
        await send_message(
            session, phone=contact.phone, text=stand_down,
            user_id=user.id, message_type=MessageType.SOS,
        )
    return [reply]


# --- Onboarding -----------------------------------------------------------------


async def _handle_onboarding(
    session: AsyncSession, user: User, command: str, just_created: bool
) -> list[str]:
    state = user.onboarding_state

    if state == OnboardingState.NEW:
        user.onboarding_state = OnboardingState.AWAITING_LANGUAGE
        await session.commit()
        return [await _reply(
            session, user, t("welcome_language_menu", Language.ENGLISH), MessageType.ONBOARDING
        )]

    if state == OnboardingState.AWAITING_LANGUAGE:
        choice = _LANGUAGE_CHOICES.get(command.strip())
        if choice is None:
            return [await _reply(
                session, user, t("invalid_language", Language.ENGLISH), MessageType.ONBOARDING
            )]
        user.language = choice
        # A registered user changing language via LANG lands here too —
        # completed profiles skip straight back to REGISTERED.
        if user.name and user.boat_type is not None:
            user.onboarding_state = OnboardingState.REGISTERED
            await session.commit()
            return [await _reply(session, user, t("language_set", choice))]
        user.onboarding_state = OnboardingState.AWAITING_NAME
        await session.commit()
        return [await _reply(session, user, t("ask_name", choice), MessageType.ONBOARDING)]

    if state == OnboardingState.AWAITING_NAME:
        name = command.strip()
        if not name:
            return [await _reply(session, user, t("ask_name", user.language), MessageType.ONBOARDING)]
        user.name = name[:100]
        user.onboarding_state = OnboardingState.AWAITING_VILLAGE
        await session.commit()
        return [await _reply(
            session, user, t("ask_village", user.language, name=user.name), MessageType.ONBOARDING
        )]

    if state == OnboardingState.AWAITING_VILLAGE:
        replies = []
        village = await user_service.match_village(session, command)
        user.village_name_raw = command.strip()[:100]
        if village is None:
            fallback = await user_service.default_village(session)
            user.village_id = fallback.id if fallback else None
            await session.commit()
            if fallback is not None:
                replies.append(await _reply(
                    session, user,
                    t("village_not_found", user.language, fallback=fallback.name),
                    MessageType.ONBOARDING,
                ))
        else:
            user.village_id = village.id
            await session.commit()
        user.onboarding_state = OnboardingState.AWAITING_BOAT_TYPE
        await session.commit()
        replies.append(await _reply(
            session, user, t("ask_boat_type", user.language), MessageType.ONBOARDING
        ))
        return replies

    if state == OnboardingState.AWAITING_BOAT_TYPE:
        boat = _BOAT_CHOICES.get(command.strip())
        if boat is None:
            return [await _reply(
                session, user, t("invalid_boat_type", user.language), MessageType.ONBOARDING
            )]
        user.boat_type = boat
        user.onboarding_state = OnboardingState.REGISTERED
        await session.commit()
        # Reload with relationships for the forecast composer.
        user = await user_service.get_user_by_phone(session, user.phone)
        village_name = user.village.name if user.village else "South Goa"
        replies = [await _reply(
            session, user,
            t("registered", user.language, name=user.name, village=village_name),
            MessageType.ONBOARDING,
        )]
        # Execution plan: "Bot sends first forecast immediately".
        replies += await _send_morning_forecast(session, user)
        return replies

    # Shouldn't happen; restart the flow defensively.
    user.onboarding_state = OnboardingState.NEW
    await session.commit()
    return await _handle_onboarding(session, user, command, just_created)


# --- Forecast & prices ------------------------------------------------------------


async def _get_user_village(session: AsyncSession, user: User):
    if user.village is not None:
        return user.village
    return await user_service.default_village(session)


async def _send_morning_forecast(session: AsyncSession, user: User) -> list[str]:
    village = await _get_user_village(session, user)
    if village is None:
        return [await _reply(session, user, t("forecast_unavailable", user.language))]
    now = _now_ist()
    try:
        forecast = await weather_service.get_or_create_forecast(session, village, now.date())
    except Exception:
        logger.exception("Forecast fetch failed for %s", village.name)
        return [await _reply(session, user, t("forecast_unavailable", user.language))]
    return [await _reply(
        session, user, composer.morning_forecast(user, forecast, now),
        MessageType.MORNING_FORECAST,
    )]


async def _send_detailed_forecast(session: AsyncSession, user: User) -> list[str]:
    village = await _get_user_village(session, user)
    if village is None:
        return [await _reply(session, user, t("forecast_unavailable", user.language))]
    now = _now_ist()
    try:
        forecast = await weather_service.get_or_create_forecast(session, village, now.date())
    except Exception:
        logger.exception("Forecast fetch failed for %s", village.name)
        return [await _reply(session, user, t("forecast_unavailable", user.language))]
    return [await _reply(
        session, user, composer.detailed_forecast(user, forecast, now),
        MessageType.DETAILED_FORECAST,
    )]


async def _send_price_digest(session: AsyncSession, user: User) -> list[str]:
    today = _now_ist().date()
    latest_day = await price_service.get_latest_price_day(session, today)
    if latest_day is None:
        return [await _reply(session, user, t("no_prices", user.language), MessageType.PRICE_DIGEST)]
    prices = await price_service.get_prices_for_day(session, latest_day)
    by_center: dict[str, list] = {}
    for price in prices:
        by_center.setdefault(price.landing_center.name, []).append(price)
    tip = price_service.best_market_tip(prices)
    text = composer.price_digest(user.language, by_center, tip, latest_day)
    return [await _reply(session, user, text, MessageType.PRICE_DIGEST)]


# --- Profile & agent commands -------------------------------------------------------


async def _handle_village_change(session: AsyncSession, user: User, command: str) -> list[str]:
    parts = command.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        return [await _reply(session, user, t("unknown_command", user.language))]
    village = await user_service.match_village(session, parts[1])
    if village is None:
        fallback = await user_service.default_village(session)
        return [await _reply(
            session, user,
            t("village_not_found", user.language, fallback=fallback.name if fallback else "Betul"),
        )]
    user.village_id = village.id
    user.village_name_raw = parts[1].strip()[:100]
    await session.commit()
    return [await _reply(session, user, t("village_changed", user.language, village=village.name))]


_CONTACT_RE = re.compile(r"^CONTACT\s+(.+?)\s+(\+?[\d\s\-]{10,15})$", re.IGNORECASE)


async def _handle_contact(session: AsyncSession, user: User, command: str) -> list[str]:
    match = _CONTACT_RE.match(command.strip())
    if not match:
        return [await _reply(session, user, t("contact_usage", user.language))]
    name, phone = match.group(1).strip(), match.group(2)
    contact = await user_service.add_emergency_contact(session, user, name, phone)
    return [await _reply(
        session, user,
        t("contact_added", user.language, name=contact.name, phone=contact.phone),
    )]


async def _handle_price_entry(session: AsyncSession, user: User, command: str) -> list[str]:
    """Field agents submit prices over WhatsApp: PRICE <center> <species> <₹/kg>."""
    if user.role not in (UserRole.FIELD_AGENT, UserRole.ADMIN):
        return [await _reply(session, user, t("price_not_agent", user.language))]

    parts = command.split()
    if len(parts) != 4:
        return [await _reply(session, user, t("price_usage", user.language))]
    _, center_raw, species_raw, price_raw = parts

    center = await price_service.get_landing_center(session, center_raw)
    species = resolve_species(species_raw)
    try:
        price_value = float(price_raw.replace("₹", "").replace(",", ""))
    except ValueError:
        price_value = -1
    if center is None or species is None or price_value <= 0:
        return [await _reply(session, user, t("price_usage", user.language))]

    day = _now_ist().date()
    await price_service.record_price(
        session,
        landing_center=center,
        species=species,
        price_per_kg=price_value,
        price_date=day,
        source=PriceSource.FIELD_AGENT,
        reported_by_phone=user.phone,
    )
    return [await _reply(
        session, user,
        t("price_recorded", user.language,
          species=species_display_name(species, user.language.value),
          price=f"{price_value:.0f}", center=center.name,
          day=day.strftime("%d %b")),
    )]
