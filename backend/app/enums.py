"""Shared enumerations used across models, services and the bot."""

import enum


class Language(str, enum.Enum):
    ENGLISH = "en"
    KONKANI = "kok"
    HINDI = "hi"
    MARATHI = "mr"


class BoatType(str, enum.Enum):
    CANOE = "canoe"                      # non-motorized dugout / canoe
    MOTORIZED_CANOE = "motorized_canoe"  # canoe with outboard motor (most common in Goa)
    RAMPON = "rampon"                    # traditional Goan shore-seine
    TRAWLER = "trawler"
    OTHER = "other"


class UserRole(str, enum.Enum):
    FISHERMAN = "fisherman"
    FIELD_AGENT = "field_agent"  # can submit market prices via WhatsApp / admin API
    ADMIN = "admin"


class OnboardingState(str, enum.Enum):
    NEW = "new"
    AWAITING_LANGUAGE = "awaiting_language"
    AWAITING_NAME = "awaiting_name"
    AWAITING_VILLAGE = "awaiting_village"
    AWAITING_BOAT_TYPE = "awaiting_boat_type"
    REGISTERED = "registered"
    # Post-registration conversational state: user asked for prices and we're
    # waiting for them to say which fish they want.
    AWAITING_FISH_TYPE = "awaiting_fish_type"


class SubscriptionStatus(str, enum.Enum):
    TRIAL = "trial"
    ACTIVE = "active"    # paying ₹99/month
    LAPSED = "lapsed"


class SafetyLevel(str, enum.Enum):
    SAFE = "green"
    CAUTION = "yellow"
    DANGER = "red"

    @property
    def emoji(self) -> str:
        return {"green": "🟢", "yellow": "🟡", "red": "🔴"}[self.value]


class SOSStatus(str, enum.Enum):
    ACTIVE = "active"
    CANCELLED = "cancelled"  # cancelled by the fisherman ("CANCEL")
    RESOLVED = "resolved"    # closed by ops / Coast Guard follow-up


class MessageDirection(str, enum.Enum):
    INBOUND = "in"
    OUTBOUND = "out"


class MessageType(str, enum.Enum):
    MORNING_FORECAST = "morning_forecast"
    DETAILED_FORECAST = "detailed_forecast"
    PRICE_DIGEST = "price_digest"
    SOS = "sos"
    ONBOARDING = "onboarding"
    HELP = "help"
    GENERIC = "generic"


class PriceSource(str, enum.Enum):
    FIELD_AGENT = "field_agent"
    FMPIS = "fmpis"
    CMFRI = "cmfri"


class WeatherSource(str, enum.Enum):
    INCOIS = "incois"
    OPENWEATHERMAP = "openweathermap"
    SYNTHETIC = "synthetic"
    OPENMETEO = "openmeteo"
