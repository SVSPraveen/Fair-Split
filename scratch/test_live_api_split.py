import requests
import base64
import json

with open('tests/sample_receipts/R2.png', 'rb') as f:
    b64 = base64.b64encode(f.read()).decode('utf-8')

payload = {
    "receipt_base64": b64,
    "description": "Four of us: Aman, Priya, Karan, Sara. The Gulab Jamun was shared just by Priya and Karan. Everything else was common to all four. Priya paid."
}

res = requests.post("http://127.0.0.1:8000/split", json=payload, timeout=30)
print(f"Status Code: {res.status_code}")
if res.status_code == 200:
    print("\nAPI Response Output:")
    print(json.dumps(res.json(), indent=2))
else:
    print("Error:", res.text)
