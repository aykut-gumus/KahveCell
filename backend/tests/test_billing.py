import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.db.database import create_db_and_tables
from app.main import app
from app.models.entities import Payment, Subscription


@pytest.fixture
def client(tmp_path):
    test_engine = create_engine(
        f"sqlite:///{tmp_path / 'billing.db'}",
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


def login(client: TestClient, phone_number: str) -> dict:
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


def purchase(
    client: TestClient, headers: dict[str, str], plan: str, card: str
) -> dict:
    response = client.post(
        "/api/v1/payments/process",
        headers=headers,
        json={"subscription_plan": plan, "card_token": card},
    )
    assert response.status_code == 200
    return response.json()


def test_plan_catalog_and_payment_success_and_failure(client):
    client, test_engine = client
    plans = client.get("/api/v1/subscriptions/plans")
    assert plans.status_code == 200
    assert {
        plan["plan_type"]: (
            plan["monthly_price_cents"],
            plan["coffee_credits"],
            plan["guest_credits"],
            plan["priority_service"],
        )
        for plan in plans.json()
    } == {
        "STARTER": (8999, 10, 0, False),
        "PREMIUM": (14999, 20, 2, False),
        "UNLIMITED": (24999, None, 5, True),
    }

    tokens = login(client, "05550000021")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    response = client.get("/api/v1/subscriptions/me", headers=headers)
    assert response.status_code == 200
    assert response.json() is None

    failed = purchase(
        client, headers, "STARTER", "4000-0000-0000-0002"
    )
    assert failed["success"] is False
    assert failed["subscription"] is None
    assert client.get("/api/v1/subscriptions/me", headers=headers).json() is None

    succeeded = purchase(
        client, headers, "STARTER", "4242-4242-4242-4242"
    )
    assert succeeded["success"] is True
    assert succeeded["amount"] == 89.99
    assert succeeded["subscription"]["remaining_credits"] == 10
    assert succeeded["subscription"]["status"] == "ACTIVE"

    history = client.get("/api/v1/payments/history", headers=headers)
    assert [payment["status"] for payment in history.json()] == [
        "SUCCEEDED",
        "FAILED",
    ]
    with Session(test_engine) as session:
        payments = list(session.scalars(select(Payment)))
        assert all(payment.transaction_id for payment in payments)
        assert all(payment.subscription_id is not None for payment in payments if payment.status == "SUCCEEDED")
        assert all(payment.subscription_id is None for payment in payments if payment.status == "FAILED")


def test_upgrade_downgrade_renewal_and_cancel(client):
    client, test_engine = client
    tokens = login(client, "05550000022")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    starter = purchase(
        client, headers, "STARTER", "4242-4242-4242-4242"
    )["subscription"]
    failed_upgrade = purchase(
        client, headers, "PREMIUM", "4000-0000-0000-0002"
    )
    assert failed_upgrade["success"] is False
    current = client.get("/api/v1/subscriptions/me", headers=headers).json()
    assert current["id"] == starter["id"]
    assert current["plan_type"] == "STARTER"
    assert current["remaining_credits"] == 10

    upgraded = purchase(
        client, headers, "PREMIUM", "4242-4242-4242-4242"
    )["subscription"]
    assert upgraded["id"] == starter["id"]
    assert upgraded["plan_type"] == "PREMIUM"
    assert upgraded["remaining_credits"] == 20

    downgraded = purchase(
        client, headers, "STARTER", "4242-4242-4242-4242"
    )["subscription"]
    assert downgraded["plan_type"] == "STARTER"
    assert downgraded["remaining_credits"] == 10

    previous_expiration = downgraded["expires_at"]
    renewed = purchase(
        client, headers, "STARTER", "4242-4242-4242-4242"
    )["subscription"]
    assert renewed["expires_at"] > previous_expiration

    unlimited = purchase(
        client, headers, "UNLIMITED", "4242-4242-4242-4242"
    )["subscription"]
    assert unlimited["remaining_credits"] is None

    cancelled = client.post("/api/v1/subscriptions/cancel", headers=headers)
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "CANCELLED"
    assert client.get("/api/v1/subscriptions/me", headers=headers).json() is None

    with Session(test_engine) as session:
        subscriptions = list(session.scalars(select(Subscription)))
        assert len(subscriptions) == 1
