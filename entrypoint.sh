#!/bin/bash
set -e

echo "🚀 Iniciando aplicação web Cartola Aero..."
echo "🌐 Iniciando servidor web..."
exec gunicorn --bind 0.0.0.0:5000 --workers 4 --timeout 120 --access-logfile - --error-logfile - wsgi:application

