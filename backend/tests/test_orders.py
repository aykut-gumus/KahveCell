from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.main import app
from app.models.entities import Subscription
from app.core.config import settings
from seed_data import seed_database


@pytest.fixture
def client(tmp_path):
    test_engine = create_engine(
        f"sqlite:///{tmp_path / 'orders.db'}",
        connect_args={"check_same_thread": False},
    )
    seed_database(test_engine)

    def override_get_db():
        with Session(test_engine) as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client, test_engine
    app.dependency_overrides.clear()
    test_engine.dispose()


def register_and_login(client: TestClient, phone_number: str) -> dict:
    response = client.post(
        "/api/v1/auth/register", json={"phone_number": phone_number}
    )
    assert response.status_code == 202
    response = client.post(
        "/api/v1/auth/verify-otp",
        json={"phone_number": phone_number, "otp": "1234"},
    )
    assert response.status_code == 200
    return response.json()


def test_order_credits_qr_and_shop_owner_workflow(client):
    client, test_engine = client
    customer = register_and_login(client, "05550000041")
    customer_headers = {
        "Authorization": f"Bearer {customer['access_token']}"
    }

    shops = client.get("/api/v1/shops").json()
    shop = shops[0]
    detail = client.get(f"/api/v1/shops/{shop['id']}").json()
    product = detail["menu"][0]
    order_request = {
        "shop_id": shop["id"],
        "product_id": product["id"],
    }

    response = client.post(
        "/api/v1/orders",
        headers=customer_headers,
        json=order_request,
    )
    assert response.status_code == 403
    assert "aktif aboneli" in response.json()["detail"]

    payment = client.post(
        "/api/v1/payments/process",
        headers=customer_headers,
        json={
            "subscription_plan": "STARTER",
            "card_token": "4242-4242-4242-4242",
        },
    )
    assert payment.status_code == 200
    assert payment.json()["success"] is True

    response = client.post(
        "/api/v1/orders",
        headers=customer_headers,
        json=order_request,
    )
    assert response.status_code == 201
    order = response.json()
    assert order["status"] == "PENDING"
    qr_code = order["qr_code"]
    assert set(qr_code) == {
        "order_id",
        "user_id",
        "shop_id",
        "created_at",
        "signature",
    }
    UUID(qr_code["order_id"])
    UUID(qr_code["user_id"])
    UUID(qr_code["shop_id"])
    assert len(qr_code["signature"]) == 64

    subscription = client.get(
        "/api/v1/subscriptions/me", headers=customer_headers
    ).json()
    assert subscription["remaining_credits"] == 9

    with Session(test_engine) as session:
        stored_subscription = session.scalar(
            select(Subscription).where(
                Subscription.user_id == customer["user"]["id"]
            )
        )
        assert stored_subscription is not None
        stored_subscription.remaining_credits = 0
        session.commit()

    response = client.post(
        "/api/v1/orders",
        headers=customer_headers,
        json=order_request,
    )
    assert response.status_code == 409
    assert "kahve hakkı" in response.json()["detail"]

    owner = register_and_login(client, "05550000042")
    owner_headers = {"Authorization": f"Bearer {owner['access_token']}"}
    response = client.get(
        f"/api/v1/shops/{shop['id']}/orders",
        headers=owner_headers,
    )
    assert response.status_code == 403

    assert settings.bootstrap_admin_phone is not None
    admin = register_and_login(client, settings.bootstrap_admin_phone)
    admin_headers = {"Authorization": f"Bearer {admin['access_token']}"}
    response = client.patch(
        f"/api/v1/admin/users/{owner['user']['id']}/role",
        headers=admin_headers,
        json={"role": "SHOP_OWNER"},
    )
    assert response.status_code == 200

    response = client.put(
        f"/api/v1/admin/shops/{shop['id']}/owner",
        headers=admin_headers,
        json={"user_id": owner["user"]["id"]},
    )
    assert response.status_code == 200

    response = client.get(
        f"/api/v1/shops/{shop['id']}/orders",
        headers=owner_headers,
    )
    assert response.status_code == 200
    assert response.json()[0]["id"] == order["id"]

    response = client.patch(
        f"/api/v1/shops/{shop['id']}/orders/{order['id']}/status",
        headers=owner_headers,
        json={"status": "PREPARING"},
    )
    assert response.status_code == 409

    for next_status in ("ACCEPTED", "PREPARING", "READY", "DELIVERED"):
        response = client.patch(
            f"/api/v1/shops/{shop['id']}/orders/{order['id']}/status",
            headers=owner_headers,
            json={"status": next_status},
        )
        assert response.status_code == 200
        assert response.json()["status"] == next_status

    response = client.post(
        "/api/v1/orders/verify-qr",
        headers=owner_headers,
        json={"qr_code": qr_code},
    )
    assert response.status_code == 200
    assert response.json()["valid"] is True
    assert response.json()["order"]["status"] == "DELIVERED"

    tampered_qr = dict(qr_code)
    tampered_qr["signature"] = (
        "0" if qr_code["signature"][0] != "0" else "1"
    ) + qr_code["signature"][1:]
    response = client.post(
        "/api/v1/orders/verify-qr",
        headers=owner_headers,
        json={"qr_code": tampered_qr},
    )
    assert response.status_code == 200
    assert response.json()["valid"] is False

    customer_orders = client.get(
        "/api/v1/orders/me", headers=customer_headers
    )
    assert customer_orders.status_code == 200
    assert customer_orders.json()[0]["status"] == "DELIVERED"


def test_unlimited_orders_do_not_consume_credits(client):
    client, _ = client
    customer = register_and_login(client, "05550000043")
    headers = {"Authorization": f"Bearer {customer['access_token']}"}

    payment = client.post(
        "/api/v1/payments/process",
        headers=headers,
        json={
            "subscription_plan": "UNLIMITED",
            "card_token": "4242-4242-4242-4242",
        },
    )
    assert payment.status_code == 200
    shop = client.get("/api/v1/shops").json()[0]
    product = client.get(f"/api/v1/shops/{shop['id']}").json()["menu"][0]
    order_request = {"shop_id": shop["id"], "product_id": product["id"]}

    for _ in range(2):
        response = client.post(
            "/api/v1/orders",
            headers=headers,
            json=order_request,
        )
        assert response.status_code == 201

    subscription = client.get(
        "/api/v1/subscriptions/me", headers=headers
    ).json()
    assert subscription["remaining_credits"] is None
