"""FastAPI dependency providers bound to application state.

Keeping dependencies here makes the app trivially testable: tests can build
their own app with a fresh manager without touching module globals.
"""

from __future__ import annotations

from fastapi import Request

from api.config import Settings
from api.session_manager import NavigationSessionManager


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_session_manager(request: Request) -> NavigationSessionManager:
    return request.app.state.manager