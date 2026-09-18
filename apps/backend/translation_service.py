"""Japanese → target-language translation with a resilient fallback chain.

Order of preference:

1. Google Cloud Translation v2 (Basic) with an API key, ``GOOGLE_TRANSLATE_API_KEY``.
   A plain REST call, so translation can bill to the same GCP project as the
   Gemini tier without a service-account file on the box.
2. Google Cloud Translation v2 through Application Default Credentials,
   ``GOOGLE_APPLICATION_CREDENTIALS`` (the original service-account route).
3. The BALANCED LLM tier.

The LLM fallback exists because the Google path fails outright when the
project's quota or billing lapses (observed as ``403 User Rate Limit
Exceeded``), and the reader's Translate button must keep working through
that. After a Google failure the service skips Google for a cooldown window
so an outage doesn't add a failing round-trip (plus a stack trace) to every
paragraph translation.
"""
import html
import logging
import os
import time

import requests
from google.cloud import translate_v2 as translate

from ai_core import Tier, query_llm
from config import ensure_dotenv_loaded

ensure_dotenv_loaded()

logger = logging.getLogger(__name__)


class TranslationError(RuntimeError):
    """Raised when neither Google nor the LLM fallback produced a translation."""


GOOGLE_COOLDOWN_SECONDS = 300
GOOGLE_V2_ENDPOINT = "https://translation.googleapis.com/language/translate/v2"
GOOGLE_TRANSLATE_API_KEY = os.getenv("GOOGLE_TRANSLATE_API_KEY", "").strip()
_google_paused_until = 0.0

translate_client = None
if GOOGLE_TRANSLATE_API_KEY:
    logger.info("Translation: Google Cloud Translation v2 via API key")
else:
    if not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
        logger.warning(
            "No Google translation credentials (GOOGLE_TRANSLATE_API_KEY or GOOGLE_APPLICATION_CREDENTIALS); "
            "falling back to the LLM translator."
        )
    try:
        translate_client = translate.Client()
    except Exception as e:
        logger.warning(f"Translation client failed to initialize: {e}")
        translate_client = None


# The frontend's selectable locales (en / ja / zh-tw) plus the aliases the
# reader sends for Traditional Chinese. Unknown codes pass through unchanged
# so the LLM still sees what was asked for.
_LANGUAGE_NAMES = {
    "zh-tw": "Traditional Chinese (繁體中文)",
    "zh-hant": "Traditional Chinese (繁體中文)",
    "zh": "Traditional Chinese (繁體中文)",
    "en": "English",
    "ja": "Japanese",
}


def _language_name(target: str) -> str:
    return _LANGUAGE_NAMES.get(target.lower(), target)


def _google_v2_with_api_key(text: str, target: str) -> str:
    # The key travels in a header, never in the URL, so request/exception
    # messages (which quote the URL) can be logged without leaking it.
    response = requests.post(
        GOOGLE_V2_ENDPOINT,
        headers={"x-goog-api-key": GOOGLE_TRANSLATE_API_KEY},
        json={"q": text, "source": "ja", "target": target, "format": "text"},
        timeout=15,
    )
    if response.status_code >= 400:
        try:
            detail = response.json().get("error", {}).get("message", "")
        except ValueError:
            detail = ""
        raise RuntimeError(f"Google Translation HTTP {response.status_code} {detail}".strip())
    return response.json()["data"]["translations"][0]["translatedText"]


def _translate_with_google(text: str, target: str) -> str | None:
    """Return Google's translation, or None when unavailable or failing."""
    global _google_paused_until

    if time.monotonic() < _google_paused_until:
        return None

    try:
        if GOOGLE_TRANSLATE_API_KEY:
            translated = _google_v2_with_api_key(text, target)
        elif translate_client is not None:
            result = translate_client.translate(text, target_language=target, source_language='ja')
            translated = result['translatedText']
        else:
            return None
        return html.unescape(translated)
    except Exception as exc:
        _google_paused_until = time.monotonic() + GOOGLE_COOLDOWN_SECONDS
        logger.warning(
            f"Google translation failed ({exc}); using the LLM fallback for the next "
            f"{GOOGLE_COOLDOWN_SECONDS}s"
        )
        return None


def _translate_with_llm(text: str, target: str) -> str:
    messages = [
        {
            "role": "system",
            "content": (
                "You are a professional translator. Translate the user's Japanese text into "
                f"{_language_name(target)}. Preserve the meaning and tone, keep numbers and proper "
                "names as they are, and output only the translation with no notes, labels, or quotation marks."
            ),
        },
        {"role": "user", "content": text},
    ]
    translated = (query_llm(messages, tier=Tier.BALANCED) or "").strip()
    if not translated:
        raise TranslationError("LLM translator returned an empty response")
    return translated


def translate_text(text: str, target: str = 'zh-TW') -> str:
    """Translate Japanese ``text`` into ``target``.

    Raises:
        TranslationError: when every translator failed. Callers that must not
            fail (e.g. exercise hint generation) catch this and degrade.
    """
    if not text or not text.strip():
        return ""

    translated = _translate_with_google(text, target)
    if translated is not None:
        return translated

    try:
        return _translate_with_llm(text, target)
    except TranslationError:
        raise
    except Exception as exc:
        logger.exception("LLM translation fallback failed")
        raise TranslationError("Translation is temporarily unavailable") from exc
