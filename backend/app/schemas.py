"""Pydantic request/response schemas for the HTTP API."""

from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator

from app.enums import PriceSource


class PriceEntry(BaseModel):
    """One price report from a field agent or ingestion job."""

    landing_center: str = Field(examples=["Betul"])
    species: str = Field(examples=["mackerel", "bangdo"])
    price_per_kg: float = Field(gt=0, le=100000)
    price_date: date | None = None  # defaults to today (IST) server-side
    source: PriceSource = PriceSource.FIELD_AGENT

    @field_validator("landing_center", "species")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value.strip()


class PriceBulkRequest(BaseModel):
    prices: list[PriceEntry] = Field(min_length=1, max_length=200)
    reported_by_phone: str | None = None


class PriceResponse(BaseModel):
    landing_center: str
    species: str
    price_per_kg: float
    price_date: date
    source: PriceSource


class BroadcastRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    village: str | None = None  # limit to one village; None = all subscribed users


class SOSAlertResponse(BaseModel):
    id: int
    user_phone: str
    user_name: str | None
    village: str | None
    status: str
    activated_at: datetime
    last_latitude: float | None
    last_longitude: float | None
    last_location_at: datetime | None
    maps_link: str | None


class ResolveSOSRequest(BaseModel):
    notes: str | None = None
