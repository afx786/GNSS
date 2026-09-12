"""Runtime configuration for the navigation API.

All values are read from environment variables with sane defaults for local
development. Nothing here is secret — secrets must never be shipped in the
client binary or committed to the repository (see ``.env.example``).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _env_str(name: str, default: str) -> str:
    value = os.getenv(name, "").strip()
    return value if value else default


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def repo_root() -> Path:
    """Repository root (``api/`` sits directly under it)."""
    return Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    """Environment-driven server settings."""

    environment: str = field(default_factory=lambda: _env_str("ENVIRONMENT", "development"))
    log_level: str = field(default_factory=lambda: _env_str("LOG_LEVEL", "INFO").upper())
    model_directory: str = field(default_factory=lambda: _env_str("MODEL_DIRECTORY", "models"))
    navigation_config: str = field(
        default_factory=lambda: _env_str(
            "NAVIGATION_CONFIG", "configs/navigation_config.yaml"
        )
    )
    fusion_config: str = field(
        default_factory=lambda: _env_str(
            "FUSION_CONFIG", "configs/fusion_config.yaml"
        )
    )
    map_matching_config: str = field(
        default_factory=lambda: _env_str(
            "MAP_MATCHING_CONFIG", "configs/map_matching_config.yaml"
        )
    )
    max_sessions: int = field(default_factory=lambda: _env_int("MAX_SESSIONS", 8))
    session_idle_timeout_s: float = field(
        default_factory=lambda: _env_float("SESSION_IDLE_TIMEOUT_S", 1800.0)
    )
    cors_origins: tuple[str, ...] = field(default_factory=lambda: _parse_origins())

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"


def _parse_origins() -> tuple[str, ...]:
    """CORS origins from ``CORS_ORIGINS`` (comma separated) or a safe default.

    The mobile client does not enforce CORS (native fetches are not
    browser-bound), so the default is deliberately permissive for local
    development while still overridable in production.
    """
    raw = os.getenv("CORS_ORIGINS", "").strip()
    if raw:
        return tuple(origin.strip() for origin in raw.split(",") if origin.strip())
    return ("*",)


def load_settings() -> Settings:
    return Settings()