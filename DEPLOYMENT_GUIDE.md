# Guía de Despliegue de Actualizaciones

Esta guía describe los pasos necesarios para desplegar y actualizar la aplicación en el servidor de producción.

## Prerrequisitos

- Acceso SSH al servidor.
- Docker y Docker Compose instalados.
- Estar en el directorio raíz del proyecto.

## 🔒 Manejo de Archivos Sensibles (Secretos)

**IMPORTANTE**: Por seguridad, los siguientes archivos **NO se guardan en el repositorio** y deben crearse o subirse manualmente al servidor antes de iniciar:

1.  **`.env`**: Variables de entorno (Base de datos, claves secretas).
2.  **`serviceAccountKey.json`**: Credenciales de Firebase.

### ¿Cómo subirlos?

Si estás en tu máquina local y necesitas enviarlos al servidor (VPS), usa `scp`:

```bash
# Ejemplo para subir el .env
scp .env usuario@tu-servidor-ip:/ruta/al/proyecto/.env

# Ejemplo para subir la llave de Firebase
scp serviceAccountKey.json usuario@tu-servidor-ip:/ruta/al/proyecto/serviceAccountKey.json
```

Una vez que los archivos estén en la carpeta del proyecto en el servidor, **Docker los detectará automáticamente** porque usamos "volúmenes" en `docker-compose.yml`.

---

## Pasos para el Despliegue / Actualización

### 1. Obtener los Últimos Cambios del Código

```bash
git pull origin main
```

### 2. Verificar Archivos Secretos
Asegúrate de que `.env` y `serviceAccountKey.json` existan en la carpeta actual.
```bash
ls -la .env serviceAccountKey.json
```

### 3. Construir y Levantar Contenedores

```bash
# Construye las imágenes (sin incluir los secretos dentro de la imagen)
docker-compose build

# Levanta los servicios (montando los secretos desde la carpeta actual)
docker-compose up -d
```

### 4. Tareas de Mantenimiento (Solo si es necesario)

Si hubo cambios en dependencias o base de datos:

```bash
# Instalar nuevas dependencias
docker-compose exec web pip install -r requirements.txt

# Ejecutar migraciones
docker-compose exec web python gestion_docentes/manage.py migrate

# Recopilar archivos estáticos
docker-compose exec web python gestion_docentes/manage.py collectstatic --noinput

# Reiniciar para aplicar cambios
docker-compose restart web
```

---
**Nota sobre Docker y Archivos Ignorados**:
Aunque `.dockerignore` evita que estos archivos se "quemen" dentro de la imagen durante el `build`, el archivo `docker-compose.yml` tiene una configuración de volúmenes (`volumes: - .:/app`) que "monta" tu carpeta actual dentro del contenedor al arrancar. Por eso, basta con que los archivos existan en tu servidor para que funcionen.
