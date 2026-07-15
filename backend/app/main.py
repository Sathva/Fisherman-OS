"""Fisherman OS backend entrypoint.

Run locally:
    uvicorn app.main:app --reload --port 8000
"""

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# Add backend directory to sys.path to support Vercel serverless imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI

from app import __version__
from app.api import admin, health, webhook
from app.config import get_settings
from app.database import get_session_factory, init_db
from app.scheduler import start_scheduler, stop_scheduler
from app.seeds import seed_reference_data

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    await init_db()
    async with get_session_factory()() as session:
        await seed_reference_data(session)
    if settings.enable_scheduler:
        start_scheduler()
    logger.info(
        "Fisherman OS %s up (env=%s, whatsapp=%s, weather=%s)",
        __version__, settings.environment,
        settings.whatsapp_provider, settings.weather_provider,
    )
    yield
    stop_scheduler()


from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Fisherman OS",
    description="WhatsApp intelligence layer for artisanal fishermen — Goa MVP (Phase 1)",
    version=__version__,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(webhook.router)
app.include_router(admin.router)
