"""Pydantic models for Commerce Analytics events and aggregates."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class EventType(StrEnum):
    PAGE_VIEW = "PAGE_VIEW"
    PRODUCT_VIEW = "PRODUCT_VIEW"
    ADD_TO_CART = "ADD_TO_CART"
    REMOVE_FROM_CART = "REMOVE_FROM_CART"
    CHECKOUT_STARTED = "CHECKOUT_STARTED"
    CHECKOUT_COMPLETED = "CHECKOUT_COMPLETED"
    SEARCH = "SEARCH"


class ClickEvent(BaseModel):
    """Inbound clickstream event from Kafka."""

    model_config = ConfigDict(str_strip_whitespace=True)

    event_id: str = Field(..., max_length=64)
    session_id: str = Field(..., max_length=64)
    customer_id: str | None = Field(None, max_length=64)
    event_type: EventType
    page_url: str | None = Field(None, max_length=512)
    product_id: str | None = Field(None, max_length=64)
    referrer: str | None = Field(None, max_length=512)
    user_agent: str | None = Field(None, max_length=512)
    ip_address: str | None = Field(None, max_length=64)
    timestamp: datetime


class OrderEvent(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    order_id: str = Field(..., max_length=64)
    customer_id: str = Field(..., max_length=64)
    session_id: str = Field(..., max_length=64)
    total_amount: Decimal = Field(..., ge=0)
    currency: str = Field("USD", max_length=3)
    items_count: int = Field(..., ge=1)
    payment_method: str
    timestamp: datetime


class InventoryEvent(BaseModel):
    product_id: str
    warehouse_id: str
    quantity_delta: int  # +N for restock, -N for sale
    reason: str  # SALE | RESTOCK | RETURN | DAMAGE
    timestamp: datetime


class Session(BaseModel):
    """A user session — aggregated from clicks."""

    session_id: str
    customer_id: str | None = None
    start_time: datetime
    last_activity: datetime
    page_views: int = 0
    products_viewed: list[str] = Field(default_factory=list)
    cart_adds: int = 0
    checkouts_started: int = 0
    checkouts_completed: int = 0
    revenue: Decimal = Field(default=Decimal("0"), ge=0)
    bot_score: float = Field(default=0.0, ge=0.0, le=1.0)
    user_agent: str | None = None
