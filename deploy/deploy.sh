#!/bin/bash
# =============================================================================
# SIGEDO - Script de despliegue en Hestia Panel (OVH / Debian)
# Uso: bash deploy/deploy.sh
# Usuario del sistema: debian
# =============================================================================
set -e

REPO_DIR="/home/debian/SIGEDO"
ENV_FILE="$REPO_DIR/.env"
COMPOSE="$REPO_DIR/docker-compose.prod.yml"

echo ""
echo "======================================"
echo "  SIGEDO - Despliegue en producción"
echo "======================================"
echo ""

# --- Verificar .env ---
if [ ! -f "$ENV_FILE" ]; then
    echo "[!] No existe .env en $REPO_DIR"
    echo "    Copia .env.hestia.example a .env y completa las credenciales."
    echo "    cp $REPO_DIR/.env.hestia.example $ENV_FILE"
    exit 1
fi

# --- Firebase: crear dummy si no existe ---
FIREBASE_KEY=$(grep "^HOST_FIREBASE_KEY=" "$ENV_FILE" | cut -d= -f2)
if [ -n "$FIREBASE_KEY" ] && [ ! -f "$FIREBASE_KEY" ]; then
    echo "[i] Firebase key no encontrada en $FIREBASE_KEY — creando dummy..."
    mkdir -p "$(dirname "$FIREBASE_KEY")"
    echo '{"type":"service_account"}' > "$FIREBASE_KEY"
    chmod 600 "$FIREBASE_KEY"
fi

# --- Levantar Docker ---
echo "[1/3] Construyendo e iniciando contenedores..."
docker compose -f "$COMPOSE" --env-file "$ENV_FILE" up -d --build

# --- Esperar a que Django esté listo ---
echo "[2/3] Esperando que la app esté lista..."
for i in $(seq 1 30); do
    if docker compose -f "$COMPOSE" --env-file "$ENV_FILE" \
        exec -T web python -c "print('ok')" > /dev/null 2>&1; then
        break
    fi
    echo "    ... esperando ($i/30)"
    sleep 3
done

# --- Migrations y collectstatic ---
echo "[3/3] Aplicando migraciones..."
docker compose -f "$COMPOSE" --env-file "$ENV_FILE" \
    exec -T web python manage.py migrate --noinput

echo ""
echo "======================================"
echo "  ✅ Despliegue completado"
echo "======================================"
echo ""
echo "  Verifica con:"
echo "  curl -I http://127.0.0.1:8010/health/"
echo ""
echo "  Logs en tiempo real:"
echo "  docker compose -f $COMPOSE logs -f"
echo ""
