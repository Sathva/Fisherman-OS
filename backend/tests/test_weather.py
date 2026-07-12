"""Weather providers and the forecast service cache."""

from datetime import date

from sqlalchemy import func, select

from app.enums import SafetyLevel, WeatherSource
from app.models import Village, WeatherForecast
from app.providers.weather.incois import INCOISProvider
from app.providers.weather.synthetic import SyntheticWeatherProvider
from app.services import weather_service

INCOIS_SAMPLE_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>INCOIS Ocean State Forecast - Goa</title>
    <item>
      <title>Goa Coast OSF</title>
      <description>
        Wave Height: 1.2 m. Wind Speed: 25 kmph from SW.
        Sea Surface Temp: 28.4 C. Rain: 30 %.
      </description>
    </item>
  </channel>
</rss>
"""


async def test_synthetic_provider_is_deterministic():
    provider = SyntheticWeatherProvider()
    day = date(2026, 7, 8)
    reading_a = await provider.fetch(15.14, 73.96, day)
    reading_b = await provider.fetch(15.14, 73.96, day)
    assert reading_a.wind_speed_kmh == reading_b.wind_speed_kmh
    assert reading_a.wave_height_m == reading_b.wave_height_m
    assert len(reading_a.hourly) == 6


def test_incois_feed_parsing():
    reading = INCOISProvider().parse_feed(INCOIS_SAMPLE_FEED, date(2026, 7, 8))
    assert reading.wave_height_m == 1.2
    assert reading.wind_speed_kmh == 25.0
    assert reading.wind_direction == "SW"
    assert reading.sea_temp_c == 28.4
    assert reading.rain_probability == 30
    assert reading.source == WeatherSource.INCOIS


def test_incois_rejects_garbage():
    import pytest

    from app.providers.weather.base import WeatherUnavailable

    with pytest.raises(WeatherUnavailable):
        INCOISProvider().parse_feed("not xml at all", date(2026, 7, 8))
    with pytest.raises(WeatherUnavailable):
        INCOISProvider().parse_feed(
            "<rss><channel><item><title>no numbers here</title></item></channel></rss>",
            date(2026, 7, 8),
        )


async def test_forecast_cached_per_village_day(db):
    village = (
        await db.execute(select(Village).where(Village.name == "Betul"))
    ).scalar_one()
    day = date(2026, 7, 8)

    first = await weather_service.get_or_create_forecast(db, village, day)
    second = await weather_service.get_or_create_forecast(db, village, day)
    assert first.id == second.id  # cached, not re-fetched

    count = (
        await db.execute(select(func.count(WeatherForecast.id)))
    ).scalar_one()
    assert count == 1


async def test_forecast_has_safety_and_hourly_strip(db):
    village = (
        await db.execute(select(Village).where(Village.name == "Betul"))
    ).scalar_one()
    forecast = await weather_service.get_or_create_forecast(db, village, date(2026, 7, 8))

    assert forecast.safety_level in list(SafetyLevel)
    assert len(forecast.hourly_level_list()) == 6
    assert forecast.source == WeatherSource.SYNTHETIC


async def test_refresh_forecast_replaces_row(db):
    village = (
        await db.execute(select(Village).where(Village.name == "Betul"))
    ).scalar_one()
    day = date(2026, 7, 8)
    first = await weather_service.get_or_create_forecast(db, village, day)
    refreshed = await weather_service.refresh_forecast(db, village, day)

    # Still exactly one row for (village, day); the refreshed row carries the
    # same deterministic synthetic data but was re-issued.
    assert refreshed.issued_at >= first.issued_at
    count = (
        await db.execute(select(func.count(WeatherForecast.id)))
    ).scalar_one()
    assert count == 1
