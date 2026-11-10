import hashlib
import hmac
import importlib
import json

import pytest
from fastapi.testclient import TestClient

import main


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_file = tmp_path / "test_customers.db"
    monkeypatch.setattr(main, "DATABASE_PATH", str(db_file))
    monkeypatch.setattr(main, "API_KEY", "test-api-key")
    monkeypatch.setattr(main, "WEBHOOK_SECRET", "test-webhook-secret")
    main.init_db()
    return TestClient(main.app)


HEADERS = {"X-API-Key": "test-api-key"}


def test_create_and_list_customers(client):
    response = client.post("/customers", headers=HEADERS,
                           json={"name": "Arun Kumar", "email": "arun@example.com"})
    assert response.status_code == 201
    listing = client.get("/customers?page=1&per_page=5", headers=HEADERS)
    assert listing.status_code == 200
    assert len(listing.json()) == 1


def test_missing_api_key_returns_401(client):
    assert client.get("/customers").status_code == 401


def test_wrong_api_key_returns_403(client):
    assert client.get("/customers", headers={"X-API-Key": "wrong"}).status_code == 403


def test_customer_not_found_returns_404(client):
    assert client.get("/customers/999", headers=HEADERS).status_code == 404


def test_duplicate_email_returns_409(client):
    payload = {"name": "Priya", "email": "priya@example.com"}
    assert client.post("/customers", headers=HEADERS, json=payload).status_code == 201
    assert client.post("/customers", headers=HEADERS, json=payload).status_code == 409


def test_invalid_customer_returns_422(client):
    response = client.post("/customers", headers=HEADERS,
                           json={"name": "A", "email": "not-an-email"})
    assert response.status_code == 422


def test_webhook_valid_signature_returns_200(client):
    body = json.dumps({"event": "order.created", "order_id": 101}).encode()
    signature = hmac.new(b"test-webhook-secret", body, hashlib.sha256).hexdigest()
    response = client.post("/webhooks/order-events", headers={
        **HEADERS, "X-Signature": signature, "Content-Type": "application/json"
    }, content=body)
    assert response.status_code == 200
    assert response.json()["status"] == "received"


def test_webhook_tampered_signature_returns_401(client):
    body = b'{"event":"order.created","order_id":101}'
    response = client.post("/webhooks/order-events", headers={
        **HEADERS, "X-Signature": "0" * 64, "Content-Type": "application/json"
    }, content=body)
    assert response.status_code == 401


def test_update_and_delete_customer(client):
    created = client.post("/customers", headers=HEADERS,
                          json={"name": "Meena", "email": "meena@example.com"}).json()
    customer_id = created["id"]
    updated = client.put(f"/customers/{customer_id}", headers=HEADERS,
                         json={"name": "Meena S", "email": "meena.s@example.com"})
    assert updated.status_code == 200
    assert updated.json()["name"] == "Meena S"
    deleted = client.delete(f"/customers/{customer_id}", headers=HEADERS)
    assert deleted.status_code == 204
