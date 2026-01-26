import os
import google.generativeai as genai

# Read API key from .env file directly
with open('/app/.env', 'r') as f:
    for line in f:
        if line.startswith('GEMINI_API_KEY='):
            api_key = line.split('=')[1].strip()
            break

genai.configure(api_key=api_key)
try:
    print("Listing models...")
    models = genai.list_models()
    for m in models:
        print(f"Model: {m.name}")
except Exception as e:
    print(f"Error: {e}")
