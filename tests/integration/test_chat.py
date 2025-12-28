import requests
import json
import sys
import os

# Add parent directory to path to allow importing if needed, 
# though this script uses HTTP requests so it doesn't strictly need app context.
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE_URL = "http://localhost:5000/api"

def test_chat():
    print("Testing /api/chat/send")
    
    # 1. Test basic greeting
    payload = {
        "message": "こんにちは",
        "history": []
    }
    try:
        res = requests.post(f"{BASE_URL}/chat/send", json=payload)
        res.raise_for_status()
        data = res.json()
        
        print("\n[Response 1 - Greeting]")
        print(f"User: {payload['message']}")
        print(f"AI: {data.get('response')}")
        print(f"Feedback: {data.get('feedback', {}).get('overall')}")
        
    except Exception as e:
        print(f"Failed Step 1: {e}")
        return

    # 2. Test correction (Grammar mistake)
    # "猫を食べました" (I ate a cat) - weird/wrong, vs "猫が食べました" (The cat ate) or "猫を飼いました" (I bought/have a cat)
    # Or strict grammar: "私は寿司が好きです" -> "私、寿司好きだ" (casual)
    # Let's try a simple particle error: "私に行きます" (I go to me/I go to?) -> Should be "私は行きます" or "学校へ行きます"
    
    payload = {
        "message": "昨日、学校に行きます", # Tense match error (Yesterday ... go) -> went
        "history": []
    }
    
    try:
        res = requests.post(f"{BASE_URL}/chat/send", json=payload)
        res.raise_for_status()
        data = res.json()
        
        print("\n[Response 2 - Correction]")
        print(f"User: {payload['message']}")
        print(f"AI: {data.get('response')}")
        print(f"Feedback: {data.get('feedback', {}).get('overall')}")
        corrections = data.get('feedback', {}).get('corrections', [])
        if corrections:
            print("Corrections found:")
            for c in corrections:
                print(f" - {c['original']} -> {c['corrected']}: {c['explanation']}")
        else:
            print("No corrections found (unexpected for this input).")
            
    except Exception as e:
         print(f"Failed Step 2: {e}")

if __name__ == "__main__":
    test_chat()
