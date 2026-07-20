"""LLM fallback: intent routing, grounded answers, declines, emergency
confirmation, and every failure mode degrading to the static help reply."""

import json

import httpx
import pytest

from app.bot.router import handle_inbound
from app.config import get_settings
from app.enums import SOSStatus
from app.services import llm_service
from app.services.llm_service import LLMUnavailable, _parse_decision

from .conftest import make_inbound, register_user

PHONE = "919822000001"


@pytest.fixture
def llm_on(monkeypatch):
    """Enable the LLM path with a dummy key (network is always faked)."""
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def fake_llm(monkeypatch, intent: str, reply: str = ""):
    """Stub the Groq HTTP call to return a fixed decision."""
    calls: list[list[dict]] = []

    async def _fake_post_chat(messages):
        calls.append(messages)
        return json.dumps({"intent": intent, "reply": reply})

    monkeypatch.setattr(llm_service, "_post_chat", _fake_post_chat)
    return calls


# --- Routing intents to existing structured handlers -------------------------


async def test_forecast_intent_routes_to_detailed_forecast(db, wa, llm_on, monkeypatch):
    await register_user(db, wa, PHONE)
    fake_llm(monkeypatch, "forecast")
    wa.sent.clear()

    await handle_inbound(db, make_inbound(phone=PHONE, text="aaj samudrat jau shakto ka?"))
    assert len(wa.sent) == 1
    assert "Fisherman OS" in wa.sent[0][1]
    assert "Source:" in wa.sent[0][1]


async def test_prices_intent_routes_to_price_digest(db, wa, llm_on, monkeypatch):
    await register_user(db, wa, PHONE)
    fake_llm(monkeypatch, "prices")
    wa.sent.clear()

    await handle_inbound(db, make_inbound(phone=PHONE, text="masli cho dor kitlo?"))
    assert len(wa.sent) == 1  # "no prices yet" or digest — either way one reply


async def test_stop_intent_unsubscribes(db, wa, llm_on, monkeypatch):
    user = await register_user(db, wa, PHONE)
    fake_llm(monkeypatch, "stop")
    wa.sent.clear()

    await handle_inbound(db, make_inbound(phone=PHONE, text="mala he messages nako aahet"))
    await db.refresh(user)
    assert user.subscribed is False


# --- Direct answers and declines ---------------------------------------------


async def test_answer_intent_sends_llm_reply(db, wa, llm_on, monkeypatch):
    await register_user(db, wa, PHONE)
    calls = fake_llm(monkeypatch, "answer", "🎣 4 वाजता समुद्र शांत आहे, जाऊ शकता.")
    wa.sent.clear()

    await handle_inbound(db, make_inbound(phone=PHONE, text="4 vajta jane thik hai kya?"))
    assert wa.sent == [(PHONE, "🎣 4 वाजता समुद्र शांत आहे, जाऊ शकता.")]

    # The prompt carried live grounding data and the raw user message.
    system_prompt = calls[0][0]["content"]
    assert "Sea forecast" in system_prompt
    assert "never invent" in system_prompt.lower() or "Never invent" in system_prompt
    assert "4 vajta jane thik hai kya?" in calls[0][1]["content"]


async def test_off_topic_intent_sends_decline(db, wa, llm_on, monkeypatch):
    await register_user(db, wa, PHONE)
    decline = "Sorry, I can only help with fishing, weather, prices and SOS."
    fake_llm(monkeypatch, "off_topic", decline)
    wa.sent.clear()

    await handle_inbound(db, make_inbound(phone=PHONE, text="write me a poem about cricket"))
    assert wa.sent == [(PHONE, decline)]


# --- Emergency confirmation ---------------------------------------------------


async def test_emergency_intent_sends_one_tap_confirmation(db, wa, llm_on, monkeypatch):
    from app.services import sos_service

    await register_user(db, wa, PHONE)
    fake_llm(monkeypatch, "emergency")
    wa.sent.clear()
    wa.options_by_index.clear()

    await handle_inbound(db, make_inbound(phone=PHONE, text="majhi hod budte aahe"))
    assert len(wa.sent) == 1
    assert "SOS" in wa.sent[0][1]
    assert wa.options_by_index.get(0) == ["SOS"]  # one-tap button attached

    # No alert yet — confirmation only.
    user_alerts = await sos_service.all_active_alerts(db)
    assert user_alerts == []

    # Tapping the button sends "SOS" → the normal keyword path activates.
    await handle_inbound(db, make_inbound(phone=PHONE, text="SOS"))
    user_alerts = await sos_service.all_active_alerts(db)
    assert len(user_alerts) == 1
    assert user_alerts[0].status == SOSStatus.ACTIVE


# --- Failure modes: never go silent -------------------------------------------


async def test_llm_disabled_falls_back_to_help(db, wa, monkeypatch):
    await register_user(db, wa, PHONE)  # no GROQ_API_KEY set
    wa.sent.clear()

    await handle_inbound(db, make_inbound(phone=PHONE, text="random question here"))
    assert len(wa.sent) == 1
    assert "HELP" in wa.sent[0][1]


async def test_groq_http_error_falls_back_to_help(db, wa, llm_on, monkeypatch):
    await register_user(db, wa, PHONE)

    async def _boom(messages):
        raise httpx.ConnectError("groq down")

    monkeypatch.setattr(llm_service, "_post_chat", _boom)
    wa.sent.clear()

    await handle_inbound(db, make_inbound(phone=PHONE, text="kal paus padel ka?"))
    assert len(wa.sent) == 1
    assert "HELP" in wa.sent[0][1]


async def test_garbage_llm_output_falls_back_to_help(db, wa, llm_on, monkeypatch):
    await register_user(db, wa, PHONE)

    async def _garbage(messages):
        return "I am not JSON at all"

    monkeypatch.setattr(llm_service, "_post_chat", _garbage)
    wa.sent.clear()

    await handle_inbound(db, make_inbound(phone=PHONE, text="kal paus padel ka?"))
    assert len(wa.sent) == 1
    assert "HELP" in wa.sent[0][1]


async def test_rate_limit_blocks_llm(db, wa, llm_on, monkeypatch):
    monkeypatch.setenv("LLM_RATE_LIMIT_PER_HOUR", "2")
    get_settings.cache_clear()
    await register_user(db, wa, PHONE)  # onboarding already logs > 2 inbound

    called = fake_llm(monkeypatch, "answer", "should never be sent")
    wa.sent.clear()

    await handle_inbound(db, make_inbound(phone=PHONE, text="question after limit"))
    assert called == []  # LLM never invoked
    assert len(wa.sent) == 1
    assert "HELP" in wa.sent[0][1]


# --- Village name spell-correction ---------------------------------------------


async def test_misspelled_village_corrected_via_llm(db, wa, llm_on, monkeypatch):
    async def _fake_post_chat(messages):
        return json.dumps({"village": "Cavelossim"})

    monkeypatch.setattr(llm_service, "_post_chat", _fake_post_chat)

    user = await register_user(db, wa, PHONE, village="Kavelosim")
    assert user.village is not None
    assert user.village.name == "Cavelossim"


async def test_village_correction_null_falls_back_to_default(db, wa, llm_on, monkeypatch):
    async def _fake_post_chat(messages):
        return json.dumps({"village": None})

    monkeypatch.setattr(llm_service, "_post_chat", _fake_post_chat)

    user = await register_user(db, wa, PHONE, village="Xyzville")
    assert user.village is not None
    assert user.village.name == "Betul"  # default fallback village


async def test_village_correction_rejects_invented_names(db, wa, llm_on, monkeypatch):
    async def _fake_post_chat(messages):
        return json.dumps({"village": "Atlantis"})  # not in the seed list

    monkeypatch.setattr(llm_service, "_post_chat", _fake_post_chat)

    user = await register_user(db, wa, PHONE, village="Atlantis")
    assert user.village is not None
    assert user.village.name == "Betul"  # invented name ignored -> fallback


async def test_village_correction_survives_llm_failure(db, wa, llm_on, monkeypatch):
    async def _boom(messages):
        raise httpx.ConnectError("groq down")

    monkeypatch.setattr(llm_service, "_post_chat", _boom)

    user = await register_user(db, wa, PHONE, village="Kavelosim")
    assert user.village is not None
    assert user.village.name == "Betul"  # degraded to the old fallback


# --- Output parsing robustness -------------------------------------------------


def test_parse_decision_accepts_fenced_json():
    decision = _parse_decision('```json\n{"intent": "answer", "reply": "hi"}\n```')
    assert decision.intent == "answer"
    assert decision.reply == "hi"


def test_parse_decision_unknown_intent_with_reply_becomes_answer():
    decision = _parse_decision('{"intent": "banter", "reply": "some text"}')
    assert decision.intent == "answer"


def test_parse_decision_rejects_empty_answer():
    with pytest.raises(LLMUnavailable):
        _parse_decision('{"intent": "answer", "reply": ""}')


def test_parse_decision_clamps_long_reply():
    decision = _parse_decision(json.dumps({"intent": "answer", "reply": "x" * 5000}))
    assert len(decision.reply) <= 900
