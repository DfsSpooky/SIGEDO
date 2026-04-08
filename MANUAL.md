# Manual de Despliegue en un VPS de OVH con Docker

Esta guía te mostrará cómo desplegar la aplicación en un VPS de OVH utilizando Docker y Docker Compose.

## 1. Prerrequisitos

Antes de comenzar, asegúrate de tener lo siguiente:

*   Un VPS de OVH con un sistema operativo Linux (por ejemplo, Ubuntu 22.04).
*   Acceso SSH al VPS.
*   Un nombre de dominio apuntando a la dirección IP de tu VPS (opcional, pero recomendado).

### Instalar Docker y Docker Compose

Conéctate a tu VPS por SSH y ejecuta los siguientes comandos para instalar Docker:

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

## 2. Configuración

### Clonar el Repositorio

Clona este repositorio en tu VPS:

```bash
git clone <URL_DEL_REPOSITORIO>
cd <NOMBRE_DEL_REPOSITORIO>
```

### Configurar el Archivo `.env`

El archivo `.env` contiene las variables de entorno para la aplicación. Necesitas editar este archivo para configurar tu entorno de producción.

```bash
nano .env
```

Asegúrate de configurar las siguientes variables:

*   `DEBUG`: Cámbialo a `False` para producción.
*   `ALLOWED_HOSTS`: Establece el nombre de dominio de tu VPS (por ejemplo, `ALLOWED_HOSTS=tudominio.com,www.tudominio.com`). Si no tienes un dominio, puedes usar la dirección IP de tu VPS.
*   `POSTGRES_PASSWORD`: Cambia la contraseña de la base de datos por una más segura.

Guarda y cierra el archivo (`Ctrl+X`, luego `Y`, y `Enter`).

## 3. Despliegue

Una vez que hayas configurado el archivo `.env`, puedes construir y ejecutar los contenedores de Docker:

```bash
sudo docker-compose up -d --build
```

Este comando construirá las imágenes de Docker y ejecutará los servicios en segundo plano (`-d`).

## 4. Tareas Iniciales

### Ejecutar Migraciones de la Base de Datos

Después de que los contenedores estén en funcionamiento, necesitas ejecutar las migraciones de la base de datos de Django:

```bash
sudo docker-compose exec web python gestion_docentes/manage.py migrate
```

### Crear un Superusuario

Para acceder al panel de administración de Django, necesitas crear un superusuario:

```bash
sudo docker-compose exec web python gestion_docentes/manage.py createsuperuser
```

Sigue las instrucciones en pantalla para crear tu cuenta de administrador.

## 5. Acceso a la Aplicación

¡Felicidades! Tu aplicación está ahora desplegada. Puedes acceder a ella abriendo tu navegador web y visitando la dirección IP o el nombre de dominio de tu VPS.

Para acceder al panel de administración, ve a `http://<TU_DOMINIO_O_IP>/admin` e inicia sesión con las credenciales de superusuario que creaste en el paso anterior.
