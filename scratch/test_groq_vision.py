import os
import base64
from dotenv import load_dotenv
load_dotenv()
from groq import Groq

client = Groq(api_key=os.getenv('GROQ_API_KEY'))
with open('tests/sample_receipts/R2.png', 'rb') as f:
    b64 = base64.b64encode(f.read()).decode('utf-8')

for m in ['qwen/qwen3.6-27b', 'openai/gpt-oss-120b', 'groq/compound']:
    try:
        resp = client.chat.completions.create(
            model=m,
            messages=[{
                'role': 'user',
                'content': [
                    {'type': 'text', 'text': 'What is the restaurant name on this receipt?'},
                    {'type': 'image_url', 'image_url': {'url': f'data:image/png;base64,{b64}'}}
                ]
            }]
        )
        print(f"Success with {m}:", resp.choices[0].message.content)
        break
    except Exception as e:
        print(f"Failed with {m}:", e)
