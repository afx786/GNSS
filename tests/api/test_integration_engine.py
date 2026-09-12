"""Engine integration tests — real IDREngine construction and behaviour.

Requirement: the API adapter must drive the *actual* navigation engine, not a
mock. These tests build a real ``NavigationSessionAdapter`` and assert engine
behaviour end-to-end (GNSS fusion mode, blackout drift, recovery, finite JSON).
"""

from __future__ import annotations

import json
import math

from api.config import repo_root
from api.navigation_adapter import (
    NavigationSessionAdapter,
    build_ml_inference_for_api,
)
from api.schemas import NavigationStateResponse
from src.navigation.engine.model_interface import (
    FallbackMLInference,
    TrainedMLInference,
)
from src.navigation.interfaces.messages import GNSSSample, IMUSample

T0 = 1_600_000_000.0

#: Config with ML explicitly disabled and map matching off: exercises the real
#: EKF engine without loading heavyweight models.
CLASSICAL_CONFIG = {
    "engine": {
        "apply_non_holonomic": True,
        "apply_zupt": True,
        "map_matching": {"enabled": False},
    },
    "ml": {"enabled": False},
}


def imu(t: float, heading_deg: float | None = 90.0) -> IMUSample:
    return IMUSample(
        timestamp=t,
        accelerometer=(0.0, 0.0, 9.8),
        gyroscope=(0.0, 0.0, 0.05),
        magnetometer=(20.0, 0.0, -30.0),
        heading_rad=math.radians(heading_deg) if heading_deg is not None else None,
    )


def gnss(t: float, accuracy: float = 3.0, east_m: float = 0.0) -> GNSSSample:
    """GNSS fix; ``east_m`` shifts the longitude so the fix stream stays
    consistent with a constant ~5 m/s speed estimate."""
    return GNSSSample(
        timestamp=t,
        latitude=25.0782,
        longitude=55.1321 + east_m / 111_320.0,
        accuracy=accuracy,
        speed=5.0,
        heading=math.radians(90.0),
    )


def make_adapter(session_id: str = "integration-1") -> NavigationSessionAdapter:
    return NavigationSessionAdapter(
        session_id=session_id,
        initial_latitude=25.0782,
        initial_longitude=55.1321,
        initial_accuracy=3.0,
        initial_heading_deg=90.0,
        config=CLASSICAL_CONFIG,
        ml_inference=FallbackMLInference(),
    )


def json_safe(state) -> bool:
    return not any(k in json.dumps(state) for k in ("NaN", "Infinity"))


def test_initialization_then_gnss_fusion():
    adapter = make_adapter()
    state = adapter.state_dict()
    assert state["mode"] == "DEAD_RECKONING"
    assert abs(state["latitude"] - 25.0782) < 1e-6

    for i in range(10):
        t = T0 + i * 0.1
        adapter.update([imu(t)], gnss(t))
    state = adapter.state_dict()
    assert state["mode"] == "GNSS_INS_FUSION"
    assert json_safe(state)


def test_blackout_switches_to_dead_reckoning_and_rebounds_after_recovery():
    adapter = make_adapter()
    adapter.update([imu(T0)], gnss(T0))
    assert adapter.state_dict()["mode"] == "GNSS_INS_FUSION"

    # Sustained GNSS blackout (gaps > 3 s trip the health monitor) ->
    # DEAD_RECKONING, still geo-referenced, confidence decaying.
    confidence_before = adapter.state_dict()["confidence"]
    for i in range(1, 10):
        adapter.update([imu(T0 + i * 4.0)], None)
    dead = adapter.state_dict()
    assert dead["mode"] == "DEAD_RECKONING"
    assert dead["latitude"] is not None
    assert dead["confidence"] <= confidence_before + 1e-9
    assert json_safe(dead)

    # Recovery: a run of acceptable fixes flips to RECOVERING then FUSION.
    # The target advances east at 5 m/s so the stream is physically
    # consistent with the engine's speed estimate.
    recovery_start = T0 + 40.0
    phases = []
    for i in range(1, 10):
        t = recovery_start + i
        adapter.update([imu(t)], gnss(t, accuracy=5.0, east_m=(i - 1) * 5.0))
        phases.append(adapter.state_dict()["mode"])
    assert "RECOVERING" in phases, f"expected RECOVERING, got {phases}"
    assert phases[-1] == "GNSS_INS_FUSION"
    final = adapter.state_dict()
    assert final["confidence"] > 0.0
    assert json_safe(final)


def test_state_response_is_always_json_safe():
    adapter = make_adapter()
    for i in range(60):
        adapter.update([imu(T0 + i * 0.5)], gnss(T0 + i * 0.5) if i % 2 == 0 else None)
    response = NavigationStateResponse.from_state_dict(adapter.state_dict())
    as_json = response.model_dump()
    assert json_safe(as_json)
    assert "mode" in as_json


def test_closed_session_is_reset():
    adapter = make_adapter("close-me")
    adapter.close()
    state = adapter.state_dict()
    assert state["mode"] == "UNINITIALIZED"


def test_real_model_artifacts_present_and_loadable():
    """The runtime ML build must produce a real TrainedMLInference locally."""
    inference = build_ml_inference_for_api(repo_root(), "models")
    assert isinstance(inference, TrainedMLInference)
    assert inference.available


def test_missing_model_directory_falls_back_without_crashing():
    inference = build_ml_inference_for_api(repo_root(), "models__does_not_exist")
    assert isinstance(inference, FallbackMLInference)