from database import get_db_connection, close_db_connection
from utils.utilidades import printdbg
import math
from api_cartola import fetch_status_data
from utils.weights import get_weight

# Função para carregar pesos dinamicamente
def _load_weights():
    """Carrega os pesos do banco de dados a cada execução."""
    return {
        'FATOR_PESO_JOGO': float(get_weight('treinador', 'FATOR_PESO_JOGO', 1.0))
    }


def calcular_melhores_treinadores(rodada_atual, top_n=100, usar_provaveis_cartola=None):
    # Carregar pesos dinamicamente a cada execução
    weights = _load_weights()
    FATOR_PESO_JOGO = weights['FATOR_PESO_JOGO']
    
    # Log dos pesos carregados
    printdbg(f"[PESOS TREINADOR] FATOR_PESO_JOGO: {FATOR_PESO_JOGO} (padrão: 1.0)")
    
    conn = get_db_connection()
    cursor = conn.cursor()

    # Filtrar treinadores (posicao_id = 6) com jogos e status Provável, obtendo nome do clube
    # NOTA: Para técnicos, sempre usamos status_id = 7 (Cartola) pois a API provaveis_cartola não tem dados de técnicos
    cursor.execute('''
        SELECT a.atleta_id, a.apelido, c.nome, a.pontos_num, a.media_num, a.preco_num, a.jogos_num, 
               a.peso_jogo, a.peso_sg, a.clube_id
        FROM acf_atletas a
        JOIN acf_clubes c ON a.clube_id = c.id
        WHERE a.posicao_id = 6 AND a.jogos_num > 0 AND a.status_id = 7
    ''')
    treinadores = cursor.fetchall()

    printdbg(f"Total de treinadores encontrados: {len(treinadores)}")

    # Calcular pontuação total
    resultados = []
    for treinador in treinadores:
        atleta_id, apelido, clube_nome, pontos, media, preco, jogos, peso_jogo, peso_sg, clube_id = treinador

        printdbg(f"\nProcessando treinador: {apelido} (ID: {atleta_id}, Clube: {clube_nome})")
        printdbg(f"  Peso Jogo (original): {peso_jogo if peso_jogo is not None else 'N/A'}")
        printdbg(f"  Peso SG: {peso_sg if peso_sg is not None else 'N/A'}")

        # Default values if weights are missing
        peso_sg = peso_sg if peso_sg is not None else 0

        # Encontrar o adversário na rodada atual
        cursor.execute('''
            SELECT p.clube_casa_id, p.clube_visitante_id
            FROM acf_partidas p
            WHERE p.rodada_id = %s AND p.valida = TRUE AND 
                  (p.clube_casa_id = %s OR p.clube_visitante_id = %s)
        ''', (rodada_atual, clube_id, clube_id))
        partida = cursor.fetchone()

        peso_sg_adversario = 0
        if partida:
            clube_casa_id, clube_visitante_id = partida
            adversario_id = clube_visitante_id if clube_id == clube_casa_id else clube_casa_id
            printdbg(f"  Partida encontrada: Clube {clube_nome} vs Adversário ID {adversario_id}")

            # Obter peso_sg do adversário
            cursor.execute('''
                SELECT AVG(a.peso_sg)
                FROM acf_atletas a
                WHERE a.clube_id = %s AND a.posicao_id IN (1, 2, 3) AND a.status_id = 7
            ''', (adversario_id,))
            peso_sg_adversario_result = cursor.fetchone()[0]
            peso_sg_adversario = float(peso_sg_adversario_result) if peso_sg_adversario_result is not None else 0.0
            printdbg(f"  Peso SG Adversário (média): {peso_sg_adversario:.2f}")
        else:
            printdbg("  Nenhuma partida encontrada para este treinador na rodada atual. Usando peso_sg_adversario = 0.")
            peso_jogo = 0

        # Calcular pontuação total (apenas peso de jogo)
        pontuacao_total = peso_jogo * FATOR_PESO_JOGO
        printdbg(f"  Cálculo: {peso_jogo:.2f} * {FATOR_PESO_JOGO:.2f} = {pontuacao_total:.2f}")

        resultados.append({
            'atleta_id': atleta_id,
            'apelido': apelido,
            'clube_nome': clube_nome,
            'clube_id': clube_id,  # Adicionado para compatibilidade com update_ranking_por_posicao
            'pontuacao_total': pontuacao_total,
            'media': media,
            'preco': preco,
            'jogos': jogos,
            'peso_jogo': peso_jogo,
            'peso_sg': peso_sg,
            'peso_sg_adversario': peso_sg_adversario
        })

    # Ordenar por pontuação total e pegar os top N
    melhores = sorted(resultados, key=lambda x: x['pontuacao_total'], reverse=True)[:top_n]

    # Imprimir resultados detalhados
    print("\nMelhores Treinadores (Ordenados por Peso de Jogo):")
    print("-" * 70)
    print(f"{'Nome':<20} {'ID':<10} {'Clube':<20} {'Pontuação':<12} {'Peso Jogo':<12}")
    print("-" * 70)
    for treinador in melhores:
        print(f"{treinador['apelido']:<20} {treinador['atleta_id']:<10} {treinador['clube_nome']:<20} {treinador['pontuacao_total']:<12.2f} {treinador['peso_jogo']:<12.2f}")
    print("-" * 70)

    # Salvar na tabela ranking_por_posicao
    from main import update_ranking_por_posicao
    update_ranking_por_posicao(conn, melhores, 6, rodada_atual)
    printdbg(f"Ranking de treinadores salvo na tabela ranking_por_posicao")
    
    close_db_connection(conn)
    return melhores

def main():
    # Obter a rodada atual
    status_data = fetch_status_data()
    if not status_data:
        printdbg("Erro ao obter dados de status.")
        return
    rodada_atual = status_data['rodada_atual']

    melhores_treinadores = calcular_melhores_treinadores(rodada_atual)
    printdbg(f"Top {len(melhores_treinadores)} treinadores calculados com sucesso.")

if __name__ == "__main__":
    main()