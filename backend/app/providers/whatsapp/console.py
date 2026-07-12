"""Console provider — logs outbound messages instead of sending.

Used in development and tests; also records messages in memory so tests can
assert on what "went out".
"""

import itertools
import logging

from app.providers.whatsapp.base import SendResult, WhatsAppProvider

logger = logging.getLogger(__name__)


class ConsoleWhatsAppProvider(WhatsAppProvider):
    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []  # (phone, text)
        self._ids = itertools.count(1)

    async def send_text(self, to_phone: str, text: str) -> SendResult:
        self.sent.append((to_phone, text))
        logger.info("[console-wa] -> %s\n%s", to_phone, text)
        return SendResult(ok=True, provider_message_id=f"console-{next(self._ids)}")
