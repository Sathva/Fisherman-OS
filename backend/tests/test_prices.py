"""Price service: upsert, tips, species resolution."""

from datetime import date, timedelta

from app.enums import PriceSource
from app.seeds import resolve_species, species_display_name
from app.services import price_service


async def test_record_price_upserts(db):
    betul = await price_service.get_landing_center(db, "Betul")
    today = date.today()

    await price_service.record_price(
        db, landing_center=betul, species="mackerel", price_per_kg=80, price_date=today
    )
    await price_service.record_price(
        db, landing_center=betul, species="mackerel", price_per_kg=90, price_date=today
    )

    prices = await price_service.get_prices_for_day(db, today)
    assert len(prices) == 1
    assert prices[0].price_per_kg == 90  # latest report wins


async def test_landing_center_fuzzy_match(db):
    assert (await price_service.get_landing_center(db, "betul")).name == "Betul Landing"
    assert (await price_service.get_landing_center(db, "Margao")).name == "Margao Fish Market"
    assert (await price_service.get_landing_center(db, "cutbona")).name == "Cutbona Harbor"
    assert await price_service.get_landing_center(db, "Mumbai") is None


async def test_best_market_tip(db):
    betul = await price_service.get_landing_center(db, "Betul")
    margao = await price_service.get_landing_center(db, "Margao")
    today = date.today()

    # Plan's example: Betul ₹85 vs Margao ₹110 -> "29% more"
    await price_service.record_price(
        db, landing_center=betul, species="mackerel", price_per_kg=85, price_date=today
    )
    await price_service.record_price(
        db, landing_center=margao, species="mackerel", price_per_kg=110, price_date=today
    )
    # pomfret has a smaller spread; mackerel should win
    await price_service.record_price(
        db, landing_center=betul, species="pomfret", price_per_kg=320, price_date=today
    )
    await price_service.record_price(
        db, landing_center=margao, species="pomfret", price_per_kg=380, price_date=today
    )

    prices = await price_service.get_prices_for_day(db, today)
    tip = price_service.best_market_tip(prices)
    assert tip is not None
    assert tip.species == "mackerel"
    assert tip.best_center == "Margao Fish Market"
    assert tip.uplift_pct == 29


async def test_no_tip_for_single_center(db):
    betul = await price_service.get_landing_center(db, "Betul")
    await price_service.record_price(
        db, landing_center=betul, species="mackerel", price_per_kg=85, price_date=date.today()
    )
    prices = await price_service.get_prices_for_day(db, date.today())
    assert price_service.best_market_tip(prices) is None


async def test_no_tip_for_tiny_spread(db):
    betul = await price_service.get_landing_center(db, "Betul")
    margao = await price_service.get_landing_center(db, "Margao")
    today = date.today()
    await price_service.record_price(
        db, landing_center=betul, species="mackerel", price_per_kg=100, price_date=today
    )
    await price_service.record_price(
        db, landing_center=margao, species="mackerel", price_per_kg=102, price_date=today
    )
    prices = await price_service.get_prices_for_day(db, today)
    assert price_service.best_market_tip(prices) is None  # 2% is not worth the fuel


async def test_latest_price_day_falls_back_to_yesterday(db):
    betul = await price_service.get_landing_center(db, "Betul")
    yesterday = date.today() - timedelta(days=1)
    await price_service.record_price(
        db, landing_center=betul, species="mackerel", price_per_kg=85,
        price_date=yesterday, source=PriceSource.FIELD_AGENT,
    )
    assert await price_service.get_latest_price_day(db, date.today()) == yesterday


def test_species_resolution():
    assert resolve_species("mackerel") == "mackerel"
    assert resolve_species("Bangdo") == "mackerel"
    assert resolve_species("BANGDA") == "mackerel"
    assert resolve_species("sungtam") == "prawns"
    assert resolve_species("paplet") == "pomfret"
    assert resolve_species("surmai") == "kingfish"
    assert resolve_species("dinosaur") is None


def test_species_display_names():
    assert species_display_name("mackerel", "en") == "Mackerel"
    assert species_display_name("mackerel", "kok") == "Bangdo"
    assert species_display_name("prawns", "hi") == "Jhinga"
    assert species_display_name("unknown-key", "en") == "Unknown-Key"
