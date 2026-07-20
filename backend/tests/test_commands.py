"""Registered-user commands: forecasts, prices, STOP/START, VILLAGE, CONTACT, HELP."""

from datetime import date

from app.bot.router import handle_inbound
from app.enums import OnboardingState, PriceSource, UserRole
from app.services import price_service
from app.services.user_service import get_user_by_phone
from tests.conftest import make_inbound, register_user

PHONE = "919822000001"


async def seed_prices(db):
    betul = await price_service.get_landing_center(db, "Betul")
    margao = await price_service.get_landing_center(db, "Margao")
    today = date.today()
    await price_service.record_price(
        db, landing_center=betul, species="mackerel", price_per_kg=85,
        price_date=today, source=PriceSource.FIELD_AGENT,
    )
    await price_service.record_price(
        db, landing_center=margao, species="mackerel", price_per_kg=110,
        price_date=today, source=PriceSource.FIELD_AGENT,
    )


async def test_detailed_forecast_command(db, wa):
    await register_user(db, wa, PHONE)
    wa.sent.clear()
    await handle_inbound(db, make_inbound(phone=PHONE, text="1"))
    assert len(wa.sent) == 1
    assert "Fisherman OS" in wa.sent[0][1]
    assert "Source:" in wa.sent[0][1]


async def test_prices_command_asks_for_fish_first(db, wa):
    await register_user(db, wa, PHONE)
    wa.sent.clear()
    wa.options_by_index.clear()
    await handle_inbound(db, make_inbound(phone=PHONE, text="PRICES"))

    assert len(wa.sent) == 1
    assert "Which fish" in wa.sent[0][1]
    assert "Mackerel" in wa.options_by_index.get(0, [])  # quick-reply buttons

    user = await get_user_by_phone(db, PHONE)
    assert user.onboarding_state == OnboardingState.AWAITING_FISH_TYPE


async def test_prices_all_returns_full_digest(db, wa):
    await register_user(db, wa, PHONE)
    await seed_prices(db)
    wa.sent.clear()
    await handle_inbound(db, make_inbound(phone=PHONE, text="PRICES"))
    await handle_inbound(db, make_inbound(phone=PHONE, text="ALL"))

    text = wa.sent[1][1]
    assert "Betul Landing" in text
    assert "Mackerel ₹85/kg" in text
    assert "29% more" in text  # Margao vs Betul tip

    user = await get_user_by_phone(db, PHONE)
    assert user.onboarding_state == OnboardingState.REGISTERED


async def test_prices_command_no_data(db, wa):
    await register_user(db, wa, PHONE)
    wa.sent.clear()
    await handle_inbound(db, make_inbound(phone=PHONE, text="2"))
    await handle_inbound(db, make_inbound(phone=PHONE, text="ALL"))
    assert "No market prices" in wa.sent[1][1]


async def test_stop_and_start(db, wa):
    await register_user(db, wa, PHONE)
    await handle_inbound(db, make_inbound(phone=PHONE, text="STOP"))
    user = await get_user_by_phone(db, PHONE)
    assert user.subscribed is False

    await handle_inbound(db, make_inbound(phone=PHONE, text="START"))
    user = await get_user_by_phone(db, PHONE)
    assert user.subscribed is True


async def test_village_change(db, wa):
    await register_user(db, wa, PHONE)
    wa.sent.clear()
    await handle_inbound(db, make_inbound(phone=PHONE, text="VILLAGE Palolem"))
    user = await get_user_by_phone(db, PHONE)
    assert user.village.name == "Palolem"
    assert "Palolem" in wa.sent[0][1]


async def test_add_emergency_contact(db, wa):
    await register_user(db, wa, PHONE)
    wa.sent.clear()
    await handle_inbound(db, make_inbound(phone=PHONE, text="CONTACT Maria 9822012345"))
    user = await get_user_by_phone(db, PHONE)
    assert len(user.emergency_contacts) == 1
    assert user.emergency_contacts[0].name == "Maria"
    assert user.emergency_contacts[0].phone == "919822012345"  # normalized to E.164


async def test_contact_bad_format_shows_usage(db, wa):
    await register_user(db, wa, PHONE)
    wa.sent.clear()
    await handle_inbound(db, make_inbound(phone=PHONE, text="CONTACT Maria"))
    assert "CONTACT <name> <phone>" in wa.sent[0][1]


async def test_help_command(db, wa):
    await register_user(db, wa, PHONE)
    wa.sent.clear()
    await handle_inbound(db, make_inbound(phone=PHONE, text="HELP"))
    text = wa.sent[0][1]
    assert "SOS" in text and "PRICES" in text and "STOP" in text


async def test_unknown_command_hint(db, wa):
    await register_user(db, wa, PHONE)
    wa.sent.clear()
    await handle_inbound(db, make_inbound(phone=PHONE, text="banana boat"))
    assert "HELP" in wa.sent[0][1]


async def test_field_agent_price_entry(db, wa):
    user = await register_user(db, wa, PHONE)
    user.role = UserRole.FIELD_AGENT
    await db.commit()
    wa.sent.clear()

    await handle_inbound(db, make_inbound(phone=PHONE, text="PRICE Betul bangdo 95"))
    assert "✅" in wa.sent[0][1]

    today = date.today()
    prices = await price_service.get_prices_for_day(db, today)
    assert len(prices) == 1
    assert prices[0].species == "mackerel"  # 'bangdo' resolved to canonical key
    assert prices[0].price_per_kg == 95


async def test_regular_user_cannot_enter_prices(db, wa):
    await register_user(db, wa, PHONE)
    wa.sent.clear()
    await handle_inbound(db, make_inbound(phone=PHONE, text="PRICE Betul bangdo 95"))
    assert "field agents" in wa.sent[0][1]

    prices = await price_service.get_prices_for_day(db, date.today())
    assert prices == []
