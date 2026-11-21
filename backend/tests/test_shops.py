import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.main import app
from seed_data import seed_database


@pytest.fixture
def client(tmp_path):
    test_engine = create_engine(
        f"sqlite:///{tmp_path / 'shops.db'}",
        connect_args={"check_same_thread": False},
    )
    seed_database(test_engine)

    def override_get_db():
        with Session(test_engine) as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    test_engine.dispose()


def test_list_search_and_nearby_sort(client):
    response = client.get("/api/v1/shops")
    assert response.status_code == 200
    assert len(response.json()) == 5
    assert all(shop["distance_km"] is None for shop in response.json())

    response = client.get(
        "/api/v1/shops",
        params={"search": "Tunalı"},
    )
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["name"] == "Cafe des Cafes"

    response = client.get(
        "/api/v1/shops",
        params={"search": "Aşkabat"},
    )
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["name"] == "A4 Kahve"

    response = client.get(
        "/api/v1/shops",
        params={"latitude": 39.9208, "longitude": 32.8541},
    )
    assert response.status_code == 200
    shops = response.json()
    distances = [shop["distance_km"] for shop in shops]
    assert distances == sorted(distances)
    assert shops[0]["name"] == "Cafe Down Engelsiz Cafe"
    assert shops[0]["distance_km"] < 1


def test_shop_detail_includes_menu_and_distance(client):
    nearby = client.get(
        "/api/v1/shops",
        params={"latitude": 39.9208, "longitude": 32.8541},
    ).json()[0]

    response = client.get(
        f"/api/v1/shops/{nearby['id']}",
        params={"latitude": 39.9208, "longitude": 32.8541},
    )
    assert response.status_code == 200
    shop = response.json()
    assert shop["name"] == "Cafe Down Engelsiz Cafe"
    assert shop["distance_km"] == nearby["distance_km"]
    assert len(shop["menu"]) == 4
    assert {product["name"] for product in shop["menu"]} == {
        "Espresso",
        "Cappuccino",
        "Türk Kahvesi",
        "Latte",
    }


def test_shop_coordinates_must_be_paired_and_unknown_shop_is_404(client):
    response = client.get("/api/v1/shops", params={"latitude": 39.9208})
    assert response.status_code == 422

    response = client.get("/api/v1/shops/99999")
    assert response.status_code == 404
