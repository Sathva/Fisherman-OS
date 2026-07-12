import os

# Must be set before any app import touches get_settings().
os.environ.setdefault("WHATSAPP_PROVIDER", "console")
os.environ.setdefault("WEATHER_PROVIDER", "synthetic")
os.environ.setdefault("ENABLE_SCHEDULER", "false")
os.environ.setdefault("ADMIN_API_KEY", "test-key")

import pytest_asyncio  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.database import get_engine, get_session_factory, init_db, reset_engine  # noqa: E402
from app.providers.whatsapp.base import InboundMessage  # noqa: E402
from app.providers.whatsapp.console import ConsoleWhatsAppProvider  # noqa: E402
from app.seeds import seed_reference_data  # noqa: E402
from app.services.messenger import set_provider  # noqa: E402


@pytest_asyncio.fixture
async def db(tmp_path, monkeypatch):
    """Fresh SQLite database (file-backed, per-test) with reference seeds."""
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path}/test.db")
    monkeypatch.setenv("WHATSAPP_PROVIDER", "console")
    monkeypatch.setenv("WEATHER_PROVIDER", "synthetic")
    monkeypatch.setenv("ENABLE_SCHEDULER", "false")
    monkeypatch.setenv("ADMIN_API_KEY", "test-key")
    get_settings.cache_clear()
    reset_engine()

    await init_db()
    async with get_session_factory()() as session:
        await seed_reference_data(session)

    async with get_session_factory()() as session:
        yield session

    await get_engine().dispose()
    reset_engine()
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def wa():
    """Console WhatsApp provider capturing everything 'sent'."""
    provider = ConsoleWhatsAppProvider()
    set_provider(provider)
    yield provider
    set_provider(None)


def make_inbound(phone: str = "919822000001", text: str = "",
                 latitude: float | None = None, longitude: float | None = None) -> InboundMessage:
    return InboundMessage(phone=phone, text=text, latitude=latitude, longitude=longitude)


async def run_conversation(db, wa, phone: str, *messages: str) -> list[str]:
    """Send messages in order; return all replies (to anyone) as texts."""
    from app.bot.router import handle_inbound

    for message in messages:
        await handle_inbound(db, make_inbound(phone=phone, text=message))
    return [text for _phone, text in wa.sent]


async def register_user(db, wa, phone: str = "919822000001", name: str = "Rajesh",
                        village: str = "Betul", language: str = "1", boat: str = "2"):
    """Complete the full onboarding flow and return the registered user."""
    from app.services.user_service import get_user_by_phone

    await run_conversation(db, wa, phone, "Hi", language, name, village, boat)
    user = await get_user_by_phone(db, phone)
    assert user is not None and user.is_registered
    return user
