"""FMPIS (fmpisnfdb.in) price fetcher — filtered, not the whole list.

Modified from the original one-market dump script:
  * queries ALL Goa markets (or one via --market) concurrently,
  * filters rows to ONE fish (--fish, alias-aware: bangdo -> mackerel),
  * prints a compact per-market table and saves the filtered rows to CSV,
  * bootstraps a fresh ci_session cookie instead of hardcoding a stale one.

Examples:
    python fmpis_prices.py --fish bangdo
    python fmpis_prices.py --fish prawns --market mapusa
    python fmpis_prices.py --fish all            # unfiltered dump (old behavior)

The same logic (markets, alias matching, defensive JSON parsing) is
integrated into the backend at backend/app/providers/prices/fmpis.py, where
the WhatsApp bot asks "which fish?" and answers with these prices.
"""

import argparse
import concurrent.futures
import csv
import json
import re

import requests

BASE_URL = "https://fmpisnfdb.in"
STATE_ID = "6"  # Goa

# FMPIS market ids for Goa.
MARKETS: dict[str, str] = {
    "assonora": "691",
    "mapusa": "569",
    "marcel": "690",
    "sgdpa wholesale": "568",
    "siolim": "737",
}

# Canonical species -> names/aliases actually used at Goan landing centers.
SPECIES_ALIASES: dict[str, list[str]] = {
    "mackerel": ["mackerel", "bangdo", "bangda", "bangde"],
    "sardine": ["sardine", "sardines", "tarlo", "tarle", "tarli", "pedvey", "pedvo"],
    "pomfret": ["pomfret", "pamplet", "paplet", "pomplet"],
    "kingfish": ["kingfish", "visvon", "viswon", "surmai", "seer", "seerfish"],
    "prawns": ["prawn", "prawns", "sungtam", "sungta", "shrimp", "jhinga", "kolambi"],
    "tuna": ["tuna", "kupa"],
    "squid": ["squid", "manki", "makul", "calamari"],
    "crab": ["crab", "crabs", "kurlyo", "kurli", "kekda", "khekda"],
    "sole": ["sole", "lepo", "lep"],
    "croaker": ["croaker", "dodyaro", "ghol", "dhoma"],
}

HEADERS = {
    "accept": "application/json, text/javascript, */*; q=0.01",
    "accept-language": "en-US,en;q=0.9",
    "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
    "origin": BASE_URL,
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"
    ),
    "x-requested-with": "XMLHttpRequest",
}


def resolve_fish(raw: str) -> str | None:
    """'bangdo' -> 'mackerel'; returns None when unrecognized."""
    needle = raw.strip().lower()
    for key, aliases in SPECIES_ALIASES.items():
        if needle == key or needle in aliases:
            return key
    return None


def fish_matches(row_name: str, species_key: str) -> bool:
    haystack = row_name.lower()
    terms = [species_key] + SPECIES_ALIASES.get(species_key, [])
    return any(term in haystack for term in terms)


def extract_records(data) -> list[dict]:
    """Find the row list in whatever envelope the endpoint wraps it in."""
    if isinstance(data, list):
        return [r for r in data if isinstance(r, dict)]
    if isinstance(data, dict):
        for value in data.values():
            if isinstance(value, list) and value and isinstance(value[0], dict):
                return [r for r in value if isinstance(r, dict)]
    return []


def row_fish_name(row: dict) -> str | None:
    for hint in ("fish", "species", "item", "commodity", "name"):
        for key, value in row.items():
            if hint in key.lower() and isinstance(value, str) and value.strip():
                return value.strip()
    return None


def row_price(row: dict) -> float | None:
    priority = ("price_per_kg", "retail", "price", "rate", "avg")
    scored = []
    for key, value in row.items():
        lower = key.lower()
        if not any(h in lower for h in ("price", "rate", "amount")):
            continue
        if isinstance(value, (int, float)):
            price = float(value)
        elif isinstance(value, str):
            cleaned = re.sub(r"[^\d.]", "", value)
            try:
                price = float(cleaned)
            except ValueError:
                continue
        else:
            continue
        if price <= 0:
            continue
        rank = next((i for i, p in enumerate(priority) if p in lower), len(priority))
        scored.append((rank, price))
    scored.sort(key=lambda pair: pair[0])
    return scored[0][1] if scored else None


def fetch_market(session: requests.Session, market_name: str, market_id: str) -> list[dict]:
    response = session.post(
        f"{BASE_URL}/prices/pricefilter",
        data={"serachbystate": STATE_ID, "searchBymarket": market_id},
        timeout=15,
    )
    response.raise_for_status()
    try:
        rows = extract_records(response.json())
    except json.JSONDecodeError:
        print(f"  {market_name}: response was not JSON, skipping")
        return []
    for row in rows:
        row["_market"] = market_name
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--fish", required=True,
                        help="fish name or alias (bangdo, tarlo, prawns...), or 'all'")
    parser.add_argument("--market", choices=sorted(MARKETS),
                        help="query one market only (default: all Goa markets)")
    parser.add_argument("--out", default="fish.csv", help="CSV output path")
    args = parser.parse_args()

    species = None
    if args.fish.lower() != "all":
        species = resolve_fish(args.fish)
        if species is None:
            known = ", ".join(sorted(SPECIES_ALIASES))
            raise SystemExit(f"Unknown fish {args.fish!r}. Known: {known} (or 'all').")

    markets = {args.market: MARKETS[args.market]} if args.market else MARKETS

    session = requests.Session()
    session.headers.update(HEADERS)
    # Fresh ci_session cookie (the dashboard sets it on the page load).
    try:
        session.get(f"{BASE_URL}/prices", timeout=15)
    except requests.RequestException as exc:
        print(f"Cookie bootstrap failed ({exc}); trying without it...")

    print(f"Querying {len(markets)} Goa market(s)...")
    all_rows: list[dict] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        futures = {
            pool.submit(fetch_market, session, name, mid): name
            for name, mid in markets.items()
        }
        for future in concurrent.futures.as_completed(futures):
            name = futures[future]
            try:
                all_rows.extend(future.result())
            except requests.RequestException as exc:
                print(f"  {name}: request failed ({exc})")

    if species is not None:
        all_rows = [
            row for row in all_rows
            if (name := row_fish_name(row)) and fish_matches(name, species)
        ]

    if not all_rows:
        print("No matching rows found.")
        return

    label = species or "all fish"
    print(f"\n{label} — {len(all_rows)} row(s):")
    for row in all_rows:
        price = row_price(row)
        price_text = f"₹{price:.0f}/kg" if price is not None else "price n/a"
        print(f"  {row['_market']:>16}: {row_fish_name(row)} — {price_text}")

    fieldnames = sorted({key for row in all_rows for key in row})
    with open(args.out, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)
    print(f"\nSaved {len(all_rows)} row(s) to {args.out}")


if __name__ == "__main__":
    main()
