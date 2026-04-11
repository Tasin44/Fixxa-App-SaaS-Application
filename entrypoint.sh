#!/usr/bin/env bash
set -euo pipefail

echo "=========================================="
echo "Django Application Startup"
echo "=========================================="

echo "Running migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "=========================================="
echo "Launching application..."
echo "=========================================="

exec gunicorn myproject.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 4 \
    --worker-class sync \
    --timeout 60 \
    --access-logfile - \
    --error-logfile - \
    --log-level info
