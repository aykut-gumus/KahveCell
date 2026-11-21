from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    phone_number: Mapped[str] = mapped_column(String(15), unique=True, index=True)
    first_name: Mapped[str] = mapped_column(String(80))
    last_name: Mapped[str] = mapped_column(String(80))
    email: Mapped[str | None] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="CUSTOMER")
    preferences: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )

    subscriptions: Mapped[list[Subscription]] = relationship(
        back_populates="user"
    )
    orders: Mapped[list[Order]] = relationship(back_populates="user")
    refresh_sessions: Mapped[list[RefreshSession]] = relationship(
        back_populates="user"
    )
    payments: Mapped[list[Payment]] = relationship(back_populates="user")

    @property
    def profile_completed(self) -> bool:
        return bool(self.first_name.strip() and self.last_name.strip())


class OtpChallenge(Base):
    __tablename__ = "otp_challenges"

    id: Mapped[int] = mapped_column(primary_key=True)
    phone_number: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    code_hash: Mapped[str] = mapped_column(String(64))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime)


class RefreshSession(Base):
    __tablename__ = "refresh_sessions"

    token_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime)

    user: Mapped[User] = relationship(back_populates="refresh_sessions")


class Subscription(Base):
    __tablename__ = "subscriptions"
    __table_args__ = (
        CheckConstraint(
            "plan_type IN ('STARTER', 'PREMIUM', 'UNLIMITED')",
            name="ck_subscriptions_plan_type",
        ),
        CheckConstraint(
            "status IN ('ACTIVE', 'PAUSED', 'CANCELLED')",
            name="ck_subscriptions_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    plan_type: Mapped[str] = mapped_column(String(20))
    monthly_price_cents: Mapped[int] = mapped_column(Integer)
    remaining_credits: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")
    started_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime)

    user: Mapped[User] = relationship(back_populates="subscriptions")
    orders: Mapped[list[Order]] = relationship(back_populates="subscription")
    payments: Mapped[list[Payment]] = relationship(back_populates="subscription")


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint(
            "plan_type IN ('STARTER', 'PREMIUM', 'UNLIMITED')",
            name="ck_payments_plan_type",
        ),
        CheckConstraint(
            "status IN ('SUCCEEDED', 'FAILED')",
            name="ck_payments_status",
        ),
        CheckConstraint("amount_cents >= 0", name="ck_payments_amount_nonnegative"),
    )

    transaction_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    subscription_id: Mapped[int | None] = mapped_column(
        ForeignKey("subscriptions.id"), index=True
    )
    plan_type: Mapped[str] = mapped_column(String(20))
    amount_cents: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )

    user: Mapped[User] = relationship(back_populates="payments")
    subscription: Mapped[Subscription | None] = relationship(
        back_populates="payments"
    )


class Shop(Base):
    __tablename__ = "shops"
    __table_args__ = (
        CheckConstraint(
            "latitude >= -90 AND latitude <= 90", name="ck_shops_latitude"
        ),
        CheckConstraint(
            "longitude >= -180 AND longitude <= 180", name="ck_shops_longitude"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150), index=True)
    address: Mapped[str] = mapped_column(Text)
    latitude: Mapped[float]
    longitude: Mapped[float]
    opening_hours: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    rating: Mapped[float | None]
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )

    products: Mapped[list[Product]] = relationship(back_populates="shop")
    orders: Mapped[list[Order]] = relationship(back_populates="shop")


class ShopOwnership(Base):
    __tablename__ = "shop_ownerships"

    shop_id: Mapped[int] = mapped_column(
        ForeignKey("shops.id"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("shop_id", "name", name="uq_products_shop_name"),
        CheckConstraint("price_cents >= 0", name="ck_products_price_nonnegative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text)
    price_cents: Mapped[int] = mapped_column(Integer)
    is_available: Mapped[bool] = mapped_column(default=True)

    shop: Mapped[Shop] = relationship(back_populates="products")
    orders: Mapped[list[Order]] = relationship(back_populates="product")


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING', 'ACCEPTED', 'PREPARING', 'READY', "
            "'COMPLETED', 'CANCELLED')",
            name="ck_orders_status",
        ),
        Index("ix_orders_user_created_at", "user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    subscription_id: Mapped[int | None] = mapped_column(
        ForeignKey("subscriptions.id"), index=True
    )
    status: Mapped[str] = mapped_column(String(20), default="PENDING")
    customizations: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    qr_code: Mapped[str | None] = mapped_column(String(255), unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )

    user: Mapped[User] = relationship(back_populates="orders")
    shop: Mapped[Shop] = relationship(back_populates="orders")
    product: Mapped[Product] = relationship(back_populates="orders")
    subscription: Mapped[Subscription | None] = relationship(
        back_populates="orders"
    )
