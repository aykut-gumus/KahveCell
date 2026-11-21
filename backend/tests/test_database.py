from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect

from app.db.database import create_db_and_tables, engine
from app.main import app


def test_startup_creates_all_tables():
    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert response.text == "çalışıyor"

    table_names = set(inspect(engine).get_table_names())
    assert table_names == {
        "users",
        "subscriptions",
        "shops",
        "products",
        "orders",
        "otp_challenges",
        "refresh_sessions",
        "payments",
        "shop_ownerships",
    }


def test_tables_have_expected_foreign_keys(tmp_path):
    test_engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    create_db_and_tables(test_engine)

    expected_foreign_keys = {
        "subscriptions": {"users"},
        "products": {"shops"},
        "orders": {"users", "shops", "products", "subscriptions"},
    }

    for table_name, referenced_tables in expected_foreign_keys.items():
        foreign_keys = inspect(test_engine).get_foreign_keys(table_name)
        assert {key["referred_table"] for key in foreign_keys} == referenced_tables

    test_engine.dispose()
