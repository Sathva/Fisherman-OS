"""Seed data for the Goa MVP: South Goa marine fishing villages, landing
centers where prices are collected, and the fish species catalog.

Coordinates are approximate village/beach centroids — good enough for the
12 km INCOIS forecast grid; refine during field onboarding.
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import LandingCenter, Village

# --- 41 South Goa marine fishing villages (Mormugao / Salcete / Quepem / Canacona) ---
SOUTH_GOA_VILLAGES: list[dict] = [
    # Mormugao taluka
    {"name": "Baina", "taluka": "Mormugao", "latitude": 15.395, "longitude": 73.805},
    {"name": "Vaddem", "taluka": "Mormugao", "latitude": 15.390, "longitude": 73.822},
    {"name": "Sada", "taluka": "Mormugao", "latitude": 15.407, "longitude": 73.797},
    {"name": "Chicalim", "taluka": "Mormugao", "latitude": 15.398, "longitude": 73.848},
    {"name": "Sao Jacinto Island", "taluka": "Mormugao", "latitude": 15.418, "longitude": 73.860},
    {"name": "Sancoale", "taluka": "Mormugao", "latitude": 15.383, "longitude": 73.885},
    {"name": "Cortalim", "taluka": "Mormugao", "latitude": 15.398, "longitude": 73.906},
    {"name": "Dabolim", "taluka": "Mormugao", "latitude": 15.383, "longitude": 73.838},
    {"name": "Bogmalo", "taluka": "Mormugao", "latitude": 15.372, "longitude": 73.834},
    {"name": "Issorcim", "taluka": "Mormugao", "latitude": 15.365, "longitude": 73.845},
    {"name": "Hollant", "taluka": "Mormugao", "latitude": 15.360, "longitude": 73.853},
    {"name": "Velsao", "taluka": "Mormugao", "latitude": 15.352, "longitude": 73.888},
    # Salcete taluka
    {"name": "Arossim", "taluka": "Salcete", "latitude": 15.337, "longitude": 73.902},
    {"name": "Cansaulim", "taluka": "Salcete", "latitude": 15.332, "longitude": 73.908},
    {"name": "Utorda", "taluka": "Salcete", "latitude": 15.318, "longitude": 73.913},
    {"name": "Majorda", "taluka": "Salcete", "latitude": 15.305, "longitude": 73.915},
    {"name": "Betalbatim", "taluka": "Salcete", "latitude": 15.293, "longitude": 73.918},
    {"name": "Colva", "taluka": "Salcete", "latitude": 15.280, "longitude": 73.917},
    {"name": "Sernabatim", "taluka": "Salcete", "latitude": 15.268, "longitude": 73.920},
    {"name": "Benaulim", "taluka": "Salcete", "latitude": 15.255, "longitude": 73.925},
    {"name": "Varca", "taluka": "Salcete", "latitude": 15.232, "longitude": 73.935},
    {"name": "Carmona", "taluka": "Salcete", "latitude": 15.212, "longitude": 73.940},
    {"name": "Cavelossim", "taluka": "Salcete", "latitude": 15.173, "longitude": 73.942},
    {"name": "Mobor", "taluka": "Salcete", "latitude": 15.152, "longitude": 73.945},
    {"name": "Assolna", "taluka": "Salcete", "latitude": 15.168, "longitude": 73.963},
    {"name": "Velim", "taluka": "Salcete", "latitude": 15.152, "longitude": 73.972},
    {"name": "Betul", "taluka": "Salcete", "latitude": 15.140, "longitude": 73.958},
    {"name": "Ambelim", "taluka": "Salcete", "latitude": 15.163, "longitude": 73.978},
    {"name": "Chinchinim", "taluka": "Salcete", "latitude": 15.212, "longitude": 73.972},
    # Quepem taluka
    {"name": "Xelvona", "taluka": "Quepem", "latitude": 15.135, "longitude": 73.985},
    {"name": "Cavorem", "taluka": "Quepem", "latitude": 15.128, "longitude": 73.992},
    # Canacona taluka
    {"name": "Cola", "taluka": "Canacona", "latitude": 15.045, "longitude": 73.930},
    {"name": "Agonda", "taluka": "Canacona", "latitude": 15.043, "longitude": 73.987},
    {"name": "Palolem", "taluka": "Canacona", "latitude": 15.010, "longitude": 74.023},
    {"name": "Colomb", "taluka": "Canacona", "latitude": 15.002, "longitude": 74.030},
    {"name": "Rajbag", "taluka": "Canacona", "latitude": 14.995, "longitude": 74.040},
    {"name": "Talpona", "taluka": "Canacona", "latitude": 14.985, "longitude": 74.052},
    {"name": "Galgibaga", "taluka": "Canacona", "latitude": 14.963, "longitude": 74.062},
    {"name": "Khola", "taluka": "Canacona", "latitude": 15.033, "longitude": 74.010},
    {"name": "Loliem", "taluka": "Canacona", "latitude": 14.948, "longitude": 74.078},
    {"name": "Polem", "taluka": "Canacona", "latitude": 14.918, "longitude": 74.088},
]

# --- Landing centers where the field agent collects prices daily by 5 AM ---
LANDING_CENTERS: list[dict] = [
    {"name": "Betul Landing", "kind": "landing", "latitude": 15.140, "longitude": 73.958},
    {"name": "Cutbona Harbor", "kind": "harbor", "latitude": 15.158, "longitude": 73.965},
    {"name": "Margao Fish Market", "kind": "market", "latitude": 15.273, "longitude": 73.958},
    {"name": "Vasco Fish Market", "kind": "market", "latitude": 15.398, "longitude": 73.812},
    {"name": "Colva Beach Landing", "kind": "landing", "latitude": 15.280, "longitude": 73.913},
]

# --- Species catalog: canonical key -> display names + aliases for parsing ---
# Konkani names are the ones actually used at Goan landing centers.
SPECIES: dict[str, dict] = {
    "mackerel": {
        "en": "Mackerel", "kok": "Bangdo", "hi": "Bangda", "mr": "Bangda",
        "aliases": ["mackerel", "bangdo", "bangda", "bangde"],
    },
    "sardine": {
        "en": "Sardine", "kok": "Tarlo", "hi": "Pedvey", "mr": "Tarli",
        "aliases": ["sardine", "sardines", "tarlo", "tarle", "tarli", "pedvey", "pedvo"],
    },
    "pomfret": {
        "en": "Pomfret", "kok": "Pamplet", "hi": "Paplet", "mr": "Paplet",
        "aliases": ["pomfret", "pamplet", "paplet", "pomplet"],
    },
    "kingfish": {
        "en": "Kingfish", "kok": "Visvon", "hi": "Surmai", "mr": "Surmai",
        "aliases": ["kingfish", "visvon", "viswon", "surmai", "seer", "seerfish"],
    },
    "prawns": {
        "en": "Prawns", "kok": "Sungtam", "hi": "Jhinga", "mr": "Kolambi",
        "aliases": ["prawn", "prawns", "sungtam", "sungta", "shrimp", "jhinga", "kolambi"],
    },
    "tuna": {
        "en": "Tuna", "kok": "Kupa", "hi": "Tuna", "mr": "Kupa",
        "aliases": ["tuna", "kupa"],
    },
    "squid": {
        "en": "Squid", "kok": "Manki", "hi": "Squid", "mr": "Makul",
        "aliases": ["squid", "manki", "makul", "calamari"],
    },
    "crab": {
        "en": "Crab", "kok": "Kurlyo", "hi": "Kekda", "mr": "Khekda",
        "aliases": ["crab", "crabs", "kurlyo", "kurli", "kekda", "khekda"],
    },
    "sole": {
        "en": "Sole Fish", "kok": "Lepo", "hi": "Sole", "mr": "Lep",
        "aliases": ["sole", "lepo", "lep"],
    },
    "croaker": {
        "en": "Croaker", "kok": "Dodyaro", "hi": "Ghol", "mr": "Dhoma",
        "aliases": ["croaker", "dodyaro", "ghol", "dhoma"],
    },
}


def resolve_species(raw: str) -> str | None:
    """Map free-text species input (any language) to its canonical key."""
    needle = raw.strip().lower()
    for key, info in SPECIES.items():
        if needle == key or needle in info["aliases"]:
            return key
    return None


def species_display_name(key: str, language: str) -> str:
    info = SPECIES.get(key)
    if not info:
        return key.title()
    return info.get(language) or info["en"]


async def seed_reference_data(session: AsyncSession) -> None:
    """Insert villages and landing centers if the tables are empty (idempotent)."""
    village_count = (await session.execute(select(func.count(Village.id)))).scalar_one()
    if village_count == 0:
        session.add_all(Village(**v) for v in SOUTH_GOA_VILLAGES)

    center_count = (await session.execute(select(func.count(LandingCenter.id)))).scalar_one()
    if center_count == 0:
        session.add_all(LandingCenter(**c) for c in LANDING_CENTERS)

    await session.commit()
