import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.core.config import settings
from app.db.database import create_db_and_tables
from app.main import app
from app.models.entities import User


@pytest.fixture
def client(tmp_path):
    test_engine = create_engine(
        f"sqlite:///{tmp_path / 'auth.db'}",
        connect_args={"check_same_thread": False},
    )
    create_db_and_tables(test_engine)

    def override_get_db():
        with Session(test_engine) as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client, test_engine
    app.dependency_overrides.clear()
    test_engine.dispose()


def register_and_verify(client: TestClient, phone_number: str) -> dict:
    response = client.post(
        "/api/v1/auth/register", json={"phone_number": phone_number}
    )
    assert response.status_code == 202
    assert response.json()["simulation_code"] == "1234"

    response = client.post(
        "/api/v1/auth/verify-otp",
        json={"phone_number": phone_number, "otp": "1234"},
    )
    assert response.status_code == 200
    return response.json()


def test_otp_login_profile_and_refresh_rotation(client):
    client, _ = client
    phone_number = "05550000002"
    response = client.post(
        "/api/v1/auth/register", json={"phone_number": phone_number}
    )
    assert response.status_code == 202

    response = client.post(
        "/api/v1/auth/verify-otp",
        json={"phone_number": phone_number, "otp": "0000"},
    )
    assert response.status_code == 400

    tokens = register_and_verify(client, phone_number)
    assert tokens["user"]["role"] == "CUSTOMER"
    assert tokens["user"]["profile_completed"] is False

    access_headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    response = client.get("/api/v1/auth/me", headers=access_headers)
    assert response.status_code == 200
    assert response.json()["phone_number"] == "+905550000002"

    response = client.patch(
        "/api/v1/auth/me",
        headers=access_headers,
        json={
            "first_name": "Test",
            "last_name": "Kullanıcı",
            "email": "test@example.com",
            "coffee_preferences": ["Latte"],
            "allergens": ["Süt"],
        },
    )
    assert response.status_code == 200
    assert response.json()["profile_completed"] is True
    assert response.json()["preferences"] == {
        "coffee_preferences": ["Latte"],
        "allergens": ["Süt"],
    }

    response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert response.status_code == 200
    rotated_tokens = response.json()
    assert rotated_tokens["refresh_token"] != tokens["refresh_token"]

    response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert response.status_code == 401

    response = client.post(
        "/api/v1/auth/verify-otp",
        json={"phone_number": phone_number, "otp": "1234"},
    )
    assert response.status_code == 400


def test_admin_bootstrap_and_role_authorization(client):
    client, _ = client
    customer = register_and_verify(client, "05550000004")
    assert settings.bootstrap_admin_phone is not None
    admin = register_and_verify(client, settings.bootstrap_admin_phone)
    customer_id = customer["user"]["id"]

    role_change = {
        "role": "SHOP_OWNER",
    }
    response = client.patch(
        f"/api/v1/admin/users/{customer_id}/role",
        headers={"Authorization": f"Bearer {customer['access_token']}"},
        json=role_change,
    )
    assert response.status_code == 403

    response = client.patch(
        f"/api/v1/admin/users/{customer_id}/role",
        headers={"Authorization": f"Bearer {admin['access_token']}"},
        json=role_change,
    )
    assert response.status_code == 200
    assert response.json()["role"] == "SHOP_OWNER"

    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {customer['access_token']}"},
    )
    assert response.status_code == 200
    assert response.json()["role"] == "SHOP_OWNER"


def test_existing_domestic_demo_phone_is_migrated_on_otp_login(client):
    client, test_engine = client
    with Session(test_engine) as session:
        user = User(
            phone_number="05550000001",
            first_name="Demo",
            last_name="Kullanıcı",
            role="CUSTOMER",
        )
        session.add(user)
        session.commit()
        user_id = user.id

    tokens = register_and_verify(client, "05550000001")

    assert tokens["user"]["id"] == user_id
    assert tokens["user"]["phone_number"] == "+905550000001"
