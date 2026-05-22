"""Tests for `logging_config` — configuration, idempotence, and the
ContextVar-driven request-ID plumbing.

Each test resets the module state via `reset_for_testing()` so ordering
doesn't matter. Caplog isn't used because we want to assert on the
formatted output (request_id placement, level-name padding) which
caplog bypasses.
"""
from __future__ import annotations

import io
import logging
import unittest
from contextvars import copy_context

import logging_config


class TestConfigureLogging(unittest.TestCase):
    def setUp(self):
        logging_config.reset_for_testing()

    def tearDown(self):
        logging_config.reset_for_testing()

    def test_attaches_single_handler_to_root(self):
        logging_config.configure_logging(level="INFO")
        self.assertEqual(len(logging.getLogger().handlers), 1)

    def test_idempotent(self):
        logging_config.configure_logging(level="INFO")
        logging_config.configure_logging(level="INFO")
        logging_config.configure_logging(level="INFO")
        # Still one handler — second/third calls noop.
        self.assertEqual(len(logging.getLogger().handlers), 1)

    def test_clears_preexisting_handlers(self):
        # Simulate a stale handler from a prior basicConfig-style init.
        root = logging.getLogger()
        stale = logging.StreamHandler()
        root.addHandler(stale)
        self.assertGreaterEqual(len(root.handlers), 1)

        logging_config.configure_logging(level="INFO")
        # Exactly one — ours — not ours plus the stale.
        self.assertEqual(len(root.handlers), 1)
        self.assertIsNot(root.handlers[0], stale)

    def test_explicit_level_overrides_env(self):
        logging_config.configure_logging(level="DEBUG")
        self.assertEqual(logging.getLogger().level, logging.DEBUG)

    def test_quiets_third_party_loggers(self):
        logging_config.configure_logging(level="DEBUG")
        # Even with root at DEBUG, the noisy libs are pinned to WARNING.
        for noisy in ("urllib3", "httpx", "httpcore"):
            self.assertEqual(
                logging.getLogger(noisy).level,
                logging.WARNING,
                f"{noisy} should be quieted",
            )


class TestRequestIdContextVar(unittest.TestCase):
    def setUp(self):
        logging_config.reset_for_testing()

    def tearDown(self):
        logging_config.reset_for_testing()

    def test_default_is_dash(self):
        self.assertEqual(logging_config.get_request_id(), "-")

    def test_set_then_get(self):
        logging_config.set_request_id("abc123")
        self.assertEqual(logging_config.get_request_id(), "abc123")

    def test_clear_returns_to_default(self):
        logging_config.set_request_id("abc123")
        logging_config.clear_request_id()
        self.assertEqual(logging_config.get_request_id(), "-")

    def test_isolated_per_context(self):
        """Two contexts should not see each other's request IDs.

        This is the contractually important property: handler threads in
        an async or threaded server cannot leak request IDs into each
        other via the module-level ContextVar. `copy_context` simulates a
        fresh context the way an async task or a Flask request thread
        would.
        """
        logging_config.set_request_id("outer")

        def inner():
            logging_config.set_request_id("inner")
            return logging_config.get_request_id()

        ctx = copy_context()
        inner_value = ctx.run(inner)

        self.assertEqual(inner_value, "inner")
        # The outer context is unaffected.
        self.assertEqual(logging_config.get_request_id(), "outer")


class TestRequestIdFilter(unittest.TestCase):
    """The filter is what makes `%(request_id)s` work in the formatter.

    We assert by capturing the rendered output of a real log call through
    a captured-stream handler — this validates filter + formatter together
    the way they're wired in `configure_logging`.
    """

    def setUp(self):
        logging_config.reset_for_testing()
        logging_config.configure_logging(level="INFO")
        # Replace the stdout handler's stream with a buffer so we can read it.
        self.buffer = io.StringIO()
        root = logging.getLogger()
        root.handlers[0].stream = self.buffer

    def tearDown(self):
        logging_config.reset_for_testing()

    def test_no_request_renders_dash(self):
        logging.getLogger("test").info("hello")
        line = self.buffer.getvalue()
        self.assertIn("[-]", line)
        self.assertIn("test: hello", line)

    def test_set_request_id_appears_in_output(self):
        logging_config.set_request_id("abcdef012345")
        logging.getLogger("test").info("hello")
        line = self.buffer.getvalue()
        self.assertIn("[abcdef012345]", line)


if __name__ == "__main__":
    unittest.main()
