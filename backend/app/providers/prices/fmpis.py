"""FMPIS (NFDB) live market prices for Goa.

fmpisnfdb.in serves its price dashboard through a form-POST endpoint
(POST /prices/pricefilter with serachbystate/searchBymarket — the typo in
"serachbystate" is the site's own field name) that returns JSON rows for one
market. This module fetches the Goa markets concurrently, filters the rows
down to a single species, and knows which market is nearest a village.

The response schema is not formally documented, so parsing is deliberately
defensive: rows are located as "the first list of dicts" anywhere in the
payload, and the fish-name / price fields are found by fuzzy key matching.
Every failure raises FMPISUnavailable so the bot can fall back to
field-agent prices — it never goes silent.
"""

import asyncio
import logging
import re
from dataclasses import dataclass

import httpx

from app.config import get_settings
from app.seeds import SPECIES

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Market:
    name: str
    market_id: str
    latitude: float
    longitude: float


# FMPIS market ids for Goa (state id 6). Coordinates are approximate market
# locations, used only to pick the market nearest the user's village.
GOA_MARKETS: list[Market] = [
    Market("Assonora", "691", 15.607, 73.867),
    Market("Mapusa", "569", 15.591, 73.808),
    Market("Marcel", "690", 15.493, 73.945),
    Market("SGDPA Wholesale (Margao)", "568", 15.270, 73.958),
    Market("Siolim", "737", 15.620, 73.768),
]


@dataclass(frozen=True)
class MarketQuote:
    market: Market
    fish_name: str      # as listed on FMPIS, e.g. "Mackerel (Bangda)"
    price_per_kg: float


class FMPISUnavailable(Exception):
    """FMPIS endpoint down / blocked / returned garbage — use the fallback."""


_POST_HEADERS = {
    "accept": "application/json, text/javascript, */*; q=0.01",
    "accept-language": "en-US,en;q=0.9",
    "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"
    ),
    "x-requested-with": "XMLHttpRequest",
}


def nearest_market(latitude: float, longitude: float) -> Market:
    """Market closest to a point (flat-earth distance is fine at Goa scale)."""
    return min(
        GOA_MARKETS,
        key=lambda m: (m.latitude - latitude) ** 2 + (m.longitude - longitude) ** 2,
    )


def extract_records(data) -> list[dict]:
    """Find the row list in whatever envelope FMPIS wraps it in."""
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    if isinstance(data, dict):
        for value in data.values():
            if isinstance(value, list) and value and isinstance(value[0], dict):
                return [row for row in value if isinstance(row, dict)]
    return []


_NAME_KEY_HINTS = ("fish", "species", "item", "commodity", "name")
_PRICE_KEY_HINTS = ("price", "rate", "amount")
# Prefer retail over wholesale when both appear; "min"/"max" lose to plain.
_PRICE_KEY_PRIORITY = ("price_per_kg", "retail", "price", "rate", "avg")


def record_fish_name(record: dict) -> str | None:
    for hint in _NAME_KEY_HINTS:
        for key, value in record.items():
            if hint in key.lower() and isinstance(value, str) and value.strip():
                return value.strip()
    return None


def _parse_price(value) -> float | None:
    if isinstance(value, (int, float)):
        return float(value) if value > 0 else None
    if isinstance(value, str):
        cleaned = re.sub(r"[^\d.]", "", value)
        try:
            price = float(cleaned)
        except ValueError:
            return None
        return price if price > 0 else None
    return None


def record_price(record: dict) -> float | None:
    scored: list[tuple[int, float]] = []
    for key, value in record.items():
        lower = key.lower()
        if not any(hint in lower for hint in _PRICE_KEY_HINTS):
            continue
        price = _parse_price(value)
        if price is None:
            continue
        rank = next(
            (i for i, pref in enumerate(_PRICE_KEY_PRIORITY) if pref in lower),
            len(_PRICE_KEY_PRIORITY),
        )
        scored.append((rank, price))
    if not scored:
        return None
    scored.sort(key=lambda pair: pair[0])
    return scored[0][1]


def species_matches(fish_name: str, species_key: str) -> bool:
    """Does an FMPIS row's fish name refer to our canonical species?"""
    info = SPECIES.get(species_key)
    if info is None:
        return False
    haystack = fish_name.lower()
    terms = {species_key, info["en"].lower(), *info["aliases"]}
    return any(term in haystack for term in terms)


async def _fetch_market_rows(
    client: httpx.AsyncClient, base_url: str, state_id: str, market: Market
) -> list[dict]:
    response = await client.post(
        f"{base_url}/prices/pricefilter",
        data={"serachbystate": state_id, "searchBymarket": market.market_id},
        headers=_POST_HEADERS,
    )
    response.raise_for_status()
    try:
        data = response.json()
    except ValueError as exc:
        raise FMPISUnavailable(f"{market.name}: non-JSON response") from exc
    return extract_records(data)


async def fetch_species_quotes(
    species_key: str, client: httpx.AsyncClient | None = None
) -> list[MarketQuote]:
    """One quote per Goa market for a species (markets without it are skipped).

    Raises FMPISUnavailable when FMPIS is disabled or no market responded.
    An empty list means FMPIS answered but the species isn't listed today.
    """
    settings = get_settings()
    if not settings.fmpis_enabled:
        raise FMPISUnavailable("FMPIS disabled via FMPIS_ENABLED")

    own_client = client is None
    if client is None:
        client = httpx.AsyncClient(
            timeout=settings.fmpis_timeout_seconds, follow_redirects=True
        )
    try:
        # Best-effort session-cookie bootstrap (mirrors the dashboard page load).
        try:
            await client.get(f"{settings.fmpis_base_url}/prices", headers=_POST_HEADERS)
        except httpx.HTTPError:
            pass

        results = await asyncio.gather(
            *(
                _fetch_market_rows(
                    client, settings.fmpis_base_url, settings.fmpis_state_id, market
                )
                for market in GOA_MARKETS
            ),
            return_exceptions=True,
        )
    finally:
        if own_client:
            await client.aclose()

    quotes: list[MarketQuote] = []
    any_market_ok = False
    for market, rows in zip(GOA_MARKETS, results):
        if isinstance(rows, BaseException):
            logger.warning("FMPIS market %s failed: %s", market.name, rows)
            continue
        any_market_ok = True
        for row in rows:
            name = record_fish_name(row)
            price = record_price(row)
            if name and price and species_matches(name, species_key):
                quotes.append(MarketQuote(market, name, price))
                break  # one quote per market

    if not any_market_ok:
        raise FMPISUnavailable("all FMPIS market requests failed")
    return quotes
