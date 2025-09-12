# Guía de Despliegue de Actualizaciones

Esta guía describe los pasos necesarios para actualizar la aplicación en el servidor de producción después de haber realizado cambios en el código.

Es importante seguir estos pasos en orden para asegurar que la aplicación se actualice correctamente.

## Prerrequisitos

- Acceso SSH al servidor donde está alojada la aplicación.
- Estar en el directorio raíz del proyecto (donde se encuentra el archivo `docker-compose.yml`).

## Pasos para el Despliegue

### Paso 1: Obtener los Últimos Cambios del Código

Primero, asegúrate de que el código en tu servidor esté actualizado con la última versión del repositorio.

```bash
git pull origin main
```
*(Reemplaza `main` con el nombre de la rama principal si es diferente, por ejemplo `master`)*

### Paso 2: Reconstruir los Contenedores de Docker

Si se han realizado cambios en los archivos de configuración de Docker (`Dockerfile`, `docker-compose.yml`) o si se han añadido nuevas dependencias, es una buena práctica reconstruir las imágenes de los contenedores.

```bash
docker-compose build
```

### Paso 3: Instalar o Actualizar Dependencias

Las nuevas funcionalidades que hemos añadido (`djangorestframework`) requieren nuevas librerías de Python. El siguiente comando leerá el archivo `requirements.txt` actualizado y las instalará dentro del contenedor de la aplicación.

```bash
docker-compose run --rm web pip install -r requirements.txt
```
* **`docker-compose run`**: Ejecuta un comando en un nuevo contenedor para un servicio.
* **`--rm`**: Elimina el contenedor después de que el comando se complete. Es útil para comandos que solo se ejecutan una vez, como este.
* **`web`**: Es el nombre del servicio de la aplicación Django definido en `docker-compose.yml`.
* **`pip install -r requirements.txt`**: Es el comando que se ejecuta dentro del contenedor.

### Paso 4: Ejecutar las Migraciones de la Base de Datos

Hemos realizado cambios en los modelos de la base de datos (añadimos el campo `dia_semana`), por lo que es crucial aplicar estas migraciones.

```bash
docker-compose run --rm web python gestion_docentes/manage.py migrate
```
Este comando ejecutará las nuevas migraciones que creamos (`0017_...` y `0018_...`) y actualizará el esquema de la base de datos.

### Paso 5: Reiniciar los Servicios

Finalmente, para que todos los cambios surtan efecto (código, dependencias y base de datos), es necesario reiniciar los servicios de la aplicación.

```bash
docker-compose up -d --force-recreate --no-deps web nginx
```
* **`up -d`**: Inicia los servicios en segundo plano (detached mode).
* **`--force-recreate`**: Fuerza la recreación de los contenedores, incluso si su configuración no ha cambiado. Esto asegura que se utilice la nueva imagen y el nuevo código.
* **`--no-deps`**: Evita que se reinicien los servicios de los que dependen (como la base de datos `db`), lo cual no es necesario en este caso.
* **`web nginx`**: Especifica los servicios que queremos reiniciar.

---

¡Y eso es todo! Después de completar estos pasos, la aplicación estará actualizada y funcionando con todas las nuevas mejoras que hemos implementado.
