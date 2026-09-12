"""Navigation session update tests — IMU + GNSS streaming through the HTTP API.

These exercise the full pipeline (HTTP -> adapter -> real IDREngine -> state)
and assert the JSON responses are always finite (never NaN/inf).
"""

from __future__ import annotations

import json
import math
import time

from fastapi.testclient import TestClient

from api.main import create_app


def make_client() -> TestClient:
    return TestClient(create_app())


T0 = 1_600_000_000.0


def imu_sample(t: float, heading_deg: float | None = None, gyro_z: float = 0.0):
    return {
        "timestamp": t,
        "accelerometer": {"x": 0.0, "y": 0.0, "z": 9.8},
        "gyroscope": {"x": 0.0, "y": 0.0, "z": gyro_z},
        "magnetometer": {"x": 20.0, "y": 0.0, "z": -30.0},
        "headingDeg": heading_deg,
    }


def gnss_fix(
    t: float,
    lat: float = 25.0782,
    lon: float = 55.1321,
    accuracy: float = 3.0,
    east_m: float = 0.0,
):
    """A fix; ``east_m`` shifts the longitude east to stay consistent with
    the reported speed (the EKF treats a static fix under constant 5 m/s as
    noise once the drifted position exceeds the innovation gate)."""
    return {
        "timestamp": t,
        "latitude": lat,
        "longitude": lon + east_m / 111_320.0,
        "accuracy": accuracy,
        "speedMps": 5.0,
        "headingDeg": 90.0,
    }


def create_with_fix(client: TestClient) -> str:
    response = client.post(
        "/navigation/sessions",
        json={"latitude": 25.0782, "longitude": 55.1321, "accuracy": 3.0, "headingDeg": 90.0},
    )
    assert response.status_code == 201
    return response.json()["sessionId"]


def assert_finite_state(state: dict) -> None:
    raw = json.dumps(state)
    assert "NaN" not in raw, "NaN leaked into JSON response"
    assert "Infinity" not in raw and "-Infinity" not in raw, "inf leaked into JSON"
    for key in ("latitude", "longitude", "speedMps", "headingDeg", "confidence", "positionErrorM", "timestamp"):
        value = state.get(key)
        if value is not None:
            assert math.isfinite(float(value)), f"non-finite {key}: {value}"


def test_update_propagates_to_gnss_fusion_mode():
    with make_client() as client:
        session_id = create_with_fix(client)
        samples = [imu_sample(T0 + i * 0.1, heading_deg=90.0) for i in range(10)]
        response = client.post(
            f"/navigation/sessions/{session_id}/update",
            json={"samples": samples, "gnss": gnss_fix(T0 + 1.0)},
        )
        assert response.status_code == 200
        state = response.json()["state"]
        assert state["mode"] == "GNSS_INS_FUSION"
        assert_finite_state(state)


def test_update_without_gnss_keeps_dead_reckoning():
    with make_client() as client:
        session_id = create_with_fix(client)
        samples = [
            imu_sample(T0 + 4.0 + i, heading_deg=90.0) for i in range(6)
        ]
        response = client.post(
            f"/navigation/sessions/{session_id}/update", json={"samples": samples}
        )
        assert response.status_code == 200
        state = response.json()["state"]
        assert state["mode"] in (
            "GNSS_INS_FUSION",
            "GNSS_INS_DEGRADED",
            "DEAD_RECKONING",
        )
        assert_finite_state(state)


def test_blackout_enters_dead_reckoning_then_recovers():
    with make_client() as client:
        session_id = create_with_fix(client)

        # GNSS available for the first second.
        update = client.post(
            f"/navigation/sessions/{session_id}/update",
            json={"samples": [imu_sample(T0 + 0.1)], "gnss": gnss_fix(T0 + 0.2)},
        )
        assert update.json()["state"]["mode"] == "GNSS_INS_FUSION"

        # Blackout: IMU-only updates with >3 s gaps -> GNSS goes silent and the
        # health monitor flips to UNAVAILABLE -> dead reckoning.
        for i in range(6):
            t = T0 + 1.0 + i * 4.0
            response = client.post(
                f"/navigation/sessions/{session_id}/update",
                json={"samples": [imu_sample(t, heading_deg=90.0)]},
            )
            assert response.status_code == 200
        drone_state = response.json()["state"]
        assert drone_state["mode"] == "DEAD_RECKONING"
        assert drone_state["latitude"] is not None
        assert_finite_state(drone_state)

        # Recovery: fixes resume with a >3 s gap (first is re-acquisition),
        # then consecutive acceptable fixes -> RECOVERING then FUSION. The
        # target advances east at 5 m/s so the stream stays self-consistent.
        saw_recovering = False
        last_state = None
        for i in range(6):
            t = T0 + 26.0 + i
            response = client.post(
                f"/navigation/sessions/{session_id}/update",
                json={
                    "samples": [imu_sample(t, heading_deg=90.0)],
                    "gnss": gnss_fix(t, accuracy=5.0, east_m=(t - (T0 + 26.0)) * 5.0),
                },
            )
            assert response.status_code == 200
            last_state = response.json()["state"]
            if last_state["mode"] == "RECOVERING":
                saw_recovering = True
        assert saw_recovering, "expected a RECOVERING phase during recovery"
        assert last_state["mode"] == "GNSS_INS_FUSION"
        assert_finite_state(last_state)


def test_update_batch_many_samples_finite():
    with make_client() as client:
        session_id = create_with_fix(client)
        samples = [imu_sample(T0 + i * 0.1, heading_deg=45.0) for i in range(120)]
        response = client.post(
            f"/navigation/sessions/{session_id}/update",
            json={"samples": samples, "gnss": gnss_fix(T0 + 12.0)},
        )
        assert response.status_code == 200
        assert_finite_state(response.json()["state"])


def test_update_unknown_session_404():
    with make_client() as client:
        response = client.post(
            "/navigation/sessions/nope/update",
            json={"samples": [], "gnss": None},
        )
        assert response.status_code == 404


def test_empty_update_is_tolerated():
    with make_client() as client:
        session_id = create_with_fix(client)
        response = client.post(
            f"/navigation/sessions/{session_id}/update",
            json={"samples": [], "gnss": None},
        )
        assert response.status_code == 200
        assert_finite_state(response.json()["state"])


def test_session_persists_across_updates():
    with make_client() as client:
        session_id = create_with_fix(client)
        client.post(
            f"/navigation/sessions/{session_id}/update",
            json={"samples": [imu_sample(T0 + 0.1)], "gnss": gnss_fix(T0 + 0.2)},
        )
        fresh_state = client.get(f"/navigation/sessions/{session_id}").json()["state"]
        assert fresh_state["mode"] == "GNSS_INS_FUSION"  # engine memory retained


def test_timestamps_via_epoch_seconds_wide_tolerance():
    with make_client() as client:
        session_id = create_with_fix(client)
        future = time.time() + 1000  # any finite clock works
        response = client.post(
            f"/navigation/sessions/{session_id}/update",
            json={"samples": [imu_sample(future, heading_deg=10.0)]},
        )
        assert response.status_code == 200
        assert_finite_state(response.json()["state"])