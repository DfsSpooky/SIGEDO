# Despliegue en Docker detrás de Hestia

Este proyecto queda pensado para:

- Docker en el VPS
- Hestia como panel del dominio y SSL
- `nginx + apache` en Hestia
- reverse proxy desde Hestia hacia `127.0.0.1:8010`
- `static` y `media` persistidos en el `public_html` del usuario `sigedo`

## Arquitectura

```text
Internet
  -> Hestia Nginx/SSL
  -> proxy_pass 127.0.0.1:8010
  -> contenedor web (Daphne / Django ASGI)
  -> contenedor db (PostgreSQL)
  -> contenedor redis
```

Los archivos:

- `static` se escriben en `/home/sigedo/web/sigedo.ddnsgeek.com/public_html/static`
- `media` se escriben en `/home/sigedo/web/sigedo.ddnsgeek.com/public_html/media`

## Archivos de apoyo

- env base: [`.env.example`](/Users/miguel/Documents/GitHub/SIGEDO/.env.example)
- env producción Hestia: [`.env.hestia.example`](/Users/miguel/Documents/GitHub/SIGEDO/.env.hestia.example)
- compose producción: [`docker-compose.prod.yml`](/Users/miguel/Documents/GitHub/SIGEDO/docker-compose.prod.yml)
- checklist operativo: [HESTIA_CHECKLIST.md](/Users/miguel/Documents/GitHub/SIGEDO/HESTIA_CHECKLIST.md)

## Comando principal

```bash
docker compose -f docker-compose.prod.yml --env-file .env up -d --build
```

## Validaciones recomendadas

```bash
docker compose -f docker-compose.prod.yml --env-file .env ps
curl -I http://127.0.0.1:8010/health/
curl -I https://sigedo.ddnsgeek.com/health/
```

## Observaciones

- Hestia sirve el dominio; Docker no necesita exponer puertos públicos distintos.
- El template nginx de Hestia debe manejar `/static/`, `/media/` y el proxy a `127.0.0.1:8010`.
- Si cambias credenciales o `.env`, reinicia con `docker compose ... up -d`.
