"""Pydantic request/response models for the navigation HTTP API.

Field names are camelCase on the wire to match the TypeScript client.
Numbers that are non-finite (``NaN``/``inf``) are never serialised into
responses — they are replaced with ``None`` by the response builders.
"""

from __future__ import annotations

import math
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.navigation.interfaces.messages import NavigationState

#: Navigation modes the engine reports, as documented by D-S11.
NAVIGATION_MODES = (
    "UNINITIALIZED",
    "DEAD_RECKONING",
    "GNSS_INS_FUSION",
    "GNSS_INS_DEGRADED",
    "RECOVERING",
)

#: Engine modes that count as a valid (usable) navigation estimate.
VALID_NAVIGATION_MODES = frozenset(
    {"DEAD_RECKONING", "GNSS_INS_FUSION", "GNSS_INS_DEGRADED", "RECOVERING"}
)


def is_finite(value: Optional[float]) -> bool:
    if value is None:
        return False
    return math.isfinite(float(value))


class Vec3(BaseModel):
    model_config = ConfigDict(extra="ignore")

    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    @field_validator("x", "y", "z")
    @classmethod
    def _finite_or_zero(cls, value: float) -> float:
        if not math.isfinite(float(value)):
            return 0.0
        return float(value)


class IMUSampleRequest(BaseModel):
    """One IMU sample (accelerometer + gyroscope + optional magnetometer)."""

    model_config = ConfigDict(extra="ignore")

    timestamp: float
    accelerometer: Vec3
    gyroscope: Vec3
    magnetometer: Optional[Vec3] = None
    headingDeg: Optional[float] = None

    @field_validator("timestamp")
    @classmethod
    def _finite_timestamp(cls, value: float) -> float:
        if not math.isfinite(float(value)):
            raise ValueError("timestamp must be finite")
        return float(value)

    @field_validator("headingDeg")
    @classmethod
    def _finite_heading(cls, value: Optional[float]) -> Optional[float]:
        if value is None or not math.isfinite(float(value)):
            return None
        return float(value) % 360.0


class GNSSSampleRequest(BaseModel):
    """One GNSS fix (EPSG:4326 degrees, WGS84)."""

    model_config = ConfigDict(extra="ignore")

    timestamp: float
    latitude: float = Field(ge=-90.0, le=90.0)
    longitude: float = Field(ge=-180.0, le=180.0)
    accuracy: float = Field(ge=0.0)
    speedMps: Optional[float] = None
    headingDeg: Optional[float] = None

    @field_validator("latitude", "longitude", "accuracy")
    @classmethod
    def _finite_geo(cls, value: float) -> float:
        if not math.isfinite(float(value)):
            raise ValueError("geographic value must be finite")
        return float(value)

    @field_validator("speedMps")
    @classmethod
    def _finite_speed(cls, value: Optional[float]) -> Optional[float]:
        if value is None or not math.isfinite(float(value)):
            return None
        return max(float(value), 0.0)

    @field_validator("headingDeg")
    @classmethod
    def _finite_heading(cls, value: Optional[float]) -> Optional[float]:
        if value is None or not math.isfinite(float(value)):
            return None
        return float(value) % 360.0


class CreateSessionRequest(BaseModel):
    """Initialise a session with the first known GNSS fix.

    A fix is required: the engine needs a position origin before it can
    start dead-reckoning, so sessions cannot be created from nothing.
    """

    model_config = ConfigDict(extra="ignore")

    latitude: float = Field(ge=-90.0, le=90.0)
    longitude: float = Field(ge=-180.0, le=180.0)
    accuracy: float = Field(ge=0.0, default=10.0)
    headingDeg: Optional[float] = None
    timestamp: Optional[float] = None


class UpdateRequest(BaseModel):
    """Per-user navigation update.

    ``samples`` are buffered IMU readings collected since the last update;
    ``gnss`` is the most recent fix (when one is available). Individual GNSS
    fixes are sent on the same channel as IMU batches so each session stays a
    single request/response — the engine merges both streams internally.
    """

    model_config = ConfigDict(extra="ignore")

    samples: list[IMUSampleRequest] = Field(default_factory=list)
    gnss: Optional[GNSSSampleRequest] = None


class NavigationStateResponse(BaseModel):
    """Sanitised navigation estimate (JSON-safe)."""

    model_config = ConfigDict(extra="ignore")

    timestamp: float
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    speedMps: Optional[float] = None
    headingDeg: Optional[float] = None
    confidence: Optional[float] = None
    positionErrorM: Optional[float] = None
    mode: str = "UNINITIALIZED"

    @classmethod
    def from_engine_state(cls, state: NavigationState) -> "NavigationStateResponse":
        def num(value) -> Optional[float]:
            if value is None:
                return None
            value = float(value)
            return value if math.isfinite(value) else None

        heading_rad = state.heading_rad
        heading_deg = None
        if is_finite(heading_rad):
            heading_deg = math.degrees(float(heading_rad) % (2.0 * math.pi))

        speed = None
        if is_finite(state.velocity_east_mps) and is_finite(state.velocity_north_mps):
            speed = math.hypot(
                float(state.velocity_east_mps), float(state.velocity_north_mps)
            )

        return cls(
            timestamp=float(state.timestamp),
            latitude=num(state.latitude),
            longitude=num(state.longitude),
            speedMps=speed,
            headingDeg=heading_deg,
            confidence=num(state.confidence),
            positionErrorM=num(state.position_error_m),
            mode=str(state.mode),
        )

    @classmethod
    def from_state_dict(cls, data: dict) -> "NavigationStateResponse":
        def num(value) -> Optional[float]:
            if value is None:
                return None
            try:
                value = float(value)
            except (TypeError, ValueError):
                return None
            return value if math.isfinite(value) else None

        heading_rad = num(data.get("heading"))
        heading_deg = None
        if heading_rad is not None:
            heading_deg = math.degrees(heading_rad % (2.0 * math.pi))

        return cls(
            timestamp=float(num(data.get("timestamp", 0.0)) or 0.0),
            latitude=num(data.get("latitude")),
            longitude=num(data.get("longitude")),
            speedMps=num(data.get("velocity")),
            headingDeg=heading_deg,
            confidence=num(data.get("confidence")),
            positionErrorM=num(data.get("position_error")),
            mode=str(data.get("mode") or "UNINITIALIZED"),
        )


class SessionCreatedResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    sessionId: str
    state: NavigationStateResponse


class SessionStateResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    sessionId: str
    state: NavigationStateResponse


class ModelStatus(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    available: bool


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    status: str = "ok"
    environment: str
    version: str


class ModelsHealthResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    status: str = "ok"
    models: list[ModelStatus]