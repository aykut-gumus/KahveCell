from datetime import datetime, timedelta, timezone

from sqlalchemy import Engine, inspect, select, text
from sqlalchemy.orm import Session

from app.db.database import create_db_and_tables, engine
from app.models.entities import Product, Shop, Subscription, User

DEMO_PHONE_NUMBER = "+905550000001"
LEGACY_DEMO_PHONE_NUMBER = "05550000001"
STARTER_MONTHLY_PRICE_CENTS = 8_999
STARTER_MONTHLY_CREDITS = 10
OPENSTREETMAP_ATTRIBUTION = (
    "Location data © OpenStreetMap contributors, ODbL 1.0; "
    "https://www.openstreetmap.org/copyright"
)

SHOPS = (
    {
        "name": "Cafe Down Engelsiz Cafe",
        "address": "İzmir 1 Caddesi, Kızılay Mahallesi, Çankaya, Ankara",
        "latitude": 39.9229865,
        "longitude": 32.8539956,
        "osm_node_id": 13760763501,
    },
    {
        "name": "Kahve Dünyası",
        "address": "69. Sokak, Yukarı Bahçelievler Mahallesi, Çankaya, Ankara",
        "latitude": 39.9185371,
        "longitude": 32.8272781,
        "osm_node_id": 12556375557,
    },
    {
        "name": "A4 Kahve",
        "address": "Aşkabat Caddesi, Yukarı Bahçelievler Mahallesi, Çankaya, Ankara",
        "latitude": 39.9219725,
        "longitude": 32.8257298,
        "osm_node_id": 5300714822,
    },
    {
        "name": "Cafe des Cafes",
        "address": "83, Tunalı Hilmi Caddesi, Çankaya, Ankara",
        "latitude": 39.9066216,
        "longitude": 32.8612044,
        "osm_node_id": 93807636,
    },
    {
        "name": "Kahve Dünyası",
        "address": "S. Saltoğlu Bulvarı, Çayyolu Mahallesi, Çankaya, Ankara",
        "latitude": 39.8756788,
        "longitude": 32.7004407,
        "osm_node_id": 13351540848,
    },
)

PRODUCTS = (
    ("Espresso", 105, "Tek shot espresso."),
    ("Cappuccino", 145, "Espresso ve süt köpüğü."),
    ("Türk Kahvesi", 110, "Geleneksel Türk kahvesi."),
    ("Latte", 155, "Espresso ve süt."),
)


def _ensure_password_hash_column(target_engine: Engine) -> None:
    columns = {column["name"] for column in inspect(target_engine).get_columns("users")}
    if "password_hash" not in columns:
        with target_engine.begin() as connection:
            connection.execute(
                text("ALTER TABLE users ADD COLUMN password_hash VARCHAR(255)")
            )


def seed_database(target_engine: Engine = engine) -> None:
    create_db_and_tables(target_engine)
    _ensure_password_hash_column(target_engine)
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    with Session(target_engine) as session, session.begin():
        for shop_data in SHOPS:
            shop = session.scalar(
                select(Shop).where(
                    Shop.name == shop_data["name"],
                    Shop.address == shop_data["address"],
                )
            )
            if shop is None:
                shop = Shop(
                    name=shop_data["name"],
                    address=shop_data["address"],
                    latitude=shop_data["latitude"],
                    longitude=shop_data["longitude"],
                )
                session.add(shop)
                session.flush()
            else:
                shop.latitude = shop_data["latitude"]
                shop.longitude = shop_data["longitude"]

            for product_name, price_lira, description in PRODUCTS:
                product = session.scalar(
                    select(Product).where(
                        Product.shop_id == shop.id,
                        Product.name == product_name,
                    )
                )
                if product is None:
                    product = Product(
                        shop_id=shop.id,
                        name=product_name,
                        description=description,
                        price_cents=price_lira * 100,
                    )
                    session.add(product)
                else:
                    product.description = description
                    product.price_cents = price_lira * 100
                    product.is_available = True

        user = session.scalar(
            select(User).where(User.phone_number == DEMO_PHONE_NUMBER)
        )
        if user is None:
            user = session.scalar(
                select(User).where(
                    User.phone_number == LEGACY_DEMO_PHONE_NUMBER
                )
            )
            if user is not None:
                user.phone_number = DEMO_PHONE_NUMBER

        if user is None:
            user = User(
                phone_number=DEMO_PHONE_NUMBER,
                first_name="Demo",
                last_name="Kullanıcı",
                role="CUSTOMER",
            )
            session.add(user)
            session.flush()
        subscription = session.scalar(
            select(Subscription).where(
                Subscription.user_id == user.id,
                Subscription.plan_type == "STARTER",
                Subscription.status == "ACTIVE",
            )
        )
        if subscription is None:
            subscription = Subscription(
                user_id=user.id,
                plan_type="STARTER",
                monthly_price_cents=STARTER_MONTHLY_PRICE_CENTS,
                remaining_credits=STARTER_MONTHLY_CREDITS,
                status="ACTIVE",
                started_at=now,
                expires_at=now + timedelta(days=30),
            )
            session.add(subscription)
        else:
            subscription.monthly_price_cents = STARTER_MONTHLY_PRICE_CENTS
            subscription.remaining_credits = STARTER_MONTHLY_CREDITS
            subscription.started_at = now
            subscription.expires_at = now + timedelta(days=30)

    print(f"Seed verileri eklendi. Konum kaynağı: {OPENSTREETMAP_ATTRIBUTION}")
    print(f"Demo telefon: {DEMO_PHONE_NUMBER}")
    print("Başlangıç paketi: ACTIVE Starter, 10 kahve, 89,99 TL / 30 gün")


if __name__ == "__main__":
    seed_database()
