import requests, base64

img = open('tests/sample_receipts/R1.png', 'rb').read()
b64 = base64.b64encode(img).decode()
r = requests.post('http://localhost:8000/split', json={
    'image_base64': b64,
    'description': 'All shared equally.',
    'filename': 'R1.png'
}, timeout=60)
print("Status:", r.status_code)
print("Body:", r.text[:3000])
