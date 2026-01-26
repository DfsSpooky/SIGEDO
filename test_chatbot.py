from django.test import Client
import json
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_docentes.settings')
import django
django.setup()

from django.contrib.auth.models import User
from core.models import Docente

client = Client()
docente = Docente.objects.filter(is_superuser=True).first()
if not docente:
    docente = Docente.objects.create_superuser('testadmin', 'admin@example.com', 'password')

client.force_login(docente)

response = client.post('/api/chatbot-horario/', 
                       data=json.dumps({'prompt': 'Hola, ¿puedes mover un curso?'}),
                       content_type='application/json')

print(f"Status: {response.status_code}")
print(f"Response: {response.json()}")
