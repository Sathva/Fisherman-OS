"""Weather provider interface and the normalized reading they all return."""

import abc
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from app.enums import WeatherSource


@dataclass
class CoastalReport:
    """Per-point weather + PFZ report for a nearby coastal location."""
    name: str
    latitude: float
    longitude: float
    wind_speed_kmh: float
    wave_height_m: float
    rain_probability: int
    wind_direction: str
    # PFZ (Potential Fishing Zone) data from INCOIS
    pfz_direction: str = ""       # e.g. "SE"
    pfz_bearing_deg: str = ""     # e.g. "142"
    pfz_distance_km: str = ""     # e.g. "112-117"
    pfz_depth_m: str = ""         # e.g. "45-50"


@dataclass
class WeatherReading:
    """Normalized sea-state snapshot for one village on one day."""

    forecast_date: date
    wind_speed_kmh: float
    wind_direction: str          # 16-point compass, e.g. "SW"
    wave_height_m: float
    rain_probability: int        # 0-100
    sea_temp_c: float | None
    source: WeatherSource
    rain_timing: str | None = None            # human hint, e.g. "after 2PM"
    # Per-hour (next 6h) wind/wave used to build the 🟢🟢🟡 outlook strip.
    hourly: list[tuple[float, float, int]] = field(default_factory=list)  # (wind, wave, rain%)
    # Per-coast breakdown when multiple INCOIS points were used
    coastal_reports: list[CoastalReport] = field(default_factory=list)
    # User-facing note when PFZ (fishing zone) data was unavailable and the
    # reading fell back to plain weather near the village.
    pfz_note: Optional[str] = None


class WeatherProvider(abc.ABC):
    """A source of sea-state forecasts. Providers raise WeatherUnavailable on
    any failure so the service can fall through to the next provider."""

    source: WeatherSource

    @abc.abstractmethod
    async def fetch(self, latitude: float, longitude: float, day: date) -> WeatherReading:
        ...


class WeatherUnavailable(Exception):
    pass


COMPASS_POINTS = [
    "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
    "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW",
]


def degrees_to_compass(degrees: float) -> str:
    index = round((degrees % 360) / 22.5) % 16
    return COMPASS_POINTS[index]
