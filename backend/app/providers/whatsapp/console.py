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
        # Quick-reply options per index into `sent` (simulator renders these
        # as tappable buttons). Kept out of `sent` so tests that unpack
        # (phone, text) pairs keep working.
        self.options_by_index: dict[int, list[str]] = {}
        self._ids = itertools.count(1)

    async def send_text(self, to_phone: str, text: str) -> SendResult:
        self.sent.append((to_phone, text))
        logger.info("[console-wa] -> %s\n%s", to_phone, text)
        return SendResult(ok=True, provider_message_id=f"console-{next(self._ids)}")

    async def send_quick_replies(
        self, to_phone: str, text: str, options: list[str]
    ) -> SendResult:
        self.options_by_index[len(self.sent)] = list(options)
        self.sent.append((to_phone, text))
        logger.info("[console-wa] -> %s\n%s\nbuttons: %s", to_phone, text, options)
        return SendResult(ok=True, provider_message_id=f"console-{next(self._ids)}")
