from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI()

def generate_audio(text: str) -> bytes:
    """
    Generates WAV audio bytes from Japanese text using OpenAI TTS.
    """
    try:
        # Instructions for natural Japanese conversation
        instructions = """日本語（標準語・東京）で自然な会話調。
- 英語っぽい抑揚を避ける（語尾を不自然に上げない）
- 助詞は弱く自然に、母音を伸ばしすぎない
- 句読点で短くポーズ
"""
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

