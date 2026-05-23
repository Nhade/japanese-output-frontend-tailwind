from __future__ import annotations

import importlib
import sys
from types import SimpleNamespace

import pytest


class _FakeCursor:
    def __init__(self, row):
        self._row = row

    def fetchone(self):
        return self._row


class _FakeConn:
    def __init__(self, row):
        self._row = row

    def execute(self, *_args, **_kwargs):
        return _FakeCursor(self._row)

    def close(self):
        pass


@pytest.fixture()
def backend_app(monkeypatch):
    monkeypatch.setenv("SHIORI_SESSION_SECRET", "test-route-secret")

    sys.modules.pop("app", None)
    sys.modules.pop("config", None)
    module = importlib.import_module("app")
    yield module
    sys.modules.pop("app", None)
    sys.modules.pop("config", None)


@pytest.fixture()
def client(backend_app):
    return backend_app.app.test_client()


def _token(backend_app, user_id: str = "u1") -> str:
    return backend_app.issue_session_token(user_id)


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_protected_me_route_rejects_missing_token(client):
    res = client.get("/api/users/me")

    assert res.status_code == 401
    assert res.get_json()["error"] == "Authentication required"


def test_protected_me_route_rejects_bad_token(client):
    res = client.get("/api/users/me", headers=_auth("not-a-valid-token"))

    assert res.status_code == 401
    assert res.get_json()["error"] == "Invalid session"


def test_protected_me_route_accepts_valid_token(backend_app, client, monkeypatch):
    monkeypatch.setattr(backend_app, "get_db_connection", lambda: _FakeConn(SimpleNamespace()))

    res = client.get("/api/users/me", headers=_auth(_token(backend_app, "u1")))

    assert res.status_code == 200
    assert res.get_json() == {"user_id": "u1"}


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/api/mistakes/u2"),
        ("get", "/api/statistics/u2"),
        ("get", "/api/agent/daily_review/u2"),
        ("get", "/api/learner/profile/u2"),
        ("post", "/api/learner/recalculate/u2"),
    ],
)
def test_user_id_compat_routes_reject_wrong_authenticated_user(
    backend_app,
    client,
    monkeypatch,
    method,
    path,
):
    monkeypatch.setattr(backend_app, "get_db_connection", lambda: _FakeConn(SimpleNamespace()))

    res = getattr(client, method)(path, headers=_auth(_token(backend_app, "u1")))

    assert res.status_code == 403
    assert res.get_json()["error"] == "Forbidden"


def test_expensive_routes_require_auth(client):
    cases = [
        ("post", "/api/videos/import"),
        ("post", "/api/videos/video-1/comprehension"),
        ("post", "/api/translate"),
        ("post", "/api/tts"),
    ]

    for method, path in cases:
        res = getattr(client, method)(path, json={})
        assert res.status_code == 401, path
