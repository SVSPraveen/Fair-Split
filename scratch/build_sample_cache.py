import hashlib
from pathlib import Path

samples = ["R1.png", "R2.png", "R3.png", "R4.png", "R5.png", "R6.png"]
for s in samples:
    for base in ["tests/sample_receipts", "frontend/samples"]:
        p = Path(base) / s
        if p.exists():
            h = hashlib.sha256(p.read_bytes()).hexdigest()
            print(f"{p}: {h}")
