#!/bin/bash
set -e

echo "🚀 Iniciando aplicação web Cartola Aero..."

# Aguardar o banco de dados estar disponível (opcional, mas útil)
echo "⏳ Aguardando banco de dados..."
until python -c "from database import get_db_connection, close_db_connection; conn = get_db_connection(); close_db_connection(conn)" 2>/dev/null; do
  echo "   Banco ainda não disponível, aguardando..."
  sleep 2
done

echo "✅ Banco de dados disponível!"

# Inicializar banco de dados
echo "📋 Inicializando banco de dados..."
python init_database.py || echo "⚠️  Aviso: Erro ao inicializar banco (pode ser que já esteja inicializado)"

# Iniciar aplicação
echo "🌐 Iniciando servidor web..."
exec gunicorn --bind 0.0.0.0:5000 --workers 4 --timeout 120 --access-logfile - --error-logfile - wsgi:application

