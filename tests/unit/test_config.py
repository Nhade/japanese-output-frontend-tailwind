"""Tests for the central Settings loader."""
from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest.mock import patch

from config import Settings


class TestSettingsFromEnv(unittest.TestCase):
    """Verify env-var parsing and defaults via the Settings.from_env factory.

    `from_env` reads `os.environ` at call time, so each test can scope env
    state with `patch.dict` without needing to reload modules. The module-
    level `settings` singleton itself is loaded once at import and is not
    exercised here.
    """

    def test_defaults_when_env_unset(self):
        with patch.dict(os.environ, {}, clear=True):
            s = Settings.from_env()
        self.assertEqual(s.ai_timeout, 120)
        self.assertFalse(s.flask_debug)
        self.assertIsInstance(s.database_path, Path)
        self.assertTrue(s.database_path.is_absolute())
        self.assertTrue(str(s.database_path).endswith(os.path.join("data", "news_corpus.db")))

    def test_database_path_honours_env(self):
        with patch.dict(os.environ, {"SHIORI_DATABASE_PATH": "/tmp/shiori-test.db"}, clear=True):
            s = Settings.from_env()
        # `.resolve()` normalises the path; on POSIX this is /tmp/shiori-test.db,
        # on Windows it absolutises against the current drive. The filename is
        # the stable invariant either way.
        self.assertEqual(s.database_path.name, "shiori-test.db")

    def test_ai_timeout_parses_int(self):
        with patch.dict(os.environ, {"AI_TIMEOUT": "30"}, clear=True):
            s = Settings.from_env()
        self.assertEqual(s.ai_timeout, 30)

    def test_flask_debug_truthy_values(self):
        for raw in ("1", "true", "TRUE", "Yes", "on"):
            with patch.dict(os.environ, {"FLASK_DEBUG": raw}, clear=True):
                s = Settings.from_env()
            self.assertTrue(s.flask_debug, f"{raw!r} should be truthy")

    def test_flask_debug_falsy_values(self):
        for raw in ("", "0", "false", "no", "off", "random"):
            with patch.dict(os.environ, {"FLASK_DEBUG": raw}, clear=True):
                s = Settings.from_env()
            self.assertFalse(s.flask_debug, f"{raw!r} should be falsy")

    def test_settings_is_frozen(self):
        with patch.dict(os.environ, {}, clear=True):
            s = Settings.from_env()
        with self.assertRaises(Exception):
            s.ai_timeout = 5  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
