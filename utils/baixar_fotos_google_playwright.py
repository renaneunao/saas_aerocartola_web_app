"""
Script para buscar e baixar fotos de atletas usando Google + Transfermarkt + Ogol
Usa Playwright para navegação e extração de imagens
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
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("ERRO: Playwright nao instalado. Execute: pip install playwright && playwright install")
    sys.exit(1)

FOTO_DIR = PROJECT_ROOT / 'static' / 'cartola_imgs' / 'foto_atletas'

def baixar_imagem(url, filepath):
    """Baixa uma imagem de uma URL"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        with open(filepath, 'wb') as f:
            f.write(response.content)
        
        return True, len(response.content) / 1024
    except Exception as e:
        return False, str(e)[:50]

def buscar_foto_transfermarkt(page, nome_atleta, clube_nome, posicao=None):
    """Busca foto no Transfermarkt via Google"""
    try:
        # Buscar no Google com nome completo, clube completo e posição
        query_parts = ["transfermarkt.com", nome_atleta, clube_nome]
        if posicao:
            query_parts.append(posicao)
        query = " ".join(query_parts)
        google_url = f"https://www.google.com/search?q={quote(query)}"
        print(f"    [DEBUG] Acessando Google: {google_url}")
        
        page.goto(google_url, wait_until='domcontentloaded', timeout=30000)
        time.sleep(3)  # Aguardar mais tempo para o Google carregar completamente
        print(f"    [DEBUG] Google carregado. URL atual: {page.url}")
        print(f"    [DEBUG] Titulo da pagina: {page.title()}")
        
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

def buscar_foto_ogol(page, nome_atleta, clube_nome, posicao=None):
    """Busca foto no Ogol via Google"""
    try:
        # Buscar no Google com nome completo, clube completo e posição
        query_parts = ["ogol.com.br", nome_atleta, clube_nome]
        if posicao:
            query_parts.append(posicao)
        query = " ".join(query_parts)
        google_url = f"https://www.google.com/search?q={quote(query)}"
        print(f"    [DEBUG] Acessando Google: {google_url}")
        
        page.goto(google_url, wait_until='domcontentloaded', timeout=30000)
        time.sleep(3)  # Aguardar mais tempo para o Google carregar completamente
        print(f"    [DEBUG] Google carregado. URL atual: {page.url}")
        print(f"    [DEBUG] Titulo da pagina: {page.title()}")
        
        # Procurar o primeiro link do ogol
        resultado_busca = page.evaluate('''() => {
            const links = Array.from(document.querySelectorAll('a'));
            const ogolLinks = links.filter(link => {
                const href = link.href || '';
                return href.includes('ogol.com.br') && 
                       (href.includes('/jogador/') || href.includes('/player/'));
            });
            return {
                total_links: links.length,
                ogol_links_encontrados: ogolLinks.length,
                primeiro_link: ogolLinks.length > 0 ? ogolLinks[0].href : null,
                exemplos_links: ogolLinks.slice(0, 3).map(l => l.href)
            };
        }''')
        
        print(f"    [DEBUG] Total de links na pagina: {resultado_busca['total_links']}")
        print(f"    [DEBUG] Links Ogol encontrados: {resultado_busca['ogol_links_encontrados']}")
        if resultado_busca['exemplos_links']:
            print(f"    [DEBUG] Exemplos de links: {resultado_busca['exemplos_links'][:2]}")
        
        links = resultado_busca['primeiro_link']
        
        if not links:
            print(f"    [DEBUG] Nenhum link do Ogol encontrado")
            return None
        
        print(f"    [DEBUG] Link selecionado: {links}")
        
        # Acessar a página do ogol
        page.goto(links, wait_until='networkidle', timeout=30000)
        time.sleep(3)  # Ogol demora mais para carregar
        print(f"    [DEBUG] Pagina Ogol carregada. URL: {page.url}")
        
        # Procurar a foto do jogador
        resultado_img = page.evaluate('''() => {
            const imgs = Array.from(document.querySelectorAll('img'));
            const playerImgs = imgs.filter(img => {
                const src = img.src || '';
                return src.includes('ogol') && 
                       (src.includes('/img/jogadores/') || src.includes('/fotos/') || 
                        src.includes('jogador')) &&
                       (img.naturalWidth || img.width || 0) > 100;
            });
            
            if (playerImgs.length > 0) {
                return {
                    encontrada: true,
                    url: playerImgs[0].src,
                    total_imgs: imgs.length,
                    player_imgs: playerImgs.length
                };
            }
            
            // Fallback: qualquer imagem grande do ogol
            const largeImgs = imgs.filter(img => {
                const src = img.src || '';
                const width = img.naturalWidth || img.width || 0;
                return src.includes('ogol') && width > 100;
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
        print(f"    [DEBUG] ERRO ao buscar Ogol: {str(e)}")
        import traceback
        print(f"    [DEBUG] Traceback: {traceback.format_exc()[:200]}")
        return None

def obter_atletas_sem_foto():
    """Obtém lista de atletas que não têm foto de nenhuma fonte"""
    conn = get_db_connection()
    if not conn:
        print("ERRO: Nao foi possivel conectar ao banco de dados")
        return []
    
    try:
        cursor = conn.cursor()
        
        # Mapeamento de posição ID para nome
        posicao_map = {
            1: 'Goleiro',
            2: 'Lateral',
            3: 'Zagueiro',
            4: 'Meia',
            5: 'Atacante',
            6: 'Técnico'
        }
        
        # Buscar TODOS os atletas (sem filtro de status)
        # Usar nome completo (campo nome), nome completo do clube (c.nome) e posicao_id
        cursor.execute('''
            SELECT a.atleta_id, a.apelido, a.nome, a.clube_id, c.nome as clube_nome, a.posicao_id
            FROM acf_atletas a
            LEFT JOIN acf_clubes c ON a.clube_id = c.id
            ORDER BY c.nome, a.nome
        ''')
        
        atletas = cursor.fetchall()
        
        # Verificar quais não têm foto de nenhuma fonte
        atletas_sem_foto = []
        for atleta_id, apelido, nome, clube_id, clube_nome, posicao_id in atletas:
            # Verificar se existe foto (qualquer uma, com ou sem sufixo)
            tem_foto = False
            for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
                # Verificar foto sem sufixo (já processada)
                foto_path = FOTO_DIR / f"{atleta_id}{ext}"
                if foto_path.exists():
                    tem_foto = True
                    break
                # Verificar fotos com sufixo
                for fonte in ['transfermarkt', 'ogol', 'custom']:
                    foto_path = FOTO_DIR / f"{atleta_id}_{fonte}{ext}"
                    if foto_path.exists():
                        tem_foto = True
                        break
                if tem_foto:
                    break
            
            # Se não tem nenhuma foto, adicionar à lista
            if not tem_foto:
                # Usar nome completo (campo nome), não apelido
                nome_completo = nome or apelido or f"Atleta {atleta_id}"
                posicao_nome = posicao_map.get(posicao_id, '')
                
                atletas_sem_foto.append({
                    'atleta_id': atleta_id,
                    'nome': nome_completo,
                    'clube_nome': clube_nome or 'Sem clube',
                    'clube_id': clube_id,
                    'posicao_id': posicao_id,
                    'posicao': posicao_nome
                })
        
        return atletas_sem_foto
    
    except Exception as e:
        print(f"ERRO ao buscar atletas: {e}")
        import traceback
        traceback.print_exc()
        return []
    finally:
        close_db_connection(conn)

def main():
    """Função principal"""
    print("=" * 70)
    print("BUSCAR FOTOS DE ATLETAS VIA GOOGLE (TRANSFERMARKT + OGOL)")
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
        print("Todos os atletas ja tem fotos!")
        return
    
    total = len(atletas_sem_foto)
    print(f"Encontrados {total} atletas sem foto")
    print("Usando: Nome completo + Nome completo do clube + Posição")
    print()
    print("=" * 70)
    print("Iniciando busca automatica...")
    print("=" * 70)
    print()
    
    # Estatísticas
    baixados_tm = 0
    baixados_ogol = 0
    nao_encontrados_tm = 0
    nao_encontrados_ogol = 0
    erros = 0
    
    # Iniciar Playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080},
            locale='pt-BR',
            timezone_id='America/Sao_Paulo',
            extra_http_headers={
                'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            }
        )
        page = context.new_page()
        
        try:
            for idx, atleta in enumerate(atletas_sem_foto, 1):
                atleta_id = atleta['atleta_id']
                nome = atleta['nome']  # Nome completo
                clube = atleta['clube_nome']  # Nome completo do clube
                posicao = atleta.get('posicao', '')  # Nome da posição
                
                print(f"[{idx}/{total}] Atleta ID: {atleta_id}")
                print(f"  Nome completo: {nome}")
                print(f"  Clube: {clube}")
                print(f"  Posição: {posicao}")
                
                # Buscar Transfermarkt
                print(f"  Buscando Transfermarkt...", end=' ', flush=True)
                img_url = buscar_foto_transfermarkt(page, nome, clube, posicao)
                
                if img_url:
                    print(f"Encontrado!")
                    print(f"    URL: {img_url[:80]}...")
                    
                    # Determinar extensão
                    ext = '.jpg'
                    if '.png' in img_url.lower():
                        ext = '.png'
                    elif '.jpeg' in img_url.lower():
                        ext = '.jpeg'
                    elif '.webp' in img_url.lower():
                        ext = '.webp'
                    
                    filepath = FOTO_DIR / f"{atleta_id}_transfermarkt{ext}"
                    sucesso, resultado = baixar_imagem(img_url, filepath)
                    
                    if sucesso:
                        print(f"    Baixado: {resultado:.1f} KB")
                        baixados_tm += 1
                    else:
                        print(f"    ERRO: {resultado}")
                        erros += 1
                else:
                    print("Nao encontrado")
                    nao_encontrados_tm += 1
                
                # Buscar Ogol
                print(f"  Buscando Ogol...", end=' ', flush=True)
                img_url = buscar_foto_ogol(page, nome, clube, posicao)
                
                if img_url:
                    print(f"Encontrado!")
                    print(f"    URL: {img_url[:80]}...")
                    
                    # Determinar extensão
                    ext = '.jpg'
                    if '.png' in img_url.lower():
                        ext = '.png'
                    elif '.jpeg' in img_url.lower():
                        ext = '.jpeg'
                    elif '.webp' in img_url.lower():
                        ext = '.webp'
                    
                    filepath = FOTO_DIR / f"{atleta_id}_ogol{ext}"
                    sucesso, resultado = baixar_imagem(img_url, filepath)
                    
                    if sucesso:
                        print(f"    Baixado: {resultado:.1f} KB")
                        baixados_ogol += 1
                    else:
                        print(f"    ERRO: {resultado}")
                        erros += 1
                else:
                    print("Nao encontrado")
                    nao_encontrados_ogol += 1
                
                print()
                
                # Progresso a cada 10
                if idx % 10 == 0:
                    print(f"  >>> Progresso: {idx}/{total} ({idx*100//total}%)")
                    print(f"      Transfermarkt: {baixados_tm} baixados, {nao_encontrados_tm} nao encontrados")
                    print(f"      Ogol: {baixados_ogol} baixados, {nao_encontrados_ogol} nao encontrados")
                    print(f"      Erros: {erros}")
                    print()
                
                # Delay para não sobrecarregar
                time.sleep(2)
        
        finally:
            browser.close()
    
    # Resumo
    print()
    print("=" * 70)
    print("RESUMO FINAL")
    print("=" * 70)
    print(f"Total de atletas processados: {total}")
    print(f"Transfermarkt: {baixados_tm} baixados, {nao_encontrados_tm} nao encontrados")
    print(f"Ogol: {baixados_ogol} baixados, {nao_encontrados_ogol} nao encontrados")
    print(f"Erros: {erros}")
    print(f"Diretorio: {FOTO_DIR}")
    print("=" * 70)

if __name__ == '__main__':
    main()

