"""
Script para buscar automaticamente URLs de fotos do Ogol usando múltiplas APIs de busca
Tenta: DuckDuckGo API (gratuita) -> Bing API -> SerpAPI -> Playwright (fallback)
"""

import os
import sys
import time
import json
import requests
from pathlib import Path
from urllib.parse import quote, unquote
from datetime import datetime

# Adicionar o diretório raiz ao path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

# Carregar variáveis de ambiente
from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / '.env')

from database import get_db_connection, close_db_connection

# Importar Playwright (fallback)
try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("[AVISO] Playwright nao instalado. Usando apenas APIs.")

FOTO_DIR = PROJECT_ROOT / 'static' / 'cartola_imgs' / 'foto_atletas'
RESULTADOS_FILE = PROJECT_ROOT / 'utils' / 'urls_ogol_atletas.json'
PROGRESSO_FILE = PROJECT_ROOT / 'utils' / 'progresso_urls_ogol.json'

def carregar_progresso():
    """Carrega o progresso salvo"""
    if PROGRESSO_FILE.exists():
        with open(PROGRESSO_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'processados': [], 'urls_encontradas': {}}

def salvar_progresso(progresso):
    """Salva o progresso"""
    with open(PROGRESSO_FILE, 'w', encoding='utf-8') as f:
        json.dump(progresso, f, indent=2, ensure_ascii=False)

def salvar_resultados(resultados):
    """Salva os resultados finais"""
    with open(RESULTADOS_FILE, 'w', encoding='utf-8') as f:
        json.dump(resultados, f, indent=2, ensure_ascii=False)

def buscar_duckduckgo(nome_atleta, clube_nome):
    """Busca usando DuckDuckGo (gratuita, sem chave)"""
    try:
        # Tentar usar biblioteca duckduckgo-search se disponível
        try:
            from duckduckgo_search import DDGS
            query = f"{nome_atleta} {clube_nome} site:ogol.com.br/jogador"
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=5))
                for result in results:
                    url = result.get('href', '')
                    if 'ogol.com.br/jogador' in url:
                        return url
            return None
        except ImportError:
            pass  # Biblioteca não instalada, usar método alternativo
        
        # Método alternativo: usar requests + BeautifulSoup
        query = f"{nome_atleta} {clube_nome} ogol.com.br/jogador"
        url = f"https://html.duckduckgo.com/html/?q={quote(query)}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7'
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Procurar links do ogol nos resultados
        links = soup.find_all('a', href=True)
        for link in links:
            href = link.get('href', '')
            if 'ogol.com.br/jogador' in href:
                # DuckDuckGo pode redirecionar
                if '/l/?kh=' in href or 'uddg=' in href:
                    # Extrair URL real do redirecionamento
                    if 'uddg=' in href:
                        import re
                        match = re.search(r'uddg=([^&]+)', href)
                        if match:
                            url_real = unquote(match.group(1))
                            if 'ogol.com.br/jogador' in url_real:
                                return url_real
                elif href.startswith('http'):
                    return href
        
        return None
    except Exception as e:
        print(f"    [ERRO DuckDuckGo] {str(e)[:50]}")
        return None

def buscar_bing_api(nome_atleta, clube_nome):
    """Busca usando Bing Search API (requer chave)"""
    bing_api_key = os.getenv('BING_SEARCH_API_KEY')
    if not bing_api_key:
        return None
    
    try:
        query = f"{nome_atleta} {clube_nome} site:ogol.com.br/jogador"
        url = "https://api.bing.microsoft.com/v7.0/search"
        headers = {
            'Ocp-Apim-Subscription-Key': bing_api_key
        }
        params = {
            'q': query,
            'count': 5
        }
        
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # Procurar links do ogol nos resultados
        if 'webPages' in data and 'value' in data['webPages']:
            for result in data['webPages']['value']:
                url_result = result.get('url', '')
                if 'ogol.com.br/jogador' in url_result:
                    return url_result
        
        return None
    except Exception as e:
        print(f"    [ERRO Bing API] {str(e)[:50]}")
        return None

def buscar_serpapi(nome_atleta, clube_nome):
    """Busca usando SerpAPI (requer chave)"""
    serpapi_key = os.getenv('SERPAPI_KEY')
    if not serpapi_key:
        return None
    
    try:
        query = f"{nome_atleta} {clube_nome} site:ogol.com.br/jogador"
        url = "https://serpapi.com/search"
        params = {
            'q': query,
            'api_key': serpapi_key,
            'engine': 'google'
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # Procurar links do ogol nos resultados
        if 'organic_results' in data:
            for result in data['organic_results']:
                link = result.get('link', '')
                if 'ogol.com.br/jogador' in link:
                    return link
        
        return None
    except Exception as e:
        print(f"    [ERRO SerpAPI] {str(e)[:50]}")
        return None

def buscar_playwright_fallback(page, nome_atleta, clube_nome):
    """Busca usando Playwright como fallback (Bing ou DuckDuckGo)"""
    try:
        # Tentar Bing primeiro (menos restritivo)
        query = f"{nome_atleta} {clube_nome} site:ogol.com.br/jogador"
        bing_url = f"https://www.bing.com/search?q={quote(query)}"
        
        print(f"    [Playwright] Tentando Bing...")
        page.goto(bing_url, wait_until='networkidle', timeout=20000)
        time.sleep(2)
        
        # Procurar links do ogol
        links_ogol = page.query_selector_all('a[href*="ogol.com.br/jogador"]')
        
        if links_ogol:
            url_ogol = links_ogol[0].get_attribute('href')
            if url_ogol and url_ogol.startswith('http'):
                return url_ogol
        
        # Se não encontrou, tentar DuckDuckGo
        print(f"    [Playwright] Tentando DuckDuckGo...")
        ddg_url = f"https://html.duckduckgo.com/html/?q={quote(query)}"
        page.goto(ddg_url, wait_until='networkidle', timeout=20000)
        time.sleep(2)
        
        links_ogol = page.query_selector_all('a[href*="ogol.com.br/jogador"]')
        if links_ogol:
            url_ogol = links_ogol[0].get_attribute('href')
            # DuckDuckGo pode ter redirecionamento
            if 'uddg=' in url_ogol:
                import re
                match = re.search(r'uddg=([^&]+)', url_ogol)
                if match:
                    url_ogol = unquote(match.group(1))
            if url_ogol and 'ogol.com.br/jogador' in url_ogol:
                return url_ogol
        
        return None
    except Exception as e:
        print(f"    [ERRO Playwright] {str(e)[:50]}")
        return None

def extrair_url_foto_ogol(url_ogol, page=None):
    """Extrai a URL da foto da página do ogol"""
    try:
        if page:
            # Usar Playwright
            page.goto(url_ogol, wait_until='networkidle', timeout=20000)
            time.sleep(2)
            
            imgs = page.query_selector_all('img')
            for img in imgs:
                src = img.get_attribute('src') or img.get_attribute('data-src') or ''
                if '/img/jogadores/' in src or '/jogadores/new/' in src:
                    if 'logo' not in src.lower() and 'icon' not in src.lower():
                        if src.startswith('//'):
                            src = 'https:' + src
                        elif src.startswith('/'):
                            src = 'https://www.ogol.com.br' + src
                        return src
        else:
            # Usar requests + BeautifulSoup
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url_ogol, headers=headers, timeout=10)
            response.raise_for_status()
            
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.text, 'html.parser')
            imgs = soup.find_all('img')
            
            for img in imgs:
                src = img.get('src') or img.get('data-src') or ''
                if '/img/jogadores/' in src or '/jogadores/new/' in src:
                    if 'logo' not in src.lower() and 'icon' not in src.lower():
                        if src.startswith('//'):
                            src = 'https:' + src
                        elif src.startswith('/'):
                            src = 'https://www.ogol.com.br' + src
                        return src
        
        return None
    except Exception as e:
        print(f"    [ERRO] Erro ao extrair foto: {str(e)[:50]}")
        return None

def buscar_url_ogol(nome_atleta, clube_nome, page=None):
    """Busca URL da foto do ogol usando múltiplas estratégias"""
    print(f"    Buscando: {nome_atleta} {clube_nome}")
    
    url_ogol = None
    
    # TENTATIVA 1: DuckDuckGo API (gratuita)
    print(f"    [1/4] Tentando DuckDuckGo API...")
    url_ogol = buscar_duckduckgo(nome_atleta, clube_nome)
    if url_ogol:
        print(f"    [OK] Link encontrado via DuckDuckGo: {url_ogol[:80]}...")
    else:
        # TENTATIVA 2: Bing API (se tiver chave)
        print(f"    [2/4] Tentando Bing API...")
        url_ogol = buscar_bing_api(nome_atleta, clube_nome)
        if url_ogol:
            print(f"    [OK] Link encontrado via Bing API: {url_ogol[:80]}...")
        else:
            # TENTATIVA 3: SerpAPI (se tiver chave)
            print(f"    [3/4] Tentando SerpAPI...")
            url_ogol = buscar_serpapi(nome_atleta, clube_nome)
            if url_ogol:
                print(f"    [OK] Link encontrado via SerpAPI: {url_ogol[:80]}...")
            else:
                # TENTATIVA 4: Playwright (fallback)
                if page and PLAYWRIGHT_AVAILABLE:
                    print(f"    [4/4] Tentando Playwright (fallback)...")
                    url_ogol = buscar_playwright_fallback(page, nome_atleta, clube_nome)
                    if url_ogol:
                        print(f"    [OK] Link encontrado via Playwright: {url_ogol[:80]}...")
    
    if not url_ogol:
        print(f"    [ERRO] Nenhum link encontrado")
        return None
    
    # Extrair URL da foto
    print(f"    Extraindo URL da foto...")
    url_foto = extrair_url_foto_ogol(url_ogol, page)
    
    if url_foto:
        print(f"    [OK] URL da foto: {url_foto[:80]}...")
        return url_foto
    else:
        print(f"    [ERRO] Foto nao encontrada na pagina")
        return None

def obter_atletas_sem_foto():
    """Obtém lista de atletas que não têm foto"""
    conn = get_db_connection()
    if not conn:
        print("ERRO: Nao foi possivel conectar ao banco de dados")
        return []
    
    try:
        cursor = conn.cursor()
        
        # Buscar TODOS os atletas
        cursor.execute('''
            SELECT a.atleta_id, a.apelido, a.nome, a.clube_id, c.nome as clube_nome
            FROM acf_atletas a
            LEFT JOIN acf_clubes c ON a.clube_id = c.id
            ORDER BY c.nome, a.nome
        ''')
        
        atletas = cursor.fetchall()
        
        # Verificar quais não têm foto
        atletas_sem_foto = []
        for atleta_id, apelido, nome, clube_id, clube_nome in atletas:
            # Verificar se existe foto (sem sufixo ou com sufixo)
            tem_foto = False
            for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
                foto_path = FOTO_DIR / f"{atleta_id}{ext}"
                if foto_path.exists():
                    tem_foto = True
                    break
            
            if not tem_foto:
                nome_completo = nome or apelido or f"Atleta {atleta_id}"
                atletas_sem_foto.append({
                    'atleta_id': atleta_id,
                    'apelido': apelido or '',
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
    print("BUSCAR URLs DO OGOL - MULTIPLAS APIs")
    print("=" * 70)
    print()
    print("Estrategias disponiveis:")
    print("  1. DuckDuckGo API (gratuita, sem chave)")
    if os.getenv('BING_SEARCH_API_KEY'):
        print("  2. Bing Search API (chave configurada)")
    if os.getenv('SERPAPI_KEY'):
        print("  3. SerpAPI (chave configurada)")
    if PLAYWRIGHT_AVAILABLE:
        print("  4. Playwright (fallback - Bing/DuckDuckGo)")
    print()
    
    # Carregar progresso
    progresso = carregar_progresso()
    processados_ids = set(progresso.get('processados', []))
    urls_encontradas = progresso.get('urls_encontradas', {})
    
    # Buscar atletas sem foto
    print("Buscando atletas sem foto...")
    todos_atletas = obter_atletas_sem_foto()
    
    # Filtrar atletas não processados
    atletas_para_processar = [
        a for a in todos_atletas 
        if a['atleta_id'] not in processados_ids
    ]
    
    total = len(atletas_para_processar)
    print(f"Total de atletas sem foto: {len(todos_atletas)}")
    print(f"Atletas ja processados: {len(processados_ids)}")
    print(f"Atletas para processar: {total}")
    print()
    
    if not atletas_para_processar:
        print("Todos os atletas ja foram processados!")
        salvar_resultados(urls_encontradas)
        print(f"\n[OK] Resultados salvos em: {RESULTADOS_FILE}")
        return
    
    print("=" * 70)
    print("Iniciando busca automatica...")
    print("=" * 70)
    print()
    
    # Inicializar Playwright apenas se necessário
    browser = None
    context = None
    page = None
    
    if PLAYWRIGHT_AVAILABLE:
        p = sync_playwright().start()
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        page = context.new_page()
    
    try:
        for idx, atleta in enumerate(atletas_para_processar, 1):
            atleta_id = atleta['atleta_id']
            nome = atleta['nome']
            clube = atleta['clube_nome']
            
            print(f"[{idx}/{total}] Atleta ID: {atleta_id}")
            print(f"  Nome: {nome}")
            print(f"  Clube: {clube}")
            
            # Buscar URL do ogol
            url_foto = buscar_url_ogol(nome, clube, page)
            
            if url_foto:
                urls_encontradas[str(atleta_id)] = {
                    'atleta_id': atleta_id,
                    'nome': nome,
                    'clube': clube,
                    'url_foto': url_foto,
                    'data_busca': datetime.now().isoformat()
                }
                print(f"  [OK] URL salva!")
            else:
                print(f"  [AVISO] URL nao encontrada")
            
            # Marcar como processado
            processados_ids.add(atleta_id)
            
            # Salvar progresso a cada 10 atletas
            if idx % 10 == 0:
                progresso['processados'] = list(processados_ids)
                progresso['urls_encontradas'] = urls_encontradas
                salvar_progresso(progresso)
                print(f"\n  [SALVO] Progresso salvo ({idx}/{total})")
            
            print()
            
            # Pequeno delay para não sobrecarregar
            time.sleep(0.5)
    
    finally:
        if browser:
            browser.close()
    
    # Salvar progresso final
    progresso['processados'] = list(processados_ids)
    progresso['urls_encontradas'] = urls_encontradas
    salvar_progresso(progresso)
    
    # Salvar resultados finais
    salvar_resultados(urls_encontradas)
    
    print("=" * 70)
    print("CONCLUIDO!")
    print("=" * 70)
    print(f"Total processado: {len(processados_ids)}")
    print(f"URLs encontradas: {len(urls_encontradas)}")
    print(f"\n[OK] Resultados salvos em: {RESULTADOS_FILE}")
    print(f"[OK] Progresso salvo em: {PROGRESSO_FILE}")

if __name__ == '__main__':
    main()

