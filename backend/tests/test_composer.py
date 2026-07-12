"""Message composer output (execution-plan template formats)."""

from datetime import date, datetime

from app.bot import composer
from app.enums import Language, SafetyLevel, WeatherSource
from app.models import User, Village, WeatherForecast
from app.services.price_service import MarketTip


def make_user(language=Language.ENGLISH, village_name="Betul") -> User:
    user = User(phone="919822000001", name="Rajesh", language=language)
    user.village = Village(
        name=village_name, taluka="Salcete", latitude=15.14, longitude=73.96
    )
    user.emergency_contacts = []
    return user


def make_forecast(level=SafetyLevel.SAFE, **overrides) -> WeatherForecast:
    values = dict(
        village_id=1,
        forecast_date=date(2026, 7, 8),
        issued_at=datetime(2026, 7, 8, 3, 15),
        wind_speed_kmh=12.0,
        wind_direction="SW",
        wave_height_m=0.8,
        rain_probability=20,
        rain_timing="after 2PM",
        sea_temp_c=28.5,
        safety_level=level,
        advisory="Return before 2PM — afternoon squall risk" if level != SafetyLevel.DANGER else "DO NOT go to sea today",
        hourly_levels="green,green,green,yellow,yellow,yellow",
        source=WeatherSource.INCOIS,
    )
    values.update(overrides)
    return WeatherForecast(**values)


def test_morning_forecast_matches_plan_format():
    text = composer.morning_forecast(make_user(), make_forecast(), datetime(2026, 7, 8, 3, 30))
    assert "🌊 Fisherman OS — Betul" in text
    assert "📅 8 July 2026 | 3:30 AM" in text
    assert "🟢 SAFE TO GO" in text
    assert "🌬️ Wind: 12 km/h SW" in text
    assert "🌊 Waves: 0.8m (calm)" in text
    assert "🌧️ Rain: 20% chance after 2PM" in text
    assert "🌡️ Sea temp: 28.5°C" in text
    assert "Next 6 hours: 🟢🟢🟢🟡🟡🟡" in text
    assert 'Type "1" for detailed forecast' in text
    assert 'Type "2" for market prices' in text
    assert 'Type "SOS" for emergency' in text


def test_morning_forecast_danger_in_konkani():
    text = composer.morning_forecast(
        make_user(language=Language.KONKANI),
        make_forecast(level=SafetyLevel.DANGER, wave_height_m=3.2, wind_speed_kmh=52),
        datetime(2026, 7, 8, 3, 30),
    )
    assert "🔴 DORYANT VOCHUM NAKA" in text  # DO NOT GO
    assert "Varem" in text  # wind
    assert "Lhara" in text  # waves


def test_detailed_forecast_includes_source():
    text = composer.detailed_forecast(make_user(), make_forecast(), datetime(2026, 7, 8, 6, 0))
    assert "Detailed Forecast" in text
    assert "Source: INCOIS" in text


def test_forecast_without_sea_temp_omits_line():
    text = composer.morning_forecast(
        make_user(), make_forecast(sea_temp_c=None), datetime(2026, 7, 8, 3, 30)
    )
    assert "Sea temp" not in text


class FakePrice:
    def __init__(self, species, price):
        self.species = species
        self.price_per_kg = price


def test_price_digest_format_and_tip():
    prices_by_center = {
        "Betul Landing": [FakePrice("mackerel", 85), FakePrice("pomfret", 320)],
        "Margao Fish Market": [FakePrice("mackerel", 110), FakePrice("pomfret", 380)],
    }
    tip = MarketTip(
        species="mackerel", best_center="Margao Fish Market", worst_center="Betul Landing",
        best_price=110, worst_price=85,
    )
    text = composer.price_digest(Language.ENGLISH, prices_by_center, tip, date(2026, 7, 7))
    assert "🐟 Today's Fish Prices (7 July 2026 closing)" in text
    assert "📍 Betul Landing:" in text
    assert "Mackerel ₹85/kg | Pomfret ₹320/kg" in text
    assert "💡 TIP: Margao Fish Market paying 29% more for Mackerel today" in text
    assert 'Type "PRICES" anytime for latest' in text


def test_price_digest_konkani_species_names():
    prices_by_center = {"Betul Landing": [FakePrice("mackerel", 85)]}
    text = composer.price_digest(Language.KONKANI, prices_by_center, None, date(2026, 7, 7))
    assert "Bangdo ₹85/kg" in text  # mackerel in Konkani


def test_empty_price_digest():
    text = composer.price_digest(Language.ENGLISH, {}, None, date(2026, 7, 7))
    assert "No market prices" in text
