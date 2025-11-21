"""
Script para baixar fotos dos atletas do arquivo player_images_by_id.js
e salvar no diretório foto_atletas com o ID do atleta como nome do arquivo.
"""

import os
import re
import requests
from pathlib import Path
from urllib.parse import urlparse

# Caminhos
PROJECT_ROOT = Path(__file__).resolve().parents[1]
JS_FILE = PROJECT_ROOT / 'static' / 'cartola_imgs' / 'player_images_by_id.js'
OUTPUT_DIR = PROJECT_ROOT / 'static' / 'cartola_imgs' / 'foto_atletas'

def extrair_dados_js():
    """Extrai os IDs e URLs do arquivo JS"""
    print(f"Lendo arquivo: {JS_FILE}", flush=True)
    
    with open(JS_FILE, 'r', encoding='utf-8') as f:
        content = f.read()
    
    print(f"Arquivo lido. Tamanho: {len(content)} caracteres", flush=True)
    
    # Extrair o objeto playerImagesById usando regex
    # Procura por: ID: "URL"
    pattern = r'(\d+):\s*"([^"]+)"'
    matches = re.findall(pattern, content)
    
    print(f"Total de matches encontrados: {len(matches)}", flush=True)
    
    dados = {}
    for atleta_id, url in matches:
        # Ignorar placeholders e null
        if url and 'placeholder' not in url.lower() and url != 'null':
            dados[int(atleta_id)] = url
    
    print(f"Encontrados {len(dados)} atletas com URLs validas (sem placeholders)", flush=True)
    return dados

def obter_extensao_arquivo(url):
    """Obtém a extensão do arquivo da URL"""
    parsed = urlparse(url)
    path = parsed.path
    if '.' in path:
        ext = os.path.splitext(path)[1]
        # Normalizar extensões
        if ext.lower() in ['.jpg', '.jpeg']:
            return '.jpg'
        elif ext.lower() == '.png':
            return '.png'
        elif ext.lower() == '.gif':
            return '.gif'
    # Padrão: jpg
    return '.jpg'

def baixar_foto(atleta_id, url, output_dir):
    """Baixa uma foto e salva com o ID do atleta"""
    try:
        # Obter extensão
        ext = obter_extensao_arquivo(url)
        filename = f"{atleta_id}{ext}"
        filepath = output_dir / filename
        
        # Se já existe, pular
        if filepath.exists():
            return True, 'ja existe'
        
        # Baixar
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        # Verificar se é uma imagem válida
        content_type = response.headers.get('content-type', '')
        if 'image' not in content_type:
            return False, f'tipo invalido: {content_type}'
        
        # Salvar
        with open(filepath, 'wb') as f:
            f.write(response.content)
        
        tamanho_kb = len(response.content) / 1024
        return True, f'baixado ({tamanho_kb:.1f} KB)'
    
    except requests.exceptions.RequestException as e:
        return False, f'erro de rede: {str(e)[:50]}'
    except Exception as e:
        return False, f'erro: {str(e)[:50]}'

def main():
    """Função principal"""
    import sys
    import codecs
    # Configurar encoding UTF-8 para Windows
    if sys.platform == 'win32':
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    
    print("=" * 60, flush=True)
    print("BAIXADOR DE FOTOS DE ATLETAS", flush=True)
    print("=" * 60, flush=True)
    
    # Criar diretório de saída
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Diretorio de saida: {OUTPUT_DIR}", flush=True)
    print("", flush=True)
    
    # Extrair dados do JS
    print("ETAPA 1: Extraindo dados do arquivo JS...", flush=True)
    dados = extrair_dados_js()
    print("", flush=True)
    
    if not dados:
        print("ERRO: Nenhum dado encontrado!", flush=True)
        return
    
    # Estatísticas
    total = len(dados)
    baixados = 0
    ja_existiam = 0
    erros = 0
    
    print("=" * 60, flush=True)
    print(f"ETAPA 2: Iniciando download de {total} fotos...", flush=True)
    print("=" * 60, flush=True)
    print("", flush=True)
    
    # Baixar cada foto
    for idx, (atleta_id, url) in enumerate(dados.items(), 1):
        print(f"[{idx}/{total}] Processando atleta {atleta_id}...", end=' ', flush=True)
        
        sucesso, status = baixar_foto(atleta_id, url, OUTPUT_DIR)
        
        if sucesso:
            if status == 'ja existe':
                ja_existiam += 1
                print(f"OK - {status}")
            else:
                baixados += 1
                print(f"OK - {status}")
        else:
            erros += 1
            print(f"ERRO - {status}")
        
        # Progresso a cada 5
        if idx % 5 == 0:
            print(f"   >>> Progresso: {idx}/{total} ({idx*100//total}%) - Baixados: {baixados}, Ja existiam: {ja_existiam}, Erros: {erros}", flush=True)
    
    # Resumo
    print("", flush=True)
    print("=" * 60, flush=True)
    print("RESUMO FINAL", flush=True)
    print("=" * 60, flush=True)
    print(f"Total de atletas processados: {total}", flush=True)
    print(f"Fotos baixadas: {baixados}", flush=True)
    print(f"Fotos que ja existiam: {ja_existiam}", flush=True)
    print(f"Erros: {erros}", flush=True)
    print(f"Diretorio: {OUTPUT_DIR}", flush=True)
    print("=" * 60, flush=True)

if __name__ == '__main__':
    main()

