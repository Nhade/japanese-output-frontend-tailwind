"""Central logging configuration with per-request correlation IDs.

Two pieces:

* `configure_logging()` — call once at process start. Idempotent so app
  startup and CLI tools that import backend modules can both call it
  freely without doubling handlers.

* Request-ID plumbing — `set_request_id` / `get_request_id` /
  `clear_request_id` operate on a `ContextVar` so callers outside a
  Flask request context (background agents, CLIs, the daily-review
  graph) don't need special handling. `RequestIdFilter` injects the
  current value into every `LogRecord`; the Flask integration in
  `app.py` stamps the contextvar in `before_request` and clears it in
  `teardown_request`.

Format:
    2026-05-21T19:48:08 INFO    [a3f9c0c4d2e1] app: db init ok

Records emitted outside a request render the literal "-" for the
request_id slot — keeps the column width predictable in log readers.
"""
from __future__ import annotations

import logging
import os
import sys
from contextvars import ContextVar

_NO_REQUEST = "-"
_REQUEST_ID: ContextVar[str] = ContextVar("request_id", default=_NO_REQUEST)
_configured = False


def set_request_id(request_id: str) -> None:
    """Stamp the request ID for the current context."""
    _REQUEST_ID.set(request_id)


def get_request_id() -> str:
    """Return the request ID set for this context, or '-' if none."""
    return _REQUEST_ID.get()


def clear_request_id() -> None:
    """Reset to the no-request placeholder. Call in `teardown_request`."""
    _REQUEST_ID.set(_NO_REQUEST)


class RequestIdFilter(logging.Filter):
    """Attach the current request_id to every record for the formatter."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = _REQUEST_ID.get()
        return True


def configure_logging(level: str | None = None) -> None:
    """Initialize the root logger once. Subsequent calls are no-ops.

    `level` overrides the `LOG_LEVEL` env var, which itself defaults to
    INFO. Tests pass an explicit level to avoid env coupling.
    """
    global _configured
    if _configured:
        return

    resolved = (level or os.getenv("LOG_LEVEL", "INFO")).upper()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)-7s [%(request_id)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
    )
    handler.addFilter(RequestIdFilter())

    root = logging.getLogger()
    # Clear in case basicConfig or a previous configure_logging() attached
    # something — we want exactly one handler with our format + filter.
    for existing in list(root.handlers):
        root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(resolved)

    # Quiet third-party libraries whose default INFO chatter buries our own.
    logging.getLogger("urllib3").setLevel("WARNING")
    logging.getLogger("httpx").setLevel("WARNING")
    logging.getLogger("httpcore").setLevel("WARNING")

    _configured = True


def reset_for_testing() -> None:
    """Re-arm `configure_logging` so the next call re-installs handlers.

    Only used by tests; production code never calls this. The contextvar
    is also reset to the no-request placeholder so test ordering can't
    leak state.
    """
    global _configured
    _configured = False
    clear_request_id()
