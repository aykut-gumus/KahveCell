from sqlalchemy import create_engine, func, inspect, select, text
from sqlalchemy.orm import Session

from app.models.entities import Product, Shop, Subscription, User
from seed_data import (
    DEMO_PHONE_NUMBER,
    SHOPS,
    _ensure_password_hash_column,
    seed_database,
)


def test_seed_data_is_complete_and_can_be_repeated(tmp_path):
    test_engine = create_engine(f"sqlite:///{tmp_path / 'seed.db'}")

    seed_database(test_engine)
    seed_database(test_engine)

    with Session(test_engine) as session:
        assert session.scalar(select(func.count()).select_from(Shop)) == len(SHOPS)
        assert session.scalar(select(func.count()).select_from(Product)) == 20

        user = session.scalar(
            select(User).where(User.phone_number == DEMO_PHONE_NUMBER)
        )
        assert user is not None

        subscription = session.scalar(
            select(Subscription).where(Subscription.user_id == user.id)
        )
        assert subscription is not None
        assert subscription.plan_type == "STARTER"
        assert subscription.status == "ACTIVE"
        assert subscription.remaining_credits == 10
        assert subscription.monthly_price_cents == 8_999

    test_engine.dispose()


def test_seed_adds_password_hash_to_an_existing_users_table(tmp_path):
    test_engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    with test_engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE users ("
                "id INTEGER PRIMARY KEY, "
                "phone_number VARCHAR(15), "
                "first_name VARCHAR(80), "
                "last_name VARCHAR(80), "
                "email VARCHAR(255), "
                "role VARCHAR(20), "
                "preferences JSON, "
                "created_at DATETIME)"
            )
        )

    _ensure_password_hash_column(test_engine)

    columns = {column["name"] for column in inspect(test_engine).get_columns("users")}
    assert "password_hash" in columns
    test_engine.dispose()
