
import requests
import json

try:
    response = requests.post(
        "http://127.0.0.1:5000/api/exercise/explain-detailed", 
        json={"log_id": "test"},
        timeout=10
    )
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")
