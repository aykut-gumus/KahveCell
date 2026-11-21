import math

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.models.entities import Product, Shop
from app.schemas.shops import (
    ProductResponse,
    ShopDetailResponse,
    ShopResponse,
)

router = APIRouter(tags=["Shops"])
EARTH_RADIUS_KM = 6371.0088


def distance_in_kilometers(
    latitude: float,
    longitude: float,
    shop_latitude: float,
    shop_longitude: float,
) -> float:
    latitude_radians = math.radians(latitude)
    shop_latitude_radians = math.radians(shop_latitude)
    latitude_delta = math.radians(shop_latitude - latitude)
    longitude_delta = math.radians(shop_longitude - longitude)
    haversine = (
        math.sin(latitude_delta / 2) ** 2
        + math.cos(latitude_radians)
        * math.cos(shop_latitude_radians)
        * math.sin(longitude_delta / 2) ** 2
    )
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(min(1.0, haversine)))


def validate_coordinate_pair(
    latitude: float | None, longitude: float | None
) -> None:
    if (latitude is None) != (longitude is None):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Yakınlık sıralaması için latitude ve longitude birlikte gönderilmelidir.",
        )


def shop_response(shop: Shop, distance_km: float | None = None) -> ShopResponse:
    return ShopResponse(
        id=shop.id,
        name=shop.name,
        address=shop.address,
        latitude=shop.latitude,
        longitude=shop.longitude,
        opening_hours=shop.opening_hours,
        rating=shop.rating,
        distance_km=(
            round(distance_km, 3) if distance_km is not None else None
        ),
    )


@router.get(
    "/shops",
    response_model=list[ShopResponse],
    summary="Dükkânları listele, ara veya konuma göre sırala",
)
def list_shops(
    search: str | None = Query(default=None, max_length=150),
    latitude: float | None = Query(default=None, ge=-90, le=90),
    longitude: float | None = Query(default=None, ge=-180, le=180),
    session: Session = Depends(get_db),
) -> list[ShopResponse]:
    validate_coordinate_pair(latitude, longitude)
    shops = list(session.scalars(select(Shop)).all())
    search_term = search.strip().casefold() if search else ""
    if search_term:
        shops = [
            shop
            for shop in shops
            if search_term in shop.name.casefold()
            or search_term in shop.address.casefold()
        ]

    if latitude is None or longitude is None:
        return [
            shop_response(shop)
            for shop in sorted(shops, key=lambda shop: (shop.name.casefold(), shop.id))
        ]

    shops_with_distance = [
        (
            shop,
            distance_in_kilometers(
                latitude, longitude, shop.latitude, shop.longitude
            ),
        )
        for shop in shops
    ]
    shops_with_distance.sort(key=lambda item: (item[1], item[0].id))
    return [
        shop_response(shop, distance)
        for shop, distance in shops_with_distance
    ]


@router.get(
    "/shops/{shop_id}",
    response_model=ShopDetailResponse,
    summary="Dükkân detayını ve menüsünü getir",
)
def get_shop(
    shop_id: int,
    latitude: float | None = Query(default=None, ge=-90, le=90),
    longitude: float | None = Query(default=None, ge=-180, le=180),
    session: Session = Depends(get_db),
) -> ShopDetailResponse:
    validate_coordinate_pair(latitude, longitude)
    shop = session.get(Shop, shop_id)
    if shop is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dükkân bulunamadı.",
        )

    distance = None
    if latitude is not None and longitude is not None:
        distance = distance_in_kilometers(
            latitude, longitude, shop.latitude, shop.longitude
        )
    products = session.scalars(
        select(Product)
        .where(Product.shop_id == shop.id)
        .order_by(Product.name, Product.id)
    )
    return ShopDetailResponse(
        **shop_response(shop, distance).model_dump(),
        menu=[
            ProductResponse(
                id=product.id,
                name=product.name,
                description=product.description,
                price_cents=product.price_cents,
                price=product.price_cents / 100,
                is_available=product.is_available,
            )
            for product in products
        ],
    )
