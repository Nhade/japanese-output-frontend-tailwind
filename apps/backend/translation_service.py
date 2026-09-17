"""Japanese → target-language translation with a resilient fallback chain.

Primary: Google Cloud Translation v2 (service-account credentials via
``GOOGLE_APPLICATION_CREDENTIALS``). Fallback: the BALANCED LLM tier. The
fallback exists because the Google path fails outright when the project's
quota or billing lapses (observed as ``403 User Rate Limit Exceeded``), and
the reader's Translate button must keep working through that.

After a Google failure the service skips Google for a cooldown window so a
quota outage doesn't add a failing round-trip (plus a stack trace) to every
paragraph translation.
"""
import html
import logging
import os
import time

from google.cloud import translate_v2 as translate

from ai_core import Tier, query_llm
from config import ensure_dotenv_loaded

ensure_dotenv_loaded()

logger = logging.getLogger(__name__)


class TranslationError(RuntimeError):
    """Raised when neither Google nor the LLM fallback produced a translation."""


GOOGLE_COOLDOWN_SECONDS = 300
_google_paused_until = 0.0

try:
    os.environ['GOOGLE_APPLICATION_CREDENTIALS']
except KeyError:
    logger.warning("Google Cloud Translation API credentials not found. Falling back to the LLM translator.")

try:
    translate_client = translate.Client()
except Exception as e:
    logger.warning(f"Translation client failed to initialize: {e}")
    translate_client = None


# BCP-47-ish codes the frontend sends (lower-cased) → names the LLM prompt uses.
_LANGUAGE_NAMES = {
    "zh-tw": "Traditional Chinese (繁體中文)",
    "zh-hant": "Traditional Chinese (繁體中文)",
    "zh": "Traditional Chinese (繁體中文)",
    "zh-cn": "Simplified Chinese (简体中文)",
    "zh-hans": "Simplified Chinese (简体中文)",
    "en": "English",
    "ja": "Japanese",
    "ko": "Korean",
}


def _language_name(target: str) -> str:
    return _LANGUAGE_NAMES.get(target.lower(), target)


def _translate_with_google(text: str, target: str) -> str | None:
    """Return Google's translation, or None when unavailable or failing."""
    global _google_paused_until

    if translate_client is None or time.monotonic() < _google_paused_until:
        return None

    try:
        result = translate_client.translate(text, target_language=target, source_language='ja')
        return html.unescape(result['translatedText'])
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
