import sys
from pathlib import Path

# Ensure project root is on sys.path when running this file directly
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from database import get_db_connection, close_db_connection
from utils.utilidades import printdbg
from api_cartola import fetch_status_data


# Fator de peso para a média
from utils.weights import get_weight

DEFAULTS = {
    'FATOR_MEDIA': 0.2,
    'FATOR_FF': 4.5,
    'FATOR_FD': 6.5,
    'FATOR_SG': 1.5,
    'FATOR_PESO_JOGO': 1.5,
    'FATOR_GOL_ADVERSARIO': 2.0,
}

# Função para carregar pesos dinamicamente
def _load_weights():
    """Carrega os pesos do banco de dados a cada execução."""
    return {
        'FATOR_MEDIA': float(get_weight('goleiro', 'FATOR_MEDIA', DEFAULTS['FATOR_MEDIA'])),
        'FATOR_FF': float(get_weight('goleiro', 'FATOR_FF', DEFAULTS['FATOR_FF'])),
        'FATOR_FD': float(get_weight('goleiro', 'FATOR_FD', DEFAULTS['FATOR_FD'])),
        'FATOR_SG': float(get_weight('goleiro', 'FATOR_SG', DEFAULTS['FATOR_SG'])),
        'FATOR_PESO_JOGO': float(get_weight('goleiro', 'FATOR_PESO_JOGO', DEFAULTS['FATOR_PESO_JOGO'])),
        'FATOR_GOL_ADVERSARIO': float(get_weight('goleiro', 'FATOR_GOL_ADVERSARIO', DEFAULTS['FATOR_GOL_ADVERSARIO']))
    }

def calcular_melhores_goleiros(top_n=10, rodada_atual=5, min_jogos_pref=3, rodada_min_jogos=8, usar_provaveis_cartola=None):
    # Carregar pesos dinamicamente a cada execução
    weights = _load_weights()
    FATOR_MEDIA = weights['FATOR_MEDIA']
    FATOR_FF = weights['FATOR_FF']
    FATOR_FD = weights['FATOR_FD']
    FATOR_SG = weights['FATOR_SG']
    FATOR_PESO_JOGO = weights['FATOR_PESO_JOGO']
    FATOR_GOL_ADVERSARIO = weights['FATOR_GOL_ADVERSARIO']
    
    # Log dos pesos carregados
    printdbg(f"[PESOS GOLEIRO] FATOR_MEDIA: {FATOR_MEDIA} (padrão: {DEFAULTS['FATOR_MEDIA']})")
    printdbg(f"[PESOS GOLEIRO] FATOR_FF: {FATOR_FF} (padrão: {DEFAULTS['FATOR_FF']})")
    printdbg(f"[PESOS GOLEIRO] FATOR_FD: {FATOR_FD} (padrão: {DEFAULTS['FATOR_FD']})")
    printdbg(f"[PESOS GOLEIRO] FATOR_SG: {FATOR_SG} (padrão: {DEFAULTS['FATOR_SG']})")
    printdbg(f"[PESOS GOLEIRO] FATOR_PESO_JOGO: {FATOR_PESO_JOGO} (padrão: {DEFAULTS['FATOR_PESO_JOGO']})")
    printdbg(f"[PESOS GOLEIRO] FATOR_GOL_ADVERSARIO: {FATOR_GOL_ADVERSARIO} (padrão: {DEFAULTS['FATOR_GOL_ADVERSARIO']})")
    
    # Se não for especificado, usa o valor da configuração global
    conn = get_db_connection()
    cursor = conn.cursor()

    # Define minimum games based on round
    min_jogos = min_jogos_pref if rodada_atual >= rodada_min_jogos else 1

    # Filtrar goleiro (posicao_id = 1) com jogos
    if usar_provaveis_cartola:
        # Usando dados da nova API de prováveis
        printdbg("Usando dados da API de prováveis para jogadores prováveis")
        cursor.execute('''
            SELECT a.atleta_id, a.apelido, a.clube_id, a.pontos_num, a.media_num, 
                   a.preco_num, a.jogos_num, a.peso_jogo, a.peso_sg, c.nome
            FROM acf_atletas a
            JOIN acf_clubes c ON a.clube_id = c.id
            JOIN provaveis_cartola p ON a.atleta_id = p.atleta_id
            WHERE a.posicao_id = 1 AND a.jogos_num >= %s AND p.status = 'provavel'
        ''', (min_jogos,))
    else:
        # Usando dados do Cartola para jogadores prováveis (status_id = 7)
        printdbg("Usando dados do Cartola para jogadores prováveis")
        cursor.execute('''
            SELECT a.atleta_id, a.apelido, a.clube_id, a.pontos_num, a.media_num, 
                   a.preco_num, a.jogos_num, a.peso_jogo, a.peso_sg, c.nome
            FROM acf_atletas a
            JOIN acf_clubes c ON a.clube_id = c.id
            WHERE a.posicao_id = 1 AND a.jogos_num >= %s AND a.status_id = 7
        ''', (min_jogos,))
    goleiros = cursor.fetchall()

    printdbg(f"Total de goleiros encontrados: {len(goleiros)}")

    # Calcular pontuação total
    resultados = []
    for goleiro in goleiros:
        atleta_id, apelido, clube_id, pontos, media, preco, jogos, peso_jogo, peso_sg, clube_nome = goleiro

        printdbg(f"\nProcessando goleiro: {apelido} (ID: {atleta_id}, Clube: {clube_nome})")
        printdbg(f"  Média: {media:.2f}, Peso Jogo (original): {peso_jogo if peso_jogo is not None else 'N/A'}, "
                 f"Peso SG: {peso_sg if peso_sg is not None else 'N/A'}")

        # Fator 1: Média do jogador
        pontos_media = media * FATOR_MEDIA
        printdbg(f"  Pontos Média: {pontos_media:.2f}")

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

        peso_finalizacoes = 0
        media_gols_adversario = 0
        if partida:
            clube_casa_id, clube_visitante_id = partida
            adversario_id = clube_visitante_id if clube_id == clube_casa_id else clube_casa_id
            printdbg(f"  Partida encontrada: Clube {clube_nome} vs Adversário ID {adversario_id}")

            peso_jogo = peso_jogo_original * FATOR_PESO_JOGO

            # Calcular finalizações esperadas do adversário (média das últimas rodadas)
            cursor.execute('''
                SELECT AVG(p.scout_ff), AVG(p.scout_fd)
                FROM acf_pontuados p
                WHERE p.clube_id = %s AND p.rodada_id <= %s AND p.entrou_em_campo = TRUE
            ''', (adversario_id, rodada_atual - 1))
            ff_avg, fd_avg = cursor.fetchone()
            ff_avg = float(ff_avg) if ff_avg is not None else 0.0
            fd_avg = float(fd_avg) if fd_avg is not None else 0.0

            peso_finalizacoes = (ff_avg * FATOR_FF) + (fd_avg * FATOR_FD)
            printdbg(f"  Finalizações Adversário: FF_avg={ff_avg:.2f} * {FATOR_FF} + "
                     f"FD_avg={fd_avg:.2f} * {FATOR_FD} = {peso_finalizacoes:.2f}")

            # Calcular média de gols do adversário usando a tabela de partidas
            cursor.execute('''
                SELECT 
                    SUM(CASE WHEN p.clube_casa_id = %s THEN p.placar_oficial_mandante ELSE 0 END) +
                    SUM(CASE WHEN p.clube_visitante_id = %s THEN p.placar_oficial_visitante ELSE 0 END) AS gols_marcados,
                    COUNT(*) AS jogos
                FROM acf_partidas p
                WHERE (p.clube_casa_id = %s OR p.clube_visitante_id = %s) 
                  AND p.rodada_id < %s AND p.valida = TRUE 
                  AND p.placar_oficial_mandante IS NOT NULL AND p.placar_oficial_visitante IS NOT NULL
            ''', (adversario_id, adversario_id, adversario_id, adversario_id, rodada_atual))
            result = cursor.fetchone()
            if result and result[1] > 0:
                gols_marcados, jogos = result
                media_gols_adversario = float(gols_marcados) / float(jogos)
                printdbg(f"  Média de Gols Adversário (partidas): {gols_marcados}/{jogos} = {media_gols_adversario:.2f}")
            else:
                printdbg(f"  Sem dados de gols para o adversário ID {adversario_id} nas partidas. Usando 0.")
        else:
            printdbg("  Nenhuma partida encontrada para este goleiro na rodada atual. Usando valores padrão.")
            peso_jogo = 0

        # Calcular pontuação total
        base_pontuacao = pontos_media + peso_jogo + peso_finalizacoes - (media_gols_adversario * FATOR_GOL_ADVERSARIO)
        pontuacao_total = base_pontuacao * (FATOR_SG + peso_sg)
        printdbg(f"  Cálculo: (({pontos_media:.2f} (média) + {peso_jogo:.2f} (jogo) + "
                 f"{peso_finalizacoes:.2f} (finalizações) - {media_gols_adversario:.2f} (gols adversário) * {FATOR_GOL_ADVERSARIO}) * "
                 f"({FATOR_SG} + {peso_sg:.2f} (SG)) = {pontuacao_total:.2f}")

        resultados.append({
            'atleta_id': atleta_id,
            'apelido': apelido,
            'clube_id': clube_id,
            'clube_nome': clube_nome,
            'pontuacao_total': pontuacao_total,
            'media': media,
            'preco': preco,
            'jogos': jogos,
            'peso_jogo': peso_jogo,
            'peso_sg': peso_sg,
            'peso_finalizacoes': peso_finalizacoes,
            'media_gols_adversario': media_gols_adversario
        })

    # Ordenar por pontuação total e pegar os top N
    melhores = sorted(resultados, key=lambda x: x['pontuacao_total'], reverse=True)[:top_n]

    # Imprimir resultados detalhados
    print("\nMelhores Goleiros:")
    print("-" * 100)
    print(f"{'Nome':<20} {'ID':<10} {'Clube':<20} {'Pontuação':<12} {'Média':<12} "
          f"{'Peso Jogo':<12} {'Peso SG':<12} {'Finalizações':<12} {'Gols Adv':<12}")
    print("-" * 100)
    for goleiro in melhores:
        print(f"{goleiro['apelido']:<20} {goleiro['atleta_id']:<10} {goleiro['clube_nome']:<20} "
              f"{goleiro['pontuacao_total']:<12.2f} {goleiro['media']:<12.2f} "
              f"{goleiro['peso_jogo']:<12.2f} {goleiro['peso_sg']:<12.2f} "
              f"{goleiro['peso_finalizacoes']:<12.2f} {goleiro['media_gols_adversario']:<12.2f}")
    print("-" * 100)

    # Salvar na tabela ranking_por_posicao
    from main import update_ranking_por_posicao
    update_ranking_por_posicao(conn, melhores, 1, rodada_atual)
    printdbg(f"Ranking de goleiros salvo na tabela ranking_por_posicao")
    
    close_db_connection(conn)
    return melhores

def main():
    # Obter a rodada atual
    status_data = fetch_status_data()
    if not status_data:
        printdbg("Erro ao obter dados de status.")
        return
    rodada_atual = status_data['rodada_atual']

    melhores_goleiros = calcular_melhores_goleiros(top_n=20, rodada_atual=rodada_atual, usar_provaveis_cartola=True)
    printdbg(f"Top {len(melhores_goleiros)} goleiros calculados com sucesso.")

if __name__ == "__main__":
    main()
