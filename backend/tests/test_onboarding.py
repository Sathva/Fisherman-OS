"""Onboarding flow: Hi -> language -> name -> village -> boat -> first forecast."""

from app.bot.router import handle_inbound
from app.enums import BoatType, Language, OnboardingState
from app.services.user_service import get_user_by_phone
from tests.conftest import make_inbound, register_user, run_conversation

PHONE = "919822000001"


async def test_hi_starts_language_menu(db, wa):
    replies = await run_conversation(db, wa, PHONE, "Hi")
    assert len(replies) == 1
    assert "Welcome to Fisherman OS" in replies[0]
    assert "1️⃣ English" in replies[0]

    user = await get_user_by_phone(db, PHONE)
    assert user.onboarding_state == OnboardingState.AWAITING_LANGUAGE


async def test_full_onboarding_sends_first_forecast(db, wa):
    await run_conversation(db, wa, PHONE, "Hi", "1", "Rajesh", "Betul", "2")

    user = await get_user_by_phone(db, PHONE)
    assert user.is_registered
    assert user.name == "Rajesh"
    assert user.language == Language.ENGLISH
    assert user.boat_type == BoatType.MOTORIZED_CANOE
    assert user.village is not None and user.village.name == "Betul"

    texts = [text for _phone, text in wa.sent]
    assert any("You're registered, Rajesh" in t for t in texts)
    # Execution plan: first forecast arrives immediately after registration.
    assert any("Fisherman OS — Betul" in t and "Next 6 hours" in t for t in texts)


async def test_onboarding_in_konkani(db, wa):
    replies = await run_conversation(db, wa, PHONE, "Hi", "2")
    assert "Tujem nanv kitem?" in replies[-1]  # "What is your name?" in Konkani

    user = await get_user_by_phone(db, PHONE)
    assert user.language == Language.KONKANI


async def test_invalid_language_reprompts(db, wa):
    replies = await run_conversation(db, wa, PHONE, "Hi", "9")
    assert "1 (English)" in replies[-1]
    user = await get_user_by_phone(db, PHONE)
    assert user.onboarding_state == OnboardingState.AWAITING_LANGUAGE


async def test_unknown_village_falls_back_to_betul(db, wa):
    replies = await run_conversation(db, wa, PHONE, "Hi", "1", "Suresh", "Atlantis")
    assert any("Betul" in r and "couldn't find" in r for r in replies)
    user = await get_user_by_phone(db, PHONE)
    assert user.village_name_raw == "Atlantis"
    assert user.village.name == "Betul"


async def test_village_fuzzy_match(db, wa):
    await run_conversation(db, wa, PHONE, "Hi", "1", "Ravi", "palolem", "1")
    user = await get_user_by_phone(db, PHONE)
    assert user.village.name == "Palolem"


async def test_invalid_boat_type_reprompts(db, wa):
    replies = await run_conversation(db, wa, PHONE, "Hi", "1", "Rajesh", "Betul", "8")
    assert "1 to 5" in replies[-1]
    user = await get_user_by_phone(db, PHONE)
    assert user.onboarding_state == OnboardingState.AWAITING_BOAT_TYPE


async def test_registered_user_can_change_language(db, wa):
    await register_user(db, wa, PHONE)
    await handle_inbound(db, make_inbound(phone=PHONE, text="LANG"))
    await handle_inbound(db, make_inbound(phone=PHONE, text="3"))

    user = await get_user_by_phone(db, PHONE)
    assert user.language == Language.HINDI
    assert user.is_registered  # language change must not restart onboarding
    assert "हिंदी" in wa.sent[-1][1]


async def test_new_user_sos_works_before_registration(db, wa):
    """A fisherman in distress mid-onboarding still gets the SOS flow."""
    replies = await run_conversation(db, wa, PHONE, "SOS")
    assert any("EMERGENCY" in r for r in replies)
    assert any("1554" in r for r in replies)
