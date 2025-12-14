import requests
import sys

BASE_URL = "http://127.0.0.1:5000/api"

def test_news_apis():
    print("Testing /api/news...")
    try:
        res = requests.get(f"{BASE_URL}/news")
        if res.status_code == 200:
            articles = res.json()
            print(f"SUCCESS: Retrieved {len(articles)} articles.")
            if articles:
                article_id = articles[0]['article_id']
                print(f"Testing /api/news/{article_id}...")
                res_detail = requests.get(f"{BASE_URL}/news/{article_id}")
                if res_detail.status_code == 200:
                    detail = res_detail.json()
                    print(f"SUCCESS: Retrieved article detail. Title: {detail['info']['title']}")
                    
                    if detail['paragraphs']:
                        text = detail['paragraphs'][0]['text']
                        print(f"Testing /api/translate with text: {text[:20]}...")
                        res_trans = requests.post(f"{BASE_URL}/translate", json={"text": text})
                        if res_trans.status_code == 200:
                            print(f"SUCCESS: Translation: {res_trans.json()['translated_text']}")
                        else:
                            print(f"FAILED: Translation status {res_trans.status_code}")

                        print("Testing /api/tts...")
                        res_tts = requests.post(f"{BASE_URL}/tts", json={"text": text})
                        if res_tts.status_code == 200:
                            print(f"SUCCESS: TTS received {len(res_tts.content)} bytes.")
                        else:
                            print(f"FAILED: TTS status {res_tts.status_code}")
                else:
                    print(f"FAILED: Article detail status {res_detail.status_code}")
        else:
            print(f"FAILED: News list status {res.status_code}")
    except Exception as e:
        print(f"EXCEPTION: {e}")

if __name__ == "__main__":
    test_news_apis()
