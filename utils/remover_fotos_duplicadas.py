"""
Script para remover fotos duplicadas do diretório foto_atletas
Remove as fotos dos atletas que tinham a URL duplicada (8hRQ7i2.png)
"""

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FOTO_DIR = PROJECT_ROOT / 'static' / 'cartola_imgs' / 'foto_atletas'

# IDs dos atletas que tinham a URL duplicada (extraído do script anterior)
# Vou ler do arquivo JS para pegar os IDs que foram removidos
JS_FILE = PROJECT_ROOT / 'static' / 'cartola_imgs' / 'player_images_by_id.js.backup'
URL_DUPLICADA = 'https://i.imgur.com/8hRQ7i2.png'

import re

print("Lendo backup do arquivo JS para identificar atletas removidos...")
with open(JS_FILE, 'r', encoding='utf-8') as f:
    content = f.read()

# Extrair IDs com a URL duplicada
pattern = r'(\d+):\s*"([^"]+)"'
matches = re.findall(pattern, content)

atletas_para_remover = []
for atleta_id, url in matches:
    if url == URL_DUPLICADA:
        atletas_para_remover.append(int(atleta_id))

print(f"Encontrados {len(atletas_para_remover)} atletas com URL duplicada")

# Remover fotos
removidos = 0
nao_encontrados = 0

print(f"\nRemovendo fotos do diretorio: {FOTO_DIR}")

for atleta_id in atletas_para_remover:
    # Tentar diferentes extensões
    for ext in ['.jpg', '.jpeg', '.png', '.gif']:
        foto_path = FOTO_DIR / f"{atleta_id}{ext}"
        if foto_path.exists():
            try:
                foto_path.unlink()
                removidos += 1
                print(f"Removido: {atleta_id}{ext}")
                break
            except Exception as e:
                print(f"Erro ao remover {atleta_id}{ext}: {e}")
        else:
            if ext == '.gif':  # Última tentativa
                nao_encontrados += 1

print("\n" + "=" * 60)
print("RESUMO")
print("=" * 60)
print(f"Atletas identificados para remover: {len(atletas_para_remover)}")
print(f"Fotos removidas: {removidos}")
print(f"Fotos nao encontradas: {nao_encontrados}")
print("=" * 60)

