"""D-S11 API + D-S8/D-S9/D-S10 runtime wiring tests."""

import math

import pytest

from src.engine.navigation_interface import (
    NavigationEngine,
    magnetometer_to_heading,
)
from src.navigation.interfaces.messages import MLNavigationOutput
from src.navigation.map_matching.road_candidate import RoadCandidate

LAT0, LON0 = 52.5, -1.9
STATIC_ACC = (0.0, 0.0, 9.81)
ZERO_GYRO = (0.0, 0.0, 0.0)


@pytest.fixture
def api():
    return NavigationEngine(auto_map_match=False)


def test_spec_state_keys(api):
    api.initialize(LAT0, LON0)
    api.update_imu(STATIC_ACC, ZERO_GYRO, None, 0.1,
                   linear_acceleration_enu=(0.0, 0.0))
    s = api.update_gnss(LAT0, LON0, 3.0, 5.0, 0.2)
    for key in ("latitude", "longitude", "velocity", "heading",
                "confidence", "position_error", "mode"):
        assert key in s, key
    assert s["latitude"] == pytest.approx(LAT0, abs=1e-6)
    assert s["mode"] == "GNSS_INS_FUSION"
    assert math.isfinite(s["confidence"]) and 0.0 <= s["confidence"] <= 1.0
    assert math.isfinite(s["position_error"]) and s["position_error"] >= 0.0


def test_confidence_degrades_then_recovers():
    api = NavigationEngine(auto_map_match=False)
    api.initialize(LAT0, LON0)
    api.update_gnss(LAT0, LON0, 3.0, 5.0, 0.0)
    early = api.get_state()
    t = 0.0
    for _ in range(600):  # 60 s outage, static
        t += 0.1
        api.update_imu(STATIC_ACC, ZERO_GYRO, None, t,
                       linear_acceleration_enu=(0.0, 0.0))
    late = api.get_state()
    assert late["mode"] == "DEAD_RECKONING"
    assert late["confidence"] < early["confidence"]
    assert late["position_error"] > early["position_error"]
    recovered = api.update_gnss(LAT0, LON0, 3.0, 5.0, t + 0.1)
    # First post-outage fix lands in RECOVERING (recovery latch); a few
    # converging fixes bring it back to full fusion.
    assert recovered["mode"] in ("RECOVERING", "GNSS_INS_FUSION")
    assert recovered["confidence"] > late["confidence"]
    for i in range(2, 7):
        s = api.update_gnss(LAT0, LON0, 3.0, 5.0, t + 0.1 * i)
    assert s["mode"] == "GNSS_INS_FUSION"


def test_lateral_constraint_reduces_sideways_drift():
    constrained = NavigationEngine(auto_map_match=False,
                                   apply_constraints=True)
    free = NavigationEngine(auto_map_match=False, apply_constraints=False)
    for api in (constrained, free):
        api.initialize()
    t = 0.0
    for _ in range(20):  # 2 s of pure-east acceleration, heading north
        t += 0.1
        for api in (constrained, free):
            api.update_imu(STATIC_ACC, ZERO_GYRO, None, t,
                           linear_acceleration_enu=(3.0, 0.0))
    vc = constrained.engine.get_state().velocity_east_mps
    vf = free.engine.get_state().velocity_east_mps
    assert vf > 0.0  # sanity: the push actually moved the free solution
    assert abs(vc) < abs(vf)


def test_magnetometer_heading():
    h = magnetometer_to_heading(STATIC_ACC, (0.0, 40.0, 10.0))
    assert h is not None and abs(h) < 0.2
    assert magnetometer_to_heading((0.0, 0.0, 0.0), (1.0, 2.0, 3.0)) is None
    assert magnetometer_to_heading(STATIC_ACC, (0.0, 0.0, 0.0)) is None
    # Opt-in compass aid runs without crashing and keeps a finite state.
    api = NavigationEngine(auto_map_match=False, use_magnetometer=True)
    api.initialize(LAT0, LON0)
    s = api.update_imu(STATIC_ACC, ZERO_GYRO, (0.0, 40.0, 10.0), 0.1,
                       linear_acceleration_enu=(0.0, 0.0))
    assert math.isfinite(s["heading"])


def test_map_match_without_graph_is_noop(api):
    api.initialize(LAT0, LON0)
    before = api.get_state()
    after = api.update_map_match()
    assert after["latitude"] == pytest.approx(before["latitude"])
    assert after["mode"] == before["mode"]


def test_teleport_guard_rejects_far_match(api):
    api.initialize(LAT0, LON0)
    st = api.engine.get_state()
    far = [RoadCandidate("r1", st.east_m + 10000.0, st.north_m, 0.0, 10000.0)]
    s_far = api.update_map_match(candidates=far)
    st2 = api.engine.get_state()
    assert st2.east_m == pytest.approx(st.east_m, abs=1e-9)

    near = [RoadCandidate("r2", st.east_m + 2.0, st.north_m, 0.0, 2.0)]
    api.update_map_match(candidates=near)
    st3 = api.engine.get_state()
    assert st3.east_m > st.east_m  # plausible snap is applied


def test_ml_passthrough(api):
    api.initialize(LAT0, LON0)
    s = api.update_ml(MLNavigationOutput(timestamp=0.1, speed_mps=0.0,
                                         speed_std_mps=0.2))
    assert math.isfinite(s["velocity"])
    assert 0.0 <= s["confidence"] <= 1.0


def test_zupt_opt_in_runs(api):
    api_z = NavigationEngine(auto_map_match=False, use_zupt=True)
    api_z.initialize(LAT0, LON0)
    s = api_z.update_imu(STATIC_ACC, ZERO_GYRO, None, 0.1,
                         linear_acceleration_enu=(0.0, 0.0))
    assert math.isfinite(s["velocity"])
