"""Message composer — turns model objects into WhatsApp-ready text.

Formats deliberately match the execution plan's approved template layouts
(morning forecast, price digest, SOS) so the WhatsApp/Meta template
submissions and the code stay in sync.
"""

from datetime import date, datetime

from app.enums import Language, SafetyLevel
from app.localization.strings import t
from app.models import SOSAlert, User, WeatherForecast
from app.providers.weather.base import CoastalReport
from app.seeds import species_display_name
from app.services.price_service import MarketTip
from app.services.safety import classify_sea_state
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
    pfz_note = getattr(forecast, "pfz_note", None)
    if pfz_note:
        lines += ["", f"🎣 {pfz_note}"]
    strip = "".join(level.emoji for level in forecast.hourly_level_list()) or level.emoji * 6
    lines += [
        "",
        f"{t('next_6_hours', language)}: {strip}",
        "",
        t("menu_footer", language),
    ]
    return "\n".join(lines)


def detailed_forecast(user: User, forecast: WeatherForecast, now: datetime, coastal_reports: list | None = None) -> str:
    """Reply to '1' — coast-by-coast conditions with fishing suggestion."""
    language = user.language
    village_name = user.village.name if user.village else "your area"
    level = forecast.safety_level

    lines = [
        f"🌊 *Fisherman OS — {village_name}*",
        f"📅 {_format_date(forecast.forecast_date)} | {_format_time(now)}",
        f"📡 Source: {forecast.source.value.upper()}",
        "",
    ]

    if coastal_reports and len(coastal_reports) >= 1:
        # Score each coast: lower is safer (SAFE=0, CAUTION=1, DANGER=2)
        _level_score = {"SAFE": 0, "CAUTION": 1, "DANGER": 2}

        scored = []
        for report in coastal_reports:
            assessment = classify_sea_state(report.wind_speed_kmh, report.wave_height_m, report.rain_probability)
            scored.append((assessment.level, report))

        lines.append("🗺️ *Nearby Sea Conditions:*")
        lines.append("─" * 28)
        for lv, report in scored:
            condition_label = {
                "SAFE": "SAFE TO GO",
                "CAUTION": "CAUTION",
                "DANGER": "DANGER — AVOID",
            }.get(lv.value, lv.value)
            lines.append(f"{lv.emoji} *{report.name}*: {condition_label}")
            lines.append(f"   Wind: {report.wind_speed_kmh:.0f} km/h {report.wind_direction} | Waves: {report.wave_height_m:.1f}m | Rain: {report.rain_probability}%")
            if report.pfz_bearing_deg:
                pfz = f"   🎣 Fish zone: {report.pfz_direction} ({report.pfz_bearing_deg}°)"
                if report.pfz_distance_km:
                    pfz += f", {report.pfz_distance_km} km out"
                if report.pfz_depth_m:
                    pfz += f", depth {report.pfz_depth_m}m"
                lines.append(pfz)
            lines.append("")

        # Recommend the safest coast(s) with a PFZ
        safest = [
            (lv, r) for lv, r in scored
            if _level_score.get(lv.value, 9) == min(_level_score.get(l.value, 9) for l, _ in scored)
        ]
        safest_with_pfz = [(lv, r) for lv, r in safest if r.pfz_bearing_deg]
        pick = safest_with_pfz[0] if safest_with_pfz else safest[0] if safest else None

        if pick:
            lv, best = pick
            lines.append("─" * 28)
            lines.append(f"✅ *Best option today:*")
            lines.append(f"   Head to *{best.name}*")
            if best.pfz_bearing_deg:
                lines.append(f"   Go {best.pfz_direction} ({best.pfz_bearing_deg}°), {best.pfz_distance_km} km")
                if best.pfz_depth_m:
                    lines.append(f"   Target depth: {best.pfz_depth_m}m")
            lines.append("")

    else:
        # Fallback to single-point summary
        lines += [
            f"{_SKY_EMOJI[level]} Overall: {safety_line(level, language)}",
            "",
            f"🌬️ Wind: {forecast.wind_speed_kmh:.0f} km/h {forecast.wind_direction}",
            f"🌊 Waves: {forecast.wave_height_m:.1f}m ({_wave_description(forecast.wave_height_m, language)})",
            f"🌧️ Rain: {_rain_line(forecast, language)}",
        ]
        if forecast.sea_temp_c is not None:
            lines.append(f"🌡️ Sea temp: {forecast.sea_temp_c:.1f}°C")
        if forecast.advisory:
            lines += ["", f"⚠️ {forecast.advisory}"]
        lines.append("")

    pfz_note = getattr(forecast, "pfz_note", None)
    if pfz_note:
        lines += [f"🎣 {pfz_note}", ""]

    lines += [
        t("menu_footer", language),
    ]
    return "\n".join(lines)



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


def live_species_prices(
    user: User,
    species_key: str,
    quotes: list,           # list[fmpis.MarketQuote]
    nearest_market_name: str,
) -> str:
    """Reply for one fish across the Goa FMPIS markets — nearest market first,
    best-price tip at the end. `quotes` must be non-empty."""
    language = user.language
    species_name = species_display_name(species_key, language.value)
    village_name = user.village.name if user.village else "your village"

    nearest = [q for q in quotes if q.market.name == nearest_market_name]
    others = [q for q in quotes if q.market.name != nearest_market_name]

    lines = [t("live_price_header", language, species=species_name), ""]
    if nearest:
        quote = nearest[0]
        lines.append(
            f"📍 {quote.market.name} (nearest to {village_name}): "
            f"₹{quote.price_per_kg:.0f}/kg"
        )
    else:
        lines.append(f"📍 No listing at the market nearest to {village_name} today.")
    for quote in others:
        lines.append(f"• {quote.market.name}: ₹{quote.price_per_kg:.0f}/kg")

    best = max(quotes, key=lambda q: q.price_per_kg)
    if len(quotes) > 1:
        lines += ["", f"💡 Best price: {best.market.name} — ₹{best.price_per_kg:.0f}/kg"]
    lines += ["", t("price_footer", language)]
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
