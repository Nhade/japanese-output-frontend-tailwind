from __future__ import annotations

import importlib
import sys

import pytest


class _FakeGoogleClient:
    def __init__(self, result=None, error: Exception | None = None):
        self.result = result
        self.error = error
        self.calls = 0

    def translate(self, text, target_language, source_language):
        self.calls += 1
        if self.error:
            raise self.error
        return {"translatedText": self.result}


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


@pytest.fixture()
def svc(monkeypatch):
    # Import without real Google credentials of either kind, then give each
    # test a clean cooldown state.
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "")
    monkeypatch.setenv("GOOGLE_TRANSLATE_API_KEY", "")
    sys.modules.pop("translation_service", None)
    module = importlib.import_module("translation_service")
    module._google_paused_until = 0.0
    yield module
    sys.modules.pop("translation_service", None)


def _capture_llm(monkeypatch, svc, reply="翻譯結果"):
    calls: list[dict] = []

    def fake_query_llm(messages, **kwargs):
        calls.append({"messages": messages, **kwargs})
        return reply

    monkeypatch.setattr(svc, "query_llm", fake_query_llm)
    return calls


def _capture_rest(monkeypatch, svc, response: _FakeResponse):
    calls: list[dict] = []

    def fake_post(url, **kwargs):
        calls.append({"url": url, **kwargs})
        return response

    monkeypatch.setattr(svc.requests, "post", fake_post)
    return calls


# ---------------------------------------------------------------------------
# Service-account (ADC) path
# ---------------------------------------------------------------------------

def test_google_result_is_used_and_unescaped(svc, monkeypatch):
    monkeypatch.setattr(svc, "translate_client", _FakeGoogleClient(result="A &amp; B"))
    llm_calls = _capture_llm(monkeypatch, svc)

    assert svc.translate_text("AとB", "en") == "A & B"
    assert llm_calls == []


def test_google_failure_falls_back_to_llm_and_pauses_google(svc, monkeypatch):
    google = _FakeGoogleClient(error=RuntimeError("403 User Rate Limit Exceeded"))
    monkeypatch.setattr(svc, "translate_client", google)
    llm_calls = _capture_llm(monkeypatch, svc, reply="  今天很熱。  ")

    assert svc.translate_text("今日は暑いですね。", "zh-TW") == "今天很熱。"
    assert svc.translate_text("明日も暑い。", "zh-TW") == "今天很熱。"

    # Google was tried once, then skipped during the cooldown window.
    assert google.calls == 1
    assert len(llm_calls) == 2
    assert llm_calls[0]["tier"] == svc.Tier.BALANCED
    system_prompt = llm_calls[0]["messages"][0]["content"]
    assert "Traditional Chinese" in system_prompt
    assert llm_calls[0]["messages"][-1] == {"role": "user", "content": "今日は暑いですね。"}


# ---------------------------------------------------------------------------
# API-key (REST) path
# ---------------------------------------------------------------------------

def test_api_key_path_calls_rest_with_key_in_header(svc, monkeypatch):
    monkeypatch.setattr(svc, "GOOGLE_TRANSLATE_API_KEY", "test-key")
    # The ADC client must not be touched once a key is configured.
    monkeypatch.setattr(svc, "translate_client", _FakeGoogleClient(error=AssertionError("ADC client used")))
    llm_calls = _capture_llm(monkeypatch, svc)
    rest_calls = _capture_rest(
        monkeypatch, svc,
        _FakeResponse(200, {"data": {"translations": [{"translatedText": "今天很熱。"}]}}),
    )

    assert svc.translate_text("今日は暑いですね。", "zh-TW") == "今天很熱。"

    assert llm_calls == []
    assert len(rest_calls) == 1
    call = rest_calls[0]
    assert call["url"] == svc.GOOGLE_V2_ENDPOINT
    assert call["headers"] == {"x-goog-api-key": "test-key"}
    assert call["json"] == {"q": "今日は暑いですね。", "source": "ja", "target": "zh-TW", "format": "text"}
    assert "key" not in call.get("params", {})


def test_api_key_http_error_falls_back_without_leaking_the_key(svc, monkeypatch, caplog):
    monkeypatch.setattr(svc, "GOOGLE_TRANSLATE_API_KEY", "super-secret-key")
    llm_calls = _capture_llm(monkeypatch, svc, reply="It is hot today.")
    rest_calls = _capture_rest(
        monkeypatch, svc,
        _FakeResponse(403, {"error": {"message": "Cloud Translation API has not been used in project 123"}}),
    )

    with caplog.at_level("WARNING", logger="translation_service"):
        assert svc.translate_text("今日は暑いですね。", "en") == "It is hot today."
        assert svc.translate_text("明日も暑い。", "en") == "It is hot today."

    assert len(rest_calls) == 1, "Google is skipped during the cooldown after a failure"
    assert len(llm_calls) == 2
    assert "HTTP 403" in caplog.text
    assert "has not been used" in caplog.text
    assert "super-secret-key" not in caplog.text


# ---------------------------------------------------------------------------
# LLM fallback
# ---------------------------------------------------------------------------

def test_missing_google_client_uses_llm(svc, monkeypatch):
    monkeypatch.setattr(svc, "translate_client", None)
    llm_calls = _capture_llm(monkeypatch, svc, reply="It is hot today.")

    assert svc.translate_text("今日は暑いですね。", "en") == "It is hot today."
    assert "English" in llm_calls[0]["messages"][0]["content"]


def test_unknown_target_code_is_passed_through_to_the_prompt(svc, monkeypatch):
    monkeypatch.setattr(svc, "translate_client", None)
    llm_calls = _capture_llm(monkeypatch, svc, reply="…")

    svc.translate_text("こんにちは", "fr")

    assert "into fr." in llm_calls[0]["messages"][0]["content"]


def test_llm_failure_raises_translation_error(svc, monkeypatch):
    monkeypatch.setattr(svc, "translate_client", None)

    def broken(messages, **kwargs):
        raise RuntimeError("provider down")

    monkeypatch.setattr(svc, "query_llm", broken)

    with pytest.raises(svc.TranslationError):
        svc.translate_text("こんにちは", "en")


def test_empty_llm_reply_raises_translation_error(svc, monkeypatch):
    monkeypatch.setattr(svc, "translate_client", None)
    _capture_llm(monkeypatch, svc, reply="   ")

    with pytest.raises(svc.TranslationError):
        svc.translate_text("こんにちは", "en")


def test_blank_input_short_circuits(svc, monkeypatch):
    monkeypatch.setattr(svc, "translate_client", None)
    llm_calls = _capture_llm(monkeypatch, svc)

    assert svc.translate_text("   ", "en") == ""
    assert llm_calls == []
