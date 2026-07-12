"""INCOIS Ocean State Forecast provider (primary marine source).

INCOIS publishes district-wise Ocean State Forecast bulletins (wave height,
wind, SST) as RSS/XML. Feed layouts have changed over the years, so the parser
is defensive: it scans item titles/descriptions for labelled numbers
("Wave Height: 1.2 m", "Wind Speed: 25 kmph", ...) rather than assuming a
fixed schema. Configure the feed URL via INCOIS_RSS_URL; any failure raises
WeatherUnavailable so the service falls through to the next provider.
"""

import re
import xml.etree.ElementTree as ET
from datetime import date

import httpx

from app.config import get_settings
from app.enums import WeatherSource
from app.providers.weather.base import WeatherProvider, WeatherReading, WeatherUnavailable

_WAVE_RE = re.compile(r"wave[^0-9]{0,30}?(\d+(?:\.\d+)?)\s*(?:m|meter|metre)", re.IGNORECASE)
_WIND_RE = re.compile(r"wind[^0-9]{0,30}?(\d+(?:\.\d+)?)\s*(?:kmph|km/h|kph)", re.IGNORECASE)
_WIND_KT_RE = re.compile(r"wind[^0-9]{0,30}?(\d+(?:\.\d+)?)\s*(?:kt|knot)", re.IGNORECASE)
_SST_RE = re.compile(r"(?:sst|sea surface temp)[^0-9]{0,30}?(\d+(?:\.\d+)?)", re.IGNORECASE)
_DIR_RE = re.compile(r"\b(N|NNE|NE|ENE|E|ESE|SE|SSE|S|SSW|SW|WSW|W|WNW|NW|NNW)(?:erly)?\b")
_RAIN_RE = re.compile(r"rain[^0-9]{0,30}?(\d{1,3})\s*%", re.IGNORECASE)


class INCOISProvider(WeatherProvider):
    source = WeatherSource.INCOIS

    def __init__(self, client: httpx.AsyncClient | None = None):
        self._client = client

    async def fetch(self, latitude: float, longitude: float, day: date) -> WeatherReading:
        settings = get_settings()
        if not settings.incois_rss_url:
            raise WeatherUnavailable("INCOIS_RSS_URL not configured")

        try:
            if self._client is not None:
                response = await self._client.get(settings.incois_rss_url)
            else:
                async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                    response = await client.get(settings.incois_rss_url)
            response.raise_for_status()
            text = response.text
        except httpx.HTTPError as exc:
            raise WeatherUnavailable(f"INCOIS feed request failed: {exc}") from exc

        return self.parse_feed(text, day)

    def parse_feed(self, feed_xml: str, day: date) -> WeatherReading:
        try:
            root = ET.fromstring(feed_xml)
        except ET.ParseError as exc:
            raise WeatherUnavailable(f"INCOIS feed is not valid XML: {exc}") from exc

        # Combine every item's title+description; bulletins are per-district blobs.
        chunks: list[str] = []
        for item in root.iter("item"):
            for tag in ("title", "description"):
                node = item.find(tag)
                if node is not None and node.text:
                    chunks.append(node.text)
        blob = " ".join(chunks)
        if not blob.strip():
            raise WeatherUnavailable("INCOIS feed contained no items")

        wave = _first_float(_WAVE_RE, blob)
        wind = _first_float(_WIND_RE, blob)
        if wind is None:
            knots = _first_float(_WIND_KT_RE, blob)
            wind = knots * 1.852 if knots is not None else None
        if wave is None or wind is None:
            raise WeatherUnavailable("INCOIS feed missing wave/wind values")

        sst = _first_float(_SST_RE, blob)
        rain = _first_float(_RAIN_RE, blob)
        direction_match = _DIR_RE.search(blob)

        return WeatherReading(
            forecast_date=day,
            wind_speed_kmh=round(wind, 1),
            wind_direction=direction_match.group(1) if direction_match else "SW",
            wave_height_m=round(wave, 1),
            rain_probability=int(rain) if rain is not None else 0,
            sea_temp_c=round(sst, 1) if sst is not None else None,
            source=self.source,
            hourly=[],  # bulletin is daily; hourly strip falls back to the day level
        )


def _first_float(pattern: re.Pattern, text: str) -> float | None:
    match = pattern.search(text)
    return float(match.group(1)) if match else None
