"""HTTP API: Gupshup webhook, admin price entry, metrics, SOS ops, auth."""

import httpx
import pytest_asyncio

from app.main import app
from tests.conftest import register_user

PHONE = "919822000001"
ADMIN_HEADERS = {"X-API-Key": "test-key"}


@pytest_asyncio.fixture
async def client(db, wa):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


def gupshup_text_payload(phone: str, text: str) -> dict:
    return {
        "app": "FishermanOS",
        "type": "message",
        "payload": {
            "id": "wamid.test123",
            "type": "text",
            "source": phone,
            "sender": {"phone": phone, "name": "Rajesh"},
            "payload": {"text": text},
        },
    }


async def test_health(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


async def test_webhook_get_verification(client):
    response = await client.get("/webhook/gupshup")
    assert response.status_code == 200


async def test_webhook_message_triggers_onboarding(client, wa):
    response = await client.post("/webhook/gupshup", json=gupshup_text_payload(PHONE, "Hi"))
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "replies": 1}
    assert "Welcome to Fisherman OS" in wa.sent[0][1]


async def test_webhook_location_payload(client, db, wa):
    await register_user(db, wa, PHONE)
    await client.post("/webhook/gupshup", json=gupshup_text_payload(PHONE, "SOS"))
    wa.sent.clear()

    location_payload = {
        "type": "message",
        "payload": {
            "id": "wamid.loc1",
            "type": "location",
            "source": PHONE,
            "sender": {"phone": PHONE},
            "payload": {"latitude": 15.1234, "longitude": 73.9876},
        },
    }
    response = await client.post("/webhook/gupshup", json=location_payload)
    assert response.status_code == 200
    assert any("15.12340" in text for _phone, text in wa.sent)


async def test_webhook_ignores_delivery_receipts(client):
    response = await client.post(
        "/webhook/gupshup", json={"type": "message-event", "payload": {"type": "delivered"}}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ignored"


async def test_admin_requires_api_key(client):
    response = await client.get("/admin/metrics")
    assert response.status_code == 401
    response = await client.get("/admin/metrics", headers={"X-API-Key": "wrong"})
    assert response.status_code == 401


async def test_admin_price_entry_and_listing(client):
    body = {
        "prices": [
            {"landing_center": "Betul", "species": "bangdo", "price_per_kg": 85},
            {"landing_center": "Margao", "species": "mackerel", "price_per_kg": 110},
        ],
        "reported_by_phone": "919800000000",
    }
    response = await client.post("/admin/prices", json=body, headers=ADMIN_HEADERS)
    assert response.status_code == 200
    entries = response.json()
    assert len(entries) == 2
    assert entries[0]["species"] == "mackerel"  # bangdo canonicalized
    assert entries[0]["landing_center"] == "Betul Landing"

    response = await client.get("/admin/prices", headers=ADMIN_HEADERS)
    assert len(response.json()) == 2


async def test_admin_price_entry_unknown_center(client):
    body = {"prices": [{"landing_center": "Mumbai", "species": "mackerel", "price_per_kg": 85}]}
    response = await client.post("/admin/prices", json=body, headers=ADMIN_HEADERS)
    assert response.status_code == 422


async def test_admin_metrics(client, db, wa):
    await register_user(db, wa, PHONE)
    response = await client.get("/admin/metrics", headers=ADMIN_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert data["registered_users"] == 1
    assert data["dau"] == 1  # onboarding messages count as activity
    assert data["registered_target"] == 500


async def test_admin_sos_listing_and_resolve(client, db, wa):
    await register_user(db, wa, PHONE)
    await client.post("/webhook/gupshup", json=gupshup_text_payload(PHONE, "SOS"))

    response = await client.get("/admin/sos", headers=ADMIN_HEADERS)
    alerts = response.json()
    assert len(alerts) == 1
    assert alerts[0]["user_phone"] == PHONE
    assert alerts[0]["village"] == "Betul"

    alert_id = alerts[0]["id"]
    response = await client.post(
        f"/admin/sos/{alert_id}/resolve", json={"notes": "ICG follow-up done"},
        headers=ADMIN_HEADERS,
    )
    assert response.status_code == 200

    response = await client.get("/admin/sos", headers=ADMIN_HEADERS)
    assert response.json() == []


async def test_admin_broadcast(client, db, wa):
    await register_user(db, wa, PHONE)
    wa.sent.clear()
    response = await client.post(
        "/admin/broadcast",
        json={"text": "⚠️ Cyclone alert: all boats return to shore"},
        headers=ADMIN_HEADERS,
    )
    assert response.status_code == 200
    assert response.json()["sent"] == 1
    assert "Cyclone alert" in wa.sent[0][1]


async def test_admin_make_field_agent(client, db, wa):
    await register_user(db, wa, PHONE)
    response = await client.post(
        f"/admin/users/{PHONE}/make-field-agent", headers=ADMIN_HEADERS
    )
    assert response.status_code == 200
    assert response.json()["role"] == "field_agent"


async def test_admin_trigger_morning_push(client, db, wa):
    await register_user(db, wa, PHONE)
    wa.sent.clear()
    response = await client.post("/admin/jobs/morning-push", headers=ADMIN_HEADERS)
    assert response.status_code == 200
    assert response.json()["sent"] == 1
