import os
import sys
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
with open('tests/sample_receipts/R6.png', 'rb') as f:
    optimized = _optimize_image_for_ocr(f.read(), max_dimension=800)
    b64 = base64.b64encode(optimized).decode('utf-8')

prompt = (
    "You are an expert receipt OCR assistant. "
    "Output ONLY valid raw JSON without any markdown formatting or <think> tags. "
    + PRIMARY_EXTRACTION_PROMPT
)

resp = client.chat.completions.create(
    model='qwen/qwen3.6-27b',
    messages=[
        {"role": "system", "content": "You are a specialized JSON-only OCR engine. You must output only raw valid JSON without reasoning, thinking, or commentary."},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
            ]
        }
    ],
    temperature=0.0,
    max_tokens=4096
)

raw = resp.choices[0].message.content
print("Length of raw response:", len(raw))
print("\nRaw response preview:")
print(raw[:500])
print("\nEnd of raw response:")
print(raw[-300:])

parsed = _clean_and_parse_json(raw)
print("\nParsed JSON Successfully!")
print("Items count:", len(parsed.get('items', [])))
print("Grand total:", parsed.get('grand_total'))

receipt = ReceiptData.model_validate(parsed)
print("\nPydantic Validation PASSED!")
