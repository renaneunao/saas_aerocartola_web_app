"""
Script para buscar e baixar fotos de atletas automaticamente do site ogol.com.br
"""

import os
import sys
import time
import requests
from pathlib import Path
from urllib.parse import urlparse, urljoin, quote
from bs4 import BeautifulSoup

# Adicionar o diretório raiz ao path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

# Carregar variáveis de ambiente
from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / '.env')

from database import get_db_connection, close_db_connection

FOTO_DIR = PROJECT_ROOT / 'static' / 'cartola_imgs' / 'foto_atletas'
BASE_URL_OGOL = 'https://www.ogol.com.br'

def obter_extensao_arquivo(url):
    """Obtém a extensão do arquivo da URL"""
    parsed = urlparse(url)
    path = parsed.path
    if '.' in path:
        ext = os.path.splitext(path)[1]
        if ext.lower() in ['.jpg', '.jpeg']:
            return '.jpg'
        elif ext.lower() == '.png':
            return '.png'
        elif ext.lower() == '.gif':
            return '.gif'
    return '.jpg'

def baixar_foto(atleta_id, url, output_dir):
    """Baixa uma foto e salva com o ID do atleta"""
    try:
        # Se a URL for relativa, adicionar o domínio do ogol
        if url.startswith('/'):
            url = urljoin(BASE_URL_OGOL, url)
        
        ext = obter_extensao_arquivo(url)
        filename = f"{atleta_id}{ext}"
        filepath = output_dir / filename
        
        if filepath.exists():
            return True, 'ja existe'
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
            'Referer': 'https://www.ogol.com.br/'
        }
        
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        content_type = response.headers.get('content-type', '')
        if 'image' not in content_type:
            return False, f'tipo invalido: {content_type}'
        
        with open(filepath, 'wb') as f:
            f.write(response.content)
        
        tamanho_kb = len(response.content) / 1024
        return True, f'baixado ({tamanho_kb:.1f} KB)'
    
    except Exception as e:
        return False, f'erro: {str(e)[:50]}'

def buscar_foto_ogol(nome_atleta, clube_nome):
    """Busca a foto do atleta no ogol.com.br"""
    try:
        # Construir query de busca: nome + clube
        query = f"{nome_atleta} {clube_nome}".strip()
        search_url = f"{BASE_URL_OGOL}/pesquisa?search_txt={quote(query)}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8'
        }
        
        response = requests.get(search_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Estratégia 1: Procurar imagens com src que contenha /img/jogadores/ (padrão do ogol)
        imgs = soup.find_all('img', src=lambda x: x and '/img/jogadores/' in str(x))
        if imgs:
            # Pegar a primeira imagem que parece ser de jogador
            for img in imgs:
                img_src = img.get('src')
                if img_src and '/img/jogadores/' in img_src:
                    # Se for URL relativa, converter para absoluta
                    if img_src.startswith('/'):
                        img_src = urljoin(BASE_URL_OGOL, img_src)
                    return img_src
        
        # Estratégia 2: Procurar em divs de resultado de pesquisa
        # O XPath fornecido sugere uma estrutura específica: div[3]/div[6]/div/div/div[1]/div[2]/div/div[2]/div/div[1]/div[1]/div[2]/a/img
        # Vamos procurar por links que contenham imagens dentro de divs aninhadas
        links = soup.find_all('a')
        for link in links:
            img = link.find('img')
            if img and img.get('src') and '/img/jogadores/' in img.get('src', ''):
                img_src = img.get('src')
                if img_src.startswith('/'):
                    img_src = urljoin(BASE_URL_OGOL, img_src)
                return img_src
        
        # Estratégia 3: Procurar qualquer imagem que pareça ser de jogador
        all_imgs = soup.find_all('img')
        for img in all_imgs:
            src = img.get('src', '')
            alt = img.get('alt', '').lower()
            # Se tem src e parece ser de jogador (não é logo, ícone, etc)
            if src and '/img/jogadores/' in src:
                if src.startswith('/'):
                    src = urljoin(BASE_URL_OGOL, src)
                return src
        
        return None
    
    except Exception as e:
        print(f"    Erro ao buscar no ogol: {str(e)[:50]}")
        return None

def obter_atletas_sem_foto():
    """Obtém lista de atletas que não têm foto"""
    conn = get_db_connection()
    if not conn:
        print("ERRO: Nao foi possivel conectar ao banco de dados")
        return []
    
    try:
        cursor = conn.cursor()
        
        # Buscar todos os atletas ativos
        cursor.execute('''
            SELECT a.atleta_id, a.apelido, a.nome, a.clube_id, c.nome as clube_nome
            FROM acf_atletas a
            LEFT JOIN acf_clubes c ON a.clube_id = c.id
            WHERE a.status_id = 7
            ORDER BY c.nome, a.apelido
        ''')
        
        atletas = cursor.fetchall()
        
        # Verificar quais não têm foto
        atletas_sem_foto = []
        for atleta_id, apelido, nome, clube_id, clube_nome in atletas:
            # Verificar se existe foto
            tem_foto = False
            for ext in ['.jpg', '.jpeg', '.png', '.gif']:
                foto_path = FOTO_DIR / f"{atleta_id}{ext}"
                if foto_path.exists():
                    tem_foto = True
                    break
            
            if not tem_foto:
                nome_completo = apelido or nome or f"Atleta {atleta_id}"
                atletas_sem_foto.append({
                    'atleta_id': atleta_id,
                    'nome': nome_completo,
                    'clube_nome': clube_nome or 'Sem clube',
                    'clube_id': clube_id
                })
        
        return atletas_sem_foto
    
    except Exception as e:
        print(f"ERRO ao buscar atletas: {e}")
        return []
    finally:
        close_db_connection(conn)

def main():
    """Função principal"""
    print("=" * 70)
    print("BUSCAR FOTOS DE ATLETAS NO OGOL.COM.BR")
    print("=" * 70)
    print()
    
    # Criar diretório se não existir
    FOTO_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Diretorio de fotos: {FOTO_DIR}")
    print()
    
    # Buscar atletas sem foto
    print("Buscando atletas sem foto...")
    atletas_sem_foto = obter_atletas_sem_foto()
    
    if not atletas_sem_foto:
        print("Nenhum atleta sem foto encontrado!")
        return
    
    total = len(atletas_sem_foto)
    print(f"Encontrados {total} atletas sem foto")
    print()
    print("=" * 70)
    print("Iniciando busca automatica no ogol.com.br...")
    print("=" * 70)
    print()
    
    # Processar cada atleta
    baixados = 0
    nao_encontrados = 0
    erros = 0
    
    for idx, atleta in enumerate(atletas_sem_foto, 1):
        atleta_id = atleta['atleta_id']
        nome = atleta['nome']
        clube = atleta['clube_nome']
        
        print(f"[{idx}/{total}] Atleta ID: {atleta_id}")
        print(f"  Nome: {nome}")
        print(f"  Clube: {clube}")
        print(f"  Buscando no ogol.com.br...", end=' ', flush=True)
        
        # Buscar foto no ogol
        foto_url = buscar_foto_ogol(nome, clube)
        
        if foto_url:
            print(f"Encontrado!")
            print(f"  URL: {foto_url}")
            print(f"  Baixando...", end=' ', flush=True)
            
            sucesso, status = baixar_foto(atleta_id, foto_url, FOTO_DIR)
            
            if sucesso:
                print(f"OK - {status}")
                baixados += 1
            else:
                print(f"ERRO - {status}")
                erros += 1
        else:
            print("Nao encontrado")
            nao_encontrados += 1
        
        # Progresso a cada 10
        if idx % 10 == 0:
            print()
            print(f"  >>> Progresso: {idx}/{total} ({idx*100//total}%) - Baixados: {baixados}, Nao encontrados: {nao_encontrados}, Erros: {erros}")
            print()
        
        # Delay para não sobrecarregar o servidor
        time.sleep(1)
    
    # Resumo
    print()
    print("=" * 70)
    print("RESUMO FINAL")
    print("=" * 70)
    print(f"Total de atletas processados: {total}")
    print(f"Fotos baixadas com sucesso: {baixados}")
    print(f"Fotos nao encontradas: {nao_encontrados}")
    print(f"Erros: {erros}")
    print(f"Diretorio: {FOTO_DIR}")
    print("=" * 70)

if __name__ == '__main__':
    main()

