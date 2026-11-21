from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

PlanType = Literal["STARTER", "PREMIUM", "UNLIMITED"]
MockCardToken = Literal["4242-4242-4242-4242", "4000-0000-0000-0002"]


class SubscriptionPlanResponse(BaseModel):
    plan_type: PlanType
    monthly_price_cents: int
    monthly_price: float
    coffee_credits: int | None
    guest_credits: int
    priority_service: bool


class SubscriptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    plan_type: PlanType
    monthly_price_cents: int
    remaining_credits: int | None
    status: Literal["ACTIVE", "PAUSED", "CANCELLED"]
    started_at: datetime
    expires_at: datetime | None


class PaymentRequest(BaseModel):
    subscription_plan: PlanType
    card_token: MockCardToken


class PaymentResponse(BaseModel):
    success: bool
    transaction_id: str
    user_id: int
    subscription_plan: PlanType
    amount: float
    currency: Literal["TRY"] = "TRY"
    timestamp: datetime
    message: str
    subscription: SubscriptionResponse | None


class PaymentHistoryResponse(BaseModel):
    transaction_id: str
    subscription_plan: PlanType
    amount: float
    currency: Literal["TRY"] = "TRY"
    status: Literal["SUCCEEDED", "FAILED"]
    timestamp: datetime
