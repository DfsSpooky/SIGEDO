# -----------------------------------------------------------------------------
# Script para ESP32 con MicroPython - Lector RFID MFRC522
#
# Funcionalidad:
# 1. Se conecta a una red WiFi.
# 2. Escanea continuamente buscando tarjetas RFID.
# 3. Cuando detecta una tarjeta, envía su UID a un servidor web (Django)
#    para registrar la asistencia.
# 4. Muestra la respuesta del servidor en la consola.
#
# Autor: Jules
# Fecha: 2025-08-09
# -----------------------------------------------------------------------------

# Importar las librerías necesarias
from machine import Pin, SPI
from time import sleep
import network
import urequests # Asegúrate de que tu firmware de MicroPython incluya 'urequests'
from mfrc522 import MFRC522 # Esta librería debe estar en la memoria del ESP32

# --- CONFIGURACIÓN (MODIFICAR SEGÚN SEA NECESARIO) ---

# 1. Configuración de la Red WiFi
WIFI_SSID = "NOMBRE_DE_TU_WIFI"  # Reemplaza con el nombre de tu red WiFi
WIFI_PASSWORD = "PASSWORD_DE_TU_WIFI" # Reemplaza con tu contraseña

# 2. Configuración del Servidor Django
# Reemplaza la IP con la dirección de tu ordenador donde corre el servidor Django.
# Asegúrate de que el ESP32 y el servidor estén en la misma red.
# Si corres Django con `python manage.py runserver 0.0.0.0:8000`, usa la IP de tu máquina.
SERVER_URL = "http://192.168.1.100:8000/api/asistencia_rfid/"

# 3. Configuración de los pines para el lector RFID MFRC522
# Estos pines deben coincidir con tu conexión física.
# SCK: 18, MOSI: 23, MISO: 19, RST: 21, CS: 5
sck_pin = Pin(18)
mosi_pin = Pin(23)
miso_pin = Pin(19)
ss_pin = Pin(5)
rst_pin = Pin(21)

# LED en la placa para feedback visual (opcional)
# La mayoría de las placas ESP32 tienen un LED en el pin 2
led = Pin(2, Pin.OUT)

# --- FIN DE LA CONFIGURACIÓN ---


# Función para conectar a la red WiFi
def conectar_wifi():
    """
    Se conecta a la red WiFi especificada en la configuración.
    """
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print('Conectando a la red WiFi...')
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        # Espera hasta que la conexión sea exitosa
        while not wlan.isconnected():
            sleep(1)
            print('.')
    print('---')
    print(f"Conexión exitosa. IP del ESP32: {wlan.ifconfig()[0]}")
    print(f"Endpoint del servidor: {SERVER_URL}")
    print('---')


# Función principal
def main():
    """
    Bucle principal que lee tarjetas y envía los datos.
    """
    # Inicializar el lector RFID
    rdr = MFRC522(sck_pin, mosi_pin, miso_pin, rst_pin, ss_pin)

    print("Lector RFID inicializado. Esperando tarjeta...")

    while True:
        # Poner el LED en bajo (listo para leer)
        led.value(0)

        (stat, tag_type) = rdr.request(rdr.REQIDL)

        if stat == rdr.OK:
            (stat, raw_uid) = rdr.anticoll()

            if stat == rdr.OK:
                # Encender el LED para indicar lectura
                led.value(1)

                # Formatear el UID a un string hexadecimal separado por dos puntos
                # Ejemplo: [10, 27, 44, 61] -> "0A:1B:2C:3D"
                uid = ":".join(["%02X" % b for b in raw_uid])
                print(f"UID encontrado: {uid}")

                # Preparar los datos para enviar al servidor
                payload = {'uid': uid}
                headers = {'Content-Type': 'application/json'}

                try:
                    print("Enviando datos al servidor...")
                    # Enviar la petición POST
                    response = urequests.post(SERVER_URL, json=payload, headers=headers)

                    # Procesar la respuesta del servidor
                    if response.status_code == 200:
                        server_data = response.json()
                        print(f"Respuesta del servidor: {server_data.get('status', 'sin_status')} - {server_data.get('message', 'sin_mensaje')}")
                    else:
                        print(f"Error del servidor. Código: {response.status_code}")
                        print(f"Respuesta: {response.text}")

                    response.close()

                except Exception as e:
                    print(f"Error al enviar la petición: {e}")

                # Apagar el LED después del proceso
                led.value(0)

                # Pausa para evitar lecturas repetidas de la misma tarjeta
                print("Esperando 2 segundos...")
                sleep(2)
                print("\nListo para la siguiente tarjeta.")


# --- Punto de entrada del script ---
if __name__ == "__main__":
    try:
        conectar_wifi()
        main()
    except KeyboardInterrupt:
        print("Programa detenido por el usuario.")
    except Exception as e:
        print(f"Ocurrió un error crítico: {e}")
        # En caso de error, es útil reiniciar para intentar reconectar
        # from machine import reset
        # print("Reiniciando en 5 segundos...")
        # sleep(5)
        # reset()
