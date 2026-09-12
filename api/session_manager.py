"""In-memory, thread-safe navigation session registry.

Sessions are per-user containers holding an isolated ``NavigationSessionAdapter``
(one ``IDREngine`` + ML buffers). No Redis/Postgres is needed at this scale;
sessions are lost on process restart, which is documented behaviour.

Thread-safety is provided by a single re-entrant lock; each adapter is only
ever mutated while holding it, so concurrent updates queue instead of racing.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from typing import Callable, Iterable, Optional

from api.navigation_adapter import NavigationSessionAdapter

logger = logging.getLogger("api.sessions")

SessionId = str
SessionFactory = Callable[[str, float, float, Optional[float], Optional[float]], NavigationSessionAdapter]


class SessionNotFoundError(Exception):
    """Raised when a session id does not exist (map to HTTP 404)."""


class SessionLimitExceededError(Exception):
    """Raised when the session slot cap is reached (map to HTTP 503)."""


def new_session_id() -> str:
    return uuid.uuid4().hex


class NavigationSessionManager:
    def __init__(
        self,
        factory: SessionFactory,
        max_sessions: int = 8,
        idle_timeout_s: float = 1800.0,
        now: Optional[Callable[[], float]] = None,
    ) -> None:
        self._factory = factory
        self._max_sessions = max(int(max_sessions), 1)
        self._idle_timeout_s = float(idle_timeout_s)
        self._now = now or time.monotonic
        self._sessions: dict[SessionId, tuple[NavigationSessionAdapter, float]] = {}
        self._lock = threading.RLock()

    # ------------------------------------------------------------------ #
    # Ops
    # ------------------------------------------------------------------ #

    def create(
        self,
        latitude: float,
        longitude: float,
        accuracy: float = 10.0,
        heading_deg: Optional[float] = None,
    ) -> NavigationSessionAdapter:
        with self._lock:
            self._prune_locked()
            session_id = new_session_id()
            if self._max_sessions is not None and len(self._sessions) >= self._max_sessions:
                raise SessionLimitExceededError(
                    f"session limit of {self._max_sessions} reached; "
                    "close an active session and retry"
                )
            adapter = self._factory(session_id, latitude, longitude, heading_deg, accuracy)
            self._sessions[session_id] = (adapter, self._now())
            logger.info("session created: %s (%d active)", session_id, len(self._sessions))
            return adapter

    def get(self, session_id: str) -> NavigationSessionAdapter:
        with self._lock:
            entry = self._sessions.get(session_id)
            if entry is None:
                raise SessionNotFoundError(f"session {session_id} not found")
            self._sessions[session_id] = (entry[0], self._now())
            return entry[0]

    def update(
        self,
        session_id: str,
        imu_samples: list,
        gnss,
    ) -> dict:
        with self._lock:
            adapter = self.get(session_id)
            state = adapter.update(imu_samples, gnss)
            self._sessions[session_id] = (adapter, self._now())
            return state

    def delete(self, session_id: str) -> bool:
        with self._lock:
            entry = self._sessions.pop(session_id, None)
            if entry is None:
                return False
            entry[0].close()
            logger.info("session closed: %s (%d active)", session_id, len(self._sessions))
            return True

    def list_ids(self) -> list[str]:
        with self._lock:
            self._prune_locked()
            return sorted(self._sessions.keys())

    def active_count(self) -> int:
        with self._lock:
            self._prune_locked()
            return len(self._sessions)

    def clear(self) -> None:
        with self._lock:
            for adapter, _ in self._sessions.values():
                adapter.close()
            self._sessions.clear()

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #

    def _prune_locked(self) -> None:
        now = self._now()
        expired = [
            session_id
            for session_id, (_, last) in self._sessions.items()
            if now - last > self._idle_timeout_s
        ]
        for session_id in expired:
            adapter = self._sessions.pop(session_id)[0]
            adapter.close()
            logger.info("session pruned (idle): %s", session_id)