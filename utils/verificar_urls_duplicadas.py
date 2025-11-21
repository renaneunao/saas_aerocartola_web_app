"""
Script para verificar URLs duplicadas no arquivo player_images_by_id.js
"""

import re
from collections import Counter

JS_FILE = 'static/cartola_imgs/player_images_by_id.js'

print("Lendo arquivo JS...")
with open(JS_FILE, 'r', encoding='utf-8') as f:
    content = f.read()

# Extrair IDs e URLs
pattern = r'(\d+):\s*"([^"]+)"'
matches = re.findall(pattern, content)

dados = {}
for atleta_id, url in matches:
    if url and 'placeholder' not in url.lower() and url != 'null':
        dados[int(atleta_id)] = url

print(f"\nTotal de atletas com URLs validas: {len(dados)}")

# Contar URLs duplicadas
url_counts = Counter(dados.values())
urls_unicas = len(url_counts)
urls_duplicadas = sum(1 for count in url_counts.values() if count > 1)

print(f"URLs unicas: {urls_unicas}")
print(f"URLs duplicadas: {urls_duplicadas}")

# Mostrar as URLs mais duplicadas
print("\nTop 10 URLs mais duplicadas:")
for url, count in url_counts.most_common(10):
    atletas_com_essa_url = [aid for aid, u in dados.items() if u == url]
    print(f"\n{count}x vezes: {url}")
    print(f"  Atletas: {atletas_com_essa_url[:10]}{'...' if len(atletas_com_essa_url) > 10 else ''}")

