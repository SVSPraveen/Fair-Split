import os
import time
from dotenv import load_dotenv
load_dotenv()
from groq import Groq

client = Groq(api_key=os.getenv('GROQ_API_KEY'))

# List all models available on Groq
try:
    models = client.models.list()
    print("Available Groq models:")
    for m in models.data:
        print(f" - {m.id}")
except Exception as e:
    print("Error listing Groq models:", e)
