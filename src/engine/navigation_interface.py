"""Standalone navigation engine API (D-S11).

Clean backend interface over :class:`IDREngine`:

    engine.initialize(...)
    engine.update_imu(accelerometer, gyroscope, magnetometer, timestamp)
    engine.update_gnss(latitude, longitude, accuracy, speed, timestamp)
    state = engine.get_state()

``get_state()`` returns ``{latitude, longitude, velocity, heading,
confidence, position_error, mode}`` (+ ``timestamp``).

Beyond raw delegation this layer wires the remaining deliverables into the
runtime path:

* D-S9  - the lateral (non-holonomic) velocity constraint is applied after
  every IMU propagation; an optional ZUPT fires when the filtered speed is
  below ``zupt_speed_mps``. Map-match corrections that would teleport the
  solution beyond ``plausible_position_step_m`` are rejected.
* D-S8  - during ``DEAD_RECKONING`` the road network is consulted
  (throttled to ``map_match_interval_s``); a no-graph matcher is a safe
  no-op.
* D-S10 - confidence comes from ``IDREngine`` (filter covariance + outage
  degradation + map-match support); nothing extra is needed here.
* D-S7  - ``update_ml`` forwards Tanishk's ``MLNavigationOutput``.
"""

from __future__ import annotations

import math
from typing import Optional, Sequence

from src.navigation.constraints.non_holonomic import NonHolonomicConstraint
from src.navigation.engine.idr_engine import IDREngine
from src.navigation.interfaces.messages import (
    GNSSSample,
    IMUSample,
    MLNavigationOutput,
)


def magnetometer_to_heading(
    accelerometer: Sequence[float],
    magnetometer: Sequence[float],
) -> Optional[float]:
    """Tilt-compensated magnetic heading (rad, clockwise from North).

    Returns a *device-frame* heading: it equals the navigation heading only
    when the device yaw is aligned with the vehicle (mounted phone). Returns
    ``None`` when either vector is unusable (non-finite, near-zero field, or
    acceleration far from 1 g so the gravity reference is untrustworthy).
    """
    try:
        ax, ay, az = (float(v) for v in accelerometer)
        mx, my, mz = (float(v) for v in magnetometer)
    except (TypeError, ValueError):
        return None
    vals = (ax, ay, az, mx, my, mz)
    if not all(math.isfinite(v) for v in vals):
        return None

    g_norm = math.sqrt(ax * ax + ay * ay + az * az)
    if g_norm < 7.0 or g_norm > 12.0:  # need a usable gravity reference
        return None
    gx, gy, gz = -ax / g_norm, -ay / g_norm, -az / g_norm

    dot = mx * gx + my * gy + mz * gz
    hx, hy, hz = mx - dot * gx, my - dot * gy, mz - dot * gz
    h_norm = math.sqrt(hx * hx + hy * hy + hz * hz)
    if h_norm < 1e-6:
        return None
    hx, hy = hx / h_norm, hy / h_norm
    # Device +y is "forward": heading clockwise from forward axis.
    return math.atan2(-hx, hy)


class NavigationEngine:
    """Spec-compliant facade for the navigation backend (D-S11)."""

    def __init__(
        self,
        engine: IDREngine | None = None,
        apply_constraints: bool = True,
        lateral_std_mps: float = 0.5,
        use_zupt: bool = False,
        zupt_speed_mps: float = 0.3,
        auto_map_match: bool = True,
        map_match_interval_s: float = 5.0,
        map_match_std_m: float | None = None,
        use_magnetometer: bool = False,
        mag_heading_std_rad: float = 0.5,
    ):
        self.engine = engine if engine is not None else IDREngine()
        self.apply_constraints = bool(apply_constraints)
        self.lateral_std_mps = float(lateral_std_mps)
        self.use_zupt = bool(use_zupt)
        self.zupt_speed_mps = float(zupt_speed_mps)
        self.auto_map_match = bool(auto_map_match)
        self.map_match_interval_s = float(map_match_interval_s)
        self.map_match_std_m = map_match_std_m
        self.use_magnetometer = bool(use_magnetometer)
        # A weak default: phone magnetometers are usually uncalibrated.
        self.mag_heading_std_rad = float(mag_heading_std_rad)
        self._last_map_match_t: float | None = None

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #

    def reset(self) -> dict:
        self.engine.reset()
        self._last_map_match_t = None
        return self.get_state()

    def initialize(
        self,
        latitude: float | None = None,
        longitude: float | None = None,
        heading: float = 0.0,
    ) -> dict:
        self.engine.initialize(latitude, longitude, float(heading))
        self._last_map_match_t = None
        return self.get_state()

    # ------------------------------------------------------------------ #
    # Runtime updates
    # ------------------------------------------------------------------ #

    def update_imu(
        self,
        accelerometer: Sequence[float],
        gyroscope: Sequence[float],
        magnetometer: Sequence[float] | None,
        timestamp: float,
        linear_acceleration_enu: Sequence[float] | None = None,
    ) -> dict:
        """Feed one IMU sample; returns the state dict."""
        sample = IMUSample(
            timestamp=float(timestamp),
            accelerometer=tuple(float(v) for v in accelerometer),
            gyroscope=tuple(float(v) for v in gyroscope),
            magnetometer=(
                tuple(float(v) for v in magnetometer)
                if magnetometer is not None
                else None
            ),
            linear_acceleration_enu=(
                tuple(float(v) for v in linear_acceleration_enu)
                if linear_acceleration_enu is not None
                else None
            ),
        )
        self.engine.update_imu(sample)

        if self.use_magnetometer and magnetometer is not None:
            mag_heading = magnetometer_to_heading(
                accelerometer, magnetometer
            )
            if mag_heading is not None:
                # Weak compass aid (D-S7 measurement path honours its std).
                self.engine.update_ml(
                    MLNavigationOutput(
                        timestamp=float(timestamp),
                        heading_rad=mag_heading,
                        heading_std_rad=self.mag_heading_std_rad,
                    )
                )

        if self.apply_constraints:
            # D-S9: lateral velocity stays small; applied weakly every step.
            self.engine.apply_non_holonomic_constraint(self.lateral_std_mps)
            if self.use_zupt:
                s = self.engine.get_state()
                speed = math.hypot(
                    s.velocity_east_mps, s.velocity_north_mps
                )
                if speed < self.zupt_speed_mps:
                    self.engine.apply_zupt()

        if (
            self.auto_map_match
            and self.engine.mode == "DEAD_RECKONING"
            and self._map_match_due(float(timestamp))
        ):
            self.update_map_match()

        return self.get_state()

    def update_gnss(
        self,
        latitude: float,
        longitude: float,
        accuracy: float,
        speed: float | None,
        timestamp: float,
        heading: float | None = None,
    ) -> dict:
        """Feed one GNSS fix; returns the state dict."""
        self.engine.update_gnss(
            GNSSSample(
                timestamp=float(timestamp),
                latitude=float(latitude),
                longitude=float(longitude),
                accuracy=float(accuracy),
                speed=None if speed is None else float(speed),
                heading=None if heading is None else float(heading),
            )
        )
        return self.get_state()

    def update_ml(self, output: MLNavigationOutput) -> dict:
        """Feed Tanishk's ML outputs (D-S7); returns the state dict."""
        self.engine.update_ml(output)
        return self.get_state()

    def update_map_match(
        self,
        candidates=None,
        std_m: float | None = None,
    ) -> dict:
        """Snap to the road network unless it would teleport (D-S8 + D-S9)."""
        state = self.engine.get_state()
        matched = self.engine.map_matcher.match(
            state.east_m,
            state.north_m,
            state.heading_rad,
            candidates,
        )
        if matched is not None and not self._is_teleport(state, matched):
            self.engine.update_map_match(
                candidates=[matched],
                std_m=std_m if std_m is not None else self.map_match_std_m,
            )
            self._last_map_match_t = state.timestamp
        return self.get_state()

    # ------------------------------------------------------------------ #
    # Output
    # ------------------------------------------------------------------ #

    def get_state(self) -> dict:
        """``{latitude, longitude, velocity, heading, confidence,
        position_error, mode}`` (+ ``timestamp``)."""
        s = self.engine.get_state()
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
        }

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _map_match_due(self, timestamp: float) -> bool:
        if self._last_map_match_t is None:
            return True
        return (
            timestamp - self._last_map_match_t
        ) >= self.map_match_interval_s

    def _is_teleport(self, state, matched) -> bool:
        """D-S9: the vehicle cannot jump between distant road positions."""
        speed = math.hypot(state.velocity_east_mps, state.velocity_north_mps)
        if self._last_map_match_t is None:
            dt = self.map_match_interval_s
        else:
            dt = max(state.timestamp - self._last_map_match_t, 0.0)
        # Allow the matcher radius as slack on top of the kinematic bound.
        slack = max(
            self.engine.map_matcher.candidate_radius_m,
            NonHolonomicConstraint.plausible_position_step_m(0.0, 0.0),
        )
        max_jump = (
            NonHolonomicConstraint.plausible_position_step_m(speed, dt)
            + slack
        )
        return NonHolonomicConstraint.is_teleport(
            state.east_m,
            state.north_m,
            matched.east_m,
            matched.north_m,
            max_jump,
        )
