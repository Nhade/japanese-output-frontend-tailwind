import logging

from openai import OpenAI

from config import ensure_dotenv_loaded

ensure_dotenv_loaded()

logger = logging.getLogger(__name__)
client = OpenAI()

def generate_audio(text: str) -> bytes:
    """
    Generates WAV audio bytes from Japanese text using OpenAI TTS.
    """
    try:
        # Instructions for natural Japanese conversation
        response = client.audio.speech.create(
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

