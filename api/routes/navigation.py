"""Navigation session endpoints — the runtime surface the mobile app uses.

A session is created from the first known GNSS fix, then fed with periodic
batches of IMU samples plus the latest GNSS fix. The response is always the
engine's current navigation estimate (never fabricated).
"""

from __future__ import annotations

import logging
import math

from fastapi import APIRouter, Depends, HTTPException, Response, status

from api.dependencies import get_session_manager
from api.navigation_adapter import NavigationSessionAdapter
from api.schemas import (
    CreateSessionRequest,
    NavigationStateResponse,
    SessionCreatedResponse,
    SessionStateResponse,
    UpdateRequest,
)
from api.session_manager import (
    NavigationSessionManager,
    SessionLimitExceededError,
    SessionNotFoundError,
)
from src.navigation.interfaces.messages import (
    GNSSSample,
    IMUSample,
)

logger = logging.getLogger("api.navigation")

router = APIRouter(prefix="/navigation", tags=["navigation"])


def _to_imu_messages(update: UpdateRequest) -> list[IMUSample]:
    """Convert request DTOs into the engine's IMUSample messages."""
    samples: list[IMUSample] = []
    for sample in update.samples:
        mag = sample.magnetometer
        heading_rad = None
        if sample.headingDeg is not None and math.isfinite(float(sample.headingDeg)):
            heading_rad = math.radians(float(sample.headingDeg))
        samples.append(
            IMUSample(
                timestamp=float(sample.timestamp),
                accelerometer=(sample.accelerometer.x, sample.accelerometer.y, sample.accelerometer.z),
                gyroscope=(sample.gyroscope.x, sample.gyroscope.y, sample.gyroscope.z),
                magnetometer=(mag.x, mag.y, mag.z) if mag else None,
                heading_rad=heading_rad,
            )
        )
    return samples


def _to_gnss_message(gnss) -> GNSSSample | None:
    if gnss is None:
        return None
    heading_rad = None
    if gnss.headingDeg is not None and math.isfinite(float(gnss.headingDeg)):
        heading_rad = math.radians(float(gnss.headingDeg))
    return GNSSSample(
        timestamp=float(gnss.timestamp),
        latitude=float(gnss.latitude),
        longitude=float(gnss.longitude),
        accuracy=float(gnss.accuracy),
        speed=float(gnss.speedMps) if gnss.speedMps is not None else None,
        heading=heading_rad,
    )


@router.post(
    "/sessions",
    response_model=SessionCreatedResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_session(
    payload: CreateSessionRequest,
    manager: NavigationSessionManager = Depends(get_session_manager),
) -> SessionCreatedResponse:
    try:
        adapter = manager.create(
            latitude=payload.latitude,
            longitude=payload.longitude,
            accuracy=payload.accuracy,
            heading_deg=payload.headingDeg,
        )
    except SessionLimitExceededError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error
    return SessionCreatedResponse(
        sessionId=adapter.session_id,
        state=NavigationStateResponse.from_state_dict(adapter.state_dict()),
    )


@router.get("/sessions", response_model=list[str])
def list_sessions(
    manager: NavigationSessionManager = Depends(get_session_manager),
) -> list[str]:
    return manager.list_ids()


@router.get("/sessions/{session_id}", response_model=SessionStateResponse)
def get_session(
    session_id: str,
    manager: NavigationSessionManager = Depends(get_session_manager),
) -> SessionStateResponse:
    adapter = _find_or_404(session_id, manager)
    return SessionStateResponse(
        sessionId=adapter.session_id,
        state=NavigationStateResponse.from_state_dict(adapter.state_dict()),
    )


@router.post("/sessions/{session_id}/update", response_model=SessionStateResponse)
def update_session(
    session_id: str,
    payload: UpdateRequest,
    manager: NavigationSessionManager = Depends(get_session_manager),
) -> SessionStateResponse:
    adapter = _find_or_404(session_id, manager)
    imu_samples = _to_imu_messages(payload)
    gnss = _to_gnss_message(payload.gnss)

    try:
        state = manager.update(session_id, imu_samples, gnss)
    except Exception as error:  # noqa: BLE001 - sanitised server-side failure
        logger.error("session %s update failed: %s", session_id, error)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Navigation update failed. Please retry.",
        ) from error

    return SessionStateResponse(
        sessionId=adapter.session_id,
        state=NavigationStateResponse.from_state_dict(state),
    )


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(
    session_id: str,
    manager: NavigationSessionManager = Depends(get_session_manager),
) -> Response:
    if not manager.delete(session_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"session {session_id} not found",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _find_or_404(
    session_id: str,
    manager: NavigationSessionManager,
) -> NavigationSessionAdapter:
    try:
        return manager.get(session_id)
    except SessionNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error