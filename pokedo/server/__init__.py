"""PokeDo server -- FastAPI application.

Provides:
  - User registration and JWT authentication (Postgres-backed)
  - Async turn-based PvP battle API
  - Leaderboard queries
  - Health check and sync stub

Run with: uvicorn pokedo.server:app
"""

import logging
import os
import threading
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from pokedo.data.server_models import init_server_db
from pokedo.server.deps import _get_db
from pokedo.server.routers import auth, battles, leaderboard, misc

__all__ = ["_get_db", "app"]

logger = logging.getLogger("pokedo.server")


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Create DB tables on startup."""
    init_server_db()
    yield


app = FastAPI(title="PokeDo Server", version="0.4.0", lifespan=lifespan)


# ---------------------------------------------------------------------------
# Rate limiting (in-process sliding window; per-instance, no shared store)
# ---------------------------------------------------------------------------


class SlidingWindowRateLimiter:
    """Thread-safe sliding-window counter keyed by arbitrary strings."""

    def __init__(self, limit: int, window_seconds: float, enabled: bool = True):
        self.limit = limit
        self.window = window_seconds
        self.enabled = enabled
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()
        self._calls = 0

    def clear(self) -> None:
        with self._lock:
            self._hits.clear()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            cutoff = now - self.window
            while hits and hits[0] <= cutoff:
                hits.popleft()
            if len(hits) >= self.limit:
                return False
            hits.append(now)
            self._calls += 1
            # Periodic prune of exhausted keys so the map cannot grow forever.
            if self._calls % 1024 == 0:
                for k in [k for k, q in self._hits.items() if not q]:
                    del self._hits[k]
            return True


# Brute-force budget for credential endpoints: attempts per minute per IP.
# POKEDO_AUTH_RATE_LIMIT tunes it (tests raise it via conftest).
AUTH_RATE_LIMIT = SlidingWindowRateLimiter(
    limit=int(os.getenv("POKEDO_AUTH_RATE_LIMIT", "10")),
    window_seconds=60.0,
)
AUTH_PATHS = {"/token", "/register"}


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if AUTH_RATE_LIMIT.enabled and request.url.path in AUTH_PATHS:
        client_host = request.client.host if request.client else "unknown"
        if not AUTH_RATE_LIMIT.allow(client_host):
            return JSONResponse(
                {"detail": "Too many requests"},
                status_code=429,
                headers={"Retry-After": "60"},
            )
    return await call_next(request)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Return a clean 500 instead of leaking a traceback to the client."""
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse({"detail": "Internal server error"}, status_code=500)


app.include_router(misc.router)
app.include_router(auth.router)
app.include_router(battles.router)
app.include_router(leaderboard.router)
