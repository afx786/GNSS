"""FastAPI application factory and entrypoint.

Run locally:

    python -m uvicorn api.main:app --host 0.0.0.0 --port 8000

On Railway the ``$PORT`` env var is bound via the Procfile/railway.toml.
"""

from __future__ import annotations

import logging
import math
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api import __version__
from api.config import Settings, load_settings, repo_root
from api.navigation_adapter import (
    NavigationSessionAdapter,
    _build_config,
    build_ml_inference_for_api,
)
from api.routes import health, navigation
from api.session_manager import NavigationSessionManager

logger = logging.getLogger("api")


def _configure_logging(settings: Settings) -> None:
    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def _build_adapter_factory(settings: Settings):
    """Create per-session adapters from the repo engine + ML artifacts."""

    def _factory(
        session_id: str,
        latitude: float,
        longitude: float,
        heading_deg: float | None,
        accuracy: float,
    ) -> NavigationSessionAdapter:
        config = _build_config(
            navigation_config=settings.navigation_config,
            fusion_config=settings.fusion_config,
            map_matching_config=settings.map_matching_config,
        )
        ml_inference = build_ml_inference_for_api(
            repo_root_dir=repo_root(),
            model_directory=settings.model_directory,
        )
        return NavigationSessionAdapter(
            session_id=session_id,
            initial_latitude=latitude,
            initial_longitude=longitude,
            initial_accuracy=accuracy,
            initial_heading_deg=heading_deg,
            config=config,
            ml_inference=ml_inference,
        )

    return _factory


def _sanitize_json(value: Any) -> Any:
    """Recursively replace non-finite floats with ``None``.

    Validation errors echo the raw offending value back to the client; a
    ``NaN`` timestamp must never leak into a JSON document (``json.dumps``
    would raise). No other structure is modified.
    """
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {key: _sanitize_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_sanitize_json(item) for item in value]
    if isinstance(value, (int, str, bool)) or value is None:
        return value
    return value


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    _configure_logging(settings)

    manager = NavigationSessionManager(
        factory=_build_adapter_factory(settings),
        max_sessions=settings.max_sessions,
        idle_timeout_s=settings.session_idle_timeout_s,
    )

    app = FastAPI(
        title="Intelligent Dead Reckoning — Navigation API",
        version=__version__,
        description=(
            "Live fused GNSS/INS navigation state from smartphone sensor "
            "streams (accelerometer, gyroscope, magnetometer, GNSS). "
            "Powering the NavSphere mobile app."
        ),
    )

    app.state.settings = settings
    app.state.manager = manager

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(navigation.router)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        cleaned = _sanitize_json(jsonable_encoder(exc.errors()))
        return JSONResponse(
            status_code=422,
            content={"detail": cleaned},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled error on %s", request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error. Please retry."},
        )

    @app.get("/")
    def root() -> dict:
        return {
            "service": "NavSphere navigation API",
            "version": __version__,
            "docs": "/docs",
        }

    return app


app = create_app()