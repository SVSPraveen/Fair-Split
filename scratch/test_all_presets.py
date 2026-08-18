import requests, base64, time

def test_preset(path, label):
    img = open(path, 'rb').read()
    b64 = base64.b64encode(img).decode()
    t = time.time()
    r = requests.post('http://localhost:8000/split', json={
        'receipt_base64': b64,
        'description': 'All shared equally.',
    }, timeout=60)
    elapsed = time.time() - t
    d = r.json()
    gt = d.get('grand_total')
    reconciled = d.get('reconciliation', {}).get('matches_bill', '?')
    print(f"[{label}] status={r.status_code} grand_total={gt} reconciled={reconciled} elapsed={elapsed:.2f}s")

for path, label in [
    ('tests/sample_receipts/R1.png', 'R1'),
    ('tests/sample_receipts/R2.png', 'R2'),
    ('tests/sample_receipts/R3.png', 'R3'),
    ('tests/sample_receipts/R4.png', 'R4'),
    ('tests/sample_receipts/R5.png', 'R5'),
    ('tests/sample_receipts/R6.png', 'R6'),
    ('tests/sample_receipts/R7.png', 'R7'),
]:
    test_preset(path, label)
