#!/bin/sh
set -e

# Migraciones y archivos estáticos antes de arrancar
python manage.py migrate --noinput
python manage.py collectstatic --noinput

exec "$@"
