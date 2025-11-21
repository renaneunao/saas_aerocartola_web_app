"""
Script interativo para adicionar fotos de atletas que estão faltando.
Verifica quais atletas não têm foto e solicita URLs para baixar.
"""

import os
import sys
import requests
from pathlib import Path
from urllib.parse import urlparse

# Adicionar o diretório raiz ao path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

# Carregar variáveis de ambiente
from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / '.env')

from database import get_db_connection, close_db_connection

FOTO_DIR = PROJECT_ROOT / 'static' / 'cartola_imgs' / 'foto_atletas'

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
        ext = obter_extensao_arquivo(url)
        filename = f"{atleta_id}{ext}"
        filepath = output_dir / filename
        
        if filepath.exists():
            return False, 'ja existe'
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
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
    print("ADICIONAR FOTOS DE ATLETAS FALTANTES")
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
    
    # Processar cada atleta
    baixados = 0
    pulados = 0
    
    for idx, atleta in enumerate(atletas_sem_foto, 1):
        atleta_id = atleta['atleta_id']
        nome = atleta['nome']
        clube = atleta['clube_nome']
        
        print()
        print(f"[{idx}/{total}] Atleta ID: {atleta_id}")
        print(f"  Nome: {nome}")
        print(f"  Clube: {clube}")
        print()
        
        while True:
            url = input(f"  Digite o URL da foto (ou 'pular' para pular, 'sair' para encerrar): ").strip()
            
            if url.lower() == 'sair':
                print("\nEncerrando...")
                return
            
            if url.lower() == 'pular' or url == '':
                print(f"  Pulando atleta {atleta_id}...")
                pulados += 1
                break
            
            if not url.startswith('http'):
                print("  ERRO: URL deve comecar com http:// ou https://")
                continue
            
            # Tentar baixar
            print(f"  Baixando foto...")
            sucesso, status = baixar_foto(atleta_id, url, FOTO_DIR)
            
            if sucesso:
                print(f"  OK: {status}")
                baixados += 1
                break
            else:
                print(f"  ERRO: {status}")
                tentar_novamente = input("  Tentar novamente? (s/n): ").strip().lower()
                if tentar_novamente != 's':
                    pulados += 1
                    break
    
    # Resumo
    print()
    print("=" * 70)
    print("RESUMO")
    print("=" * 70)
    print(f"Total de atletas processados: {total}")
    print(f"Fotos baixadas: {baixados}")
    print(f"Atletas pulados: {pulados}")
    print("=" * 70)

if __name__ == '__main__':
    main()

