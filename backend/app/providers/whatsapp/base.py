"""WhatsApp provider interface (BSP-agnostic).

The MVP ships with Gupshup; the interface keeps a move to Wati/Meta Cloud API
a one-file change (execution plan risk: "WhatsApp API cost scaling —
negotiate with BSPs").
"""

import abc
from dataclasses import dataclass


@dataclass
class SendResult:
    ok: bool
    provider_message_id: str | None = None
    error: str | None = None


class WhatsAppProvider(abc.ABC):
    @abc.abstractmethod
    async def send_text(self, to_phone: str, text: str) -> SendResult:
        """Send a plain text message to `to_phone` (digits-only E.164)."""

    async def send_quick_replies(
        self, to_phone: str, text: str, options: list[str]
    ) -> SendResult:
        """Send `text` with tappable quick-reply buttons (max 3, titles ≤ 20
        chars — WhatsApp limits). Tapping a button sends its title back as an
        inbound message. Providers without button support fall back to
        appending the options as text."""
        suffix = "\n\n" + "\n".join(f"👉 {option}" for option in options)
        return await self.send_text(to_phone, text + suffix)


@dataclass
class InboundMessage:
    """Normalized inbound WhatsApp message."""

    phone: str                       # sender, digits-only E.164
    text: str = ""                   # empty for pure location messages
    latitude: float | None = None    # set for location shares
    longitude: float | None = None
    sender_name: str | None = None   # WhatsApp profile name, if provided
    provider_message_id: str | None = None

    @property
    def has_location(self) -> bool:
        return self.latitude is not None and self.longitude is not None
