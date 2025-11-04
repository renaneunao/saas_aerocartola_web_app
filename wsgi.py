"""
WSGI config for Cartoleiro Aero.

This module contains the WSGI application used by Gunicorn in production.
"""
import os
import sys

# Adiciona o diretório atual ao path do Python
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

# Importa o app após garantir que o path está correto
from app import app

# O Gunicorn procura por 'application'
application = app

if __name__ == "__main__":
    # Este bloco é usado apenas ao executar o arquivo diretamente
    # (não através do Gunicorn). Útil para desenvolvimento.
    application.run(host='0.0.0.0', port=5000, debug=False)
