from __future__ import annotations

import dataclasses
import importlib
import sys
from datetime import datetime, timedelta

import pytest

import usage_limits
from tests.unit.test_guest_service import build_db


@pytest.fixture()
def backend_app(monkeypatch, tmp_path):
    monkeypatch.setenv("SHIORI_SESSION_SECRET", "test-route-secret")

    sys.modules.pop("app", None)
    sys.modules.pop("config", None)
    module = importlib.import_module("app")

    conn = build_db(tmp_path / "routes.db")
    conn.close()
    monkeypatch.setattr(module, "DATABASE_PATH", str(tmp_path / "routes.db"))

    yield module
    sys.modules.pop("app", None)
    sys.modules.pop("config", None)


@pytest.fixture()
def client(backend_app):
    return backend_app.app.test_client()


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_guest(client) -> dict:
    res = client.post("/api/guest/session", json={})
    assert res.status_code == 201, res.get_json()
    return res.get_json()


def test_guest_session_is_created_and_reported_by_me(client):
    session = _create_guest(client)

    assert session["guest"] is True
    assert session["sample_history"] is True
    assert session["token"]

    me = client.get("/api/users/me", headers=_auth(session["token"]))
    assert me.status_code == 200
    body = me.get_json()
    assert body["user_id"] == session["user_id"]
    assert body["guest"] is True
    assert body["expires_at"] == session["expires_at"]


def test_guest_session_can_skip_sample_history(client):
    res = client.post("/api/guest/session", json={"seed_history": False})

    assert res.status_code == 201
    assert res.get_json()["sample_history"] is False


def test_guest_session_disabled_by_setting(backend_app, client, monkeypatch):
    monkeypatch.setattr(backend_app, "settings", dataclasses.replace(backend_app.settings, guest_preview_enabled=False))

    res = client.post("/api/guest/session", json={})

    assert res.status_code == 404
    assert res.get_json()["code"] == "preview_disabled"


def test_guest_creation_is_rate_limited_per_ip(client, monkeypatch):
    monkeypatch.setattr(usage_limits, "GUEST_CREATES_PER_IP_PER_HOUR", 1)

    _create_guest(client)
    res = client.post("/api/guest/session", json={}, headers={"X-Forwarded-For": "203.0.113.9, 10.0.0.1"})
    assert res.status_code == 201, "a different forwarded client IP gets its own bucket"

    res = client.post("/api/guest/session", json={}, headers={"X-Forwarded-For": "203.0.113.9"})
    assert res.status_code == 429
    assert res.get_json()["code"] == "preview_busy"


def test_guest_cannot_import_videos(client):
    session = _create_guest(client)

    res = client.post("/api/videos/import", json={"url": "https://youtube.com/watch?v=abc"}, headers=_auth(session["token"]))

    assert res.status_code == 403
    assert res.get_json()["code"] == "guest_forbidden"


def test_guest_budget_returns_429_after_limit(backend_app, client, monkeypatch):
    monkeypatch.setattr(usage_limits, "GUEST_ACTION_LIMITS", {"tts": 1})
    monkeypatch.setattr(backend_app, "generate_audio", lambda text: b"RIFF")
    session = _create_guest(client)

    first = client.post("/api/tts", json={"text": "こんにちは"}, headers=_auth(session["token"]))
    assert first.status_code == 200

    second = client.post("/api/tts", json={"text": "こんにちは"}, headers=_auth(session["token"]))
    assert second.status_code == 429
    body = second.get_json()
    assert body["code"] == "preview_limit"
    assert body["action"] == "tts"


def test_registered_users_are_not_metered(backend_app, client, monkeypatch):
    monkeypatch.setattr(usage_limits, "GUEST_ACTION_LIMITS", {"tts": 0})
    monkeypatch.setattr(backend_app, "generate_audio", lambda text: b"RIFF")
    session = _create_guest(client)
    upgraded = client.post(
        "/api/users/register",
        json={"username": "ray", "password": "correct horse"},
        headers=_auth(session["token"]),
    ).get_json()

    res = client.post("/api/tts", json={"text": "こんにちは"}, headers=_auth(upgraded["token"]))

    assert res.status_code == 200


def test_register_with_guest_token_upgrades_in_place(backend_app, client):
    session = _create_guest(client)

    res = client.post(
        "/api/users/register",
        json={"username": "ray", "password": "correct horse battery"},
        headers=_auth(session["token"]),
    )

    assert res.status_code == 200
    body = res.get_json()
    assert body["upgraded"] is True
    assert body["user_id"] == session["user_id"]

    me = client.get("/api/users/me", headers=_auth(body["token"])).get_json()
    assert me == {"user_id": session["user_id"], "guest": False}

    conn = backend_app.get_db_connection()
    try:
        assert conn.execute("SELECT COUNT(*) FROM answer_log WHERE user_id = ?", (session["user_id"],)).fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1
    finally:
        conn.close()

    login = client.post("/api/users/login", json={"username": "ray", "password": "correct horse battery"})
    assert login.status_code == 200


def test_register_without_guest_token_still_creates_a_new_user(backend_app, client):
    res = client.post("/api/users/register", json={"username": "solo", "password": "pw"})

    assert res.status_code == 201
    assert "token" not in res.get_json()


def test_expired_guest_session_is_rejected_with_code(backend_app, client):
    session = _create_guest(client)
    conn = backend_app.get_db_connection()
    try:
        conn.execute(
            "UPDATE users SET guest_expires_at = ? WHERE user_id = ?",
            ((datetime.now() - timedelta(minutes=1)).isoformat(), session["user_id"]),
        )
        conn.commit()
    finally:
        conn.close()

    res = client.get("/api/users/me", headers=_auth(session["token"]))

    assert res.status_code == 401
    assert res.get_json() == {"error": "Preview session ended", "code": "guest_expired"}


def test_mistakes_flag_sample_rows(client):
    session = _create_guest(client)

    res = client.get("/api/mistakes/me", headers=_auth(session["token"]))

    assert res.status_code == 200
    rows = res.get_json()
    assert rows and all(row["is_sample"] is True for row in rows)


def test_daily_review_is_metered_for_guests(backend_app, client, monkeypatch):
    monkeypatch.setattr(usage_limits, "GUEST_ACTION_LIMITS", {"daily_review": 1})
    monkeypatch.setattr(backend_app, "generate_daily_review_agent", lambda user_id, db_path: "# Review")
    session = _create_guest(client)

    first = client.get("/api/agent/daily_review/me", headers=_auth(session["token"]))
    assert first.status_code == 200
    assert first.get_json() == {"review": "# Review"}

    second = client.get("/api/agent/daily_review/me", headers=_auth(session["token"]))
    assert second.status_code == 429
    assert second.get_json()["action"] == "daily_review"


def test_explain_is_metered_and_works_on_sample_rows(backend_app, client, monkeypatch):
    monkeypatch.setattr(usage_limits, "GUEST_ACTION_LIMITS", {"explain": 1})
    monkeypatch.setattr(
        backend_app,
        "evaluate_submission",
        lambda question, user_answer, correct_answer: {"feedback": "助詞が違います", "score": 95, "error_type": "particle"},
    )
    session = _create_guest(client)
    mistakes = client.get("/api/mistakes/me", headers=_auth(session["token"])).get_json()
    log_id = mistakes[0]["log_id"]

    first = client.post("/api/exercise/explain", json={"log_id": log_id}, headers=_auth(session["token"]))
    assert first.status_code == 200
    assert first.get_json()["error_type"] == "particle"

    second = client.post("/api/exercise/explain", json={"log_id": log_id}, headers=_auth(session["token"]))
    assert second.status_code == 429
    assert second.get_json()["code"] == "preview_limit"


def test_translate_route_maps_translation_errors_to_503(backend_app, client, monkeypatch):
    session = _create_guest(client)

    monkeypatch.setattr(backend_app, "translate_text", lambda text, target: "今天很熱")
    ok = client.post("/api/translate", json={"text": "今日は暑い", "target": "zh-TW"}, headers=_auth(session["token"]))
    assert ok.status_code == 200
    assert ok.get_json() == {"translated_text": "今天很熱"}

    def broken(text, target):
        raise backend_app.TranslationError("all translators failed")

    monkeypatch.setattr(backend_app, "translate_text", broken)
    res = client.post("/api/translate", json={"text": "今日は暑い", "target": "zh-TW"}, headers=_auth(session["token"]))
    assert res.status_code == 503
    assert "unavailable" in res.get_json()["error"].lower()
