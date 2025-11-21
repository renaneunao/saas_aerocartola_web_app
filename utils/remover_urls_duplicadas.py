"""
Script para remover URLs duplicadas do arquivo player_images_by_id.js
Remove atletas que têm a URL duplicada (8hRQ7i2.png) e mantém apenas URLs únicas
"""

import re
from collections import Counter

JS_FILE = 'static/cartola_imgs/player_images_by_id.js'
URL_DUPLICADA = 'https://i.imgur.com/8hRQ7i2.png'

print("Lendo arquivo JS...")
with open(JS_FILE, 'r', encoding='utf-8') as f:
    content = f.read()

# Extrair todas as linhas
lines = content.split('\n')

# Encontrar início e fim do objeto
start_idx = None
end_idx = None
for i, line in enumerate(lines):
    if 'const playerImagesById = {' in line:
        start_idx = i
    if '};' in line and start_idx is not None and i > start_idx:
        end_idx = i
        break

if start_idx is None or end_idx is None:
    print("ERRO: Não foi possível encontrar o objeto playerImagesById")
    exit(1)

print(f"Objeto encontrado nas linhas {start_idx} a {end_idx}")

# Extrair todas as entradas
pattern = r'(\d+):\s*"([^"]+)"'
matches = re.findall(pattern, content)

dados = {}
for atleta_id, url in matches:
    if url and url != 'null':
        dados[int(atleta_id)] = url

print(f"\nTotal de entradas encontradas: {len(dados)}")

# Contar URLs
url_counts = Counter(dados.values())
print(f"URLs unicas: {len(url_counts)}")

# Identificar atletas com URL duplicada
atletas_com_url_duplicada = [aid for aid, url in dados.items() if url == URL_DUPLICADA]
print(f"\nAtletas com URL duplicada ({URL_DUPLICADA}): {len(atletas_com_url_duplicada)}")

# Remover entradas com URL duplicada
atletas_para_remover = set(atletas_com_url_duplicada)
print(f"Removendo {len(atletas_para_remover)} atletas com URL duplicada...")

# Reconstruir o arquivo
new_lines = []
in_object = False
removidos = 0
mantidos = 0

for i, line in enumerate(lines):
    if i < start_idx or i > end_idx:
        # Linhas antes e depois do objeto - manter
        new_lines.append(line)
        continue
    
    if i == start_idx:
        # Linha de abertura do objeto
        new_lines.append(line)
        in_object = True
        continue
    
    if i == end_idx:
        # Linha de fechamento do objeto
        # Remover vírgula extra se necessário
        if new_lines and new_lines[-1].strip().endswith(','):
            new_lines[-1] = new_lines[-1].rstrip().rstrip(',')
        new_lines.append(line)
        break
    
    # Dentro do objeto - verificar se deve manter
    match = re.search(r'(\d+):\s*"([^"]+)"', line)
    if match:
        atleta_id = int(match.group(1))
        if atleta_id in atletas_para_remover:
            removidos += 1
            continue  # Pular esta linha
        else:
            mantidos += 1
            new_lines.append(line)
    else:
        # Linha sem match (comentários, etc) - manter
        new_lines.append(line)

# Escrever novo arquivo
new_content = '\n'.join(new_lines)

# Backup do arquivo original
backup_file = JS_FILE + '.backup'
print(f"\nCriando backup: {backup_file}")
with open(backup_file, 'w', encoding='utf-8') as f:
    f.write(content)

# Escrever novo arquivo
print(f"Escrevendo novo arquivo...")
with open(JS_FILE, 'w', encoding='utf-8') as f:
    f.write(new_content)

print("\n" + "=" * 60)
print("RESUMO")
print("=" * 60)
print(f"Total de entradas originais: {len(dados)}")
print(f"Atletas removidos (URL duplicada): {removidos}")
print(f"Atletas mantidos: {mantidos}")
print(f"Backup salvo em: {backup_file}")
print("=" * 60)

