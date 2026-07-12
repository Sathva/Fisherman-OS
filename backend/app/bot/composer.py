"""Message composer — turns model objects into WhatsApp-ready text.

Formats deliberately match the execution plan's approved template layouts
(morning forecast, price digest, SOS) so the WhatsApp/Meta template
submissions and the code stay in sync.
"""

from datetime import date, datetime

from app.enums import Language, SafetyLevel
from app.localization.strings import t
from app.models import SOSAlert, User, WeatherForecast
from app.seeds import species_display_name
from app.services.price_service import MarketTip
from app.services.sos_service import maps_link

_SAFETY_KEY = {
    SafetyLevel.SAFE: "safety_safe",
    SafetyLevel.CAUTION: "safety_caution",
    SafetyLevel.DANGER: "safety_danger",
}

_SKY_EMOJI = {
    SafetyLevel.SAFE: "☀️",
    SafetyLevel.CAUTION: "⛅",
    SafetyLevel.DANGER: "⛈️",
}


def _format_date(day: date) -> str:
    return f"{day.day} {day.strftime('%B %Y')}"  # "8 July 2026"


def _format_time(moment: datetime) -> str:
    return moment.strftime("%I:%M %p").lstrip("0")  # "3:30 AM"


def _wave_description(wave_height_m: float, language: Language) -> str:
    if wave_height_m < 1.0:
        key = "waves_calm"
    elif wave_height_m < 1.5:
        key = "waves_moderate"
    elif wave_height_m < 2.5:
        key = "waves_rough"
    else:
        key = "waves_very_rough"
    return t(key, language)


def _rain_line(forecast: WeatherForecast, language: Language) -> str:
    text = t("rain_chance", language, pct=forecast.rain_probability)
    if forecast.rain_timing:
        text += f" {forecast.rain_timing}"
    return text


def safety_line(level: SafetyLevel, language: Language) -> str:
    return f"{level.emoji} {t(_SAFETY_KEY[level], language)}"


def morning_forecast(user: User, forecast: WeatherForecast, now: datetime) -> str:
    """The 3:30 AM auto-push (execution plan Feature 1)."""
    language = user.language
    village_name = user.village.name if user.village else "South Goa"
    level = forecast.safety_level

    lines = [
        f"🌊 Fisherman OS — {village_name}",
        f"📅 {_format_date(forecast.forecast_date)} | {_format_time(now)}",
        "",
        f"{_SKY_EMOJI[level]} {t('todays_sea', language)}: {safety_line(level, language)}",
        "",
        f"🌬️ {t('wind', language)}: {forecast.wind_speed_kmh:.0f} km/h {forecast.wind_direction}",
        f"🌊 {t('waves', language)}: {forecast.wave_height_m:.1f}m "
        f"({_wave_description(forecast.wave_height_m, language)})",
        f"🌧️ {t('rain', language)}: {_rain_line(forecast, language)}",
    ]
    if forecast.sea_temp_c is not None:
        lines.append(f"🌡️ {t('sea_temp', language)}: {forecast.sea_temp_c:.1f}°C")
    if forecast.advisory:
        lines += ["", f"⚠️ {forecast.advisory}"]
    strip = "".join(level.emoji for level in forecast.hourly_level_list()) or level.emoji * 6
    lines += [
        "",
        f"{t('next_6_hours', language)}: {strip}",
        "",
        t("menu_footer", language),
    ]
    return "\n".join(lines)


def detailed_forecast(user: User, forecast: WeatherForecast, now: datetime) -> str:
    """Reply to "1" — morning forecast plus source/issue metadata."""
    language = user.language
    body = morning_forecast(user, forecast, now)
    header, _, rest = body.partition("\n")
    detail_header = f"{header} — {t('detailed_forecast_title', language)}"
    meta = (
        f"\n\n{t('forecast_source', language)}: {forecast.source.value.upper()}"
        f" | {t('issued_at', language)}: {_format_time(forecast.issued_at)} IST"
    )
    return detail_header + "\n" + rest + meta


def price_digest(
    language: Language,
    prices_by_center: dict[str, list],
    tip: MarketTip | None,
    day: date,
) -> str:
    """The price message (execution plan Feature 2). `prices_by_center` maps
    center name -> list[FishPrice]."""
    if not prices_by_center:
        return t("no_prices", language)

    lines = [t("price_header", language, day=_format_date(day)), ""]
    for center_name, quotes in prices_by_center.items():
        lines.append(f"📍 {center_name}:")
        parts = [
            f"{species_display_name(q.species, language.value)} ₹{q.price_per_kg:.0f}/kg"
            for q in sorted(quotes, key=lambda q: q.species)
        ]
        lines.append("   " + " | ".join(parts))
        lines.append("")

    if tip is not None:
        lines.append(
            t(
                "price_tip",
                language,
                best_center=tip.best_center,
                pct=tip.uplift_pct,
                species=species_display_name(tip.species, language.value),
            )
        )
        lines.append("")
    lines.append(t("price_footer", language))
    return "\n".join(lines)


def sos_activated(user: User, alert: SOSAlert, coast_guard: str) -> str:
    language = user.language
    if alert.last_latitude is not None and alert.last_longitude is not None:
        location_line = t(
            "sos_location_line", language,
            link=maps_link(alert.last_latitude, alert.last_longitude),
        )
    else:
        location_line = t("sos_no_location_line", language)
    contacts = len(user.emergency_contacts)
    contacts_text = str(contacts) if contacts else "0 — add with CONTACT <name> <phone>"
    return t(
        "sos_activated", language,
        location_line=location_line,
        coast_guard=coast_guard,
        contacts=contacts_text,
    )


def sos_contact_alert(user: User, alert: SOSAlert, coast_guard: str) -> str:
    """Sent to each emergency contact (English — contact language unknown)."""
    if alert.last_latitude is not None and alert.last_longitude is not None:
        location_line = (
            f"📍 Last location: {maps_link(alert.last_latitude, alert.last_longitude)}\n"
        )
    else:
        location_line = "📍 Location not yet available.\n"
    return t(
        "sos_contact_alert",
        Language.ENGLISH,
        name=user.name or user.phone,
        phone=user.phone,
        location_line=location_line,
        coast_guard=coast_guard,
    )


def sos_location_received(user: User, latitude: float, longitude: float) -> str:
    return t("sos_location_received", user.language, link=maps_link(latitude, longitude))


def sos_contact_location_update(user: User, latitude: float, longitude: float, at: datetime) -> str:
    return t(
        "sos_contact_location_update",
        Language.ENGLISH,
        name=user.name or user.phone,
        link=maps_link(latitude, longitude),
        time=_format_time(at) + " IST",
    )


def sos_cancelled(user: User) -> str:
    return t("sos_cancelled", user.language)


def sos_contact_stand_down(user: User) -> str:
    return t("sos_contact_stand_down", Language.ENGLISH, name=user.name or user.phone)
