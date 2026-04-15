from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
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

    except Exception as e:
        print(f"OpenAI TTS Error: {e}")
        return None

