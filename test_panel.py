import requests
from bs4 import BeautifulSoup
import time

time.sleep(5)

session = requests.Session()
BASE_URL = "http://localhost:8000"

# Get login page and CSRF token
try:
    login_page_url = f"{BASE_URL}/accounts/login/?next=/panel/"
    response = session.get(login_page_url)
    response.raise_for_status()
    soup = BeautifulSoup(response.content, 'html.parser')
    csrf_token = soup.find('input', {'name': 'csrfmiddlewaretoken'})['value']
    print("Successfully fetched login page and CSRF token.")
except Exception as e:
    print(f"Failed to get login page: {e}")
    exit()

# Login
login_data = {
    'username': 'admin',
    'password': 'admin123',
    'csrfmiddlewaretoken': csrf_token,
}
try:
    response = session.post(login_page_url, data=login_data, headers={'Referer': login_page_url})
    response.raise_for_status()
    if "panel" in response.url:
        print("Login successful.")
    else:
        print("Login failed. Redirected to:", response.url)
        exit()
except Exception as e:
    print(f"Login request failed: {e}")
    exit()

# Test pages
models_to_test = ['docente', 'semestre', 'curso', 'grupo', 'asistenciadiaria', 'solicitudintercambio', 'notificacion']
for model in models_to_test:
    url = f"{BASE_URL}/panel/core/{model}/"
    try:
        response = session.get(url)
        response.raise_for_status()
        if response.status_code == 200:
            print(f"Successfully reached list page for {model}.")
        else:
            print(f"Failed to reach list page for {model}. Status: {response.status_code}")
    except Exception as e:
        print(f"Failed to reach list page for {model}: {e}")
