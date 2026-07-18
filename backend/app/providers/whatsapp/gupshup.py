"""Gupshup WhatsApp Business API provider.

Docs: https://docs.gupshup.io/docs/whatsapp-api-documentation
Outbound: POST /wa/api/v1/msg (form-encoded, apikey header).
Inbound: Gupshup POSTs JSON webhooks; parse_webhook() normalizes the
"message" event's text and location payloads into InboundMessage.
"""

import json
import logging

import httpx

from app.config import get_settings
from app.providers.whatsapp.base import InboundMessage, SendResult, WhatsAppProvider

logger = logging.getLogger(__name__)


class GupshupWhatsAppProvider(WhatsAppProvider):
    def __init__(self, client: httpx.AsyncClient | None = None):
        self._client = client

    async def send_text(self, to_phone: str, text: str) -> SendResult:
        return await self._send(to_phone, {"type": "text", "text": text})

    async def send_quick_replies(
        self, to_phone: str, text: str, options: list[str]
    ) -> SendResult:
        # WhatsApp interactive quick-reply: max 3 buttons, titles ≤ 20 chars.
        # Tapping one delivers a button_reply webhook whose title we treat as
        # inbound text (see parse_webhook).
        message = {
            "type": "quick_reply",
            "content": {"type": "text", "text": text},
            "options": [{"type": "text", "title": title[:20]} for title in options[:3]],
        }
        return await self._send(to_phone, message)

    async def _send(self, to_phone: str, message: dict) -> SendResult:
        settings = get_settings()
        if not settings.gupshup_api_key or not settings.gupshup_source_number:
            return SendResult(ok=False, error="Gupshup credentials not configured")

        data = {
            "channel": "whatsapp",
            "source": settings.gupshup_source_number,
            "destination": to_phone,
            "src.name": settings.gupshup_app_name,
            "message": json.dumps(message),
        }
        headers = {
            "apikey": settings.gupshup_api_key,
            "Content-Type": "application/x-www-form-urlencoded",
        }
        try:
            if self._client is not None:
                response = await self._client.post(
                    settings.gupshup_api_url, data=data, headers=headers
                )
            else:
                async with httpx.AsyncClient(timeout=15) as client:
                    response = await client.post(
                        settings.gupshup_api_url, data=data, headers=headers
                    )
            response.raise_for_status()
            payload = response.json()
            return SendResult(ok=True, provider_message_id=payload.get("messageId"))
        except (httpx.HTTPError, ValueError) as exc:
            logger.error("Gupshup send to %s failed: %s", to_phone, exc)
            return SendResult(ok=False, error=str(exc))


def parse_webhook(payload: dict) -> InboundMessage | None:
    """Normalize a Gupshup inbound webhook into an InboundMessage.

    Returns None for non-message events (delivery receipts, opt-ins, ...).
    Expected shape:
        {"type": "message",
         "payload": {"id": "...", "type": "text"|"location",
                     "source": "91982...", "sender": {"phone": "...", "name": "..."},
                     "payload": {"text": "Hi"} | {"latitude": .., "longitude": ..}}}
    """
    if payload.get("type") != "message":
        return None
    outer = payload.get("payload") or {}
    sender = outer.get("sender") or {}
    phone = outer.get("source") or sender.get("phone")
    if not phone:
        return None

    inner = outer.get("payload") or {}
    message_type = outer.get("type", "text")

    text = ""
    latitude = longitude = None
    if message_type == "text":
        text = inner.get("text", "") or ""
    elif message_type == "location":
        try:
            latitude = float(inner["latitude"])
            longitude = float(inner["longitude"])
        except (KeyError, TypeError, ValueError):
            return None
    elif message_type == "button_reply":
        text = inner.get("title", "") or ""
    else:
        # Voice notes / images arrive here in Phase 2 (Bhashini ASR).
        return None

    return InboundMessage(
        phone=str(phone),
        text=text,
        latitude=latitude,
        longitude=longitude,
        sender_name=sender.get("name"),
        provider_message_id=outer.get("id"),
    )
