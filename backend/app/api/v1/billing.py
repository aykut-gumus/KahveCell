from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.models.entities import Payment, Subscription, User
from app.schemas.billing import (
    PaymentHistoryResponse,
    PaymentRequest,
    PaymentResponse,
    SubscriptionPlanResponse,
    SubscriptionResponse,
)

router = APIRouter(tags=["Subscriptions & Payments"])

PLAN_DETAILS: dict[str, dict[str, int | None | bool]] = {
    "STARTER": {
        "monthly_price_cents": 8_999,
        "coffee_credits": 10,
        "guest_credits": 0,
        "priority_service": False,
    },
    "PREMIUM": {
        "monthly_price_cents": 14_999,
        "coffee_credits": 20,
        "guest_credits": 2,
        "priority_service": False,
    },
    "UNLIMITED": {
        "monthly_price_cents": 24_999,
        "coffee_credits": None,
        "guest_credits": 5,
        "priority_service": True,
    },
}
SUCCESSFUL_CARD = "4242-4242-4242-4242"
SUBSCRIPTION_PERIOD = timedelta(days=30)


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def amount_in_lira(amount_cents: int) -> Decimal:
    return Decimal(amount_cents) / Decimal(100)


@router.get(
    "/subscriptions/plans",
    response_model=list[SubscriptionPlanResponse],
    summary="Abonelik paketlerini listele",
)
def list_subscription_plans() -> list[SubscriptionPlanResponse]:
    return [
        SubscriptionPlanResponse(
            plan_type=plan_type,
            monthly_price_cents=int(details["monthly_price_cents"]),
            monthly_price=amount_in_lira(int(details["monthly_price_cents"])),
            coffee_credits=details["coffee_credits"],
            guest_credits=int(details["guest_credits"]),
            priority_service=bool(details["priority_service"]),
        )
        for plan_type, details in PLAN_DETAILS.items()
    ]


@router.get(
    "/subscriptions/me",
    response_model=SubscriptionResponse | None,
    summary="Aktif aboneliğimi ve kalan kahve hakkımı getir",
)
def get_my_subscription(
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SubscriptionResponse | None:
    now = utc_now()
    subscription = session.scalar(
        select(Subscription)
        .where(
            Subscription.user_id == user.id,
            Subscription.status == "ACTIVE",
            Subscription.expires_at > now,
        )
        .order_by(Subscription.started_at.desc(), Subscription.id.desc())
    )
    if subscription is None:
        return None
    return SubscriptionResponse.model_validate(subscription)


@router.post(
    "/payments/process",
    response_model=PaymentResponse,
    summary="Paket satın al, değiştir veya aylık yenilemeyi simüle et",
)
def process_payment(
    payload: PaymentRequest,
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PaymentResponse:
    details = PLAN_DETAILS[payload.subscription_plan]
    amount_cents = int(details["monthly_price_cents"])
    now = utc_now()
    transaction_id = str(uuid4())
    succeeded = payload.card_token == SUCCESSFUL_CARD
    subscription: Subscription | None = None

    if succeeded:
        active_subscriptions = list(
            session.scalars(
                select(Subscription)
                .where(
                    Subscription.user_id == user.id,
                    Subscription.status == "ACTIVE",
                )
                .order_by(Subscription.started_at.desc(), Subscription.id.desc())
            )
        )
        subscription = next(
            (
                item
                for item in active_subscriptions
                if item.expires_at is not None and item.expires_at > now
            ),
            None,
        )
        for item in active_subscriptions:
            if item is not subscription:
                item.status = "CANCELLED"

        coffee_credits = details["coffee_credits"]
        if subscription is None:
            subscription = Subscription(
                user_id=user.id,
                plan_type=payload.subscription_plan,
                monthly_price_cents=amount_cents,
                remaining_credits=coffee_credits,
                status="ACTIVE",
                started_at=now,
                expires_at=now + SUBSCRIPTION_PERIOD,
            )
            session.add(subscription)
        else:
            is_same_plan = subscription.plan_type == payload.subscription_plan
            period_start = (
                max(subscription.expires_at, now)
                if is_same_plan and subscription.expires_at is not None
                else now
            )
            subscription.plan_type = payload.subscription_plan
            subscription.monthly_price_cents = amount_cents
            subscription.remaining_credits = coffee_credits
            subscription.status = "ACTIVE"
            if not is_same_plan:
                subscription.started_at = now
            subscription.expires_at = period_start + SUBSCRIPTION_PERIOD

    payment = Payment(
        transaction_id=transaction_id,
        user_id=user.id,
        subscription=subscription if succeeded else None,
        plan_type=payload.subscription_plan,
        amount_cents=amount_cents,
        status="SUCCEEDED" if succeeded else "FAILED",
        created_at=now,
    )
    session.add(payment)
    session.commit()
    if subscription is not None:
        session.refresh(subscription)

    return PaymentResponse(
        success=succeeded,
        transaction_id=transaction_id,
        user_id=user.id,
        subscription_plan=payload.subscription_plan,
        amount=amount_in_lira(amount_cents),
        timestamp=payment.created_at or now,
        message=(
            "Ödeme başarılı; abonelik etkinleştirildi."
            if succeeded
            else "Ödeme başarısız; aktif abonelik değişmedi."
        ),
        subscription=(
            SubscriptionResponse.model_validate(subscription)
            if subscription is not None
            else None
        ),
    )


@router.get(
    "/payments/history",
    response_model=list[PaymentHistoryResponse],
    summary="Ödeme geçmişimi getir",
)
def get_payment_history(
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[PaymentHistoryResponse]:
    payments = session.scalars(
        select(Payment)
        .where(Payment.user_id == user.id)
        .order_by(Payment.created_at.desc(), Payment.transaction_id.desc())
    )
    return [
        PaymentHistoryResponse(
            transaction_id=payment.transaction_id,
            subscription_plan=payment.plan_type,
            amount=amount_in_lira(payment.amount_cents),
            status=payment.status,
            timestamp=payment.created_at,
        )
        for payment in payments
    ]


@router.post(
    "/subscriptions/cancel",
    response_model=SubscriptionResponse,
    summary="Aktif aboneliğimi iptal et",
)
def cancel_my_subscription(
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SubscriptionResponse:
    now = utc_now()
    subscription = session.scalar(
        select(Subscription)
        .where(
            Subscription.user_id == user.id,
            Subscription.status == "ACTIVE",
            Subscription.expires_at > now,
        )
        .order_by(Subscription.started_at.desc(), Subscription.id.desc())
    )
    if subscription is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="İptal edilecek aktif abonelik bulunamadı.",
        )
    subscription.status = "CANCELLED"
    session.commit()
    session.refresh(subscription)
    return SubscriptionResponse.model_validate(subscription)
