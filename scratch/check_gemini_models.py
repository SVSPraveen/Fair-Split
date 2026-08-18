import os
from dotenv import load_dotenv
load_dotenv()
from google import genai
from PIL import Image

client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))
img = Image.open('tests/sample_receipts/R2.png')

models_to_test = [
    'gemini-2.5-flash',
    'gemini-2.0-flash',
    'gemini-1.5-flash',
    'gemini-2.0-flash-lite',
    'gemini-1.5-flash-8b',
    'gemini-3.7-flash'
]

print("Testing Gemini model quotas on GEMINI_API_KEY:")
for m in models_to_test:
    try:
        resp = client.models.generate_content(
            model=m,
            contents=[img, 'What is the restaurant name? Answer in 3 words.']
        )
        print(f"--> [SUCCESS] {m}: {resp.text.strip()}")
    except Exception as e:
        err_msg = str(e)
        status = "429 Quota Exceeded" if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg else err_msg[:80]
        print(f"--> [FAILED]  {m}: {status}")
