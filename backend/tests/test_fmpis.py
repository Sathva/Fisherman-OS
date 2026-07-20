"""FMPIS live prices: parsing, market selection, and the ask-fish chat flow."""

import httpx
import pytest

from app.bot.router import handle_inbound
from app.enums import OnboardingState
from app.providers.prices import fmpis
from app.providers.prices.fmpis import (
    FMPISUnavailable,
    MarketQuote,
    extract_records,
    fetch_species_quotes,
    nearest_market,
    record_fish_name,
    record_price,
    species_matches,
)
from app.services.user_service import get_user_by_phone
from tests.conftest import make_inbound, register_user

PHONE = "919822000001"


# --- Parsing helpers -----------------------------------------------------------


def test_extract_records_handles_common_envelopes():
    rows = [{"fish_name": "Mackerel", "price": "180"}]
    assert extract_records(rows) == rows
    assert extract_records({"data": rows}) == rows
    assert extract_records({"status": "ok", "results": rows}) == rows
    assert extract_records({"status": "ok"}) == []
    assert extract_records("<html>") == []


def test_record_fish_name_and_price_are_fuzzy():
    row = {"id": 7, "fishName": "Pomfret (White)", "retail_price": "₹1,250.50/kg"}
    assert record_fish_name(row) == "Pomfret (White)"
    assert record_price(row) == 1250.50


def test_record_price_prefers_retail_over_wholesale():
    row = {"fish": "Sardine", "wholesale_price": "90", "retail_price": "120"}
    assert record_price(row) == 120.0


def test_record_price_rejects_garbage():
    assert record_price({"fish": "Tuna", "price": "call market"}) is None
    assert record_price({"fish": "Tuna", "note": "fresh"}) is None


def test_species_matches_uses_aliases():
    assert species_matches("Mackerel (Bangda)", "mackerel")
    assert species_matches("bangdo - large", "mackerel")
    assert species_matches("White Pomfret", "pomfret")
    assert not species_matches("Sardine", "mackerel")


def test_nearest_market_by_village_coordinates():
    # Betul (South Goa) -> SGDPA Wholesale (Margao); Anjuna-ish north -> Mapusa
    assert nearest_market(15.140, 73.958).name == "SGDPA Wholesale (Margao)"
    assert nearest_market(15.585, 73.795).name == "Mapusa"


# --- fetch_species_quotes against a mocked FMPIS -------------------------------


def _mock_client(rows_by_market: dict[str, list[dict]], fail_ids: set[str] = frozenset()):
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.endswith("/prices"):
            return httpx.Response(200, text="<html>dashboard</html>")
        body = request.read().decode()
        market_id = body.split("searchBymarket=")[-1]
        if market_id in fail_ids:
            return httpx.Response(500, text="boom")
        return httpx.Response(200, json={"data": rows_by_market.get(market_id, [])})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_fetch_species_quotes_one_per_market(db):
    rows = {
        "568": [{"fish_name": "Mackerel", "price": "110"},
                {"fish_name": "Sardine", "price": "70"}],
        "569": [{"fish_name": "Bangda Mackerel", "price": "95"}],
        "691": [{"fish_name": "Sardine", "price": "65"}],  # no mackerel here
    }
    async with _mock_client(rows) as client:
        quotes = await fetch_species_quotes("mackerel", client=client)

    assert {q.market.market_id: q.price_per_kg for q in quotes} == {"568": 110.0, "569": 95.0}


async def test_fetch_species_quotes_survives_partial_failures(db):
    rows = {"568": [{"fish_name": "Mackerel", "price": "110"}]}
    async with _mock_client(rows, fail_ids={"569", "690", "691", "737"}) as client:
        quotes = await fetch_species_quotes("mackerel", client=client)
    assert len(quotes) == 1


async def test_fetch_species_quotes_raises_when_all_markets_fail(db):
    async with _mock_client({}, fail_ids={"568", "569", "690", "691", "737"}) as client:
        with pytest.raises(FMPISUnavailable):
            await fetch_species_quotes("mackerel", client=client)


# --- Chat flow: which fish? -> live prices -------------------------------------


def _fake_quotes(monkeypatch, quotes):
    async def _fake(species_key, client=None):
        return quotes

    monkeypatch.setattr(fmpis, "fetch_species_quotes", _fake)


async def test_fish_reply_returns_only_that_fish_across_markets(db, wa, monkeypatch):
    await register_user(db, wa, PHONE)  # village Betul -> nearest SGDPA
    markets = {m.market_id: m for m in fmpis.GOA_MARKETS}
    _fake_quotes(monkeypatch, [
        MarketQuote(markets["568"], "Mackerel (Bangda)", 110.0),
        MarketQuote(markets["569"], "Mackerel", 95.0),
        MarketQuote(markets["737"], "Mackerel", 130.0),
    ])
    await handle_inbound(db, make_inbound(phone=PHONE, text="2"))
    wa.sent.clear()

    await handle_inbound(db, make_inbound(phone=PHONE, text="bangdo"))
    assert len(wa.sent) == 1
    text = wa.sent[0][1]
    assert "Mackerel" in text
    assert "SGDPA Wholesale (Margao) (nearest to Betul): ₹110/kg" in text
    assert "Mapusa: ₹95/kg" in text
    assert "Best price: Siolim — ₹130/kg" in text
    assert "Sardine" not in text  # only the requested fish

    user = await get_user_by_phone(db, PHONE)
    assert user.onboarding_state == OnboardingState.REGISTERED


async def test_fish_not_listed_message(db, wa, monkeypatch):
    await register_user(db, wa, PHONE)
    _fake_quotes(monkeypatch, [])
    await handle_inbound(db, make_inbound(phone=PHONE, text="2"))
    wa.sent.clear()

    await handle_inbound(db, make_inbound(phone=PHONE, text="squid"))
    assert len(wa.sent) == 1
    assert "No Squid listed" in wa.sent[0][1]


async def test_fmpis_down_falls_back_to_recorded_digest(db, wa, monkeypatch):
    await register_user(db, wa, PHONE)

    async def _boom(species_key, client=None):
        raise FMPISUnavailable("blocked")

    monkeypatch.setattr(fmpis, "fetch_species_quotes", _boom)
    await handle_inbound(db, make_inbound(phone=PHONE, text="2"))
    wa.sent.clear()

    await handle_inbound(db, make_inbound(phone=PHONE, text="bangdo"))
    assert len(wa.sent) == 2
    assert "Live market prices are unavailable" in wa.sent[0][1]
    # No seeded prices in this test -> the recorded-price fallback says so.
    assert "No market prices" in wa.sent[1][1]


async def test_non_fish_reply_falls_through_to_commands(db, wa, monkeypatch):
    await register_user(db, wa, PHONE)
    await handle_inbound(db, make_inbound(phone=PHONE, text="2"))
    wa.sent.clear()

    await handle_inbound(db, make_inbound(phone=PHONE, text="1"))
    assert len(wa.sent) == 1
    assert "Source:" in wa.sent[0][1]  # detailed forecast, not a price reply

    user = await get_user_by_phone(db, PHONE)
    assert user.onboarding_state == OnboardingState.REGISTERED
