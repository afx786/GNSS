"""IDREngine - public navigation backend facade (D-S11).

The engine consumes sensor-sample messages and optional ML outputs
(``navigation/interfaces/messages.py``) and produces a ``NavigationState``
with position, velocity, heading, mode and confidence, plus a JSON-style
dict via ``get_state_dict()``.

Owns:
    * ``GNSSINSFusion``    (filter + GNSS health + ENU origin)  [D-S3..D-S6]
    * ``MapMatcher``       (road network constraints)           [D-S8]
    * ``ConfidenceEstimator``                                    [D-S10]
    * an optional ``MLInference``                               [D-S7]
"""

from __future__ import annotations

import math

from src.navigation.core.math_utils import LocalENU
from src.navigation.core.sensor_transform import phone_to_navigation_2d
from src.navigation.interfaces.messages import (
    GNSSSample,
    IMUSample,
    MLNavigationOutput,
    NavigationState,
)
from src.navigation.ins.orientation import OrientationEstimator
from src.navigation.fusion.ekf import EKF
from src.navigation.fusion.gnss_ins_fusion import GNSSINSFusion
from src.navigation.health.gnss_health import GNSSHealthMonitor, GNSSMode
from src.navigation.constraints.non_holonomic import NonHolonomicConstraint
from src.navigation.map_matching.map_matcher import MapMatcher
from src.navigation.confidence.confidence import ConfidenceEstimator
from src.navigation.engine.model_interface import FallbackMLInference, MLInference

HEADING_STD_RAD = 0.3


class IDREngine:
    """Public facade for the Phase 1 intelligent dead-reckoning backend."""

    def __init__(
        self,
        fusion: GNSSINSFusion | None = None,
        map_matcher: MapMatcher | None = None,
        confidence: ConfidenceEstimator | None = None,
        constraints: NonHolonomicConstraint | None = None,
        ml_inference: MLInference | None = None,
        map_match_std_m: float = 3.0,
    ):
        self.fusion = fusion or GNSSINSFusion()
        self.map_matcher = map_matcher or MapMatcher()
        self.confidence = confidence or ConfidenceEstimator()
        self.constraints = constraints or NonHolonomicConstraint()
        self.ml_inference = ml_inference or FallbackMLInference()
        self.map_match_std_m = float(map_match_std_m)

        self.orientation = OrientationEstimator()
        self.initialized = False
        self.last_imu_timestamp: float | None = None
        self.last_gnss_timestamp: float | None = None
        self.mode = "UNINITIALIZED"
        self._state = NavigationState()
        self._ml_position_error_m: float | None = None
        # D-S10: corroboration from map matching. Set to 1.0 on every
        # successful road snap; decays exponentially (tau = 30 s) so stale
        # matches stop supporting the confidence estimate.
        self._map_support = 0.0
        self._map_support_time: float | None = None
        self.map_support_tau_s = 30.0

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #

    def reset(self) -> None:
        self.fusion.reset()
        self.initialized = False
        self.last_imu_timestamp = None
        self.last_gnss_timestamp = None
        self.mode = "UNINITIALIZED"
        self._state = NavigationState()
        self._ml_position_error_m = None
        self._map_support = 0.0
        self._map_support_time = None

    def initialize(
        self,
        latitude: float | None = None,
        longitude: float | None = None,
        heading_rad: float = 0.0,
    ) -> "NavigationState":
        self.fusion.initialize(latitude, longitude, heading_rad)
        self.initialized = True
        self.mode = "DEAD_RECKONING"
        self._refresh_state(self.last_imu_timestamp or 0.0)
        return self.get_state()

    def _ensure_initialized(self, gnss: GNSSSample | None = None) -> None:
        if self.initialized:
            return
        if gnss is not None:
            self.fusion.initialize(
                gnss.latitude, gnss.longitude, gnss.heading or 0.0
            )
        else:
            self.fusion.initialize()
        self.initialized = True

    # ------------------------------------------------------------------ #
    # Runtime updates
    # ------------------------------------------------------------------ #

    def update_imu(self, sample: IMUSample) -> "NavigationState":
        self._ensure_initialized()

        if self.last_imu_timestamp is None:
            dt = 0.0
        else:
            dt = sample.timestamp - self.last_imu_timestamp
        self.last_imu_timestamp = sample.timestamp

        if dt > 0.0:
            gyro_z = float(sample.gyroscope[2])

            # Optional external compass heading (e.g. from magnetometer or
            # upstream preprocessing) is applied as a measurement first.
            if sample.heading_rad is not None:
                self.fusion.filter.update_heading(
                    float(sample.heading_rad), HEADING_STD_RAD
                )

            if sample.linear_acceleration_enu is not None:
                accel_enu = sample.linear_acceleration_enu
            else:
                heading = self.fusion.filter.heading_rad
                ax, ay = sample.accelerometer[0], sample.accelerometer[1]
                accel_enu = phone_to_navigation_2d(ax, ay, heading)

            self.mode = self.fusion.predict_imu(
                accel_enu, gyro_z, dt, timestamp=sample.timestamp
            )

        self._refresh_state(sample.timestamp)
        return self.get_state()

    def update_gnss(self, sample: GNSSSample) -> "NavigationState":
        self._ensure_initialized(sample)

        self.mode, _accepted, _innovation = self.fusion.update_gnss(
            latitude=sample.latitude,
            longitude=sample.longitude,
            accuracy=sample.accuracy,
            timestamp=sample.timestamp,
            speed=sample.speed,
            heading=sample.heading,
        )
        self.last_gnss_timestamp = sample.timestamp

        self._refresh_state(sample.timestamp)
        return self.get_state()

    def update_ml(self, output: MLNavigationOutput) -> "NavigationState":
        """Feed Tanishk's ML outputs (D-S7) into the filter."""
        self._ensure_initialized()
        self.fusion.update_ml(
            speed_mps=output.speed_mps,
            speed_std_mps=output.speed_std_mps,
            heading_rad=output.heading_rad,
            heading_std_rad=output.heading_std_rad,
            accel_correction_enu=output.accel_correction_enu,
            accel_correction_std_mps2=output.accel_correction_std_mps2,
        )
        # D-T5: predict navigation error floor used by confidence/error report.
        self._ml_position_error_m = output.position_error_m
        self._refresh_state(output.timestamp)
        return self.get_state()

    # ------------------------------------------------------------------ #
    # Constraints & map matching
    # ------------------------------------------------------------------ #

    def apply_non_holonomic_constraint(
        self, lateral_std_mps: float = 0.5
    ) -> "NavigationState":
        self.fusion.apply_lateral_constraint(lateral_std_mps)
        self._refresh_state(self._state.timestamp)
        return self.get_state()

    def apply_zupt(self) -> "NavigationState":
        self.fusion.apply_zupt()
        self._refresh_state(self._state.timestamp)
        return self.get_state()

    def update_map_match(
        self,
        candidates=None,
        std_m: float | None = None,
    ) -> "NavigationState":
        """Correct the solution using the nearest plausible road.

        ``candidates`` are optional ``RoadCandidate`` instances; when omitted
        the configured ``MapMatcher`` generates them from its road graph.
        """
        matched = self.map_matcher.match(
            self._state.east_m,
            self._state.north_m,
            self._state.heading_rad,
            candidates,
        )
        if matched is not None:
            self.fusion.re_localize(
                matched.east_m,
                matched.north_m,
                std_m if std_m is not None else self.map_match_std_m,
            )
            self._map_support = 1.0
            self._map_support_time = self._state.timestamp
        self._refresh_state(self._state.timestamp)
        return self.get_state()

    def update_ml_and_fuse(
        self,
        output: MLNavigationOutput,
        sample: IMUSample | None = None,
    ) -> "NavigationState":
        """Convenience: apply ML corrections then a map-matched update."""
        self.update_ml(output)
        if sample is not None:
            self.update_imu(sample)
        if self.map_matcher is not None:
            self.update_map_match()
        return self.get_state()

    # ------------------------------------------------------------------ #
    # Output
    # ------------------------------------------------------------------ #

    def get_state(self) -> NavigationState:
        return self._state

    def get_state_dict(self) -> dict:
        """JSON-style state per the D-S11 engine API spec."""
        s = self._state
        return {
            "timestamp": float(s.timestamp),
            "latitude": s.latitude,
            "longitude": s.longitude,
            "velocity": float(
                math.hypot(s.velocity_east_mps, s.velocity_north_mps)
            ),
            "heading": float(s.heading_rad),
            "confidence": float(s.confidence),
            "position_error": float(s.position_error_m),
            "mode": str(s.mode),
            "east_m": float(s.east_m),
            "north_m": float(s.north_m),
            "velocity_east_mps": float(s.velocity_east_mps),
            "velocity_north_mps": float(s.velocity_north_mps),
        }

    def _refresh_state(self, timestamp: float) -> None:
        s = self.fusion.to_state(timestamp)
        # Baseline position error comes from the filter covariance; a learned
        # D-T5 floor may raise it (never lower it) to reflect predicted
        # outage drift.
        base_error = self.fusion.filter.position_std_m
        if self._ml_position_error_m is not None and self._ml_position_error_m >= 0.0:
            s.position_error_m = max(base_error, float(self._ml_position_error_m))
        else:
            s.position_error_m = base_error
        support = 0.0
        if self._map_support_time is not None:
            age = max(float(timestamp) - float(self._map_support_time), 0.0)
            support = self._map_support * math.exp(
                -age / max(self.map_support_tau_s, 1e-6)
            )
        s.confidence = self.confidence.estimate(
            s.position_error_m,
            self.mode,
            gnss_age_s=self.fusion.gnss_age(timestamp),
            support=support,
        )
        s.mode = self.mode
        self._state = s

    @property
    def state(self) -> NavigationState:
        return self._state