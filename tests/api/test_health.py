"""Health endpoint tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from api.main import create_app


def make_client() -> TestClient:
    return TestClient(create_app())


def test_health_ok():
    with make_client() as client:
        response = client.get("/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["environment"] == "development"
        assert body["version"]


def test_health_models_lists_artifacts():
    with make_client() as client:
        response = client.get("/health/models")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        names = {entry["name"] for entry in body["models"]}
        for expected in (
            "speed-lstm",
            "speed-gru",
            "speed-tcn",
            "vibration-classifier",
            "imu-correction",
            "error-model",
        ):
            assert expected in names, f"missing model status {expected}"
        for entry in body["models"]:
            assert isinstance(entry["available"], bool)


def test_ready():
    with make_client() as client:
        response = client.get("/ready")
        assert response.status_code == 200
        assert response.json()["status"] == "ready"


def test_root_info():
    with make_client() as client:
        response = client.get("/")
        assert response.status_code == 200
        assert response.json()["service"]