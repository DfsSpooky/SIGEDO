# Checklist Hestia + Docker

Escenario objetivo:

- VPS Debian en OVH
- usuario del sistema: `debian`
- usuario web de Hestia: `sigedo`
- dominio: `sigedo.ddnsgeek.com`
- Hestia usa `nginx + apache`
- Docker corre SIGEDO y Hestia hace reverse proxy al puerto `127.0.0.1:8000`

## Rutas recomendadas

- código: `/home/debian/SIGEDO`
- public_html del dominio: `/home/sigedo/web/sigedo.ddnsgeek.com/public_html`
- static en host: `/home/sigedo/web/sigedo.ddnsgeek.com/public_html/static`
- media en host: `/home/sigedo/web/sigedo.ddnsgeek.com/public_html/media`
- credencial Firebase en host: `/home/sigedo/.secrets/serviceAccountKey.json`

## Archivos del proyecto a usar

- env de producción: [`.env.hestia.example`](/Users/miguel/Documents/GitHub/SIGEDO/.env.hestia.example)
- compose de producción: [`docker-compose.prod.yml`](/Users/miguel/Documents/GitHub/SIGEDO/docker-compose.prod.yml)
- template nginx sin SSL: [`sigedo-docker.tpl`](/Users/miguel/Documents/GitHub/SIGEDO/deploy/hestia/sigedo-docker.tpl)
- template nginx SSL: [`sigedo-docker.stpl`](/Users/miguel/Documents/GitHub/SIGEDO/deploy/hestia/sigedo-docker.stpl)
- template Apache: puedes dejar el default de Hestia, no hace falta uno custom para este despliegue

## Preparación

1. Copia `SIGEDO` a `/home/debian/SIGEDO`.
2. Copia [`.env.hestia.example`](/Users/miguel/Documents/GitHub/SIGEDO/.env.hestia.example) a `/home/debian/SIGEDO/.env`.
3. Completa las credenciales reales.
4. Crea las carpetas del dominio:

```bash
mkdir -p /home/sigedo/web/sigedo.ddnsgeek.com/public_html/static
mkdir -p /home/sigedo/web/sigedo.ddnsgeek.com/public_html/media
mkdir -p /home/sigedo/.secrets
```

5. Copia la credencial de Firebase a `/home/sigedo/.secrets/serviceAccountKey.json`.

## Instalar templates en Hestia

```bash
sudo cp /home/debian/SIGEDO/deploy/hestia/sigedo-docker.tpl /usr/local/hestia/data/templates/web/nginx/
sudo cp /home/debian/SIGEDO/deploy/hestia/sigedo-docker.stpl /usr/local/hestia/data/templates/web/nginx/
sudo v-rebuild-web-domains sigedo
```

Luego, en el panel de Hestia, asigna al dominio el template nginx `sigedo-docker`.
En Apache puedes dejar el template estándar del dominio.

## Levantar Docker

```bash
cd /home/debian/SIGEDO
docker compose -f docker-compose.prod.yml --env-file .env up -d --build
```

## Verificación

```bash
curl -I http://127.0.0.1:8000/health/
curl -I https://sigedo.ddnsgeek.com/health/
docker compose -f /home/debian/SIGEDO/docker-compose.prod.yml --env-file /home/debian/SIGEDO/.env ps
```

## Notas importantes

- Hestia seguirá manejando SSL y el dominio.
- Docker no expone nada público salvo `127.0.0.1:8000`.
- `static` y `media` quedan en `public_html`, por eso Hestia puede servirlos con permisos del usuario web `sigedo`.
- websockets quedan cubiertos por el template nginx porque se envían headers `Upgrade` y `Connection`.
