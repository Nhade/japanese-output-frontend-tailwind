from google.cloud import translate_v2 as translate
import os
from dotenv import load_dotenv

load_dotenv()

try:
    os.environ['GOOGLE_APPLICATION_CREDENTIALS']
except KeyError:
    print("Google Cloud Translation API credentials not found. Translation service will not work.")

try:
    translate_client = translate.Client()
except Exception as e:
    print(f"Translation Client failed to initialize: {e}")
    translate_client = None

def translate_text(text: str, target='zh-TW') -> str:
    """
    Translates text to Traditional Chinese using Google Cloud Translation API.
    """
    if not translate_client:
        print("Translation attempted but client is not initialized.")
        return "翻譯服務暫時無法使用。"

    try:
        result = translate_client.translate(text, target_language=target, source_language='ja')
        return result['translatedText']
    except Exception as e:
        print(f"Translation Service Error: {e}")
        return "翻譯服務出現錯誤，請稍後再試。"
