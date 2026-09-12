"""Navigation session lifecycle tests (create / list / get / delete)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from api.main import create_app


def make_client() -> TestClient:
    return TestClient(create_app())


def create_payload():
    return {
        "latitude": 25.0782,
        "longitude": 55.1321,
        "accuracy": 3.0,
        "headingDeg": 90.0,
    }


def test_create_session_returns_state():
    with make_client() as client:
        response = client.post("/navigation/sessions", json=create_payload())
        assert response.status_code == 201
        body = response.json()
        assert body["sessionId"]
        state = body["state"]
        assert state["mode"] == "DEAD_RECKONING"
        assert abs(state["latitude"] - 25.0782) < 1e-6
        assert abs(state["longitude"] - 55.1321) < 1e-6
        assert state["headingDeg"] is not None


def test_list_sessions():
    with make_client() as client:
        first = client.post("/navigation/sessions", json=create_payload())
        second = client.post("/navigation/sessions", json=create_payload())
        assert first.status_code == 201
        assert second.status_code == 201
        listing = client.get("/navigation/sessions")
        assert listing.status_code == 200
        ids = listing.json()
        assert first.json()["sessionId"] in ids
        assert second.json()["sessionId"] in ids


def test_get_session_by_id():
    with make_client() as client:
        created = client.post("/navigation/sessions", json=create_payload()).json()
        session_id = created["sessionId"]
        response = client.get(f"/navigation/sessions/{session_id}")
        assert response.status_code == 200
        body = response.json()
        assert body["sessionId"] == session_id
        assert body["state"]["latitude"] is not None


def test_delete_session():
    with make_client() as client:
        session_id = client.post("/navigation/sessions", json=create_payload()).json()[
            "sessionId"
        ]
        response = client.delete(f"/navigation/sessions/{session_id}")
        assert response.status_code == 204
        gone = client.get(f"/navigation/sessions/{session_id}")
        assert gone.status_code == 404
        listing = client.get("/navigation/sessions")
        assert session_id not in listing.json()


def test_delete_unknown_session_404():
    with make_client() as client:
        response = client.delete("/navigation/sessions/does-not-exist")
        assert response.status_code == 404