from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


OrderStatus = Literal[
    "PENDING",
    "ACCEPTED",
    "PREPARING",
    "READY",
    "DELIVERED",
]


class CreateOrderRequest(BaseModel):
    shop_id: int = Field(gt=0)
    product_id: int = Field(gt=0)
    customizations: dict[str, Any] | None = None


class QRCodePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_id: UUID
    user_id: UUID
    shop_id: UUID
    created_at: str
    signature: str = Field(pattern=r"^[a-f0-9]{64}$")

    @field_validator("created_at")
    @classmethod
    def validate_created_at(cls, value: str) -> str:
        try:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("created_at ISO 8601 biçiminde olmalıdır.") from exc
        return value


class QRCodeVerifyRequest(BaseModel):
    qr_code: QRCodePayload


class OrderStatusUpdate(BaseModel):
    status: Literal["ACCEPTED", "PREPARING", "READY", "DELIVERED"]


class OrderResponse(BaseModel):
    id: int
    user_id: int
    shop_id: int
    product_id: int
    product_name: str
    status: OrderStatus
    customizations: dict[str, Any] | None
    created_at: datetime
    qr_code: QRCodePayload | None


class QRCodeVerificationResponse(BaseModel):
    valid: bool
    order_id: UUID | None
    message: str
    order: OrderResponse | None = None


class ShopOwnerAssignmentRequest(BaseModel):
    user_id: int = Field(gt=0)


class ShopOwnerAssignmentResponse(BaseModel):
    shop_id: int
    user_id: int
