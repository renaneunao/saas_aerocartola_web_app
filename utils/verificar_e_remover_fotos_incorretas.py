"""
Script para verificar e remover fotos baixadas que não correspondem aos nomes dos atletas.
Extrai o nome do arquivo da URL e compara com o nome do atleta no banco de dados.
"""

import os
import re
from pathlib import Path
from urllib.parse import urlparse
from difflib import SequenceMatcher

# Adicionar o diretório raiz ao path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(PROJECT_ROOT))

# Carregar variáveis de ambiente
from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / '.env')

from database import get_db_connection, close_db_connection

FOTO_DIR = PROJECT_ROOT / 'static' / 'cartola_imgs' / 'foto_atletas'

def normalizar_nome(nome):
    """Normaliza um nome para comparação"""
    if not nome:
        return ""
    # Converter para minúsculas, remover acentos básicos, remover espaços extras
    nome = nome.lower().strip()
    # Remover caracteres especiais comuns
    nome = re.sub(r'[^\w\s]', '', nome)
    # Remover espaços múltiplos
    nome = re.sub(r'\s+', ' ', nome)
    return nome

def extrair_nome_da_url(url):
    """Extrai o nome do atleta da URL do ogol"""
    # Exemplo: https://www.ogol.com.br/img/jogadores/33/102033_20200402043715_juan_barrera.jpg
    # Ou: https://www.ogol.com.br/img/jogadores/new/02/71/650271_erick_pulga_20250109094705.png
    
    # Pegar o nome do arquivo
    parsed = urlparse(url)
    filename = os.path.basename(parsed.path)
    
    # Remover extensão
    filename = os.path.splitext(filename)[0]
    
    # Padrão: ID_data_nome_timestamp ou ID_nome_timestamp
    # Tentar extrair o nome (parte entre underscores, geralmente a última parte significativa)
    parts = filename.split('_')
    
    # Se tiver muitas partes, o nome geralmente está no meio
    # Exemplo: 102033_20200402043715_juan_barrera_1693682228
    # Ou: 650271_erick_pulga_20250109094705
    
    # Procurar por partes que parecem nomes (não são números puros e não são timestamps longos)
    nome_parts = []
    for part in parts:
        # Ignorar partes que são apenas números (IDs ou timestamps)
        if part.isdigit() and len(part) > 6:
            continue
        # Ignorar partes muito curtas
        if len(part) < 2:
            continue
        # Se não for número puro, pode ser parte do nome
        if not part.isdigit():
            nome_parts.append(part)
    
    if nome_parts:
        # Juntar as partes do nome
        nome = ' '.join(nome_parts)
        return normalizar_nome(nome)
    
    return ""

def similaridade_nomes(nome1, nome2):
    """Calcula similaridade entre dois nomes (0 a 1)"""
    if not nome1 or not nome2:
        return 0.0
    
    nome1 = normalizar_nome(nome1)
    nome2 = normalizar_nome(nome2)
    
    # Se forem idênticos
    if nome1 == nome2:
        return 1.0
    
    # Calcular similaridade usando SequenceMatcher
    similarity = SequenceMatcher(None, nome1, nome2).ratio()
    
    # Também verificar se um nome contém o outro (para apelidos)
    if nome1 in nome2 or nome2 in nome1:
        similarity = max(similarity, 0.7)
    
    return similarity

def obter_atletas_com_fotos():
    """Obtém lista de atletas que têm fotos e seus dados"""
    conn = get_db_connection()
    if not conn:
        print("ERRO: Nao foi possivel conectar ao banco de dados")
        return {}
    
    try:
        cursor = conn.cursor()
        
        # Buscar todos os atletas
        cursor.execute('''
            SELECT a.atleta_id, a.apelido, a.nome, a.clube_id, c.nome as clube_nome
            FROM acf_atletas a
            LEFT JOIN acf_clubes c ON a.clube_id = c.id
            WHERE a.status_id = 7
        ''')
        
        atletas = {}
        for atleta_id, apelido, nome, clube_id, clube_nome in cursor.fetchall():
            nome_completo = apelido or nome or f"Atleta {atleta_id}"
            atletas[int(atleta_id)] = {
                'nome': nome_completo,
                'apelido': apelido or '',
                'nome_completo': nome or '',
                'clube_nome': clube_nome or 'Sem clube'
            }
        
        return atletas
    
    except Exception as e:
        print(f"ERRO ao buscar atletas: {e}")
        return {}
    finally:
        close_db_connection(conn)

def verificar_fotos():
    """Verifica todas as fotos e identifica as incorretas"""
    print("=" * 70)
    print("VERIFICANDO FOTOS DE ATLETAS")
    print("=" * 70)
    print()
    
    # Buscar dados dos atletas
    print("Buscando dados dos atletas no banco...")
    atletas = obter_atletas_com_fotos()
    print(f"Encontrados {len(atletas)} atletas no banco")
    print()
    
    # Listar todas as fotos
    fotos = list(FOTO_DIR.glob('*.*'))
    fotos = [f for f in fotos if f.suffix.lower() in ['.jpg', '.jpeg', '.png', '.gif']]
    
    print(f"Encontradas {len(fotos)} fotos no diretorio")
    print()
    print("=" * 70)
    print("VERIFICANDO CORRESPONDENCIA DE NOMES...")
    print("=" * 70)
    print()
    
    # Ler o arquivo JS para obter as URLs originais
    js_file = PROJECT_ROOT / 'static' / 'cartola_imgs' / 'player_images_by_id.js'
    urls_por_id = {}
    
    if js_file.exists():
        with open(js_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        pattern = r'(\d+):\s*"([^"]+)"'
        matches = re.findall(pattern, content)
        for atleta_id, url in matches:
            if url and url.startswith('http'):
                urls_por_id[int(atleta_id)] = url
    
    removidas = 0
    mantidas = 0
    nao_encontrados = 0
    
    for foto_path in fotos:
        # Extrair ID do nome do arquivo
        filename = foto_path.stem  # Nome sem extensão
        try:
            atleta_id = int(filename)
        except ValueError:
            print(f"ERRO: Nao foi possivel extrair ID de {foto_path.name}")
            continue
        
        # Buscar dados do atleta
        if atleta_id not in atletas:
            print(f"[{atleta_id}] Atleta nao encontrado no banco - REMOVENDO")
            try:
                foto_path.unlink()
                removidas += 1
            except Exception as e:
                print(f"  ERRO ao remover: {e}")
            continue
        
        atleta = atletas[atleta_id]
        nome_atleta = atleta['nome']
        
        # Buscar URL original se disponível
        url_original = urls_por_id.get(atleta_id, '')
        
        if url_original:
            # Extrair nome da URL
            nome_na_url = extrair_nome_da_url(url_original)
            
            if nome_na_url:
                # Calcular similaridade
                sim_apelido = similaridade_nomes(nome_na_url, atleta['apelido']) if atleta['apelido'] else 0
                sim_nome = similaridade_nomes(nome_na_url, atleta['nome_completo']) if atleta['nome_completo'] else 0
                sim_nome_completo = similaridade_nomes(nome_na_url, nome_atleta)
                
                similarity = max(sim_apelido, sim_nome, sim_nome_completo)
                
                if similarity < 0.5:  # Threshold de 50% de similaridade
                    print(f"[{atleta_id}] {nome_atleta} ({atleta['clube_nome']})")
                    print(f"  Nome na URL: {nome_na_url}")
                    print(f"  Similaridade: {similarity:.2%}")
                    print(f"  REMOVENDO (similaridade muito baixa)")
                    try:
                        foto_path.unlink()
                        removidas += 1
                    except Exception as e:
                        print(f"  ERRO ao remover: {e}")
                    print()
                else:
                    mantidas += 1
            else:
                # Não conseguiu extrair nome da URL, manter por segurança
                mantidas += 1
        else:
            # Não tem URL no JS, manter por segurança
            nao_encontrados += 1
            mantidas += 1
    
    # Resumo
    print()
    print("=" * 70)
    print("RESUMO")
    print("=" * 70)
    print(f"Total de fotos verificadas: {len(fotos)}")
    print(f"Fotos mantidas: {mantidas}")
    print(f"Fotos removidas (nomes incorretos): {removidas}")
    print(f"Fotos sem URL no JS: {nao_encontrados}")
    print("=" * 70)

if __name__ == '__main__':
    verificar_fotos()

