"""OpenWeatherMap backup provider (free tier, point forecast).

OWM's free tier has no marine/wave data, so wave height is *estimated* from
wind speed (Beaufort-style). This provider exists purely as a fallback when
INCOIS is unreachable — INCOIS remains the primary marine source.
"""

from datetime import date, datetime

import httpx

from app.config import get_settings
from app.enums import WeatherSource
from app.providers.weather.base import (
    WeatherProvider,
    WeatherReading,
    WeatherUnavailable,
    degrees_to_compass,
)
from app.services.safety import estimate_wave_height_from_wind


class OpenWeatherMapProvider(WeatherProvider):
    source = WeatherSource.OPENWEATHERMAP

    def __init__(self, client: httpx.AsyncClient | None = None):
        self._client = client

    async def fetch(self, latitude: float, longitude: float, day: date) -> WeatherReading:
        settings = get_settings()
        if not settings.openweather_api_key:
            raise WeatherUnavailable("OPENWEATHER_API_KEY not configured")

        params = {
            "lat": latitude,
            "lon": longitude,
            "appid": settings.openweather_api_key,
            "units": "metric",
        }
        try:
            if self._client is not None:
                response = await self._client.get(settings.openweather_api_url, params=params)
            else:
                async with httpx.AsyncClient(timeout=15) as client:
                    response = await client.get(settings.openweather_api_url, params=params)
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise WeatherUnavailable(f"OpenWeatherMap request failed: {exc}") from exc

        # /forecast returns 3-hourly slots; keep the requested day's slots.
        slots = [
            entry for entry in payload.get("list", [])
            if datetime.fromtimestamp(entry["dt"]).date() == day
        ]
        if not slots:
            slots = payload.get("list", [])[:4]
        if not slots:
            raise WeatherUnavailable("OpenWeatherMap returned no forecast slots")

        first = slots[0]
        wind_ms = first.get("wind", {}).get("speed", 0.0)
        wind_kmh = wind_ms * 3.6
        wind_deg = first.get("wind", {}).get("deg", 225.0)
        rain_prob = int(max((s.get("pop", 0.0) for s in slots), default=0.0) * 100)

        hourly = []
        for slot in slots[:6]:
            slot_wind = slot.get("wind", {}).get("speed", 0.0) * 3.6
            hourly.append((slot_wind, estimate_wave_height_from_wind(slot_wind),
                           int(slot.get("pop", 0.0) * 100)))

        rain_timing = None
        for slot in slots:
            if slot.get("pop", 0.0) >= 0.5:
                hour = datetime.fromtimestamp(slot["dt"]).hour
                rain_timing = f"after {hour % 12 or 12}{'PM' if hour >= 12 else 'AM'}"
                break

        return WeatherReading(
            forecast_date=day,
            wind_speed_kmh=round(wind_kmh, 1),
            wind_direction=degrees_to_compass(wind_deg),
            wave_height_m=round(estimate_wave_height_from_wind(wind_kmh), 1),
            rain_probability=rain_prob,
            rain_timing=rain_timing,
            sea_temp_c=first.get("main", {}).get("temp"),  # air temp ≈ coastal SST proxy
            source=self.source,
            hourly=hourly,
        )
