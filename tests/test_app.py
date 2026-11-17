from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_cpu():
    r = client.get("/cpu?iterations=1000")
    assert r.status_code == 200
    assert r.json()["iterations"] == 1000


def test_memory():
    r = client.get("/memory?mb=1&hold_ms=0")
    assert r.status_code == 200
    assert r.json()["allocated_mb"] == 1


def test_io():
    r = client.get("/io?delay_ms=10")
    assert r.status_code == 200


def test_metrics_exposed():
    client.get("/health")
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "app_requests_total" in r.text
