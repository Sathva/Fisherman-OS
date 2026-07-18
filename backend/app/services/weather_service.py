"""Weather service: provider fallback chain + per-village daily cache.

Order (weather_provider="auto"): INCOIS → OpenWeatherMap → synthetic.
INCOIS is the authoritative marine source; OWM is a point-forecast backup;
synthetic keeps dev/pilot demos alive with deterministic data.
"""

import logging
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.enums import SafetyLevel, WeatherSource
from app.models import Village, WeatherForecast
from app.providers.weather.base import WeatherProvider, WeatherReading, WeatherUnavailable, CoastalReport
from app.providers.weather.incois import INCOISProvider
from app.providers.weather.openmeteo import OpenMeteoProvider
from app.providers.weather.openweathermap import OpenWeatherMapProvider
from app.providers.weather.synthetic import SyntheticWeatherProvider
from app.services.safety import classify_sea_state

logger = logging.getLogger(__name__)

_PROVIDERS: dict[str, type[WeatherProvider]] = {
    "incois": INCOISProvider,
    "openweathermap": OpenWeatherMapProvider,
    "synthetic": SyntheticWeatherProvider,
    "openmeteo": OpenMeteoProvider,
}


def build_provider_chain() -> list[WeatherProvider]:
    mode = get_settings().weather_provider
    if mode == "auto":
        return [OpenMeteoProvider(), INCOISProvider(), OpenWeatherMapProvider()]
    provider_cls = _PROVIDERS.get(mode)
    if provider_cls is None:
        raise ValueError(f"Unknown weather_provider: {mode!r}")
    chain: list[WeatherProvider] = [provider_cls()]
    return chain


async def fetch_reading(village: Village, day: date) -> WeatherReading:
    last_error: Exception | None = None
    for provider in build_provider_chain():
        try:
            # Pass village_name as a hint for the fallback label
            if hasattr(provider, 'fetch') and 'village_name' in provider.fetch.__code__.co_varnames:
                reading = await provider.fetch(village.latitude, village.longitude, day, village_name=village.name)
            else:
                reading = await provider.fetch(village.latitude, village.longitude, day)
            logger.info("Weather for %s on %s from %s", village.name, day, provider.source.value)
            return reading
        except WeatherUnavailable as exc:
            last_error = exc
            logger.warning("Weather provider %s unavailable: %s", provider.source.value, exc)
    raise WeatherUnavailable(f"All weather providers failed (last: {last_error})")


def _advisory_for(reading: WeatherReading, level: SafetyLevel, reasons: list[str]) -> str | None:
    if level == SafetyLevel.DANGER:
        return "DO NOT go to sea today — " + ", ".join(reasons)
    if level == SafetyLevel.CAUTION:
        if reading.rain_timing:
            return f"Return before conditions worsen ({reading.rain_timing} rain/squall risk)"
        return "Caution advised — " + ", ".join(reasons)
    if reading.rain_probability >= 40 and reading.rain_timing:
        return f"Return early — rain expected {reading.rain_timing}"
    return None


def _hourly_levels(reading: WeatherReading, day_level: SafetyLevel) -> list[SafetyLevel]:
    """Next-6-hours strip; falls back to repeating the day level when the
    source has no hourly data (e.g. INCOIS daily bulletins)."""
    if not reading.hourly:
        return [day_level] * 6
    levels = [
        classify_sea_state(wind, wave, rain).level
        for wind, wave, rain in reading.hourly[:6]
    ]
    while len(levels) < 6:
        levels.append(levels[-1])
    return levels

async def get_or_create_forecast(
    session: AsyncSession, village: Village, day: date
) -> tuple[WeatherForecast, list[CoastalReport]]:
    """Always fetch a fresh forecast — no DB caching."""
    reading = await fetch_reading(village, day)
    assessment = classify_sea_state(
        reading.wind_speed_kmh, reading.wave_height_m, reading.rain_probability
    )
    hourly = _hourly_levels(reading, assessment.level)

    forecast = WeatherForecast(
        village_id=village.id,
        forecast_date=day,
        wind_speed_kmh=reading.wind_speed_kmh,
        wind_direction=reading.wind_direction,
        wave_height_m=reading.wave_height_m,
        rain_probability=reading.rain_probability,
        rain_timing=reading.rain_timing,
        sea_temp_c=reading.sea_temp_c,
        safety_level=assessment.level,
        advisory=_advisory_for(reading, assessment.level, assessment.reasons),
        hourly_levels=",".join(level.value for level in hourly),
        source=reading.source,
    )
    # Not persisted — transient object only, no DB commit
    return forecast, reading.coastal_reports


async def refresh_forecast(session: AsyncSession, village: Village, day: date) -> WeatherForecast:
    """Fetch a fresh forecast (used by the 3:30 AM scheduler push). Forecasts
    are never persisted, so a refresh is simply a new fetch."""
    forecast, _ = await get_or_create_forecast(session, village, day)
    return forecast


# Re-export for callers that only need the source enum default
__all__ = [
    "build_provider_chain",
    "fetch_reading",
    "get_or_create_forecast",
    "refresh_forecast",
    "WeatherSource",
]
