"""Application configuration loaded once from the environment.

`.env` is loaded on import via python-dotenv. Any module that imports
`settings` transitively triggers this, so no other module should call
`load_dotenv()` directly.

Only operational config lives here (paths, timeouts, debug flag). The
LLM tier registry stays in `ai_core.py` because:

  * `ModelConfig` is domain-specific to the provider matrix.
  * `tests/unit/test_llm_logic.py` mutates tier env vars and calls
    `importlib.reload(ai_core)` to re-read them. Routing tier config
    through the frozen `settings` singleton here would not pick up
    those mutations on reload, silently breaking the tests.

The same caveat applies to `GROQ_API_KEY` / `ENABLE_SAFETY_CHECK`: they
gate the module-level `safeguard_client` in `ai_core` and the test
exercises them via the same reload mechanism. They stay in `ai_core`.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

_DOTENV_LOADED = False


def ensure_dotenv_loaded() -> None:
    """Load `.env` once before SDKs read environment variables."""
    global _DOTENV_LOADED
    if not _DOTENV_LOADED:
        load_dotenv()
        _DOTENV_LOADED = True


ensure_dotenv_loaded()

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_DB_PATH = _REPO_ROOT / "data" / "news_corpus.db"


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _resolve_db_path() -> Path:
    raw = os.getenv("SHIORI_DATABASE_PATH")
    candidate = Path(raw) if raw else _DEFAULT_DB_PATH
    return candidate.expanduser().resolve()


def _resolve_session_secret(flask_debug: bool) -> str:
    secret = os.getenv("SHIORI_SESSION_SECRET") or os.getenv("SECRET_KEY")
    if secret:
        return secret
    if flask_debug or _bool_env("SHIORI_ALLOW_INSECURE_SESSION_SECRET", False):
        return "dev-insecure-session-secret-change-me"
    raise RuntimeError(
        "SHIORI_SESSION_SECRET must be set unless FLASK_DEBUG=true or "
        "SHIORI_ALLOW_INSECURE_SESSION_SECRET=true is explicitly configured."
    )


@dataclass(frozen=True)
class Settings:
    """Operational config loaded once from the environment."""

    database_path: Path
    ai_timeout: int
    flask_debug: bool
    session_secret: str
    session_max_age_seconds: int

    @classmethod
    def from_env(cls) -> Settings:
        flask_debug = _bool_env("FLASK_DEBUG", False)
        return cls(
            database_path=_resolve_db_path(),
            ai_timeout=int(os.getenv("AI_TIMEOUT", "120")),
            flask_debug=flask_debug,
            session_secret=_resolve_session_secret(flask_debug),
            session_max_age_seconds=int(os.getenv("SHIORI_SESSION_MAX_AGE_SECONDS", str(60 * 60 * 24 * 30))),
        )


settings = Settings.from_env()
