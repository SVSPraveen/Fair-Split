import requests
import base64
import json

with open('tests/sample_receipts/R6.png', 'rb') as f:
    b64 = base64.b64encode(f.read()).decode('utf-8')

desc = (
    "Party of six: Vikram, Ananya, Kabir, Rhea, Siddharth, Tara. "
    "Vikram and Kabir shared the 3 pints of Craft IPA Beer. "
    "Ananya and Tara had the Fresh Mint Mojitos. "
    "Siddharth and Rhea shared the Smoked BBQ Pork Ribs and Crispy Calamari. "
    "All six of us shared the 2 Wood-Fired Truffle Pizzas, Loaded Nachos Supreme, and Mineral Water. "
    "Ananya had the Classic Caesar Salad. "
    "Rhea, Tara, and Vikram shared the 2 Belgian Chocolate Lava Cakes. "
    "Vikram paid the entire bill."
)

payload = {
    "receipt_base64": b64,
    "description": desc
}

res = requests.post("http://127.0.0.1:8000/split", json=payload, timeout=30)
print(f"Status Code: {res.status_code}")
if res.status_code == 200:
    print("\nAPI Response Output for R6 (Urban Brewery):")
    print(json.dumps(res.json(), indent=2))
else:
    print("Error:", res.text)
