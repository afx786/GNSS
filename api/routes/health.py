"""Health / readiness endpoints.

These never run model inference — they only report service reachability and
artifact availability (a fast filesystem check).
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends

from api.config import Settings, repo_root
from api.dependencies import get_settings
from api.schemas import (
    HealthResponse,
    ModelStatus,
    ModelsHealthResponse,
)

router = APIRouter(tags=["health"])


def _artifact_status(settings: Settings) -> list[ModelStatus]:
    model_dir = Path(settings.model_directory)
    if not model_dir.is_absolute():
        model_dir = repo_root() / model_dir

    candidates = [
        ("speed-lstm", ("speed_lstm.pt", "speed_lstm_scaler.npz")),
        ("speed-gru", ("speed_gru.pt", "speed_gru_scaler.npz")),
        ("speed-tcn", ("speed_tcn.pt", "speed_tcn_scaler.npz")),
        ("vibration-classifier", ("vibration_classifier.joblib",)),
        ("imu-correction", ("imu_correction.joblib",)),
        ("error-model", ("error_model.joblib",)),
    ]
    statuses: list[ModelStatus] = []
    for name, files in candidates:
        available = all((model_dir / file).exists() for file in files)
        statuses.append(ModelStatus(name=name, available=available))
    return statuses


@router.get("/health", response_model=HealthResponse)
def health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    return HealthResponse(
        status="ok",
        environment=settings.environment,
        version="1.0.0",
    )


@router.get("/health/models", response_model=ModelsHealthResponse)
def health_models(settings: Settings = Depends(get_settings)) -> ModelsHealthResponse:
    return ModelsHealthResponse(status="ok", models=_artifact_status(settings))


@router.get("/ready")
def ready() -> dict:
    return {"status": "ready"}