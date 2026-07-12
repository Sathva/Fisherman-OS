"""Inbound WhatsApp webhook (Gupshup).

Configure this URL in the Gupshup app dashboard:
    POST https://<host>/webhook/gupshup
Gupshup retries on non-200, so we always ack with 200 and log failures —
a poison message must never wedge the queue.
"""

import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.router import handle_inbound
from app.database import get_db
from app.providers.whatsapp.gupshup import parse_webhook

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook", tags=["webhook"])


@router.get("/gupshup")
async def verify() -> dict:
    """Gupshup pings the callback URL with GET during setup."""
    return {"status": "ok"}


@router.post("/gupshup")
async def gupshup_webhook(request: Request, db: AsyncSession = Depends(get_db)) -> dict:
    try:
        payload = await request.json()
    except Exception:
        logger.warning("Webhook received non-JSON body")
        return {"status": "ignored"}

    inbound = parse_webhook(payload)
    if inbound is None:
        return {"status": "ignored"}  # delivery receipts, unsupported types, etc.

    try:
        replies = await handle_inbound(db, inbound)
        return {"status": "ok", "replies": len(replies)}
    except Exception:
        logger.exception("Failed to handle inbound message from %s", inbound.phone)
        return {"status": "error"}
