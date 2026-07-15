"""Application settings, loaded from environment variables / .env file."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- General -----------------------------------------------------------
    app_name: str = "Fisherman OS"
    environment: str = "development"  # development | staging | production
    timezone: str = "Asia/Kolkata"

    # --- Database ----------------------------------------------------------
    # Local dev defaults to SQLite; production points at Supabase Postgres,
    # e.g. postgresql+asyncpg://postgres:<password>@db.<ref>.supabase.co:5432/postgres
    database_url: str = "sqlite+aiosqlite:///./fisherman_os.db"

    # --- WhatsApp (BSP) -----------------------------------------------------
    # "console" logs outbound messages instead of sending (dev / tests).
    # "gupshup" sends through the Gupshup WhatsApp Business API.
    whatsapp_provider: str = "console"
    gupshup_api_key: str = ""
    gupshup_app_name: str = ""
    gupshup_source_number: str = ""  # the bot's WhatsApp number, e.g. 917700012345
    gupshup_api_url: str = "https://api.gupshup.io/wa/api/v1/msg"

    # --- Weather providers ---------------------------------------------------
    # "auto" tries INCOIS, then OpenWeatherMap, then the synthetic provider.
    weather_provider: str = "auto"  # auto | incois | openweathermap | synthetic
    incois_rss_url: str = "https://tools.incois.gov.in/osf/rss/goa.xml"
    openweather_api_key: str = ""
    openweather_api_url: str = "https://api.openweathermap.org/data/2.5/forecast"

    # --- Scheduler -----------------------------------------------------------
    enable_scheduler: bool = True
    morning_forecast_hour: int = 3
    morning_forecast_minute: int = 30
    price_push_hour: int = 5
    price_push_minute: int = 0
    price_fetch_hour: int = 4  # FMPIS/CMFRI ingestion attempt before the price push
    price_fetch_minute: int = 30
    sos_ping_interval_minutes: int = 5

    # --- SOS -----------------------------------------------------------------
    coast_guard_number: str = "1554"  # Indian Coast Guard maritime emergency

    # --- Admin / field-agent API --------------------------------------------
    admin_api_key: str = "change-me"

    # --- Business ------------------------------------------------------------
    trial_days: int = 30
    subscription_price_inr: int = 99


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    import os
    if "VERCEL" in os.environ:
        # Avoid running background scheduler threads in serverless execution context
        settings.enable_scheduler = False
        # Redirect default SQLite location to /tmp to prevent read-only filesystem errors
        if settings.database_url == "sqlite+aiosqlite:///./fisherman_os.db":
            settings.database_url = "sqlite+aiosqlite:////tmp/fisherman_os.db"
    return settings
