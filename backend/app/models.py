"""Database models for the Goa MVP.

Schema mirrors the execution plan's Supabase schema task:
users, villages/landing centers, prices, forecasts, SOS alerts, message logs.
"""

from datetime import date, datetime, timezone

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.enums import (
    BoatType,
    Language,
    MessageDirection,
    MessageType,
    OnboardingState,
    PriceSource,
    SafetyLevel,
    SOSStatus,
    SubscriptionStatus,
    UserRole,
    WeatherSource,
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Village(Base):
    """A marine fishing village (South Goa has 41)."""

    __tablename__ = "villages"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    taluka: Mapped[str] = mapped_column(String(50))
    district: Mapped[str] = mapped_column(String(50), default="South Goa")
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    is_active: Mapped[bool] = mapped_column(default=True)

    users: Mapped[list["User"]] = relationship(back_populates="village")


class LandingCenter(Base):
    """A fish landing center / market where prices are collected."""

    __tablename__ = "landing_centers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    kind: Mapped[str] = mapped_column(String(30), default="landing")  # landing | harbor | market
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    is_active: Mapped[bool] = mapped_column(default=True)

    prices: Mapped[list["FishPrice"]] = relationship(back_populates="landing_center")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    phone: Mapped[str] = mapped_column(String(20), unique=True, index=True)  # E.164, no "+"
    name: Mapped[str | None] = mapped_column(String(100))
    village_id: Mapped[int | None] = mapped_column(ForeignKey("villages.id"))
    village_name_raw: Mapped[str | None] = mapped_column(String(100))  # as typed, if unmatched
    boat_type: Mapped[BoatType | None] = mapped_column(Enum(BoatType))
    language: Mapped[Language] = mapped_column(Enum(Language), default=Language.ENGLISH)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.FISHERMAN)
    onboarding_state: Mapped[OnboardingState] = mapped_column(
        Enum(OnboardingState), default=OnboardingState.NEW
    )
    subscribed: Mapped[bool] = mapped_column(default=True)  # morning auto-push opt-in
    subscription_status: Mapped[SubscriptionStatus] = mapped_column(
        Enum(SubscriptionStatus), default=SubscriptionStatus.TRIAL
    )
    trial_started_at: Mapped[datetime | None] = mapped_column(DateTime)
    referred_by_phone: Mapped[str | None] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_active_at: Mapped[datetime | None] = mapped_column(DateTime)

    village: Mapped[Village | None] = relationship(back_populates="users")
    emergency_contacts: Mapped[list["EmergencyContact"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    sos_alerts: Mapped[list["SOSAlert"]] = relationship(back_populates="user")

    @property
    def is_registered(self) -> bool:
        return self.onboarding_state == OnboardingState.REGISTERED


class EmergencyContact(Base):
    __tablename__ = "emergency_contacts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    phone: Mapped[str] = mapped_column(String(20))

    user: Mapped[User] = relationship(back_populates="emergency_contacts")


class FishPrice(Base):
    """One species' price at one landing center on one day (latest entry wins)."""

    __tablename__ = "fish_prices"
    __table_args__ = (
        UniqueConstraint("landing_center_id", "species", "price_date", name="uq_price_per_day"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    landing_center_id: Mapped[int] = mapped_column(ForeignKey("landing_centers.id"), index=True)
    species: Mapped[str] = mapped_column(String(50), index=True)  # canonical english key
    price_per_kg: Mapped[float] = mapped_column(Float)
    price_date: Mapped[date] = mapped_column(Date, index=True)
    source: Mapped[PriceSource] = mapped_column(Enum(PriceSource), default=PriceSource.FIELD_AGENT)
    reported_by_phone: Mapped[str | None] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    landing_center: Mapped[LandingCenter] = relationship(back_populates="prices")


class WeatherForecast(Base):
    """A day's sea-state forecast for one village."""

    __tablename__ = "weather_forecasts"
    __table_args__ = (
        UniqueConstraint("village_id", "forecast_date", name="uq_forecast_per_day"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    village_id: Mapped[int] = mapped_column(ForeignKey("villages.id"), index=True)
    forecast_date: Mapped[date] = mapped_column(Date, index=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    wind_speed_kmh: Mapped[float] = mapped_column(Float)
    wind_direction: Mapped[str] = mapped_column(String(5))  # e.g. "SW"
    wave_height_m: Mapped[float] = mapped_column(Float)
    rain_probability: Mapped[int] = mapped_column(Integer)  # 0-100
    rain_timing: Mapped[str | None] = mapped_column(String(50))  # e.g. "after 2PM"
    sea_temp_c: Mapped[float | None] = mapped_column(Float)
    safety_level: Mapped[SafetyLevel] = mapped_column(Enum(SafetyLevel))
    advisory: Mapped[str | None] = mapped_column(Text)  # e.g. "Return before 2PM — squall risk"
    hourly_levels: Mapped[str] = mapped_column(String(60), default="")  # csv of next-6h levels
    source: Mapped[WeatherSource] = mapped_column(Enum(WeatherSource))

    village: Mapped[Village] = relationship()

    def hourly_level_list(self) -> list[SafetyLevel]:
        return [SafetyLevel(v) for v in self.hourly_levels.split(",") if v]


class SOSAlert(Base):
    __tablename__ = "sos_alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[SOSStatus] = mapped_column(Enum(SOSStatus), default=SOSStatus.ACTIVE, index=True)
    activated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_latitude: Mapped[float | None] = mapped_column(Float)
    last_longitude: Mapped[float | None] = mapped_column(Float)
    last_location_at: Mapped[datetime | None] = mapped_column(DateTime)
    contacts_notified: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str | None] = mapped_column(Text)

    user: Mapped[User] = relationship(back_populates="sos_alerts")
    pings: Mapped[list["SOSLocationPing"]] = relationship(
        back_populates="alert", cascade="all, delete-orphan"
    )


class SOSLocationPing(Base):
    __tablename__ = "sos_location_pings"

    id: Mapped[int] = mapped_column(primary_key=True)
    alert_id: Mapped[int] = mapped_column(ForeignKey("sos_alerts.id"), index=True)
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    alert: Mapped[SOSAlert] = relationship(back_populates="pings")


class MessageLog(Base):
    """Every inbound/outbound WhatsApp message — powers DAU/engagement KPIs."""

    __tablename__ = "message_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    phone: Mapped[str] = mapped_column(String(20), index=True)
    direction: Mapped[MessageDirection] = mapped_column(Enum(MessageDirection))
    message_type: Mapped[MessageType] = mapped_column(Enum(MessageType), default=MessageType.GENERIC)
    content: Mapped[str] = mapped_column(Text)
    provider_message_id: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
