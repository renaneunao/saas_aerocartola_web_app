"""
Script para buscar automaticamente URLs de fotos do Ogol para todos os atletas sem foto
Busca no Google: "nome completo + nome do clube + ogol"
Extrai a URL da foto do ogol e salva em um arquivo JSON
"""

import os
import sys
import time
import json
from pathlib import Path
from urllib.parse import quote
from datetime import datetime

# Adicionar o diretório raiz ao path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

# Carregar variáveis de ambiente
from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / '.env')

from database import get_db_connection, close_db_connection

# Importar Playwright
try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
except ImportError:
    print("ERRO: Playwright nao instalado. Execute: pip install playwright && playwright install chromium")
    sys.exit(1)

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

def buscar_url_ogol(page, nome_atleta, clube_nome):
    """Busca URL da foto do ogol usando busca direta no ogol ou Bing como alternativa"""
    try:
        # TENTATIVA 1: Busca direta no ogol
        query_ogol = f"{nome_atleta} {clube_nome}".strip()
        ogol_search_url = f"https://www.ogol.com.br/pesquisa?search_txt={quote(query_ogol)}"
        
        print(f"    Buscando no Ogol: {query_ogol}")
        try:
            page.goto(ogol_search_url, wait_until='networkidle', timeout=20000)
            time.sleep(2)
            
            # Procurar links de jogador nos resultados
            links_jogador = page.query_selector_all('a[href*="/jogador/"]')
            
            if links_jogador:
                url_ogol = links_jogador[0].get_attribute('href')
                if url_ogol and not url_ogol.startswith('http'):
                    url_ogol = 'https://www.ogol.com.br' + url_ogol
                
                if url_ogol and 'ogol.com.br/jogador' in url_ogol:
                    print(f"    [OK] Link ogol encontrado (busca direta): {url_ogol[:80]}...")
                    # Ir direto para a página do jogador
                    page.goto(url_ogol, wait_until='networkidle', timeout=20000)
                    time.sleep(2)
                else:
                    raise Exception("URL invalida")
            else:
                raise Exception("Nenhum resultado")
        except:
            # TENTATIVA 2: Buscar no Bing (menos restritivo que Google)
            print(f"    Tentando Bing: {nome_atleta} {clube_nome} ogol")
            query_bing = f"{nome_atleta} {clube_nome} ogol"
            bing_url = f"https://www.bing.com/search?q={quote(query_bing)}"
            
            page.goto(bing_url, wait_until='networkidle', timeout=20000)
            time.sleep(2)
            
            # Procurar links do ogol nos resultados
            links_ogol = page.query_selector_all('a[href*="ogol.com.br/jogador"]')
            
            if not links_ogol:
                links_ogol = page.query_selector_all('a')
                links_ogol = [link for link in links_ogol if 'ogol.com.br/jogador' in (link.get_attribute('href') or '')]
            
            if not links_ogol:
                print(f"    [ERRO] Nenhum link do ogol encontrado")
                return None
            
            # Pegar o primeiro link do ogol
            primeiro_link = links_ogol[0]
            url_ogol = primeiro_link.get_attribute('href') or ''
            
            # Limpar URL do Bing
            if url_ogol.startswith('http://') or url_ogol.startswith('https://'):
                pass  # OK
            elif url_ogol.startswith('//'):
                url_ogol = 'https:' + url_ogol
            elif url_ogol.startswith('/'):
                url_ogol = 'https://www.ogol.com.br' + url_ogol
            
            if not url_ogol or 'ogol.com.br/jogador' not in url_ogol:
                print(f"    [ERRO] URL do ogol invalida: {url_ogol[:100]}")
                return None
            
            print(f"    [OK] Link ogol encontrado (via Bing): {url_ogol[:80]}...")
            
            # Acessar a página do ogol
            page.goto(url_ogol, wait_until='networkidle', timeout=20000)
            time.sleep(2)
        
        # Procurar a imagem do jogador
        imgs = page.query_selector_all('img')
        url_foto = None
        
        for img in imgs:
            src = img.get_attribute('src') or img.get_attribute('data-src') or ''
            if not src:
                continue
                
            # Procurar por padrões de URL de foto de jogador
            if '/img/jogadores/' in src or '/jogadores/new/' in src:
                # Verificar se não é logo/ícone
                if 'logo' not in src.lower() and 'icon' not in src.lower() and 'banner' not in src.lower():
                    # Verificar se parece ser uma foto de jogador (tem dimensões razoáveis)
                    width = img.get_attribute('width')
                    height = img.get_attribute('height')
                    if width and height:
                        try:
                            w, h = int(width), int(height)
                            if w > 100 and h > 100:  # Fotos geralmente são maiores
                                url_foto = src
                                break
                        except:
                            pass
                    else:
                        url_foto = src
                        break
        
        if url_foto:
            # Garantir URL completa
            if url_foto.startswith('//'):
                url_foto = 'https:' + url_foto
            elif url_foto.startswith('/'):
                url_foto = 'https://www.ogol.com.br' + url_foto
            
            print(f"    [OK] URL da foto encontrada: {url_foto[:80]}...")
            return url_foto
        else:
            print(f"    [ERRO] Foto nao encontrada na pagina do ogol")
            return None
        
    except PlaywrightTimeout:
        print(f"    [ERRO] Timeout ao buscar")
        return None
    except Exception as e:
        print(f"    [ERRO] Erro: {str(e)[:50]}")
        return None

def main():
    """Função principal"""
    print("=" * 70)
    print("BUSCAR URLs DO OGOL PARA ATLETAS SEM FOTO")
    print("=" * 70)
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
    print(f"Atletas já processados: {len(processados_ids)}")
    print(f"Atletas para processar: {total}")
    print()
    
    if not atletas_para_processar:
        print("Todos os atletas já foram processados!")
        # Salvar resultados finais
        salvar_resultados(urls_encontradas)
        print(f"\n✅ Resultados salvos em: {RESULTADOS_FILE}")
        return
    
    print("=" * 70)
    print("Iniciando busca automática...")
    print("=" * 70)
    print()
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # headless=False para ver o processo
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
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
                url_foto = buscar_url_ogol(page, nome, clube)
                
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
                time.sleep(1)
        
        finally:
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

