import os
import time
import base64
from dotenv import load_dotenv
load_dotenv()
from openai import OpenAI

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY")
)

with open('tests/sample_receipts/R2.png', 'rb') as f:
    b64 = base64.b64encode(f.read()).decode('utf-8')

models = [
    "nvidia/nemotron-nano-12b-v2-vl:free",
    "google/gemma-4-26b-a4b-it:free",
    "meta-llama/llama-3.2-11b-vision-instruct:free",
    "mistralai/pixtral-12b:free"
]

for m in models:
    try:
        t0 = time.time()
        resp = client.chat.completions.create(
            model=m,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "Extract restaurant name from this image."},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}
                ]
            }],
            max_tokens=100
        )
        print(f"[SUCCESS] {m} ({time.time()-t0:.2f}s): {resp.choices[0].message.content}")
    except Exception as e:
        print(f"[FAILED]  {m}: {e}")
