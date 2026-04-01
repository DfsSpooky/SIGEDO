#!/bin/sh
set -e

cd /app/gestion_docentes

python manage.py migrate --noinput
python manage.py collectstatic --noinput

exec "$@"
