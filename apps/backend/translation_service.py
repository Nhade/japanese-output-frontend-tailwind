from google.cloud import translate_v2 as translate
import os

def translate_text(text: str, target='zh-TW') -> str:
    """
    Translates text to Traditional Chinese using Google Cloud Translation API.
    """
    try:
        # Check if credentials are available
        if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
            pass
        
        translate_client = translate.Client()
        
        result = translate_client.translate(text, target_language=target, source_language='ja')
        return result['translatedText']
    except Exception as e:
        print(f"Translation Service Error: {e}")
        return "翻譯服務暫時無法使用，請檢查伺服器設定。"
