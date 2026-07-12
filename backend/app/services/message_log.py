"""Message logging — every inbound/outbound message is recorded.

This powers the KPI dashboard (DAU = distinct users messaging in a day,
forecast delivery counts, etc.) and gives ops an audit trail.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import MessageDirection, MessageType
from app.models import MessageLog


async def log_message(
    session: AsyncSession,
    *,
    phone: str,
    direction: MessageDirection,
    content: str,
    user_id: int | None = None,
    message_type: MessageType = MessageType.GENERIC,
    provider_message_id: str | None = None,
    commit: bool = True,
) -> MessageLog:
    entry = MessageLog(
        phone=phone,
        direction=direction,
        content=content,
        user_id=user_id,
        message_type=message_type,
        provider_message_id=provider_message_id,
    )
    session.add(entry)
    if commit:
        await session.commit()
    return entry
