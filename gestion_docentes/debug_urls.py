import os
import django
from django.conf import settings
from django.urls import get_resolver, reverse
from django.contrib import admin

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_docentes.settings')
django.setup()

print("Searching for password_change URLs in admin site...")

found = False
for url in admin.site.get_urls():
    if hasattr(url, 'name') and url.name and 'password_change' in url.name:
        print(f"Found Admin URL: {url.name}")
        if 'core_docente_password_change' in url.name:
            found = True

if not found:
    print("WARNING: 'core_docente_password_change' NOT found in admin.site.get_urls()")
else:
    print("SUCCESS: 'core_docente_password_change' found.")

print("\nAttempting reverse resolution:")
try:
    print(f"Reverse 'admin:core_docente_password_change' -> {url}")
    print("SUCCESS: Resolved 'core_docente_password_change'")
except Exception as e:
    print(f"Error reversing 'admin:core_docente_password_change': {e}")
    print("FAILURE: Could not resolve 'core_docente_password_change'")

try:
    url = reverse('admin:core_personaldocente_password_change', args=[1])
    print(f"Reverse 'admin:core_personaldocente_password_change' -> {url}")
except Exception as e:
    print(f"Error reversing 'admin:core_personaldocente_password_change': {e}")
