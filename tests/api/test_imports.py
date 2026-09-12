"""Import & packaging tests for the API surface."""

from __future__ import annotations

from api import config, main
from api.config import Settings, repo_root


def test_app_importable():
    assert main.app is not None


def test_routes_registered():
    paths = {route.path for route in main.app.routes}
    for expected in (
        "/health",
        "/health/models",
        "/ready",
        "/navigation/sessions",
        "/navigation/sessions/{session_id}",
        "/navigation/sessions/{session_id}/update",
    ):
        assert expected in paths, f"missing route {expected}"


def test_settings_defaults_are_safe():
    settings = config.load_settings()
    assert settings.environment in {"development", "production"}
    assert settings.max_sessions >= 1
    assert settings.session_idle_timeout_s > 0
    assert settings.log_level.upper() in {"DEBUG", "INFO", "WARNING", "ERROR"}


def test_settings_custom_env(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("MAX_SESSIONS", "3")
    monkeypatch.setenv("LOG_LEVEL", "warning")
    settings = Settings(environment="production", max_sessions=3, log_level="WARNING")
    assert settings.environment == "production"
    assert settings.max_sessions == 3


def test_repo_root_is_repo():
    assert (repo_root() / "src").is_dir()
    assert (repo_root() / "configs").is_dir()


def test_requirements_declared():
    text = (repo_root() / "requirements.txt").read_text(encoding="utf-8")
    for package in ("fastapi", "uvicorn", "pydantic", "numpy", "scikit-learn", "torch"):
        assert package in text, f"requirements.txt missing {package}"


def test_railway_start_command_declared():
    text = (repo_root() / "railway.toml").read_text(encoding="utf-8")
    assert "uvicorn api.main:app" in text
    assert "$PORT" in text