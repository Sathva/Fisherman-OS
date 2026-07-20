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
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
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
from app.models import MessageLog, User
from app.providers.prices import fmpis
from app.providers.prices.fmpis import FMPISUnavailable
from app.providers.whatsapp.base import InboundMessage
from app.seeds import resolve_species, species_display_name
from app.services import llm_service, price_service, sos_service, user_service, weather_service
from app.services.llm_service import LLMUnavailable
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

    # --- 2. Price flow: we asked which fish they want -------------------------
    if user.onboarding_state == OnboardingState.AWAITING_FISH_TYPE:
        return await _handle_fish_type_reply(session, user, command)

    # --- 3. Onboarding state machine -----------------------------------------
    if user.onboarding_state != OnboardingState.REGISTERED:
        return await _handle_onboarding(session, user, command, created)

    return await _handle_registered_command(session, user, command)


async def _handle_registered_command(
    session: AsyncSession, user: User, command: str
) -> list[str]:
    """Keyword commands for registered users, with the LLM as last resort."""
    upper = command.strip().upper()

    if upper == "1":
        return await _send_detailed_forecast(session, user)
    if upper in PRICE_KEYWORDS:
        return await _ask_fish_type(session, user)
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

    # --- 4. LLM fallback: everything the keyword router couldn't handle ------
    return await _handle_llm_fallback(session, user, command)


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
        forecast, _ = await weather_service.get_or_create_forecast(session, village, now.date())
    except Exception as exc:
        logger.exception("Forecast fetch failed for %s", village.name)
        return [await _reply(session, user, f"⚠️ Forecast error for {village.name}:\n{exc}")]
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
        forecast, coastal_reports = await weather_service.get_or_create_forecast(session, village, now.date())
    except Exception as exc:
        logger.exception("Forecast fetch failed for %s", village.name)
        return [await _reply(session, user, f"⚠️ Forecast error for {village.name}:\n{exc}")]
    return [await _reply(
        session, user, composer.detailed_forecast(user, forecast, now, coastal_reports),
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


# --- Live per-species prices (FMPIS) ------------------------------------------

# Quick-reply buttons shown with the "which fish?" prompt.
_FISH_BUTTON_SPECIES = ["mackerel", "sardine", "kingfish", "pomfret", "prawns"]


async def _ask_fish_type(session: AsyncSession, user: User) -> list[str]:
    """Step 1 of the price flow: ask which fish before quoting prices."""
    user.onboarding_state = OnboardingState.AWAITING_FISH_TYPE
    await session.commit()
    text = t("ask_fish_type", user.language)
    options = [
        species_display_name(key, user.language.value) for key in _FISH_BUTTON_SPECIES
    ]
    await send_message(
        session, phone=user.phone, text=text, user_id=user.id,
        message_type=MessageType.PRICE_DIGEST, options=options,
    )
    return [text]


async def _handle_fish_type_reply(
    session: AsyncSession, user: User, command: str
) -> list[str]:
    """Step 2: resolve the fish they named and send only that fish's prices."""
    # Leave the waiting state before anything else — no way to get stuck here.
    user.onboarding_state = OnboardingState.REGISTERED
    await session.commit()

    if command.strip().upper() == "ALL":
        return await _send_price_digest(session, user)

    species = resolve_species(command)
    if species is None:
        species = await llm_service.correct_species_name(command)
    if species is None:
        # Not a fish we know — treat it as a normal command/question instead.
        return await _handle_registered_command(session, user, command)

    return await _send_live_species_prices(session, user, species)


async def _send_live_species_prices(
    session: AsyncSession, user: User, species: str
) -> list[str]:
    village = await _get_user_village(session, user)
    if village is not None:
        nearest = fmpis.nearest_market(village.latitude, village.longitude)
    else:
        nearest = fmpis.GOA_MARKETS[0]

    try:
        quotes = await fmpis.fetch_species_quotes(species)
    except FMPISUnavailable as exc:
        logger.warning("FMPIS unavailable, falling back to recorded prices: %s", exc)
        warning = await _reply(
            session, user, t("live_prices_unavailable", user.language),
            MessageType.PRICE_DIGEST,
        )
        return [warning] + await _send_price_digest(session, user)

    if not quotes:
        name = species_display_name(species, user.language.value)
        return [await _reply(
            session, user,
            t("species_not_listed", user.language, species=name),
            MessageType.PRICE_DIGEST,
        )]

    text = composer.live_species_prices(user, species, quotes, nearest.name)
    return [await _reply(session, user, text, MessageType.PRICE_DIGEST)]


# --- LLM fallback -------------------------------------------------------------------


async def _llm_rate_limited(session: AsyncSession, user: User) -> bool:
    """Cost/abuse guard: cap inbound messages per user per rolling hour."""
    limit = get_settings().llm_rate_limit_per_hour
    if limit <= 0:
        return False
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1)
    count = (
        await session.execute(
            select(func.count(MessageLog.id)).where(
                MessageLog.phone == user.phone,
                MessageLog.direction == MessageDirection.INBOUND,
                MessageLog.created_at >= cutoff,
            )
        )
    ).scalar_one()
    return count > limit


async def _build_llm_context(session: AsyncSession, user: User) -> str:
    """Compact, factual data block the LLM is allowed to quote from."""
    now = _now_ist()
    lines = [f"Current date/time (IST): {now.strftime('%A %d %B %Y, %I:%M %p')}"]

    village = await _get_user_village(session, user)
    if village is not None:
        try:
            forecast, coastal_reports = await weather_service.get_or_create_forecast(
                session, village, now.date()
            )
            lines.append(
                f"Sea forecast for {village.name} today: safety={forecast.safety_level.name}, "
                f"wind {forecast.wind_speed_kmh:.0f} km/h {forecast.wind_direction}, "
                f"waves {forecast.wave_height_m:.1f} m, rain chance {forecast.rain_probability}%."
            )
            if forecast.advisory:
                lines.append(f"Advisory: {forecast.advisory}")
            pfz_note = getattr(forecast, "pfz_note", None)
            if pfz_note:
                lines.append(f"Fishing zone (PFZ) data: {pfz_note}")
            for report in coastal_reports or []:
                lines.append(
                    f"- {report.name}: wind {report.wind_speed_kmh:.0f} km/h "
                    f"{report.wind_direction}, waves {report.wave_height_m:.1f} m, "
                    f"rain {report.rain_probability}%."
                )
        except Exception:
            logger.exception("LLM context: forecast fetch failed for %s", village.name)
            lines.append(
                "Sea forecast: currently unavailable — tell the user to send 1 and try again later."
            )
    else:
        lines.append("Sea forecast: no village configured — user can set one with VILLAGE <name>.")

    try:
        latest_day = await price_service.get_latest_price_day(session, now.date())
        if latest_day is not None:
            prices = await price_service.get_prices_for_day(session, latest_day)
            quotes = ", ".join(
                f"{p.species} ₹{p.price_per_kg:.0f}/kg at {p.landing_center.name}"
                for p in prices[:15]
            )
            lines.append(f"Fish prices ({latest_day.strftime('%d %b')}): {quotes}")
        else:
            lines.append("Fish prices: none reported yet today.")
    except Exception:
        logger.exception("LLM context: price fetch failed")
        lines.append("Fish prices: currently unavailable.")

    return "\n".join(lines)


async def _handle_llm_fallback(session: AsyncSession, user: User, command: str) -> list[str]:
    """Unmatched message from a registered user → single Groq call that either
    routes to an existing structured handler or answers/declines directly.
    Any LLM failure degrades to the old static help reply — never silence.

    With LLM_DEBUG=true, a "🐛 [LLM debug]" chat message reports whether Groq
    was called, the detected intent, or why the call was skipped/failed."""
    settings = get_settings()
    replies: list[str] = []

    async def _debug_note(text: str) -> None:
        if settings.llm_debug:
            replies.append(await _reply(session, user, f"🐛 [LLM debug] {text}"))

    if not llm_service.is_configured():
        await _debug_note("Groq NOT called — LLM disabled or GROQ_API_KEY not set.")
        replies.append(await _reply(session, user, t("unknown_command", user.language), MessageType.HELP))
        return replies
    if await _llm_rate_limited(session, user):
        await _debug_note("Groq NOT called — per-user hourly rate limit reached.")
        replies.append(await _reply(session, user, t("unknown_command", user.language), MessageType.HELP))
        return replies

    context_block = await _build_llm_context(session, user)
    try:
        decision = await llm_service.classify_and_answer(user, command, context_block)
    except LLMUnavailable as exc:
        await _debug_note(f"Groq call FAILED ({exc}) — sending static help fallback.")
        replies.append(await _reply(session, user, t("unknown_command", user.language), MessageType.HELP))
        return replies

    await _debug_note(f'Groq called ({settings.groq_model}) — intent "{decision.intent}".')

    if decision.intent == "forecast":
        return replies + await _send_detailed_forecast(session, user)
    if decision.intent == "prices":
        return replies + await _ask_fish_type(session, user)
    if decision.intent == "help":
        return replies + [await _reply(session, user, t("help", user.language), MessageType.HELP)]
    if decision.intent == "stop":
        user.subscribed = False
        await session.commit()
        return replies + [await _reply(session, user, t("stopped", user.language))]
    if decision.intent == "start":
        user.subscribed = True
        await session.commit()
        return replies + [await _reply(session, user, t("started", user.language))]
    if decision.intent == "language":
        user.onboarding_state = OnboardingState.AWAITING_LANGUAGE
        await session.commit()
        return replies + [await _reply(session, user, t("language_menu", user.language))]
    if decision.intent == "emergency":
        # The LLM never triggers SOS itself — one tap on the button sends
        # "SOS", which goes through the exact same keyword path as typing it.
        text = t("sos_confirm_prompt", user.language)
        await send_message(
            session, phone=user.phone, text=text, user_id=user.id,
            message_type=MessageType.SOS, options=["SOS"],
        )
        return replies + [text]

    # "answer" and "off_topic": send the LLM's own (grounded or declining) text.
    return replies + [await _reply(session, user, decision.reply, MessageType.GENERIC)]


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
