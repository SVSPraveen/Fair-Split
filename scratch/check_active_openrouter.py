import os
import requests
from dotenv import load_dotenv
load_dotenv()

key = os.getenv('OPENROUTER_API_KEY')
res = requests.get(
    'https://openrouter.ai/api/v1/models',
    headers={'Authorization': f'Bearer {key}'}
)
if res.status_code == 200:
    data = res.json()
    free_models = [m['id'] for m in data.get('data', []) if ':free' in m['id']]
    print(f"Total free models found: {len(free_models)}")
    for fm in free_models[:25]:
        print(f" - {fm}")
else:
    print("Error:", res.status_code, res.text)
