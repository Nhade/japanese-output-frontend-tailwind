from gtts import gTTS
import io
def generate_audio(text: str) -> bytes:
    """
    Generates MP3 audio bytes from Japanese text using Google TTS (gTTS).
    """
    try:
        # lang='ja' specifies Japanese
        tts = gTTS(text=text, lang='ja')
        
        # Write audio to memory (BytesIO) instead of a file to avoid disk I/O
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        
        return fp.getvalue()
    except Exception as e:
        print(f"gTTS Error: {e}")
        return None
