"""
Script de teste para debug da busca de fotos - processa apenas 1 atleta
"""

import os
import sys
import time
import requests
from pathlib import Path
from urllib.parse import quote

# Adicionar o diretório raiz ao path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

# Carregar variáveis de ambiente
from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / '.env')

from database import get_db_connection, close_db_connection

# Importar Playwright
from playwright.sync_api import sync_playwright

FOTO_DIR = PROJECT_ROOT / 'static' / 'cartola_imgs' / 'foto_atletas'

def buscar_foto_transfermarkt(page, nome_atleta, clube_nome):
    """Busca foto no Transfermarkt via Google"""
    try:
        # Buscar no Google
        query = f"transfermarkt.com {nome_atleta} {clube_nome}"
        google_url = f"https://www.google.com/search?q={quote(query)}"
        print(f"    [DEBUG] Acessando Google: {google_url}")
        
        page.goto(google_url, wait_until='networkidle', timeout=30000)
        time.sleep(2)
        print(f"    [DEBUG] Google carregado. URL atual: {page.url}")
        
        # Procurar o primeiro link do Transfermarkt
        resultado_busca = page.evaluate('''() => {
            const links = Array.from(document.querySelectorAll('a'));
            const tmLinks = links.filter(link => {
                const href = link.href || '';
                return href.includes('transfermarkt.com') && 
                       (href.includes('/spieler/') || href.includes('/profil/'));
            });
            return {
                total_links: links.length,
                tm_links_encontrados: tmLinks.length,
                primeiro_link: tmLinks.length > 0 ? tmLinks[0].href : null,
                exemplos_links: tmLinks.slice(0, 3).map(l => l.href)
            };
        }''')
        
        print(f"    [DEBUG] Total de links na pagina: {resultado_busca['total_links']}")
        print(f"    [DEBUG] Links Transfermarkt encontrados: {resultado_busca['tm_links_encontrados']}")
        if resultado_busca['exemplos_links']:
            print(f"    [DEBUG] Exemplos de links: {resultado_busca['exemplos_links'][:2]}")
        
        links = resultado_busca['primeiro_link']
        
        if not links:
            print(f"    [DEBUG] Nenhum link do Transfermarkt encontrado")
            return None
        
        print(f"    [DEBUG] Link selecionado: {links}")
        
        # Acessar a página do Transfermarkt
        page.goto(links, wait_until='networkidle', timeout=30000)
        time.sleep(2)
        print(f"    [DEBUG] Pagina Transfermarkt carregada. URL: {page.url}")
        
        # Aceitar cookies se necessário
        try:
            accept_button = page.locator('button:has-text("Aceitar"), button:has-text("Accept")').first
            if accept_button.is_visible(timeout=2000):
                print(f"    [DEBUG] Aceitando cookies...")
                accept_button.click()
                time.sleep(1)
        except Exception as e:
            print(f"    [DEBUG] Nenhum botao de cookies encontrado ou erro: {str(e)[:30]}")
        
        # Procurar a foto do jogador
        resultado_img = page.evaluate('''() => {
            const imgs = Array.from(document.querySelectorAll('img'));
            const playerImgs = imgs.filter(img => {
                const src = img.src || '';
                return (src.includes('/bilder/') || src.includes('/headshots/') || 
                        src.includes('transfermarkt') || src.includes('portrait')) && 
                       (src.includes('spieler') || src.includes('headshot') || 
                        (img.naturalWidth || img.width || 0) > 100);
            });
            
            if (playerImgs.length > 0) {
                return {
                    encontrada: true,
                    url: playerImgs[0].src,
                    total_imgs: imgs.length,
                    player_imgs: playerImgs.length
                };
            }
            
            // Fallback: qualquer imagem grande do transfermarkt
            const largeImgs = imgs.filter(img => {
                const src = img.src || '';
                const width = img.naturalWidth || img.width || 0;
                return src.includes('transfermarkt') && width > 100;
            });
            
            return {
                encontrada: largeImgs.length > 0,
                url: largeImgs.length > 0 ? largeImgs[0].src : null,
                total_imgs: imgs.length,
                large_imgs: largeImgs.length
            };
        }''')
        
        print(f"    [DEBUG] Total de imagens na pagina: {resultado_img['total_imgs']}")
        print(f"    [DEBUG] Imagens de jogador encontradas: {resultado_img.get('player_imgs', resultado_img.get('large_imgs', 0))}")
        
        if resultado_img['encontrada']:
            print(f"    [DEBUG] Imagem encontrada: {resultado_img['url'][:80]}...")
            return resultado_img['url']
        else:
            print(f"    [DEBUG] Nenhuma imagem de jogador encontrada")
            return None
    
    except Exception as e:
        print(f"    [DEBUG] ERRO ao buscar Transfermarkt: {str(e)}")
        import traceback
        print(f"    [DEBUG] Traceback: {traceback.format_exc()[:200]}")
        return None

def main():
    """Teste com apenas 1 atleta"""
    print("=" * 70)
    print("TESTE DE BUSCA DE FOTOS - 1 ATLETA")
    print("=" * 70)
    print()
    
    # Buscar 1 atleta
    conn = get_db_connection()
    if not conn:
        print("ERRO: Nao foi possivel conectar ao banco de dados")
        return
    
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT a.atleta_id, a.apelido, a.nome, a.clube_id, c.nome as clube_nome
            FROM acf_atletas a
            LEFT JOIN acf_clubes c ON a.clube_id = c.id
            LIMIT 1
        ''')
        
        row = cursor.fetchone()
        if not row:
            print("Nenhum atleta encontrado")
            return
        
        atleta_id, apelido, nome, clube_id, clube_nome = row
        nome_completo = apelido or nome or f"Atleta {atleta_id}"
        
        print(f"Atleta ID: {atleta_id}")
        print(f"Nome: {nome_completo}")
        print(f"Clube: {clube_nome or 'Sem clube'}")
        print()
        
        # Iniciar Playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)  # headless=False para ver o navegador
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )
            page = context.new_page()
            
            try:
                print("Buscando Transfermarkt...")
                img_url = buscar_foto_transfermarkt(page, nome_completo, clube_nome or '')
                
                if img_url:
                    print(f"\nSUCESSO! URL da imagem: {img_url}")
                else:
                    print("\nFALHA: Nenhuma imagem encontrada")
                
                # Manter o navegador aberto por 10 segundos para inspeção
                print("\nMantendo navegador aberto por 10 segundos para inspeção...")
                time.sleep(10)
            
            finally:
                browser.close()
    
    except Exception as e:
        print(f"ERRO: {e}")
        import traceback
        traceback.print_exc()
    finally:
        close_db_connection(conn)

if __name__ == '__main__':
    main()

