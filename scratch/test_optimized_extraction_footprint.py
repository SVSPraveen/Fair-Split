import os
import sys
import time
import base64
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from dotenv import load_dotenv
load_dotenv()
from groq import Groq
from backend.extraction import _clean_and_parse_json
from backend.llm_provider import _optimize_image_for_ocr
from backend.models import ReceiptData

client = Groq(api_key=os.getenv('GROQ_API_KEY'), timeout=15.0, max_retries=0)

COMPACT_OCR_PROMPT = """Extract receipt data into JSON:
{
  "restaurant_name": string | null,
  "bill_number": string | null,
  "items": [{"name": string, "qty": float, "unit_price": float, "amount": float}],
  "subtotal": float,
  "discount": {"amount": float, "label": string} | null,
  "service_charge": float | null,
  "tax": {"cgst": float, "sgst": float, "total_tax": float} | null,
  "round_off": float | null,
  "grand_total": float
}
Output only raw valid JSON."""

def test_compact_ocr(image_path: str):
    with open(image_path, 'rb') as f:
        opt = _optimize_image_for_ocr(f.read(), max_dimension=540)
        b64 = base64.b64encode(opt).decode('utf-8')
    
    t0 = time.time()
    resp = client.chat.completions.create(
        model='qwen/qwen3.6-27b',
        messages=[
            {"role": "system", "content": "You are a JSON-only receipt OCR parser. Output valid JSON only."},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": COMPACT_OCR_PROMPT},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
                ]
            }
        ],
        temperature=0.0,
        max_tokens=2048,
        timeout=15.0
    )
    elapsed = time.time() - t0
    raw = resp.choices[0].message.content or ""
    print(f"OCR finished in {elapsed:.2f}s, response length: {len(raw)}")
    parsed = _clean_and_parse_json(raw)
    receipt = ReceiptData.model_validate(parsed)
    print(f"Extracted {len(receipt.items)} items, Grand Total: {receipt.grand_total}")
    return receipt

print("Testing compact OCR on R6.png (10 items)...")
r6 = test_compact_ocr('tests/sample_receipts/R6.png')
print("R6 result:", r6.restaurant_name, r6.grand_total)
