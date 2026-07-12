"""Scheduled pushes: 3:30 AM forecast and 5 AM price digest."""

from datetime import date

from app.bot.router import handle_inbound
from app.scheduler import push_morning_forecasts, push_price_digests
from app.services import price_service
from tests.conftest import make_inbound, register_user

RAJESH = "919822000001"
SURESH = "919822000002"


async def test_morning_push_reaches_all_subscribed_users(db, wa):
    await register_user(db, wa, RAJESH, name="Rajesh", village="Betul")
    await register_user(db, wa, SURESH, name="Suresh", village="Palolem")
    wa.sent.clear()

    sent = await push_morning_forecasts()
    assert sent == 2
    sent_to = {phone for phone, _ in wa.sent}
    assert sent_to == {RAJESH, SURESH}
    for _phone, text in wa.sent:
        assert "Fisherman OS —" in text
        assert "Next 6 hours" in text


async def test_morning_push_skips_unsubscribed(db, wa):
    await register_user(db, wa, RAJESH)
    await register_user(db, wa, SURESH)
    await handle_inbound(db, make_inbound(phone=SURESH, text="STOP"))
    wa.sent.clear()

    sent = await push_morning_forecasts()
    assert sent == 1
    assert wa.sent[0][0] == RAJESH


async def test_morning_push_no_users(db, wa):
    assert await push_morning_forecasts() == 0


async def test_price_push_sends_digest(db, wa):
    await register_user(db, wa, RAJESH)
    betul = await price_service.get_landing_center(db, "Betul")
    await price_service.record_price(
        db, landing_center=betul, species="mackerel", price_per_kg=85, price_date=date.today()
    )
    wa.sent.clear()

    sent = await push_price_digests()
    assert sent == 1
    assert "Mackerel ₹85/kg" in wa.sent[0][1]


async def test_price_push_skips_when_no_prices(db, wa):
    await register_user(db, wa, RAJESH)
    wa.sent.clear()
    assert await push_price_digests() == 0
    assert wa.sent == []


async def test_localized_push(db, wa):
    """A Konkani user gets the Konkani morning forecast."""
    await register_user(db, wa, RAJESH, language="2")  # Konkani
    wa.sent.clear()

    await push_morning_forecasts()
    text = wa.sent[0][1]
    assert "Aizcho Dorya" in text  # "Today's Sea"
