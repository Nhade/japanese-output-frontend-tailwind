import logging

from openai import OpenAI

from config import ensure_dotenv_loaded

ensure_dotenv_loaded()

logger = logging.getLogger(__name__)

# Constructed lazily on first call. Older revisions instantiated `OpenAI()` at
# module body, which fails on import in environments without `OPENAI_API_KEY`
# set (CI test runners, dev shells without `.env`) because newer SDK versions
# raise immediately when no credentials are available.
_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI()
    return _client


def generate_audio(text: str) -> bytes:
    """
    Generates WAV audio bytes from Japanese text using OpenAI TTS.
    """
    try:
        response = _get_client().audio.speech.create(
            model="gpt-4o-mini-tts",  # Or "tts-1" / "tts-1-hd" depending on availability/preference, but using user reference
            voice="alloy",
            input=text,
            response_format="wav",
            speed=1.0
        )

        # response.content contains the bytes of the audio file
        return response.content

    except Exception:
        logger.exception("OpenAI TTS error")
        return None

