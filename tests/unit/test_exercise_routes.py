from __future__ import annotations

import importlib
import sqlite3
import sys

import pytest

ANSWERS = {"ex-1": "を", "ex-2": "に", "ex-3": "で", "ex-4": "が", "ex-5": "へ"}


@pytest.fixture()
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("SHIORI_SESSION_SECRET", "test-route-secret")
    sys.modules.pop("app", None)
    sys.modules.pop("config", None)
    module = importlib.import_module("app")

    db_path = tmp_path / "exercise.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE exercise (exercise_id TEXT PRIMARY KEY, question_sentence TEXT, correct_answer TEXT, "
        "hint_chinese TEXT, part_of_speech TEXT, jlpt_level INTEGER)"
    )
    conn.executemany(
        "INSERT INTO exercise VALUES (?, ?, ?, ?, ?, ?)",
        [(eid, "文[＿＿＿]。", answer, "提示", "助詞", 4) for eid, answer in ANSWERS.items()],
    )
    conn.commit()
    conn.close()
    monkeypatch.setattr(module, "DATABASE_PATH", str(db_path))

    yield module.app.test_client()
    sys.modules.pop("app", None)
    sys.modules.pop("config", None)


def test_mcq_returns_requested_exercise_with_distractors(client):
    res = client.get("/api/exercise/random", query_string={"mode": "mcq", "exercise_id": "ex-3"})

    assert res.status_code == 200
    body = res.get_json()
    assert body["exercise_id"] == "ex-3"
    assert body["correct_answer"] == "で"
    assert "で" in body["choices"]
    assert len(set(body["choices"])) == 4


def test_mcq_with_unknown_exercise_id_is_404(client):
    res = client.get("/api/exercise/random", query_string={"mode": "mcq", "exercise_id": "missing"})

    assert res.status_code == 404


def test_typing_mode_ignores_exercise_id_and_hides_answer(client):
    res = client.get("/api/exercise/random", query_string={"exercise_id": "ex-3"})

    assert res.status_code == 200
    assert "correct_answer" not in res.get_json()
