import hashlib
import hmac
import json
from datetime import datetime, timezone
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db, require_roles
from app.core.config import settings
from app.models.entities import (
    Order,
    Product,
    Shop,
    ShopOwnership,
    Subscription,
    User,
)
from app.schemas.orders import (
    CreateOrderRequest,
    OrderResponse,
    OrderStatusUpdate,
    QRCodePayload,
    QRCodeVerificationResponse,
    QRCodeVerifyRequest,
    ShopOwnerAssignmentRequest,
    ShopOwnerAssignmentResponse,
)

router = APIRouter(tags=["Orders"])
ORDER_TRANSITIONS = {
    "PENDING": "ACCEPTED",
    "ACCEPTED": "PREPARING",
    "PREPARING": "READY",
    "READY": "COMPLETED",
}
QR_SIGNING_PREFIX = b"kahvecell-order-qr-v1:"


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def unsigned_qr_data(
    order_id: UUID, user_id: UUID, shop_id: UUID, created_at: str
) -> dict[str, str]:
    return {
        "order_id": str(order_id),
        "user_id": str(user_id),
        "shop_id": str(shop_id),
        "created_at": created_at,
    }


def canonical_qr_json(data: dict[str, str]) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"))


def sign_qr_data(data: dict[str, str]) -> str:
    message = QR_SIGNING_PREFIX + canonical_qr_json(data).encode("utf-8")
    return hmac.new(
        settings.jwt_secret_key.encode("utf-8"), message, hashlib.sha256
    ).hexdigest()


def public_entity_id(entity_type: str, internal_id: int) -> UUID:
    return uuid5(NAMESPACE_URL, f"kahvecell:{entity_type}:{internal_id}")


def serialize_qr(payload: QRCodePayload) -> str:
    data = unsigned_qr_data(
        payload.order_id,
        payload.user_id,
        payload.shop_id,
        payload.created_at,
    )
    return canonical_qr_json({**data, "signature": payload.signature})


def order_response(order: Order) -> OrderResponse:
    qr_code = (
        QRCodePayload.model_validate_json(order.qr_code)
        if order.qr_code is not None
        else None
    )
    return OrderResponse(
        id=order.id,
        user_id=order.user_id,
        shop_id=order.shop_id,
        product_id=order.product_id,
        product_name=order.product.name,
        status="DELIVERED" if order.status == "COMPLETED" else order.status,
        customizations=order.customizations,
        created_at=order.created_at,
        qr_code=qr_code,
    )


def require_shop_access(session: Session, shop_id: int, user: User) -> None:
    if user.role == "ADMIN":
        return
    if user.role != "SHOP_OWNER":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Yalnızca dükkân sahibi bu siparişlere erişebilir.",
        )
    assignment = session.get(ShopOwnership, shop_id)
    if assignment is None or assignment.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bu dükkânın siparişlerini yönetme yetkiniz yok.",
        )


@router.post(
    "/orders",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Abonelik kahve hakkıyla sipariş oluştur ve QR üret",
)
def create_order(
    payload: CreateOrderRequest,
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> OrderResponse:
    shop = session.get(Shop, payload.shop_id)
    if shop is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dükkân bulunamadı.",
        )
    product = session.get(Product, payload.product_id)
    if product is None or product.shop_id != shop.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bu dükkânda ürün bulunamadı.",
        )
    if not product.is_available:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Seçilen ürün şu anda satışta değil.",
        )

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
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sipariş vermek için aktif aboneliğiniz olmalıdır.",
        )

    if subscription.remaining_credits is not None:
        result = session.execute(
            update(Subscription)
            .where(
                Subscription.id == subscription.id,
                Subscription.status == "ACTIVE",
                Subscription.expires_at > now,
                Subscription.remaining_credits > 0,
            )
            .values(remaining_credits=Subscription.remaining_credits - 1)
            .execution_options(synchronize_session=False)
        )
        if result.rowcount != 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Aktif aboneliğinizde sipariş için kahve hakkı kalmadı.",
            )

    order_id = uuid4()
    qr_created_at = datetime.now(timezone.utc).isoformat(timespec="microseconds")
    unsigned_data = unsigned_qr_data(
        order_id,
        public_entity_id("user", user.id),
        public_entity_id("shop", shop.id),
        qr_created_at,
    )
    qr_code = QRCodePayload(
        **unsigned_data,
        signature=sign_qr_data(unsigned_data),
    )
    order = Order(
        user_id=user.id,
        shop_id=shop.id,
        product_id=product.id,
        status="PENDING",
        customizations=payload.customizations,
        qr_code=serialize_qr(qr_code),
    )
    session.add(order)
    session.commit()
    session.refresh(order)
    return order_response(order)


@router.get(
    "/orders/me",
    response_model=list[OrderResponse],
    summary="Müşterinin sipariş geçmişini getir",
)
def get_my_orders(
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[OrderResponse]:
    orders = session.scalars(
        select(Order)
        .where(Order.user_id == user.id)
        .order_by(Order.created_at.desc(), Order.id.desc())
    )
    return [order_response(order) for order in orders]


@router.get(
    "/shops/{shop_id}/orders",
    response_model=list[OrderResponse],
    summary="Yetkili dükkânın siparişlerini getir",
)
def get_shop_orders(
    shop_id: int,
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[OrderResponse]:
    require_shop_access(session, shop_id, user)
    orders = session.scalars(
        select(Order)
        .where(Order.shop_id == shop_id)
        .order_by(Order.created_at.desc(), Order.id.desc())
    )
    return [order_response(order) for order in orders]


@router.patch(
    "/shops/{shop_id}/orders/{order_id}/status",
    response_model=OrderResponse,
    summary="Dükkân sipariş durumunu bir sonraki aşamaya al",
)
def update_order_status(
    shop_id: int,
    order_id: int,
    payload: OrderStatusUpdate,
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> OrderResponse:
    require_shop_access(session, shop_id, user)
    order = session.scalar(
        select(Order).where(
            Order.id == order_id,
            Order.shop_id == shop_id,
        )
    )
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dükkânda bu sipariş bulunamadı.",
        )

    expected_status = ORDER_TRANSITIONS.get(order.status)
    if expected_status is None or payload.status != (
        "DELIVERED" if expected_status == "COMPLETED" else expected_status
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Sipariş durumu sırası geçersiz.",
        )
    order.status = expected_status
    session.commit()
    session.refresh(order)
    return order_response(order)


@router.post(
    "/orders/verify-qr",
    response_model=QRCodeVerificationResponse,
    summary="Sipariş QR imzasını ve kaydını doğrula",
)
def verify_order_qr(
    payload: QRCodeVerifyRequest,
    session: Session = Depends(get_db),
    user: User = Depends(require_roles("SHOP_OWNER", "ADMIN")),
) -> QRCodeVerificationResponse:
    qr_code = payload.qr_code
    unsigned_data = unsigned_qr_data(
        qr_code.order_id,
        qr_code.user_id,
        qr_code.shop_id,
        qr_code.created_at,
    )
    if not hmac.compare_digest(
        qr_code.signature,
        sign_qr_data(unsigned_data),
    ):
        return QRCodeVerificationResponse(
            valid=False,
            order_id=qr_code.order_id,
            message="QR imzası geçersiz.",
        )

    order = session.scalar(
        select(Order).where(Order.qr_code == serialize_qr(qr_code))
    )
    if order is None:
        return QRCodeVerificationResponse(
            valid=False,
            order_id=qr_code.order_id,
            message="QR koduna ait sipariş bulunamadı.",
        )
    require_shop_access(session, order.shop_id, user)
    return QRCodeVerificationResponse(
        valid=True,
        order_id=qr_code.order_id,
        message="QR kodu gerçek; sipariş kaydı doğrulandı.",
        order=order_response(order),
    )


@router.put(
    "/admin/shops/{shop_id}/owner",
    response_model=ShopOwnerAssignmentResponse,
    summary="Dükkâna dükkân sahibi ata",
    dependencies=[Depends(require_roles("ADMIN"))],
)
def assign_shop_owner(
    shop_id: int,
    payload: ShopOwnerAssignmentRequest,
    session: Session = Depends(get_db),
) -> ShopOwnerAssignmentResponse:
    if session.get(Shop, shop_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dükkân bulunamadı.",
        )
    owner = session.get(User, payload.user_id)
    if owner is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kullanıcı bulunamadı.",
        )
    if owner.role != "SHOP_OWNER":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Atama için kullanıcının SHOP_OWNER rolünde olması gerekir.",
        )

    assignment = session.get(ShopOwnership, shop_id)
    if assignment is None:
        assignment = ShopOwnership(shop_id=shop_id, user_id=owner.id)
        session.add(assignment)
    else:
        assignment.user_id = owner.id
    session.commit()
    return ShopOwnerAssignmentResponse(shop_id=shop_id, user_id=owner.id)
