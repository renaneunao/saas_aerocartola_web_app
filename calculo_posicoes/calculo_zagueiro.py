import math
import sys
from pathlib import Path

# Ensure project root is on sys.path when running this file directly
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from database import get_db_connection, close_db_connection
from utils.utilidades import printdbg
from api_cartola import fetch_status_data
from utils.weights import get_weight

# Fatores multiplicadores
DEFAULTS = {
    'FATOR_MEDIA': 1.5,
    'FATOR_DS': 4.5,
    'FATOR_SG': 4.0,
    'FATOR_ESCALACAO': 5.0,
    'FATOR_PESO_JOGO': 5.0,
}

# Função para carregar pesos dinamicamente
def _load_weights():
    """Carrega os pesos do banco de dados a cada execução."""
    return {
        'FATOR_MEDIA': float(get_weight('zagueiro', 'FATOR_MEDIA', DEFAULTS['FATOR_MEDIA'])),
        'FATOR_DS': float(get_weight('zagueiro', 'FATOR_DS', DEFAULTS['FATOR_DS'])),
        'FATOR_SG': float(get_weight('zagueiro', 'FATOR_SG', DEFAULTS['FATOR_SG'])),
        'FATOR_ESCALACAO': float(get_weight('zagueiro', 'FATOR_ESCALACAO', DEFAULTS['FATOR_ESCALACAO'])),
        'FATOR_PESO_JOGO': float(get_weight('zagueiro', 'FATOR_PESO_JOGO', DEFAULTS['FATOR_PESO_JOGO']))
    }

def calcular_melhores_zagueiros(top_n=10, rodada_atual=6, min_jogos_pref=3, rodada_min_jogos=8, usar_provaveis_cartola=None):
    # Carregar pesos dinamicamente a cada execução
    weights = _load_weights()
    FATOR_MEDIA = weights['FATOR_MEDIA']
    FATOR_DS = weights['FATOR_DS']
    FATOR_SG = weights['FATOR_SG']
    FATOR_ESCALACAO = weights['FATOR_ESCALACAO']
    FATOR_PESO_JOGO = weights['FATOR_PESO_JOGO']
    
    # Log dos pesos carregados
    printdbg(f"[PESOS ZAGUEIRO] FATOR_MEDIA: {FATOR_MEDIA} (padrão: {DEFAULTS['FATOR_MEDIA']})")
    printdbg(f"[PESOS ZAGUEIRO] FATOR_DS: {FATOR_DS} (padrão: {DEFAULTS['FATOR_DS']})")
    printdbg(f"[PESOS ZAGUEIRO] FATOR_SG: {FATOR_SG} (padrão: {DEFAULTS['FATOR_SG']})")
    printdbg(f"[PESOS ZAGUEIRO] FATOR_ESCALACAO: {FATOR_ESCALACAO} (padrão: {DEFAULTS['FATOR_ESCALACAO']})")
    printdbg(f"[PESOS ZAGUEIRO] FATOR_PESO_JOGO: {FATOR_PESO_JOGO} (padrão: {DEFAULTS['FATOR_PESO_JOGO']})")
    
    conn = get_db_connection()
    cursor = conn.cursor()

    # Define minimum games based on round
    min_jogos = min_jogos_pref if rodada_atual >= rodada_min_jogos else 1

    # Filtrar zagueiros (posicao_id = 3) com jogos
    if usar_provaveis_cartola:
        # Usando dados do Joga 10 para jogadores prováveis
        printdbg("Usando dados do Joga 10 para jogadores prováveis")
        cursor.execute('''
            SELECT a.atleta_id, a.apelido, a.clube_id, a.pontos_num, a.media_num, 
                   a.preco_num, a.jogos_num, c.nome
            FROM acf_atletas a
            JOIN acf_clubes c ON a.clube_id = c.id
            JOIN provaveis_cartola p ON a.atleta_id = p.atleta_id
            WHERE a.posicao_id = 3 AND a.jogos_num >= %s AND p.status = 'provavel'
        ''', (min_jogos,))
    else:
        # Usando dados do Cartola para jogadores prováveis (status_id = 7)
        printdbg("Usando dados do Cartola para jogadores prováveis")
        cursor.execute('''
            SELECT a.atleta_id, a.apelido, a.clube_id, a.pontos_num, a.media_num, 
                   a.preco_num, a.jogos_num, c.nome
            FROM acf_atletas a
            JOIN acf_clubes c ON a.clube_id = c.id
            WHERE a.posicao_id = 3 AND a.jogos_num >= %s AND a.status_id = 7
        ''', (min_jogos,))
    zagueiros = cursor.fetchall()

    printdbg(f"Total de zagueiros encontrados: {len(zagueiros)}")

    # Buscar peso_jogo e peso_sg das tabelas de perfis (usando perfil padrão 1 e 2)
    perfil_peso_jogo_padrao = 1
    perfil_peso_sg_padrao = 2
    
    # Coletar todos os clube_ids únicos
    clube_ids = list(set([z[2] for z in zagueiros]))
    peso_jogo_dict = {}
    peso_sg_dict = {}
    
    if clube_ids:
        placeholders = ','.join(['%s'] * len(clube_ids))
        # Buscar peso_jogo
        try:
            cursor.execute(f'''
                SELECT clube_id, peso_jogo
                FROM acp_peso_jogo_perfis
                WHERE perfil_id = %s AND rodada_atual = %s AND clube_id IN ({placeholders})
            ''', [perfil_peso_jogo_padrao, rodada_atual] + clube_ids)
            for row in cursor.fetchall():
                if row and len(row) >= 2:
                    clube_id, peso_jogo = row
                    peso_jogo_dict[clube_id] = float(peso_jogo) if peso_jogo else 0
        except Exception as e:
            printdbg(f"Erro ao buscar peso_jogo: {e}")
        
        # Buscar peso_sg
        try:
            cursor.execute(f'''
                SELECT clube_id, peso_sg
                FROM acp_peso_sg_perfis
                WHERE perfil_id = %s AND rodada_atual = %s AND clube_id IN ({placeholders})
            ''', [perfil_peso_sg_padrao, rodada_atual] + clube_ids)
            for row in cursor.fetchall():
                if row and len(row) >= 2:
                    clube_id, peso_sg = row
                    peso_sg_dict[clube_id] = float(peso_sg) if peso_sg else 0
        except Exception as e:
            printdbg(f"Erro ao buscar peso_sg: {e}")

    # Obter os 20 jogadores mais escalados na tabela destaques
    cursor.execute('''
        SELECT atleta_id, escalacoes
        FROM acf_destaques
        ORDER BY escalacoes DESC
        LIMIT 20
    ''')
    destaques_top = cursor.fetchall()
    total_escalacoes_top = sum(float(d[1]) for d in destaques_top) if destaques_top else 1.0  # Evitar divisão por zero
    printdbg(f"Total de jogadores no top 20 destaques: {len(destaques_top)}, Total de escalações: {total_escalacoes_top}")

    # Criar dicionário para acesso rápido às escalações
    escalacoes_por_atleta = {d[0]: float(d[1]) for d in destaques_top}

    # Calcular pontuação total
    resultados = []
    for zagueiro in zagueiros:
        atleta_id, apelido, clube_id, pontos, media, preco, jogos, clube_nome = zagueiro
        peso_jogo = peso_jogo_dict.get(clube_id, 0)
        peso_sg = peso_sg_dict.get(clube_id, 0)

        printdbg(f"\nProcessando zagueiro: {apelido} (ID: {atleta_id}, Clube: {clube_nome})")
        printdbg(f"  Média: {media:.2f}, Peso Jogo (original): {peso_jogo if peso_jogo is not None else 'N/A'}, "
                 f"Peso SG: {peso_sg if peso_sg is not None else 'N/A'}")

        # Fator 1: Média do jogador
        pontos_media = media * FATOR_MEDIA
        printdbg(f"  Pontos Média: {pontos_media:.2f}")

        # Fator 2: Média de desarmes do zagueiro (scout_ds)
        cursor.execute('''
            SELECT AVG(p.scout_ds)
            FROM acf_pontuados p
            WHERE p.atleta_id = %s AND p.entrou_em_campo = TRUE AND p.rodada_id <= %s
        ''', (atleta_id, rodada_atual - 1))
        media_ds_result = cursor.fetchone()[0]
        media_ds = float(media_ds_result) if media_ds_result is not None else 0.0
        printdbg(f"  Média Desarmes Zagueiro: {media_ds:.2f}")

        # Default values if weights are missing
        peso_sg = peso_sg if peso_sg is not None else 0
        peso_jogo_original = peso_jogo if peso_jogo is not None else 0

        # Encontrar o adversário na rodada atual
        cursor.execute('''
            SELECT p.clube_casa_id, p.clube_visitante_id
            FROM acf_partidas p
            WHERE p.rodada_id = %s AND p.valida = TRUE AND 
                  (p.clube_casa_id = %s OR p.clube_visitante_id = %s)
        ''', (rodada_atual, clube_id, clube_id))
        partida = cursor.fetchone()

        media_ds_cedidos = 0
        adversario_nome = "N/A"
        if partida:
            clube_casa_id, clube_visitante_id = partida
            adversario_id = clube_visitante_id if clube_id == clube_casa_id else clube_casa_id

            # Obter o nome do clube adversário
            cursor.execute('''
                SELECT nome
                FROM acf_clubes
                WHERE id = %s
            ''', (adversario_id,))
            adversario_nome_result = cursor.fetchone()
            adversario_nome = adversario_nome_result[0] if adversario_nome_result else "Desconhecido"
            printdbg(f"  Partida encontrada: Clube {clube_nome} vs Adversário {adversario_nome} (ID: {adversario_id})")

            peso_jogo = peso_jogo_original * FATOR_PESO_JOGO

            # Calcular média de desarmes cedidos pelo adversário a zagueiros
            cursor.execute('''
                SELECT AVG(p.scout_ds)
                FROM acf_pontuados p
                JOIN acf_partidas pt ON p.rodada_id = pt.rodada_id AND 
                    ((pt.clube_casa_id = %s AND p.clube_id = pt.clube_visitante_id) OR 
                     (pt.clube_visitante_id = %s AND p.clube_id = pt.clube_casa_id))
                WHERE p.posicao_id = 3 AND p.entrou_em_campo = TRUE AND p.rodada_id <= %s
            ''', (adversario_id, adversario_id, rodada_atual - 1))
            media_ds_cedidos_result = cursor.fetchone()[0]
            media_ds_cedidos = float(media_ds_cedidos_result) if media_ds_cedidos_result is not None else 0.0
            printdbg(f"  Média Desarmes Cedidos pelo Adversário: {media_ds_cedidos:.2f}")
        else:
            printdbg("  Nenhuma partida encontrada para este zagueiro na rodada atual. Usando peso_jogo = 0 e media_ds_cedidos = 0.")
            peso_jogo = 0

        # Calcular contribuição dos desarmes (produto de media_ds e media_ds_cedidos)
        pontos_ds = media_ds * media_ds_cedidos * FATOR_DS
        printdbg(f"  Pontos Desarmes: {media_ds:.2f} * {media_ds_cedidos:.2f} * {FATOR_DS} = {pontos_ds:.2f}")

        # Calcular pontuação base
        base_pontuacao = pontos_media + peso_jogo + pontos_ds
        pontuacao_total = base_pontuacao * (1 + peso_sg * FATOR_SG)
        printdbg(f"  Pontuação Base: (({pontos_media:.2f} (média) + {peso_jogo:.2f} (jogo) + "
                 f"{pontos_ds:.2f} (desarmes)) * (1 + {peso_sg:.2f} * {FATOR_SG})) = {pontuacao_total:.2f}")

        # Calcular peso de escalação
        escalacoes = escalacoes_por_atleta.get(atleta_id, 0)
        percentual_escalacoes = escalacoes / total_escalacoes_top if total_escalacoes_top > 0 else 0
        peso_escalacao = 1 + percentual_escalacoes * FATOR_ESCALACAO
        printdbg(f"  Escalções: {escalacoes}, Percentual: {percentual_escalacoes:.4f}, Peso Escalação: {peso_escalacao:.4f}")

        # Ajustar pontuação final com peso de escalação e aplicar raiz quadrada, evitando valores negativos
        pontuacao_total_final = math.sqrt(max(0, pontuacao_total * peso_escalacao))
        printdbg(f"  Pontuação Final: sqrt(max(0, {pontuacao_total:.2f} * {peso_escalacao:.4f})) = {pontuacao_total_final:.2f}")

        resultados.append({
            'atleta_id': atleta_id,
            'apelido': apelido,
            'clube_id': clube_id,
            'clube_nome': clube_nome,
            'pontuacao_total': pontuacao_total_final,
            'media': media,
            'preco': preco,
            'jogos': jogos,
            'peso_jogo': peso_jogo,
            'peso_sg': peso_sg,
            'media_ds': media_ds,
            'media_ds_cedidos': media_ds_cedidos,
            'adversario_nome': adversario_nome,
            'peso_escalacao': peso_escalacao
        })

    # Ordenar por pontuação total e pegar os top N
    melhores = sorted(resultados, key=lambda x: x['pontuacao_total'], reverse=True)[:top_n]

    # Imprimir resultados detalhados
    print("\nMelhores Zagueiros:")
    print("-" * 160)
    print(f"{'Nome':<20} {'ID':<10} {'Clube':<20} {'Adversário':<20} {'Pontuação':<12} {'Média':<12} "
          f"{'Peso Jogo':<12} {'Peso SG':<12} {'Média DS':<12} {'DS Cedidos':<12} {'Peso Esc':<12}")
    print("-" * 160)
    for zagueiro in melhores:
        print(f"{zagueiro['apelido']:<20} {zagueiro['atleta_id']:<10} {zagueiro['clube_nome']:<20} "
              f"{zagueiro['adversario_nome']:<20} {zagueiro['pontuacao_total']:<12.2f} {zagueiro['media']:<12.2f} "
              f"{zagueiro['peso_jogo']:<12.2f} {zagueiro['peso_sg']:<12.2f} {zagueiro['media_ds']:<12.2f} "
              f"{zagueiro['media_ds_cedidos']:<12.2f} {zagueiro['peso_escalacao']:<12.4f}")
    print("-" * 160)

    # Salvar na tabela ranking_por_posicao
    from main import update_ranking_por_posicao
    update_ranking_por_posicao(conn, melhores, 3, rodada_atual)
    printdbg(f"Ranking de zagueiros salvo na tabela ranking_por_posicao")
    
    close_db_connection(conn)
    return melhores

def main():
    # Obter a rodada atual
    status_data = fetch_status_data()
    if not status_data:
        printdbg("Erro ao obter dados de status.")
        return
    rodada_atual = status_data['rodada_atual']
    melhores_zagueiros = calcular_melhores_zagueiros(top_n=20, rodada_atual=rodada_atual, usar_provaveis_cartola=False)
    printdbg(f"Top {len(melhores_zagueiros)} zagueiros calculados com sucesso.")

if __name__ == "__main__":
    main()