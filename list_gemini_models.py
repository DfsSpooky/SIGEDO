import os
import google.generativeai as genai
from django.conf import settings
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_docentes.settings')
django.setup()

genai.configure(api_key=settings.GEMINI_API_KEY)
try:
    models = genai.list_models()
    for m in models:
        print(f"Model: {m.name}, Methods: {m.supported_generation_methods}")
except Exception as e:
    print(f"Error: {e}")
