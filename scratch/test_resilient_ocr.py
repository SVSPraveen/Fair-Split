import os
import sys
import time
import re
import json
import base64
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from dotenv import load_dotenv
load_dotenv()
from groq import Groq
from backend.extraction import PRIMARY_EXTRACTION_PROMPT, _clean_and_parse_json
from backend.llm_provider import _optimize_image_for_ocr
from backend.models import ReceiptData

client = Groq(api_key=os.getenv('GROQ_API_KEY'), timeout=20.0, max_retries=0)

def extract_with_groq_resilient(image_path: str, max_retries: int = 2):
    with open(image_path, 'rb') as f:
        # Optimized to 640px to use < 450 tokens
        optimized = _optimize_image_for_ocr(f.read(), max_dimension=640)
        b64 = base64.b64encode(optimized).decode('utf-8')

    prompt = (
        "You are an expert receipt OCR assistant. "
        "Output ONLY valid raw JSON conforming strictly to the requested schema. "
        "Do not include <think> tags, markdown commentary, or preambles.\n\n"
        + PRIMARY_EXTRACTION_PROMPT
    )

    for attempt in range(max_retries + 1):
        try:
            t0 = time.time()
            resp = client.chat.completions.create(
                model='qwen/qwen3.6-27b',
                messages=[
                    {
                        "role": "system", 
                        "content": "You are a specialized receipt OCR JSON engine. You must output only raw valid JSON without reasoning, thinking, or commentary."
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
                        ]
                    }
                ],
                temperature=0.0,
                max_tokens=2500,
                timeout=15.0
            )
            elapsed = time.time() - t0
            raw = resp.choices[0].message.content or ""
            print(f"[Attempt {attempt+1}] SUCCESS in {elapsed:.2f}s! Raw length: {len(raw)}")
            parsed = _clean_and_parse_json(raw)
            receipt = ReceiptData.model_validate(parsed)
            print(f"--> Extracted {len(receipt.items)} items, Grand Total: {receipt.grand_total}")
            return receipt
        except Exception as e:
            err_str = str(e)
            print(f"[Attempt {attempt+1}] Error: {err_str[:120]}")
            if "429" in err_str and attempt < max_retries:
                # Extract wait seconds from error message if present e.g. "try again in 2.5s"
                match = re.search(r"try again in ([\d\.]+)s", err_str)
                delay = float(match.group(1)) + 0.5 if match else 2.5
                print(f"--> Rate limit 429 detected. Sleeping for {delay:.2f}s before retry...")
                time.sleep(delay)
            else:
                raise e

print("Testing resilient extraction on R6.png...")
r6 = extract_with_groq_resilient('tests/sample_receipts/R6.png')
print("R6 result:", r6.restaurant_name, r6.grand_total)

print("\nTesting resilient extraction on R2.png...")
r2 = extract_with_groq_resilient('tests/sample_receipts/R2.png')
print("R2 result:", r2.restaurant_name, r2.grand_total)
