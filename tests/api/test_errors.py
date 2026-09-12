"""Error handling tests — validation, 404s, session limits, sanitized 500s."""

from __future__ import annotations

from fastapi.testclient import TestClient

from api.config import Settings
from api.main import create_app


def make_client(**settings_kwargs) -> TestClient:
    settings = Settings(**settings_kwargs)
    return TestClient(create_app(settings=settings))


def test_create_requires_latitude():
    with make_client() as client:
        response = client.post(
            "/navigation/sessions", json={"longitude": 55.1, "accuracy": 5.0}
        )
        assert response.status_code == 422


def test_create_rejects_out_of_range_coordinates():
    with make_client() as client:
        response = client.post(
            "/navigation/sessions",
            json={"latitude": 95.0, "longitude": 55.1, "accuracy": 5.0},
        )
        assert response.status_code == 422


def test_create_rejects_non_finite_timestamp():
    with make_client() as client:
        response = client.post(
            "/navigation/sessions",
            json={"latitude": 25.0, "longitude": 55.0, "accuracy": 5.0},
        )
        assert response.status_code == 201
        session_id = response.json()["sessionId"]
        bad = client.post(
            f"/navigation/sessions/{session_id}/update",
            json={"samples": [{"timestamp": float("nan"), "accelerometer": {}, "gyroscope": {}}]},
        )
        assert bad.status_code == 422


def test_unknown_session_operations_404():
    with make_client() as client:
        assert client.get("/navigation/sessions/ghost").status_code == 404
        assert (
            client.post(
                "/navigation/sessions/ghost/update", json={"samples": [], "gnss": None}
            ).status_code
            == 404
        )
        assert client.delete("/navigation/sessions/ghost").status_code == 404


def test_session_limit_returns_503():
    with make_client(max_sessions=1) as client:
        first = client.post(
            "/navigation/sessions",
            json={"latitude": 25.0, "longitude": 55.0, "accuracy": 5.0},
        )
        assert first.status_code == 201
        second = client.post(
            "/navigation/sessions",
            json={"latitude": 25.0, "longitude": 55.0, "accuracy": 5.0},
        )
        assert second.status_code == 503
        assert "session limit" in second.json()["detail"]


def test_update_failure_is_sanitized(monkeypatch):
    with make_client() as client:
        session_id = client.post(
            "/navigation/sessions",
            json={"latitude": 25.0, "longitude": 55.0, "accuracy": 5.0},
        ).json()["sessionId"]

        def boom(*_args, **_kwargs):
            raise RuntimeError("secret internal detail: /home/user/.env")

        monkeypatch.setattr(client.app.state.manager, "update", boom)
        response = client.post(
            f"/navigation/sessions/{session_id}/update",
            json={"samples": [], "gnss": None},
        )
        assert response.status_code == 500
        body = response.json()
        assert "secret internal detail" not in str(body)
        assert "Please retry" in body["detail"]


def test_unhandled_exception_is_sanitized(monkeypatch):
    import api.session_manager

    # Force the documented global handler path: unexpected error, no traceback leak.
    def broken_impl(*_args, **_kwargs):
        raise ValueError("secrets_in_traceback")

    monkeypatch.setattr(api.session_manager.NavigationSessionManager, "delete", broken_impl)
    client = TestClient(create_app(), raise_server_exceptions=False)
    with client:
        response = client.delete("/navigation/sessions/x")
        assert response.status_code == 500
        assert response.json()["detail"] == "Internal server error. Please retry."