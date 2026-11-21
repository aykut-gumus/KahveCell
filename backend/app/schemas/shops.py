from typing import Any

from pydantic import BaseModel


class ProductResponse(BaseModel):
    id: int
    name: str
    description: str | None
    price_cents: int
    price: float
    is_available: bool


class ShopResponse(BaseModel):
    id: int
    name: str
    address: str
    latitude: float
    longitude: float
    opening_hours: dict[str, Any] | None
    rating: float | None
    distance_km: float | None = None


class ShopDetailResponse(ShopResponse):
    menu: list[ProductResponse]
