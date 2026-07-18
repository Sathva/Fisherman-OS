"""Messenger facade: pick the configured WhatsApp provider, send, and log.

All outbound traffic goes through send_message() so every message lands in
message_logs (KPI source of truth).
"""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.enums import MessageDirection, MessageType
from app.providers.whatsapp.base import SendResult, WhatsAppProvider
from app.providers.whatsapp.console import ConsoleWhatsAppProvider
from app.providers.whatsapp.gupshup import GupshupWhatsAppProvider
from app.services.message_log import log_message

logger = logging.getLogger(__name__)

_provider: WhatsAppProvider | None = None


def get_provider() -> WhatsAppProvider:
    global _provider
    if _provider is None:
        name = get_settings().whatsapp_provider
        if name == "gupshup":
            _provider = GupshupWhatsAppProvider()
        elif name == "console":
            _provider = ConsoleWhatsAppProvider()
        else:
            raise ValueError(f"Unknown whatsapp_provider: {name!r}")
    return _provider


def set_provider(provider: WhatsAppProvider | None) -> None:
    """Override the provider (tests inject a ConsoleWhatsAppProvider)."""
    global _provider
    _provider = provider


async def send_message(
    session: AsyncSession,
    *,
    phone: str,
    text: str,
    user_id: int | None = None,
    message_type: MessageType = MessageType.GENERIC,
    options: list[str] | None = None,
) -> SendResult:
    """Send `text`; pass `options` to attach tappable quick-reply buttons."""
    provider = get_provider()
    if options:
        result = await provider.send_quick_replies(phone, text, options)
    else:
        result = await provider.send_text(phone, text)
    if not result.ok:
        logger.error("Send to %s failed: %s", phone, result.error)
    # Outbound messages are not logged to DB — only inbound messages are stored
    return result
