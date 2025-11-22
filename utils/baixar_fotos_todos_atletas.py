"""
Script para baixar fotos de TODOS os atletas usando Google + Transfermarkt + Ogol
Salva progresso para poder retomar se interrompido
"""

import os
import sys
import time
import json
import requests
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
PROGRESSO_FILE = PROJECT_ROOT / 'utils' / 'progresso_fotos.json'

def carregar_progresso():
    """Carrega o progresso salvo"""
    if PROGRESSO_FILE.exists():
        with open(PROGRESSO_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'processados': [], 'erros': []}

def salvar_progresso(progresso):
    """Salva o progresso"""
    with open(PROGRESSO_FILE, 'w', encoding='utf-8') as f:
        json.dump(progresso, f, indent=2, ensure_ascii=False)

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
    """Busca foto no Transfermarkt diretamente (sem Google)"""
    try:
        # Buscar diretamente no Transfermarkt usando a busca rápida
        # URL de busca: https://www.transfermarkt.com.br/schnellsuche/ergebnis/schnellsuche?query=nome+clube+posicao
        query_parts = [nome_atleta, clube_nome]
        if posicao:
            query_parts.append(posicao)
        query = " ".join(query_parts)
        search_url = f"https://www.transfermarkt.com.br/schnellsuche/ergebnis/schnellsuche?query={quote(query)}"
        
        page.goto(search_url, wait_until='domcontentloaded', timeout=30000)
        time.sleep(3)
        
        # Aceitar cookies se necessário
        try:
            accept_button = page.locator('button:has-text("Aceitar"), button:has-text("Accept")').first
            if accept_button.is_visible(timeout=2000):
                accept_button.click()
                time.sleep(1)
        except:
            pass
        
        # Procurar link do jogador nos resultados
        resultado = page.evaluate('''() => {
            // Procurar por links de jogadores nos resultados
            const links = Array.from(document.querySelectorAll('a'));
            const playerLinks = links.filter(link => {
                const href = link.href || '';
                return href.includes('/profil/spieler/') || href.includes('/spieler/');
            });
            
            // Se encontrou links, pegar o primeiro
            if (playerLinks.length > 0) {
                return playerLinks[0].href;
            }
            
            // Tentar encontrar na tabela de resultados
            const tableRows = Array.from(document.querySelectorAll('table tr'));
            for (const row of tableRows) {
                const link = row.querySelector('a[href*="/profil/spieler/"], a[href*="/spieler/"]');
                if (link) {
                    return link.href;
                }
            }
            
            return null;
        }''')
        
        if not resultado:
            return None, 'jogador_nao_encontrado'
        
        # Acessar página do jogador
        page.goto(resultado, wait_until='domcontentloaded', timeout=30000)
        time.sleep(2)
        
        # Aceitar cookies se necessário
        try:
            accept_button = page.locator('button:has-text("Aceitar"), button:has-text("Accept")').first
            if accept_button.is_visible(timeout=2000):
                accept_button.click()
                time.sleep(1)
        except:
            pass
        
        # Procurar foto
        img_url = page.evaluate('''() => {
            const imgs = Array.from(document.querySelectorAll('img'));
            const playerImgs = imgs.filter(img => {
                const src = img.src || '';
                return (src.includes('/bilder/') || src.includes('/headshots/') || 
                        src.includes('transfermarkt') || src.includes('portrait')) && 
                       (src.includes('spieler') || src.includes('headshot') || 
                        (img.naturalWidth || img.width || 0) > 100);
            });
            
            if (playerImgs.length > 0) {
                return playerImgs[0].src;
            }
            
            const largeImgs = imgs.filter(img => {
                const src = img.src || '';
                const width = img.naturalWidth || img.width || 0;
                return src.includes('transfermarkt') && width > 100;
            });
            
            return largeImgs.length > 0 ? largeImgs[0].src : null;
        }''')
        
        return img_url, None if img_url else 'foto_nao_encontrada'
    
    except PlaywrightTimeout:
        return None, 'timeout'
    except Exception as e:
        return None, f'erro: {str(e)[:30]}'

def buscar_foto_ogol(page, nome_atleta, clube_nome, posicao=None):
    """Busca foto no Ogol diretamente (sem Google)"""
    try:
        # Buscar diretamente no Ogol
        # URL de busca: https://www.ogol.com.br/pesquisa?search_txt=nome+clube+posicao
        query_parts = [nome_atleta, clube_nome]
        if posicao:
            query_parts.append(posicao)
        query = " ".join(query_parts)
        search_url = f"https://www.ogol.com.br/pesquisa?search_txt={quote(query)}"
        
        page.goto(search_url, wait_until='domcontentloaded', timeout=30000)
        time.sleep(3)
        
        # Procurar link do jogador nos resultados
        resultado = page.evaluate('''() => {
            // Procurar por links de jogadores nos resultados
            const links = Array.from(document.querySelectorAll('a'));
            const playerLinks = links.filter(link => {
                const href = link.href || '';
                return href.includes('/jogador/') || href.includes('/player.php');
            });
            
            // Se encontrou links, pegar o primeiro
            if (playerLinks.length > 0) {
                return playerLinks[0].href;
            }
            
            return null;
        }''')
        
        if not resultado:
            return None, 'jogador_nao_encontrado'
        
        # Acessar página do jogador
        page.goto(resultado, wait_until='domcontentloaded', timeout=30000)
        time.sleep(3)
        
        # Procurar foto
        img_url = page.evaluate('''() => {
            const imgs = Array.from(document.querySelectorAll('img'));
            const playerImgs = imgs.filter(img => {
                const src = img.src || '';
                return src.includes('ogol') && 
                       (src.includes('/img/jogadores/') || src.includes('/fotos/') || 
                        src.includes('jogador')) &&
                       (img.naturalWidth || img.width || 0) > 100;
            });
            
            if (playerImgs.length > 0) {
                return playerImgs[0].src;
            }
            
            const largeImgs = imgs.filter(img => {
                const src = img.src || '';
                const width = img.naturalWidth || img.width || 0;
                return src.includes('ogol') && width > 100;
            });
            
            return largeImgs.length > 0 ? largeImgs[0].src : null;
        }''')
        
        return img_url, None if img_url else 'foto_nao_encontrada'
    
    except PlaywrightTimeout:
        return None, 'timeout'
    except Exception as e:
        return None, f'erro: {str(e)[:30]}'

def obter_todos_atletas():
    """Obtém atletas sem foto do banco"""
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
        
        # Buscar atletas com nome completo, nome completo do clube e posição
        cursor.execute('''
            SELECT a.atleta_id, a.apelido, a.nome, a.clube_id, c.nome as clube_nome, a.posicao_id
            FROM acf_atletas a
            LEFT JOIN acf_clubes c ON a.clube_id = c.id
            ORDER BY c.nome, a.nome
        ''')
        
        atletas = []
        for atleta_id, apelido, nome, clube_id, clube_nome, posicao_id in cursor.fetchall():
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
                
                atletas.append({
                    'atleta_id': atleta_id,
                    'nome': nome_completo,
                    'clube_nome': clube_nome or 'Sem clube',
                    'clube_id': clube_id,
                    'posicao_id': posicao_id,
                    'posicao': posicao_nome
                })
        
        return atletas
    
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
    print("BAIXAR FOTOS DE ATLETAS SEM FOTO (TRANSFERMARKT + OGOL)")
    print("Busca direta nas plataformas (sem Google)")
    print("=" * 70)
    print()
    
    # Criar diretório
    FOTO_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Diretorio de fotos: {FOTO_DIR}")
    print()
    
    # Carregar progresso
    progresso = carregar_progresso()
    processados_ids = set(progresso.get('processados', []))
    print(f"Progresso anterior: {len(processados_ids)} atletas processados")
    print()
    
    # Buscar atletas sem foto
    print("Buscando atletas sem foto...")
    todos_atletas = obter_todos_atletas()
    total = len(todos_atletas)
    print(f"Total de atletas sem foto: {total}")
    print("Usando: Nome completo + Nome completo do clube + Posição")
    print()
    
    # Filtrar atletas não processados
    atletas_para_processar = [a for a in todos_atletas if a['atleta_id'] not in processados_ids]
    print(f"Atletas para processar: {len(atletas_para_processar)}")
    print()
    
    if not atletas_para_processar:
        print("Todos os atletas sem foto ja foram processados!")
        return
    
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
        # Usar headless=True já que não precisa mais passar pelo Google
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080},
            locale='pt-BR',
            timezone_id='America/Sao_Paulo',
            extra_http_headers={
                'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            }
        )
        page = context.new_page()
        
        try:
            for idx, atleta in enumerate(atletas_para_processar, 1):
                atleta_id = atleta['atleta_id']
                nome = atleta['nome']  # Nome completo
                clube = atleta['clube_nome']  # Nome completo do clube
                posicao = atleta.get('posicao', '')  # Nome da posição
                
                print(f"[{idx}/{len(atletas_para_processar)}] Atleta ID: {atleta_id}")
                print(f"  Nome completo: {nome}")
                print(f"  Clube: {clube}")
                print(f"  Posição: {posicao}")
                
                resultado_atleta = {
                    'atleta_id': atleta_id,
                    'timestamp': datetime.now().isoformat(),
                    'transfermarkt': None,
                    'ogol': None
                }
                
                # Verificar se já tem foto
                tem_tm = any((FOTO_DIR / f"{atleta_id}_transfermarkt{ext}").exists() 
                            for ext in ['.jpg', '.jpeg', '.png', '.webp'])
                tem_ogol = any((FOTO_DIR / f"{atleta_id}_ogol{ext}").exists() 
                              for ext in ['.jpg', '.jpeg', '.png', '.webp'])
                
                # Buscar Transfermarkt
                if not tem_tm:
                    print(f"  Transfermarkt...", end=' ', flush=True)
                    img_url, erro = buscar_foto_transfermarkt(page, nome, clube, posicao)
                    
                    if img_url:
                        print(f"Encontrado!")
                        ext = '.jpg'
                        if '.png' in img_url.lower():
                            ext = '.png'
                        filepath = FOTO_DIR / f"{atleta_id}_transfermarkt{ext}"
                        sucesso, resultado = baixar_imagem(img_url, filepath)
                        if sucesso:
                            print(f"    Baixado: {resultado:.1f} KB")
                            baixados_tm += 1
                            resultado_atleta['transfermarkt'] = 'sucesso'
                        else:
                            print(f"    ERRO ao baixar: {resultado}")
                            resultado_atleta['transfermarkt'] = f'erro_download: {resultado}'
                            erros += 1
                    else:
                        print(f"Nao encontrado ({erro})")
                        resultado_atleta['transfermarkt'] = erro
                        nao_encontrados_tm += 1
                else:
                    print(f"  Transfermarkt: ja existe")
                    resultado_atleta['transfermarkt'] = 'ja_existia'
                
                # Buscar Ogol
                if not tem_ogol:
                    print(f"  Ogol...", end=' ', flush=True)
                    img_url, erro = buscar_foto_ogol(page, nome, clube, posicao)
                    
                    if img_url:
                        print(f"Encontrado!")
                        ext = '.jpg'
                        if '.png' in img_url.lower():
                            ext = '.png'
                        filepath = FOTO_DIR / f"{atleta_id}_ogol{ext}"
                        sucesso, resultado = baixar_imagem(img_url, filepath)
                        if sucesso:
                            print(f"    Baixado: {resultado:.1f} KB")
                            baixados_ogol += 1
                            resultado_atleta['ogol'] = 'sucesso'
                        else:
                            print(f"    ERRO ao baixar: {resultado}")
                            resultado_atleta['ogol'] = f'erro_download: {resultado}'
                            erros += 1
                    else:
                        print(f"Nao encontrado ({erro})")
                        resultado_atleta['ogol'] = erro
                        nao_encontrados_ogol += 1
                else:
                    print(f"  Ogol: ja existe")
                    resultado_atleta['ogol'] = 'ja_existia'
                
                # Salvar progresso
                processados_ids.add(atleta_id)
                progresso['processados'] = list(processados_ids)
                if 'detalhes' not in progresso:
                    progresso['detalhes'] = []
                progresso['detalhes'].append(resultado_atleta)
                salvar_progresso(progresso)
                
                print()
                
                # Progresso a cada 10
                if idx % 10 == 0:
                    print(f"  >>> Progresso: {idx}/{len(atletas_para_processar)} ({idx*100//len(atletas_para_processar)}%)")
                    print(f"      Transfermarkt: {baixados_tm} baixados, {nao_encontrados_tm} nao encontrados")
                    print(f"      Ogol: {baixados_ogol} baixados, {nao_encontrados_ogol} nao encontrados")
                    print(f"      Erros: {erros}")
                    print()
                
                # Delay entre requisições
                time.sleep(3)
        
        finally:
            browser.close()
    
    # Resumo final
    print()
    print("=" * 70)
    print("RESUMO FINAL")
    print("=" * 70)
    print(f"Total processado nesta execucao: {len(atletas_para_processar)}")
    print(f"Total geral processado: {len(processados_ids)}/{total}")
    print(f"Transfermarkt: {baixados_tm} baixados, {nao_encontrados_tm} nao encontrados")
    print(f"Ogol: {baixados_ogol} baixados, {nao_encontrados_ogol} nao encontrados")
    print(f"Erros: {erros}")
    print(f"Diretorio: {FOTO_DIR}")
    print(f"Arquivo de progresso: {PROGRESSO_FILE}")
    print("=" * 70)

if __name__ == '__main__':
    main()

