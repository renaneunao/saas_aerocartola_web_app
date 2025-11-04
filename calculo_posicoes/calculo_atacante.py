import sys
from pathlib import Path

# Ensure project root is on sys.path when running this file directly
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from database import get_db_connection, close_db_connection
from utils.utilidades import printdbg
from api_cartola import fetch_status_data
import math
from utils.weights import get_weight

# Fatores multiplicadores
DEFAULTS = {
    'FATOR_MEDIA': 2.5,
    'FATOR_DS': 2.0,
    'FATOR_FF': 1.2,
    'FATOR_FS': 1.3,
    'FATOR_FD': 1.3,
    'FATOR_G': 2.5,
    'FATOR_A': 2.5,
    'FATOR_ESCALACAO': 10.0,
    'FATOR_PESO_JOGO': 10.0,
}

# Função para carregar pesos dinamicamente
def _load_weights():
    """Carrega os pesos do banco de dados a cada execução."""
    return {
        'FATOR_MEDIA': float(get_weight('atacante', 'FATOR_MEDIA', DEFAULTS['FATOR_MEDIA'])),
        'FATOR_DS': float(get_weight('atacante', 'FATOR_DS', DEFAULTS['FATOR_DS'])),
        'FATOR_FF': float(get_weight('atacante', 'FATOR_FF', DEFAULTS['FATOR_FF'])),
        'FATOR_FS': float(get_weight('atacante', 'FATOR_FS', DEFAULTS['FATOR_FS'])),
        'FATOR_FD': float(get_weight('atacante', 'FATOR_FD', DEFAULTS['FATOR_FD'])),
        'FATOR_G': float(get_weight('atacante', 'FATOR_G', DEFAULTS['FATOR_G'])),
        'FATOR_A': float(get_weight('atacante', 'FATOR_A', DEFAULTS['FATOR_A'])),
        'FATOR_ESCALACAO': float(get_weight('atacante', 'FATOR_ESCALACAO', DEFAULTS['FATOR_ESCALACAO'])),
        'FATOR_PESO_JOGO': float(get_weight('atacante', 'FATOR_PESO_JOGO', DEFAULTS['FATOR_PESO_JOGO']))
    }

def calcular_melhores_atacantes(top_n=20, rodada_atual=None, min_jogos_pref=3, rodada_min_jogos=8, usar_provaveis_cartola=None):
    # Carregar pesos dinamicamente a cada execução
    weights = _load_weights()
    FATOR_MEDIA = weights['FATOR_MEDIA']
    FATOR_DS = weights['FATOR_DS']
    FATOR_FF = weights['FATOR_FF']
    FATOR_FS = weights['FATOR_FS']
    FATOR_FD = weights['FATOR_FD']
    FATOR_G = weights['FATOR_G']
    FATOR_A = weights['FATOR_A']
    FATOR_ESCALACAO = weights['FATOR_ESCALACAO']
    FATOR_PESO_JOGO = weights['FATOR_PESO_JOGO']
    
    # Log dos pesos carregados
    printdbg(f"[PESOS ATACANTE] FATOR_MEDIA: {FATOR_MEDIA} (padrão: {DEFAULTS['FATOR_MEDIA']})")
    printdbg(f"[PESOS ATACANTE] FATOR_DS: {FATOR_DS} (padrão: {DEFAULTS['FATOR_DS']})")
    printdbg(f"[PESOS ATACANTE] FATOR_FF: {FATOR_FF} (padrão: {DEFAULTS['FATOR_FF']})")
    printdbg(f"[PESOS ATACANTE] FATOR_FS: {FATOR_FS} (padrão: {DEFAULTS['FATOR_FS']})")
    printdbg(f"[PESOS ATACANTE] FATOR_FD: {FATOR_FD} (padrão: {DEFAULTS['FATOR_FD']})")
    printdbg(f"[PESOS ATACANTE] FATOR_G: {FATOR_G} (padrão: {DEFAULTS['FATOR_G']})")
    printdbg(f"[PESOS ATACANTE] FATOR_A: {FATOR_A} (padrão: {DEFAULTS['FATOR_A']})")
    printdbg(f"[PESOS ATACANTE] FATOR_ESCALACAO: {FATOR_ESCALACAO} (padrão: {DEFAULTS['FATOR_ESCALACAO']})")
    printdbg(f"[PESOS ATACANTE] FATOR_PESO_JOGO: {FATOR_PESO_JOGO} (padrão: {DEFAULTS['FATOR_PESO_JOGO']})")
    
    conn = get_db_connection()
    cursor = conn.cursor()

    # Define minimum games based on round
    min_jogos = min_jogos_pref if rodada_atual >= rodada_min_jogos else 1

    # Filtrar atacantes (posicao_id = 5) com jogos
    if usar_provaveis_cartola:
        # Usando dados do Joga 10 para jogadores prováveis
        printdbg("Usando dados do Joga 10 para jogadores prováveis")
        cursor.execute('''
            SELECT a.atleta_id, a.apelido, a.clube_id, a.pontos_num, a.media_num, 
                   a.preco_num, a.jogos_num, a.peso_jogo, c.nome
            FROM acf_atletas a
            JOIN acf_clubes c ON a.clube_id = c.id
            JOIN provaveis_cartola p ON a.atleta_id = p.atleta_id
            WHERE a.posicao_id = 5 AND a.jogos_num >= %s AND p.status = 'provavel'
        ''', (min_jogos,))
    else:
        # Usando dados do Cartola para jogadores prováveis (status_id = 7)
        printdbg("Usando dados do Cartola para jogadores prováveis")
        cursor.execute('''
            SELECT a.atleta_id, a.apelido, a.clube_id, a.pontos_num, a.media_num, 
                   a.preco_num, a.jogos_num, a.peso_jogo, c.nome
            FROM acf_atletas a
            JOIN acf_clubes c ON a.clube_id = c.id
            WHERE a.posicao_id = 5 AND a.jogos_num >= %s AND a.status_id = 7
        ''', (min_jogos,))
    atacantes = cursor.fetchall()

    printdbg(f"Total de atacantes encontrados: {len(atacantes)}")

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
    for atacante in atacantes:
        atleta_id, apelido, clube_id, pontos, media, preco, jogos, peso_jogo, clube_nome = atacante

        printdbg(f"\nProcessando atacante: {apelido} (ID: {atleta_id}, Clube: {clube_nome})")
        printdbg(f"  Média: {media:.2f}, Peso Jogo (original): {peso_jogo if peso_jogo is not None else 'N/A'}")

        # Fator 1: Média do jogador
        pontos_media = media * FATOR_MEDIA
        printdbg(f"  Pontos Média: {pontos_media:.2f}")

        # Fator 2: Média de desarmes do atacante (scout_ds)
        cursor.execute('''
            SELECT AVG(p.scout_ds)
            FROM acf_pontuados p
            WHERE p.atleta_id = %s AND p.entrou_em_campo = TRUE AND p.rodada_id <= %s
        ''', (atleta_id, rodada_atual - 1))
        media_ds_result = cursor.fetchone()[0]
        media_ds = float(media_ds_result) if media_ds_result is not None else 0.0
        printdbg(f"  Média Desarmes Atacante: {media_ds:.2f}")

        # Fator 3: Média de finalizações para fora (scout_ff)
        cursor.execute('''
            SELECT AVG(p.scout_ff)
            FROM acf_pontuados p
            WHERE p.atleta_id = %s AND p.entrou_em_campo = TRUE AND p.rodada_id <= %s
        ''', (atleta_id, rodada_atual - 1))
        media_ff_result = cursor.fetchone()[0]
        media_ff = float(media_ff_result) if media_ff_result is not None else 0.0
        printdbg(f"  Média Finalizações Fora: {media_ff:.2f}")

        # Fator 4: Média de faltas sofridas (scout_fs)
        cursor.execute('''
            SELECT AVG(p.scout_fs)
            FROM acf_pontuados p
            WHERE p.atleta_id = %s AND p.entrou_em_campo = TRUE AND p.rodada_id <= %s
        ''', (atleta_id, rodada_atual - 1))
        media_fs_result = cursor.fetchone()[0]
        media_fs = float(media_fs_result) if media_fs_result is not None else 0.0
        printdbg(f"  Média Faltas Sofridas: {media_fs:.2f}")

        # Fator 5: Média de finalizações defendidas (scout_fd)
        cursor.execute('''
            SELECT AVG(p.scout_fd)
            FROM acf_pontuados p
            WHERE p.atleta_id = %s AND p.entrou_em_campo = TRUE AND p.rodada_id <= %s
        ''', (atleta_id, rodada_atual - 1))
        media_fd_result = cursor.fetchone()[0]
        media_fd = float(media_fd_result) if media_fd_result is not None else 0.0
        printdbg(f"  Média Finalizações Defendidas: {media_fd:.2f}")

        # Fator 6: Média de gols (scout_g)
        cursor.execute('''
            SELECT AVG(p.scout_g)
            FROM acf_pontuados p
            WHERE p.atleta_id = %s AND p.entrou_em_campo = TRUE AND p.rodada_id <= %s
        ''', (atleta_id, rodada_atual - 1))
        media_g_result = cursor.fetchone()[0]
        media_g = float(media_g_result) if media_g_result is not None else 0.0
        printdbg(f"  Média Gols: {media_g:.2f}")

        # Fator 7: Média de assistências (scout_a)
        cursor.execute('''
            SELECT AVG(p.scout_a)
            FROM acf_pontuados p
            WHERE p.atleta_id = %s AND p.entrou_em_campo = TRUE AND p.rodada_id <= %s
        ''', (atleta_id, rodada_atual - 1))
        media_a_result = cursor.fetchone()[0]
        media_a = float(media_a_result) if media_a_result is not None else 0.0
        printdbg(f"  Média Assistências: {media_a:.2f}")

        # Default values if weights are missing
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

            # Calcular média de desarmes cedidos pelo adversário a atacantes
            cursor.execute('''
                SELECT AVG(p.scout_ds)
                FROM acf_pontuados p
                JOIN acf_partidas pt ON p.rodada_id = pt.rodada_id AND 
                    ((pt.clube_casa_id = %s AND p.clube_id = pt.clube_visitante_id) OR 
                     (pt.clube_visitante_id = %s AND p.clube_id = pt.clube_casa_id))
                WHERE p.posicao_id = 5 AND p.entrou_em_campo = TRUE AND p.rodada_id <= %s
            ''', (adversario_id, adversario_id, rodada_atual - 1))
            media_ds_cedidos_result = cursor.fetchone()[0]
            media_ds_cedidos = float(media_ds_cedidos_result) if media_ds_cedidos_result is not None else 0.0
            printdbg(f"  Média Desarmes Cedidos pelo Adversário: {media_ds_cedidos:.2f}")
        else:
            printdbg("  Nenhuma partida encontrada para este atacante na rodada atual. Usando peso_jogo = 0 e media_ds_cedidos = 0.")
            peso_jogo = 0

        # Calcular contribuição dos desarmes (produto de media_ds e media_ds_cedidos)
        pontos_ds = media_ds * media_ds_cedidos * FATOR_DS
        printdbg(f"  Pontos Desarmes: {media_ds:.2f} * {media_ds_cedidos:.2f} * {FATOR_DS} = {pontos_ds:.2f}")

        # Calcular contribuição dos scouts ofensivos
        pontos_ff = media_ff * FATOR_FF
        pontos_fs = media_fs * FATOR_FS
        pontos_fd = media_fd * FATOR_FD
        pontos_g = media_g * FATOR_G
        pontos_a = media_a * FATOR_A
        printdbg(f"  Pontos FF: {media_ff:.2f} * {FATOR_FF} = {pontos_ff:.2f}")
        printdbg(f"  Pontos FS: {media_fs:.2f} * {FATOR_FS} = {pontos_fs:.2f}")
        printdbg(f"  Pontos FD: {media_fd:.2f} * {FATOR_FD} = {pontos_fd:.2f}")
        printdbg(f"  Pontos G: {media_g:.2f} * {FATOR_G} = {pontos_g:.2f}")
        printdbg(f"  Pontos A: {media_a:.2f} * {FATOR_A} = {pontos_a:.2f}")

        # Calcular pontuação base
        base_pontuacao = (pontos_media + peso_jogo + pontos_ds +
                          pontos_ff + pontos_fs + pontos_fd + pontos_g + pontos_a)
        pontuacao_total = base_pontuacao  # Sem FATOR_SG para atacantes
        printdbg(f"  Pontuação Base: ({pontos_media:.2f} (média) + {peso_jogo:.2f} (jogo) + "
                 f"{pontos_ds:.2f} (desarmes) + {pontos_ff:.2f} (FF) + {pontos_fs:.2f} (FS) + "
                 f"{pontos_fd:.2f} (FD) + {pontos_g:.2f} (G) + {pontos_a:.2f} (A)) = {pontuacao_total:.2f}")

        # Calcular peso de escalação
        escalacoes = escalacoes_por_atleta.get(atleta_id, 0)
        percentual_escalacoes = escalacoes / total_escalacoes_top if total_escalacoes_top > 0 else 0
        peso_escalacao = 1 + percentual_escalacoes * FATOR_ESCALACAO
        printdbg(f"  Escalções: {escalacoes}, Percentual: {percentual_escalacoes:.4f}, Peso Escalação: {peso_escalacao:.4f}")

        # Ajustar pontuação final: primeiro raiz, depois multiplica pelo peso
        if pontuacao_total < 0:
            printdbg(f"  Aviso: Pontuação total negativa ({pontuacao_total}). Ajustando para 0 antes da raiz.")
            pontuacao_total = 0

        pontuacao_total_final = math.sqrt(pontuacao_total) * peso_escalacao

        if pontuacao_total_final < 0:  # Verificação adicional (caso peso_escalacao seja negativo)
            printdbg(f"  Aviso: Pontuação final negativa ({pontuacao_total_final}). Ajustando para 0.")
            pontuacao_total_final = 0

        printdbg(f"  Pontuação Final: sqrt({pontuacao_total:.2f}) * {peso_escalacao:.4f} = {pontuacao_total_final:.2f}")

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
            'media_ds': media_ds,
            'media_ds_cedidos': media_ds_cedidos,
            'media_ff': media_ff,
            'media_fs': media_fs,
            'media_fd': media_fd,
            'media_g': media_g,
            'media_a': media_a,
            'adversario_nome': adversario_nome,
            'peso_escalacao': peso_escalacao
        })

    # Ordenar por pontuação total e pegar os top N
    melhores = sorted(resultados, key=lambda x: x['pontuacao_total'], reverse=True)[:top_n]

    # Imprimir resultados detalhados
    print("\nMelhores Atacantes:")
    print("-" * 230)
    print(f"{'Nome':<20} {'ID':<10} {'Clube':<20} {'Adversário':<20} {'Pontuação':<12} {'Média':<12} "
          f"{'Peso Jogo':<12} {'Média DS':<12} {'DS Cedidos':<12} {'Média FF':<12} "
          f"{'Média FS':<12} {'Média FD':<12} {'Média G':<12} {'Média A':<12} {'Peso Esc':<12}")
    print("-" * 230)
    for atacante in melhores:
        print(f"{atacante['apelido']:<20} {atacante['atleta_id']:<10} {atacante['clube_nome']:<20} "
              f"{atacante['adversario_nome']:<20} {atacante['pontuacao_total']:<12.2f} {atacante['media']:<12.2f} "
              f"{atacante['peso_jogo']:<12.2f} {atacante['media_ds']:<12.2f} {atacante['media_ds_cedidos']:<12.2f} "
              f"{atacante['media_ff']:<12.2f} {atacante['media_fs']:<12.2f} {atacante['media_fd']:<12.2f} "
              f"{atacante['media_g']:<12.2f} {atacante['media_a']:<12.2f} {atacante['peso_escalacao']:<12.4f}")
    print("-" * 230)

    # Salvar na tabela ranking_por_posicao
    from main import update_ranking_por_posicao
    update_ranking_por_posicao(conn, melhores, 5, rodada_atual)
    printdbg(f"Ranking de atacantes salvo na tabela ranking_por_posicao")
    
    close_db_connection(conn)
    return melhores

def main():
    # Obter a rodada atual
    status_data = fetch_status_data()
    if not status_data:
        printdbg("Erro ao obter dados de status.")
        return
    rodada_atual = status_data['rodada_atual']
    print(rodada_atual)

    melhores_atacantes = calcular_melhores_atacantes(top_n=20, rodada_atual=rodada_atual, min_jogos_pref=2, usar_provaveis_cartola=False)
    printdbg(f"Top {len(melhores_atacantes)} atacantes calculados com sucesso.")

if __name__ == "__main__":
    main()