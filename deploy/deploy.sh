#!/bin/bash
# =============================================================================
# SIGEDO - Script de despliegue en Hestia Panel (OVH / Debian)
# Repositorio: https://github.com/DfsSpooky/SIGEDO
# Rama: Despliegue-final-SIGEDO
# Uso: bash deploy/deploy.sh
# Usuario del sistema: debian
# =============================================================================
set -e

REPO_URL="https://github.com/DfsSpooky/SIGEDO.git"
REPO_BRANCH="Despliegue-final-SIGEDO"
REPO_DIR="/home/debian/SIGEDO"
ENV_FILE="$REPO_DIR/.env"
COMPOSE="$REPO_DIR/docker-compose.prod.yml"

echo ""
echo "======================================"
echo "  SIGEDO - Despliegue en producción"
echo "======================================"
echo ""

# --- Obtener código desde Git ---
if [ ! -d "$REPO_DIR/.git" ]; then
    echo "[i] Clonando repositorio (rama: $REPO_BRANCH)..."
    git clone --branch "$REPO_BRANCH" "$REPO_URL" "$REPO_DIR"
else
    echo "[i] Actualizando código desde Git..."
    git -C "$REPO_DIR" fetch origin
    git -C "$REPO_DIR" checkout "$REPO_BRANCH"
    git -C "$REPO_DIR" pull origin "$REPO_BRANCH"
fi

# --- Verificar .env ---
if [ ! -f "$ENV_FILE" ]; then
    echo ""
    echo "[!] No existe .env — creando desde el ejemplo..."
    cp "$REPO_DIR/.env.hestia.example" "$ENV_FILE"
    echo ""
    echo "    ⚠️  EDITA el archivo .env antes de continuar:"
    echo "    nano $ENV_FILE"
    echo ""
    echo "    Cambia al menos: SECRET_KEY, ID_ENCRYPTION_KEY, POSTGRES_PASSWORD"
    echo ""
    exit 1
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
