#!/bin/bash
set -e

echo "=========================================="
echo "🚀 Django Application Startup"
echo "=========================================="

# Run migrations
echo "🔄 Running migrations..."
python manage.py migrate --noinput

# Collect static files
echo "📦 Collecting static files..."
python manage.py collectstatic --noinput

echo "=========================================="
echo "✨ Launching application..."
echo "=========================================="

# Use Django development server for local development
if [ "$DEBUG" = "True" ]; then
    exec python manage.py runserver 0.0.0.0:8000
else
    # Use Gunicorn for production
    exec gunicorn myproject.wsgi:application \
        --bind 0.0.0.0:8000 \
        --workers 4 \
        --worker-class sync \
        --timeout 60 \
        --access-logfile - \
        --error-logfile - \
        --log-level info
fi
