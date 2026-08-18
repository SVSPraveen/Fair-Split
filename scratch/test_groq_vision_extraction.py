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
from backend.models import ReceiptData

client = Groq(api_key=os.getenv('GROQ_API_KEY'))
with open('tests/sample_receipts/R2.png', 'rb') as f:
    b64 = base64.b64encode(f.read()).decode('utf-8')

resp = client.chat.completions.create(
    model='qwen/qwen3.6-27b',
    messages=[{
        'role': 'user',
        'content': [
            {'type': 'text', 'text': PRIMARY_EXTRACTION_PROMPT},
            {'type': 'image_url', 'image_url': {'url': f'data:image/png;base64,{b64}'}}
        ]
    }],
    temperature=0.1,
    max_tokens=2048
)

raw = resp.choices[0].message.content
print("Raw response from Groq qwen/qwen3.6-27b vision:")
print(raw)

parsed = _clean_and_parse_json(raw)
print("\nParsed JSON:")
print(json.dumps(parsed, indent=2))

receipt = ReceiptData.model_validate(parsed)
print("\nPydantic ReceiptData:")
print(receipt.model_dump_json(indent=2))
