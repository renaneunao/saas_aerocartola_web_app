"""
ATENÇÃO: Este arquivo é apenas uma REFERÊNCIA e NÃO é mais usado pela aplicação.

O cálculo da escalação ideal agora é feito completamente em JavaScript no frontend.
Ver: static/js/calculo_escalacao_ideal.js

Este arquivo foi mantido apenas como referência de lógica, mas não deve ser executado.
"""

from database import get_db_connection, close_db_connection
from utils.utilidades import printdbg, is_debug
from api_cartola import fetch_status_data, fetch_team_data, salvar_time_no_cartola
from itertools import combinations, product
from threading import Thread
from models.credenciais import get_all_credenciais

# Definir top_n para busca de candidatos nas combinações
top_n = 10  # Número de candidatos para atacantes, laterais, meias
top_n_reduzido = top_n // 2  # Número de candidatos para goleiros, técnicos, zagueiros (5)

def fetch_melhores_jogadores_por_posicao(conn, posicao_id, quantidade, rodada_atual, max_preco=None, is_reserva=False,
                                         escalados_ids=None, usar_provaveis_cartola=True):
    """
    Consulta a tabela 'ranking_por_posicao' e 'atletas' para obter os melhores jogadores de uma posição, incluindo preço.
    Args:
        conn: Conexão com o banco de dados.
        posicao_id: ID da posição.
        quantidade: Número de jogadores a retornar.
        rodada_atual: Rodada atual.
        max_preco: Preço máximo permitido (usado para reservas).
        is_reserva: Se True, busca apenas 1 jogador com preço <= max_preco.
        escalados_ids: Lista de atleta_id já escalados (para evitar duplicatas).
    """
    printdbg(
        f"Buscando {quantidade} {'reservas' if is_reserva else 'titulares'} para posicao_id {posicao_id} na rodada {rodada_atual}")
    cursor = conn.cursor()
    # Filtrar por jogadores prováveis - usar nova API ou Cartola dependendo do parâmetro
    # EXCEÇÃO: Técnicos (posição 6) sempre usam status_id = 7 pois não estão na nova API
    if usar_provaveis_cartola and posicao_id != 6:
        query = '''
            SELECT r.atleta_id, r.apelido, r.clube_id, r.pontuacao_total, a.preco_num
            FROM ranking_por_posicao r
            JOIN acf_atletas a ON r.atleta_id = a.atleta_id
            JOIN provaveis_cartola pc ON r.atleta_id = pc.atleta_id
            WHERE r.posicao_id = %s AND r.rodada_atual = %s AND pc.status = 'provavel'
        '''
    else:
        query = '''
            SELECT r.atleta_id, r.apelido, r.clube_id, r.pontuacao_total, a.preco_num
            FROM ranking_por_posicao r
            JOIN acf_atletas a ON r.atleta_id = a.atleta_id
            WHERE r.posicao_id = %s AND r.rodada_atual = %s AND a.status_id = 7
        '''
    params = [posicao_id, rodada_atual]

    if max_preco is not None:
        query += ' AND a.preco_num <= %s'
        params.append(max_preco)

    if escalados_ids:
        query += ' AND r.atleta_id NOT IN ({})'.format(','.join(['%s'] * len(escalados_ids)))
        params.extend(escalados_ids)

    query += ' ORDER BY r.pontuacao_total DESC LIMIT %s'
    params.append(quantidade)

    cursor.execute(query, params)
    jogadores = cursor.fetchall()
    printdbg(f"Encontrados {len(jogadores)} {'reservas' if is_reserva else 'titulares'} para posicao_id {posicao_id}")
    return [
        {
            'atleta_id': jogador[0],
            'apelido': jogador[1],
            'clube_id': jogador[2],
            'pontuacao_total': jogador[3],
            'preco_num': jogador[4]
        } for jogador in jogadores
    ]

def calcular_escalacao_ideal(rodada_atual, posicao_capitao='atacantes', access_token=None, env_key="ACCESS_TOKEN", nome_time="Time", estrategia: int = 1, usar_provaveis_cartola=True):
    """
    Calcula a escalação ideal para a formação 4-3-3, considerando preços, orçamento e prioridades.
    A posição do capitão também define a posição do reserva de luxo.
    Escala posições na ordem: atacantes, laterais, meias, zagueiros, goleiros, técnicos.
    Args:
        rodada_atual: Rodada atual do Cartola FC.
        posicao_capitao: Posição do capitão e reserva de luxo (padrão: 'atacantes').
        access_token: Token de autenticação para o time específico.
        env_key: Nome da variável no .env que armazena o token (ex.: ACCESS_TOKEN_TIME1).
        nome_time: Nome do time para exibição na pergunta de escalação.
    Returns:
        Dicionário com os dados da escalação para a API do Cartola.
    """
    printdbg(f"Iniciando cálculo da escalação ideal para {nome_time} com capitão e reserva de luxo na posição: {posicao_capitao}, env_key={env_key}, estrategia={estrategia}")
    if not access_token:
        printdbg(f"Erro: Nenhum access_token fornecido para o time associado a {env_key}")
        return None

    conn = get_db_connection()

    # Confirmação automática desativada: vamos enviar diretamente sem prompt

    # Verificar status do mercado
    status_data = fetch_status_data()
    if status_data:
        printdbg(f"Status do mercado: {status_data.get('status_mercado', 'Desconhecido')}")
        printdbg(f"Rodada atual: {status_data.get('rodada_atual', rodada_atual)}")
        if status_data.get('status_mercado') == 2:
            printdbg(f"Mercado fechado para a rodada {rodada_atual}. Escalação não enviada.")
            close_db_connection(conn)
            return None
    else:
        printdbg("Aviso: Não foi possível obter o status do mercado.")

    # Obter patrimônio do time
    printdbg("Chamando fetch_team_data para obter patrimônio")
    team_data, updated_token = fetch_team_data(access_token=access_token, env_key=env_key)
    if not team_data:
        printdbg("Erro ao obter dados do time.")
        close_db_connection(conn)
        return None
    patrimonio = team_data.get('patrimonio', 0)
    printdbg(f"Orçamento disponível: {patrimonio:.2f} cartoletas")

    # Definir a formação 4-3-3
    formacao = {
        'nome': '4-3-3',
        'qt_goleiro': 1,
        'qt_zagueiro': 2,
        'qt_lateral': 2,
        'qt_meia': 3,
        'qt_atacante': 3,
        'qt_tecnico': 1
    }
    printdbg("Formação definida: 4-3-3")

    # Prioridades das posições para escalação
    prioridades = ['atacantes', 'laterais', 'meias', 'zagueiros', 'goleiros', 'tecnicos']
    # Ordem de desescalação (inversa das prioridades)
    ordem_desescalacao = prioridades[::-1]  # ['tecnicos', 'goleiros', 'zagueiros', 'meias', 'laterais', 'atacantes']
    posicao_ids = {'goleiros': 1, 'zagueiros': 3, 'laterais': 2, 'meias': 4, 'atacantes': 5, 'tecnicos': 6}

    # Mapeamento de plural para singular
    plural_to_singular = {
        'goleiros': 'goleiro',
        'zagueiros': 'zagueiro',
        'laterais': 'lateral',
        'meias': 'meia',
        'atacantes': 'atacante',
        'tecnicos': 'tecnico'
    }

    def try_escalacao(posicoes_desescaladas=None):
        if posicoes_desescaladas is None:
            posicoes_desescaladas = []
        escalacao = {
            'titulares': {pos: [] for pos in posicao_ids.keys()},
            'reservas': {pos: [] for pos in posicao_ids.keys() if pos != 'tecnicos'},
            'custo_total': 0,
            'pontuacao_total': 0
        }
        escalados_ids = []  # Lista de atleta_id já escalados
        printdbg(f"Estrutura de escalação inicializada. Posições desescaladas: {posicoes_desescaladas}")

        # Estratégia 2: fechar defesa antes (goleiro, zagueiros, laterais)
        predefinido_defesa = { 'goleiros': [], 'zagueiros': [], 'laterais': [] }
        if estrategia == 2:
            cursor = conn.cursor()
            # clubes com maior peso_sg (valor único por clube) - buscar da tabela de perfis
            # Usar perfil 2 como padrão (padrão do sistema)
            perfil_peso_sg_padrao = 2
            cursor.execute('''
                SELECT clube_id, peso_sg as club_sg
                FROM acp_peso_sg_perfis
                WHERE perfil_id = %s AND rodada_atual = %s
                ORDER BY peso_sg DESC
            ''', (perfil_peso_sg_padrao, rodada_atual))
            clubes_rank = cursor.fetchall()

            # Mostrar um resumo claro da escolha do melhor SG (sempre visível)
            try:
                top_preview = clubes_rank[:6]
                printdbg("\nResumo SG (estratégia defesa) - Top clubes por SG da rodada:")
                printdbg("clube_id   SG")
                for row in top_preview:
                    # row pode ser tupla (clube_id, club_sg) ou dict-like, dependendo do cursor
                    cid = row[0] if isinstance(row, (tuple, list)) else row['clube_id']
                    sgv = row[1] if isinstance(row, (tuple, list)) else row.get('club_sg')
                    printdbg(f"{cid:<9} {sgv:.2f}")
                if top_preview:
                    cid0 = top_preview[0][0] if isinstance(top_preview[0], (tuple, list)) else top_preview[0]['clube_id']
                    sgv0 = top_preview[0][1] if isinstance(top_preview[0], (tuple, list)) else top_preview[0].get('club_sg')
                    printdbg(f"Avaliando primeiro clube por SG: {cid0} (SG={sgv0:.2f})\n")
            except Exception:
                pass

            def fetch_by_clube_pos(pos_id: int, clube_id: int, limit: int):
                # Busca somente jogadores PROVÁVEIS do clube/posição
                # 1) Prioriza ranking_por_posicao (melhor sinal de pontuação prevista)
                # EXCEÇÃO: Técnicos (posição 6) sempre usam status_id = 7 pois não estão na nova API
                if usar_provaveis_cartola and pos_id != 6:
                    q = '''
                        SELECT r.atleta_id, r.apelido, r.clube_id, r.pontuacao_total, a.preco_num
                        FROM ranking_por_posicao r
                        JOIN acf_atletas a ON r.atleta_id = a.atleta_id
                        JOIN provaveis_cartola pc ON r.atleta_id = pc.atleta_id
                        WHERE r.posicao_id = %s AND r.rodada_atual = %s AND r.clube_id = %s AND pc.status = 'provavel'
                        ORDER BY r.pontuacao_total DESC
                        LIMIT %s
                    '''
                else:
                    q = '''
                        SELECT r.atleta_id, r.apelido, r.clube_id, r.pontuacao_total, a.preco_num
                        FROM ranking_por_posicao r
                        JOIN acf_atletas a ON r.atleta_id = a.atleta_id
                        WHERE r.posicao_id = %s AND r.rodada_atual = %s AND r.clube_id = %s AND a.status_id = 7
                        ORDER BY r.pontuacao_total DESC
                        LIMIT %s
                    '''
                cursor.execute(q, (pos_id, rodada_atual, clube_id, limit))
                rows = cursor.fetchall()
                lista = [
                    {'atleta_id': x[0], 'apelido': x[1], 'clube_id': x[2], 'pontuacao_total': x[3], 'preco_num': x[4]}
                    for x in rows
                ]
                faltam = max(0, limit - len(lista))
                if faltam > 0:
                    # 2) Completa com jogadores prováveis (mais baratos primeiro),
                    # ainda restrito a 'provavel', excluindo já selecionados. pontuacao_total=0 como fallback.
                    # EXCEÇÃO: Técnicos (posição 6) sempre usam status_id = 7 pois não estão na nova API
                    excl = tuple(j['atleta_id'] for j in lista) or (-1,)
                    if usar_provaveis_cartola and pos_id != 6:
                        q2 = f'''
                            SELECT a.atleta_id, a.apelido, a.clube_id, a.preco_num
                            FROM acf_atletas a
                            JOIN provaveis_cartola pc ON a.atleta_id = pc.atleta_id
                            WHERE a.posicao_id = %s AND a.clube_id = %s AND pc.status = 'provavel' AND a.atleta_id NOT IN ({','.join(['%s'] * len(excl))})
                            ORDER BY a.preco_num ASC
                            LIMIT %s
                        '''
                    else:
                        q2 = f'''
                            SELECT a.atleta_id, a.apelido, a.clube_id, a.preco_num
                            FROM acf_atletas a
                            WHERE a.posicao_id = %s AND a.clube_id = %s AND a.status_id = 7 AND a.atleta_id NOT IN ({','.join(['%s'] * len(excl))})
                            ORDER BY a.preco_num ASC
                            LIMIT %s
                        '''
                    params = [pos_id, clube_id, *excl, faltam]
                    cursor.execute(q2, params)
                    for aid, apelido, cid, preco in cursor.fetchall():
                        lista.append({'atleta_id': aid, 'apelido': apelido, 'clube_id': cid, 'pontuacao_total': 0.0, 'preco_num': preco})
                try:
                    if lista:
                        mn = min(x['preco_num'] for x in lista)
                        mx = max(x['preco_num'] for x in lista)
                        printdbg(f"Candidatos clube {clube_id} pos {pos_id}: {len(lista)} (preço min={mn:.2f}, max={mx:.2f})")
                except Exception:
                    pass
                return lista

            chosen = None
            # Fechar defesa do melhor clube por SG imediatamente (sem testar outros clubes)
            if clubes_rank:
                top_clube_id = clubes_rank[0][0] if isinstance(clubes_rank[0], (tuple, list)) else clubes_rank[0]['clube_id']
                try:
                    printdbg(f"Fechando defesa do clube_id {top_clube_id} (melhor SG da rodada)...")
                except Exception:
                    pass
                gks = fetch_by_clube_pos(posicao_ids['goleiros'], top_clube_id, 5)
                zgs = fetch_by_clube_pos(posicao_ids['zagueiros'], top_clube_id, 8)
                lts = fetch_by_clube_pos(posicao_ids['laterais'], top_clube_id, 8)
                # Só fecha a defesa se houver prováveis suficientes para o clube (1 GK, 2 ZAG, 2 LAT)
                if gks and len(zgs) >= 2 and len(lts) >= 2:
                    # Diagnóstico: patrimônio e custo mínimo possível desta defesa
                    try:
                        min_gk = min(gks, key=lambda x: x['preco_num'])
                        min_zgs = sorted(zgs, key=lambda x: x['preco_num'])[:2]
                        min_lts = sorted(lts, key=lambda x: x['preco_num'])[:2]
                        min_cost = min_gk['preco_num'] + sum(j['preco_num'] for j in min_zgs) + sum(j['preco_num'] for j in min_lts)
                        printdbg(f"Patrimônio disponível: R${patrimonio:.2f} | Custo mínimo possível da defesa do clube {top_clube_id}: R${min_cost:.2f}")
                    except Exception:
                        pass
                    best_combo = None
                    best_score = -1
                    # procurar a melhor combinação dentro do próprio clube para caber no orçamento
                    for gk in gks:
                        for zcomb in combinations(zgs[:8], 2):
                            for lcomb in combinations(lts[:8], 2):
                                jogadores = [gk] + list(zcomb) + list(lcomb)
                                custo = sum(j['preco_num'] for j in jogadores)
                                if custo <= patrimonio:
                                    score = sum(j['pontuacao_total'] for j in jogadores)
                                    if score > best_score:
                                        best_score = score
                                        best_combo = jogadores
                    # Se não achou por score, tentar combo mais barato possível
                    if best_combo is None:
                        try:
                            cheapest_gk = min(gks, key=lambda x: x['preco_num'])
                            cheapest_z = sorted(zgs, key=lambda x: x['preco_num'])[:2]
                            cheapest_l = sorted(lts, key=lambda x: x['preco_num'])[:2]
                            cheap_combo = [cheapest_gk] + cheapest_z + cheapest_l
                            cheap_cost = sum(j['preco_num'] for j in cheap_combo)
                            if cheap_cost <= patrimonio:
                                best_combo = cheap_combo
                                best_score = sum(j.get('pontuacao_total', 0.0) for j in cheap_combo)
                                printdbg(f"Usando fallback: combinação mais barata cabe no orçamento (R${cheap_cost:.2f}).")
                        except Exception:
                            pass
                    if best_combo:
                        chosen = (top_clube_id, best_combo)
                    else:
                        # Não dá pra fechar com 5? Fecha com o MÁXIMO possível dentro do orçamento
                        try:
                            caps = { 'goleiros': 1, 'zagueiros': 2, 'laterais': 2 }
                            bucket = []
                            for j in gks:
                                bucket.append( ('goleiros', j['preco_num'], -j.get('pontuacao_total', 0.0), j) )
                            for j in zgs:
                                bucket.append( ('zagueiros', j['preco_num'], -j.get('pontuacao_total', 0.0), j) )
                            for j in lts:
                                bucket.append( ('laterais', j['preco_num'], -j.get('pontuacao_total', 0.0), j) )
                            # Ordena por preço crescente, depois melhor pontuação
                            bucket.sort(key=lambda t: (t[1], t[2]))
                            taken = { 'goleiros': 0, 'zagueiros': 0, 'laterais': 0 }
                            partial = []
                            partial_cost = 0.0
                            for pos, price, _neg_score, player in bucket:
                                if taken[pos] < caps[pos] and partial_cost + price <= patrimonio:
                                    partial.append(player)
                                    taken[pos] += 1
                                    partial_cost += price
                                    # Se já pegamos todos os 5, para
                                    if sum(taken.values()) >= 5:
                                        break
                            if partial:
                                printdbg(f"Fechando parcialmente a defesa do clube {top_clube_id}: {sum(taken.values())} jogadores (custo R${partial_cost:.2f})")
                                for pj in partial:
                                    printdbg(f"  - {pj['apelido']} (R${pj['preco_num']:.2f} - {pj.get('pontuacao_total', 0.0):.2f})")
                                chosen = (top_clube_id, partial)
                            else:
                                printdbg(f"Estratégia 2: Nenhum jogador do clube {top_clube_id} pôde ser travado dentro do orçamento.")
                        except Exception:
                            pass
                else:
                    # Não há prováveis suficientes para fechar com 5, mas vamos travar o MÁXIMO possível
                    try:
                        printdbg(f"Estratégia 2: Clube {top_clube_id} não possui prováveis suficientes para fechar defesa completa. Tentando fechar PARCIALMENTE.")
                        caps = {
                            'goleiros': 1 if len(gks) >= 1 else 0,
                            'zagueiros': min(2, len(zgs)),
                            'laterais': min(2, len(lts)),
                        }
                        bucket = []
                        for j in gks:
                            bucket.append(('goleiros', j['preco_num'], -j.get('pontuacao_total', 0.0), j))
                        for j in zgs:
                            bucket.append(('zagueiros', j['preco_num'], -j.get('pontuacao_total', 0.0), j))
                        for j in lts:
                            bucket.append(('laterais', j['preco_num'], -j.get('pontuacao_total', 0.0), j))
                        bucket.sort(key=lambda t: (t[1], t[2]))
                        taken = { 'goleiros': 0, 'zagueiros': 0, 'laterais': 0 }
                        partial = []
                        partial_cost = 0.0
                        max_needed = caps['goleiros'] + caps['zagueiros'] + caps['laterais']
                        for pos, price, _neg_score, player in bucket:
                            if caps[pos] == 0:
                                continue
                            if taken[pos] < caps[pos] and partial_cost + price <= patrimonio:
                                partial.append(player)
                                taken[pos] += 1
                                partial_cost += price
                                if sum(taken.values()) >= max_needed:
                                    break
                        if partial:
                            printdbg(f"Fechando parcialmente a defesa do clube {top_clube_id}: {sum(taken.values())} jogadores (custo R${partial_cost:.2f})")
                            for pj in partial:
                                printdbg(f"  - {pj['apelido']} (R${pj['preco_num']:.2f} - {pj.get('pontuacao_total', 0.0):.2f})")
                            chosen = (top_clube_id, partial)
                        else:
                            printdbg(f"Estratégia 2: Nenhum jogador do clube {top_clube_id} pôde ser travado dentro do orçamento.")
                    except Exception:
                        pass

            if chosen:
                clube_escolhido, jogadores_escolhidos = chosen
                # aplicar defesa escolhida por pertencimento às listas gks/zgs/lts
                predefinido_defesa['goleiros'] = [j for j in jogadores_escolhidos if j in gks][:1]
                predefinido_defesa['zagueiros'] = [j for j in jogadores_escolhidos if 'zgs' in locals() and j in zgs][:2]
                predefinido_defesa['laterais'] = [j for j in jogadores_escolhidos if 'lts' in locals() and j in lts][:2]
                # atualizar estrutura inicial
                for pos in ['goleiros','zagueiros','laterais']:
                    if predefinido_defesa[pos]:
                        escalacao['titulares'][pos] = predefinido_defesa[pos]
                        escalacao['custo_total'] += sum(j['preco_num'] for j in predefinido_defesa[pos])
                        escalados_ids.extend(j['atleta_id'] for j in predefinido_defesa[pos])
                try:
                    nomes = []
                    for pos in ['goleiros','zagueiros','laterais']:
                        for j in predefinido_defesa[pos]:
                            nomes.append(f"{j['apelido']} ({pos[:-1].upper()} - R${j['preco_num']:.2f} - {j['pontuacao_total']:.2f})")
                    printdbg(f"Defesa escolhida do clube_id {clube_escolhido}: ")
                    for n in nomes:
                        printdbg(f"  - {n}")
                    printdbg(f"Custo parcial da defesa: R${escalacao['custo_total']:.2f}")
                except Exception:
                    pass
                printdbg(f"Estratégia 2: Defesa fechada aplicada. Custo até aqui: {escalacao['custo_total']:.2f}")
            else:
                printdbg("Estratégia 2: Não foi possível fechar defesa dentro do orçamento. Prosseguindo com estratégia padrão.")

        # Escalar posições que não foram desescaladas
        for posicao in prioridades:
            if posicao in posicoes_desescaladas:
                # Se for defesa com pré-definição pela estratégia 2, não pular: vamos completar as vagas
                if not (estrategia == 2 and posicao in ['goleiros','zagueiros','laterais'] and escalacao['titulares'][posicao]):
                    continue  # Pular posições que serão tratadas nas combinações
            # Se a estratégia 2 pré-definiu parte da defesa, completar as vagas restantes em vez de pular
            existentes = escalacao['titulares'][posicao] if posicao in ['goleiros','zagueiros','laterais'] else []
            qt_titulares = formacao[f'qt_{plural_to_singular[posicao]}']
            if estrategia == 2 and posicao in ['goleiros','zagueiros','laterais'] and existentes:
                restantes = max(0, qt_titulares - len(existentes))
                if restantes <= 0:
                    printdbg(f"Estratégia 2: {posicao} já completa pelos pré-definidos.")
                    continue
                printdbg(f"Estratégia 2: {posicao} pré-definida parcialmente ({len(existentes)}/{qt_titulares}). Completando {restantes} restantes.")
            else:
                restantes = None  # sinaliza fluxo normal sem pré-definição
            printdbg(f"Processando posição (titulares): {posicao}")
            pos_id = posicao_ids[posicao]

            # Para a posição do capitão, buscar 1 jogador a mais (reserva de luxo)
            alvo = (restantes if restantes is not None else formacao[f'qt_{plural_to_singular[posicao]}'])
            quantidade_busca = alvo + 1 if posicao == posicao_capitao and posicao != 'tecnicos' else alvo

            candidatos = fetch_melhores_jogadores_por_posicao(
                conn, pos_id, quantidade_busca * 2, rodada_atual, escalados_ids=escalados_ids, usar_provaveis_cartola=usar_provaveis_cartola
            )
            printdbg(f"Filtrando jogadores para {posicao} com custo total atual: {escalacao['custo_total']:.2f}")
            candidatos_validos = []
            custo_temp = escalacao['custo_total']
            selecionados = []
            for candidato in candidatos:
                if custo_temp + candidato['preco_num'] <= patrimonio and len(selecionados) < quantidade_busca:
                    selecionados.append(candidato)
                    custo_temp += candidato['preco_num']
                if len(selecionados) == quantidade_busca:
                    break
            candidatos_validos = selecionados
            printdbg(f"Encontrados {len(candidatos_validos)} candidatos válidos para {posicao}")

            needed_check = alvo
            if len(candidatos_validos) < needed_check:
                printdbg(f"Não há jogadores suficientes para {posicao} (necessários: {needed_check}) dentro do orçamento.")
                return None

            # Atribuir titulares e reserva de luxo (se aplicável)
            if posicao == posicao_capitao and posicao != 'tecnicos' and len(candidatos_validos) >= needed_check:
                candidatos_validos.sort(key=lambda x: x['preco_num'], reverse=True)
                # anexar aos existentes se houver pré-definição parcial
                if existentes and restantes is not None:
                    novos = candidatos_validos[:needed_check]
                    escalacao['titulares'][posicao] = existentes + novos
                    if len(candidatos_validos) > needed_check:
                        escalacao['reservas'][posicao] = [candidatos_validos[needed_check]]
                else:
                    escalacao['titulares'][posicao] = candidatos_validos[:needed_check]
                    if len(candidatos_validos) > needed_check:
                        escalacao['reservas'][posicao] = [candidatos_validos[needed_check]]
                printdbg(
                    f"Selecionados {needed_check} titulares (mais caros) e 1 reserva de luxo para {posicao}: "
                    f"Titulares: {[f'{j['apelido']} ({j['preco_num']:.2f})' for j in escalacao['titulares'][posicao]]}, "
                    f"Reserva: {escalacao['reservas'][posicao][0]['apelido']} ({escalacao['reservas'][posicao][0]['preco_num']:.2f})"
                )
            else:
                if existentes and restantes is not None:
                    novos = candidatos_validos[:needed_check]
                    escalacao['titulares'][posicao] = existentes + novos
                else:
                    escalacao['titulares'][posicao] = candidatos_validos[:needed_check]
                printdbg(
                    f"Selecionados {needed_check} titulares para {posicao}: "
                    f"{[f'{j['apelido']} ({j['pontuacao_total']:.2f})' for j in escalacao['titulares'][posicao]]}"
                )

            custo_posicao = sum(j['preco_num'] for j in escalacao['titulares'][posicao])
            escalacao['custo_total'] += custo_posicao
            escalados_ids.extend(j['atleta_id'] for j in escalacao['titulares'][posicao])
            printdbg(f"Custo da posição {posicao}: {custo_posicao:.2f}. IDs escalados: {escalados_ids}")

        # Tentar combinações para posições desescaladas
        orcamento_restante = patrimonio - escalacao['custo_total']
        printdbg(f"Orçamento restante para posições desescaladas: {orcamento_restante:.2f}")

        # Remover das desescaladas as posições que já estão completas (inclui defesa parcialmente pré-definida que foi completada)
        efetivas_desescaladas = []
        for pos in posicoes_desescaladas:
            qt = formacao[f'qt_{plural_to_singular[pos]}']
            if len(escalacao['titulares'][pos]) < qt:
                efetivas_desescaladas.append(pos)

        # Buscar candidatos para posições desescaladas
        candidatos = {}
        for pos in efetivas_desescaladas:
            qt = formacao[f'qt_{plural_to_singular[pos]}']
            # Usar top_n para atacantes, laterais, meias; top_n_reduzido para goleiros, técnicos, zagueiros
            quantidade_candidatos = top_n_reduzido if pos in ['goleiros', 'tecnicos', 'zagueiros'] else top_n
            candidatos[pos] = fetch_melhores_jogadores_por_posicao(
                conn, posicao_ids[pos], quantidade_candidatos, rodada_atual, escalados_ids=escalados_ids, usar_provaveis_cartola=usar_provaveis_cartola
            )
            printdbg(f"Candidatos a {pos} disponíveis (top {quantidade_candidatos}):")
            for cand in candidatos[pos]:
                printdbg(
                    f"  - {cand['apelido']} (ID: {cand['atleta_id']}, Pontuação: {cand['pontuacao_total']:.2f}, "
                    f"Preço: {cand['preco_num']:.2f})"
                )

        # Gerar combinações
        combinacoes = []
        if efetivas_desescaladas:
            combos_posicoes = []
            for pos in efetivas_desescaladas:
                qt = formacao[f'qt_{plural_to_singular[pos]}']
                combos_pos = list(combinations(candidatos[pos], qt))
                combos_posicoes.append([(pos, combo) for combo in combos_pos])
            for combo_outras in product(*combos_posicoes):
                jogadores_outras = []
                for pos, combo_pos in combo_outras:
                    jogadores_outras.extend(combo_pos)
                combinacoes.append(jogadores_outras)
        else:
            # Se não há posições desescaladas, todas as posições já foram escaladas
            return escalacao

        # Avaliar combinações
        melhor_combinacao = None
        for combo in combinacoes:
            custo_combo = sum(j['preco_num'] for j in combo)
            pontuacao_combo = sum(j['pontuacao_total'] for j in combo)
            jogadores_nomes = [j['apelido'] for j in combo]
            printdbg(
                f"  - Combinação: {jogadores_nomes}, Pontuação Total: {pontuacao_combo:.2f}, "
                f"Custo Total: {custo_combo:.2f}, Dentro do orçamento: {custo_combo <= orcamento_restante}"
            )
            if custo_combo <= orcamento_restante:
                melhor_combinacao = combo
                printdbg(
                    f"Primeira combinação válida encontrada: {jogadores_nomes}, "
                    f"Pontuação: {pontuacao_combo:.2f}, Custo: {custo_combo:.2f}"
                )
                break

        if melhor_combinacao:
            for pos in efetivas_desescaladas:
                qt = formacao[f'qt_{plural_to_singular[pos]}']
                jogadores = [j for j in melhor_combinacao if j in candidatos[pos]][:qt]
                if len(jogadores) != qt:
                    printdbg(f"Erro: Combinação não contém {qt} jogadores para {pos}. Jogadores encontrados: {len(jogadores)}")
                    return None
                escalacao['titulares'][pos] = jogadores
                printdbg(f"Reescalado {pos}: {[j['apelido'] for j in jogadores]} (Preço total: {sum(j['preco_num'] for j in jogadores):.2f})")
            custo_posicao = sum(j['preco_num'] for j in melhor_combinacao)
            escalacao['custo_total'] += custo_posicao
            escalados_ids.extend(j['atleta_id'] for j in melhor_combinacao)
            printdbg(f"Custo das posições combinadas: {custo_posicao:.2f}. IDs escalados: {escalados_ids}")
            return escalacao
        else:
            printdbg("Nenhuma combinação válida encontrada.")
            return None

    # Tentar escalação com desescalação progressiva
    posicoes_desescaladas = []
    escalacao = None
    while escalacao is None and len(posicoes_desescaladas) < len(ordem_desescalacao):
        escalacao = try_escalacao(posicoes_desescaladas)
        if escalacao is None and len(posicoes_desescaladas) < len(ordem_desescalacao):
            proxima_posicao = ordem_desescalacao[len(posicoes_desescaladas)]
            posicoes_desescaladas.append(proxima_posicao)
            printdbg(f"Sem escalação válida. Adicionando {proxima_posicao} às posições desescaladas: {posicoes_desescaladas}")

    if escalacao is None:
        printdbg("Erro: Não foi possível encontrar uma escalação válida mesmo após desescalar todas as posições.")
        close_db_connection(conn)
        return None

    # Validar número de jogadores por posição
    for posicao in posicao_ids:
        qt_esperada = formacao[f'qt_{plural_to_singular[posicao]}']
        qt_atual = len(escalacao['titulares'][posicao])
        if qt_atual != qt_esperada:
            printdbg(f"Erro: Quantidade inválida de jogadores para {posicao}. Esperado: {qt_esperada}, Encontrado: {qt_atual}")
            close_db_connection(conn)
            return None

    # Aplicar hack do goleiro: garantir que o goleiro titular seja um que não joga e o reserva seja bom
    if 'goleiros' in escalacao['titulares'] and escalacao['titulares']['goleiros']:
        printdbg("Aplicando hack do goleiro...")
        
        # 1. Buscar todos os goleiros prováveis (que vão jogar)
        cursor = conn.cursor()
        # EXCEÇÃO: Técnicos (posição 6) sempre usam status_id = 7 pois não estão na nova API
        if usar_provaveis_cartola and posicao_ids['goleiros'] != 6:
            cursor.execute('''
                SELECT a.atleta_id, a.apelido, a.clube_id, a.preco_num, a.status_id, 
                       (SELECT pontuacao_total FROM ranking_por_posicao WHERE atleta_id = a.atleta_id AND rodada_atual = %s) as pontuacao_total 
                FROM acf_atletas a 
                JOIN provaveis_cartola pc ON a.atleta_id = pc.atleta_id
                WHERE a.posicao_id = %s AND pc.status = 'provavel' 
                ORDER BY a.preco_num DESC
            ''', (rodada_atual, posicao_ids['goleiros']))
        else:
            cursor.execute('''
                SELECT a.atleta_id, a.apelido, a.clube_id, a.preco_num, a.status_id, 
                       (SELECT pontuacao_total FROM ranking_por_posicao WHERE atleta_id = a.atleta_id AND rodada_atual = %s) as pontuacao_total 
                FROM acf_atletas a 
                WHERE a.posicao_id = %s AND a.status_id = 7 
                ORDER BY a.preco_num DESC
            ''', (rodada_atual, posicao_ids['goleiros']))
        
        goleiros_provaveis = [
            {
                'atleta_id': row[0],
                'apelido': row[1],
                'clube_id': row[2],
                'preco_num': row[3],
                'status_id': row[4],
                'pontuacao_total': row[5] or 0
            } for row in cursor.fetchall()
        ]
        
        # 2. Buscar goleiros nulos (que não vão jogar - não podem ser provável=7 nem dúvida=2)
        cursor.execute('''
            SELECT a.atleta_id, a.apelido, a.clube_id, a.preco_num, a.status_id, 0 as pontuacao_total
            FROM acf_atletas a
            WHERE a.posicao_id = %s AND a.status_id NOT IN (2, 7)  -- Goleiros nulos (qualquer status exceto provável=7 e dúvida=2)
            ORDER BY a.preco_num ASC  -- Ordena do mais barato para o mais caro
        ''', (posicao_ids['goleiros'],))
        
        goleiros_nao_relacionados = [
            {
                'atleta_id': row[0],
                'apelido': row[1],
                'clube_id': row[2],
                'preco_num': row[3],
                'status_id': row[4],
                'pontuacao_total': 0  # Pontuação zero pois não vai jogar
            } for row in cursor.fetchall()
        ]
        
        # 3. Selecionar o melhor goleiro que vai jogar de fato
        melhor_goleiro_provavel = None
        if goleiros_provaveis:
            melhor_goleiro_provavel = max(goleiros_provaveis, key=lambda x: x['pontuacao_total'])
            printdbg(f"Melhor goleiro provável: {melhor_goleiro_provavel['apelido']} (R$ {melhor_goleiro_provavel['preco_num']:.2f}, Pontuação: {melhor_goleiro_provavel['pontuacao_total']:.2f})")
        
        # 4. Tentar aplicar o hack do goleiro
        if melhor_goleiro_provavel and goleiros_nao_relacionados:
            # Encontrar o goleiro nulo mais barato entre os que custam mais que o melhor goleiro
            goleiro_nulo = None
            for g in goleiros_nao_relacionados:
                if g['preco_num'] > melhor_goleiro_provavel['preco_num']:
                    goleiro_nulo = g
                    break  # Pega o primeiro (mais barato) que custa mais
            
            if goleiro_nulo:
                # Verificar se o saldo permite o hack
                diferenca_preco = goleiro_nulo['preco_num'] - melhor_goleiro_provavel['preco_num']
                printdbg(f"Diferença de preço para hack: R$ {diferenca_preco:.2f}")
                
                if escalacao['custo_total'] + diferenca_preco <= patrimonio:
                    # Aplicar o hack do goleiro
                    printdbg(f"Aplicando hack do goleiro:")
                    printdbg(f"  - Titular (não joga): {goleiro_nulo['apelido']} (R$ {goleiro_nulo['preco_num']:.2f})")
                    printdbg(f"  - Reserva (joga): {melhor_goleiro_provavel['apelido']} (R$ {melhor_goleiro_provavel['preco_num']:.2f})")
                    
                    escalacao['titulares']['goleiros'] = [goleiro_nulo]
                    escalacao['reservas']['goleiros'] = [melhor_goleiro_provavel]
                    escalacao['custo_total'] += diferenca_preco
                    
                    printdbg(f"Hack do goleiro aplicado! Novo custo total: R$ {escalacao['custo_total']:.2f}")
                else:
                    printdbg(f"Saldo insuficiente para hack do goleiro. Escalando normalmente com reserva.")
                    # Usar o melhor goleiro normalmente
                    escalacao['titulares']['goleiros'] = [melhor_goleiro_provavel]
                    escalacao['custo_total'] += melhor_goleiro_provavel['preco_num']
                    
                    # Selecionar melhor reserva entre os mais baratos que o titular
                    melhor_reserva = None
                    goleiros_mais_baratos = [g for g in goleiros_provaveis if g['preco_num'] < melhor_goleiro_provavel['preco_num']]
                    if goleiros_mais_baratos:
                        melhor_reserva = max(goleiros_mais_baratos, key=lambda x: x['pontuacao_total'])
                        escalacao['reservas']['goleiros'] = [melhor_reserva]
                        printdbg(f"Reserva de goleiro: {melhor_reserva['apelido']} (R$ {melhor_reserva['preco_num']:.2f}, Pontuação: {melhor_reserva['pontuacao_total']:.2f})")
                    else:
                        printdbg("Não há goleiros mais baratos para reserva.")
            else:
                printdbg("Não encontrou goleiro nulo adequado para hack. Escalando normalmente com reserva.")
                escalacao['titulares']['goleiros'] = [melhor_goleiro_provavel]
                escalacao['custo_total'] += melhor_goleiro_provavel['preco_num']
                
                # Selecionar melhor reserva entre os mais baratos que o titular
                melhor_reserva = None
                goleiros_mais_baratos = [g for g in goleiros_provaveis if g['preco_num'] < melhor_goleiro_provavel['preco_num']]
                if goleiros_mais_baratos:
                    melhor_reserva = max(goleiros_mais_baratos, key=lambda x: x['pontuacao_total'])
                    escalacao['reservas']['goleiros'] = [melhor_reserva]
                    printdbg(f"Reserva de goleiro: {melhor_reserva['apelido']} (R$ {melhor_reserva['preco_num']:.2f}, Pontuação: {melhor_reserva['pontuacao_total']:.2f})")
                else:
                    printdbg("Não há goleiros mais baratos para reserva.")
        else:
            printdbg("Não foi possível aplicar hack do goleiro. Escalando normalmente com reserva.")
            if melhor_goleiro_provavel:
                escalacao['titulares']['goleiros'] = [melhor_goleiro_provavel]
                escalacao['custo_total'] += melhor_goleiro_provavel['preco_num']
                
                # Selecionar melhor reserva entre os mais baratos que o titular
                melhor_reserva = None
                goleiros_mais_baratos = [g for g in goleiros_provaveis if g['preco_num'] < melhor_goleiro_provavel['preco_num']]
                if goleiros_mais_baratos:
                    melhor_reserva = max(goleiros_mais_baratos, key=lambda x: x['pontuacao_total'])
                    escalacao['reservas']['goleiros'] = [melhor_reserva]
                    printdbg(f"Reserva de goleiro: {melhor_reserva['apelido']} (R$ {melhor_reserva['preco_num']:.2f}, Pontuação: {melhor_reserva['pontuacao_total']:.2f})")
                else:
                    printdbg("Não há goleiros mais baratos para reserva.")
    
    # Selecionar reservas para outras posições (exceto posição do capitão e técnicos)
    for posicao in prioridades:
        if posicao == posicao_capitao or posicao == 'tecnicos' or posicao == 'goleiros':  # Já tratamos os goleiros
            continue
            
        printdbg(f"Processando posição (reservas): {posicao}")
        min_preco_titular = min(j['preco_num'] for j in escalacao['titulares'][posicao]) if escalacao['titulares'][posicao] else float('inf')
        printdbg(f"Preço mínimo dos titulares para {posicao}: {min_preco_titular:.2f}")
        candidatos_reserva = fetch_melhores_jogadores_por_posicao(
            conn, posicao_ids[posicao], 5, rodada_atual, max_preco=min_preco_titular, is_reserva=True,
            escalados_ids=[j['atleta_id'] for pos in escalacao['titulares'] for j in escalacao['titulares'][pos]], usar_provaveis_cartola=usar_provaveis_cartola
        )

        if not candidatos_reserva:
            printdbg(f"Aviso: Não há reservas com preço <= {min_preco_titular:.2f} para {posicao}. Pulando reserva.")
            continue

        escalacao['reservas'][posicao] = [candidatos_reserva[0]]
        printdbg(
            f"Selecionado 1 reserva para {posicao}: {candidatos_reserva[0]['apelido']}. "
            f"Preço: {candidatos_reserva[0]['preco_num']:.2f}, Pontuação: {candidatos_reserva[0]['pontuacao_total']:.2f}, "
            f"ID: {candidatos_reserva[0]['atleta_id']}"
        )

    # Calcular pontuação total dos titulares
    escalacao['pontuacao_total'] = sum(
        jogador['pontuacao_total']
        for posicao in escalacao['titulares'].values()
        for jogador in posicao
    )
    printdbg(f"Pontuação total calculada: {escalacao['pontuacao_total']:.2f}")

    # Identificar reserva de luxo
    reserva_de_luxo = None
    if posicao_capitao in escalacao['reservas'] and escalacao['reservas'][posicao_capitao]:
        reserva_de_luxo = {
            'posicao': posicao_capitao,
            'atleta_id': escalacao['reservas'][posicao_capitao][0]['atleta_id'],
            'apelido': escalacao['reservas'][posicao_capitao][0]['apelido'],
            'clube_id': escalacao['reservas'][posicao_capitao][0]['clube_id'],
            'pontuacao_total': escalacao['reservas'][posicao_capitao][0]['pontuacao_total'],
            'preco_num': escalacao['reservas'][posicao_capitao][0]['preco_num']
        }
        printdbg(
            f"Reserva de luxo identificada: {reserva_de_luxo['apelido']} "
            f"(Posição: {posicao_capitao}, Pontuação: {reserva_de_luxo['pontuacao_total']:.2f}, Preço: {reserva_de_luxo['preco_num']:.2f})"
        )

    # Selecionar capitão
    printdbg("Selecionando capitão")
    capitao = None
    if posicao_capitao in escalacao['titulares'] and escalacao['titulares'][posicao_capitao]:
        capitao = max(escalacao['titulares'][posicao_capitao], key=lambda x: x['pontuacao_total'])
        printdbg(
            f"Capitão selecionado: {capitao['apelido']} (Posição: {posicao_capitao.capitalize()}, "
            f"Pontuação: {capitao['pontuacao_total']:.2f}, ID: {capitao['atleta_id']})"
        )
    else:
        printdbg(f"Posição de capitão inválida ou sem titulares: {posicao_capitao}. Selecionando o jogador com maior pontuação.")
        maior_pontuacao = -float('inf')
        for posicao, jogadores in escalacao['titulares'].items():
            for jogador in jogadores:
                if jogador['pontuacao_total'] > maior_pontuacao:
                    maior_pontuacao = jogador['pontuacao_total']
                    capitao = jogador
                    posicao_capitao = posicao
        if capitao:
            printdbg(
                f"Capitão selecionado: {capitao['apelido']} (Posição: {posicao_capitao.capitalize()}, "
                f"Pontuação: {capitao['pontuacao_total']:.2f}, ID: {capitao['atleta_id']})"
            )

    # Exibir escalação (apenas em modo debug para não misturar com tqdm)
    if is_debug():
        printdbg(f"\nEsquema: {formacao['nome']}")
        printdbg(f"Pontuação Total Estimada (Titulares): {escalacao['pontuacao_total']:.2f}")
        printdbg(f"Custo Total: {escalacao['custo_total']:.2f} cartoletas")
        printdbg(f"Orçamento Restante: {patrimonio - escalacao['custo_total']:.2f} cartoletas")
        printdbg("\n--- Escalação Titular ---")
        for posicao, jogadores in escalacao['titulares'].items():
            if jogadores:
                printdbg(f"{posicao.capitalize()}:")
                for jogador in jogadores:
                    printdbg(f"DEBUG jogador: {jogador}")  # <-- ADICIONE ESTA LINHA
                    printdbg(
                        f"  - {jogador['apelido']} (Clube ID: {jogador['clube_id']}, "
                        f"Pontuação: {jogador['pontuacao_total']:.2f}, Preço: {jogador['preco_num']:.2f}, ID: {jogador['atleta_id']})"
                    )

        printdbg("\n--- Escalação Reserva ---")
        for posicao, jogadores in escalacao['reservas'].items():
            if jogadores:
                printdbg(f"{posicao.capitalize()}:")
                for jogador in jogadores:
                    printdbg(
                        f"  - {jogador['apelido']} (Clube ID: {jogador['clube_id']}, "
                        f"Pontuação: {jogador['pontuacao_total']:.2f}, Preço: {jogador['preco_num']:.2f}, ID: {jogador['atleta_id']})"
                    )

        if reserva_de_luxo:
            printdbg(f"\n--- Reserva de Luxo ---")
            printdbg(
                f"{reserva_de_luxo['posicao'].capitalize()}: {reserva_de_luxo['apelido']} "
                f"(Clube ID: {reserva_de_luxo['clube_id']}, Pontuação: {reserva_de_luxo['pontuacao_total']:.2f}, "
                f"Preço: {reserva_de_luxo['preco_num']:.2f})"
            )

        if capitao:
            printdbg("\n--- Capitão ---")
            printdbg(f"{capitao['apelido']} (Posição: {posicao_capitao.capitalize()}, Pontuação: {capitao['pontuacao_total']:.2f}, ID: {capitao['atleta_id']})")

    # Preparar dados para a API do Cartola
    reservas_map = {
        str(posicao_ids[posicao]): escalacao['reservas'][posicao][0]['atleta_id']
        for posicao in escalacao['reservas']
        if escalacao['reservas'][posicao] and posicao != posicao_capitao
    }
    # Alinhar com comportamento do navegador: incluir a chave da posição do capitão
    # apontando para o mesmo atleta do reserva de luxo
    if reserva_de_luxo:
        reservas_map[str(posicao_ids[posicao_capitao])] = reserva_de_luxo['atleta_id']

    time_para_escalacao = {
        'esquema': 3,  # 4-3-3
        'atletas': [
            jogador['atleta_id']
            for posicao in ['goleiros', 'laterais', 'zagueiros', 'meias', 'atacantes', 'tecnicos']
            for jogador in escalacao['titulares'][posicao]
        ],
        'capitao': capitao['atleta_id'] if capitao else None,
        'reservas': reservas_map,
        'reserva_luxo_id': reserva_de_luxo['atleta_id'] if reserva_de_luxo else None
    }
    printdbg(f"Dados preparados para API do Cartola: {time_para_escalacao}")

    # Validar número de atletas titulares (incluindo técnico)
    if len(time_para_escalacao['atletas']) != 12:
        printdbg(f"Erro: Escalação inválida. Número de atletas (incluindo técnico): {len(time_para_escalacao['atletas'])}. Esperado: 12")
        close_db_connection(conn)
        return None

    # Enviar diretamente sem confirmação
    sucesso = salvar_time_no_cartola(time_para_escalacao, access_token=updated_token, env_key=env_key)
    if not sucesso:
        printdbg(f"Falha ao escalar o {nome_time} no Cartola.")
        # Resumo conciso do payload para depuração
        try:
            atletas_ids = time_para_escalacao.get('atletas', [])
            total_atletas = len(atletas_ids)
            reservas_map = time_para_escalacao.get('reservas', {})
            capitao_id = time_para_escalacao.get('capitao')
            reserva_luxo_id = time_para_escalacao.get('reserva_luxo_id')
            esquema = time_para_escalacao.get('esquema')

            # Contagem por posição
            contagem_pos = {pos: len(escalacao['titulares'].get(pos, [])) for pos in ['goleiros','laterais','zagueiros','meias','atacantes','tecnicos']}
            # IDs duplicados
            seen = set()
            dups = sorted({x for x in atletas_ids if (x in seen) or seen.add(x) is not None and atletas_ids.count(x) > 1})

            printdbg(
                f"Resumo payload -> esquema:{esquema} total_atletas:{total_atletas} capitao:{capitao_id} reserva_luxo:{reserva_luxo_id}"
            )
            printdbg(f"Contagem por posição: {contagem_pos}")
            printdbg(f"Reservas (pos_id->atleta_id): {reservas_map}")
            if dups:
                printdbg(f"IDs duplicados nos atletas: {dups}")
            else:
                printdbg("Nenhum ID duplicado entre os 12 atletas.")
            # Opcional: prévia dos IDs
            printdbg(f"Atletas IDs (12 esperados): {atletas_ids}")
        except Exception as _e:
            printdbg(f"Falha ao gerar resumo do payload: {_e}")
    else:
        printdbg(f"{nome_time} escalado com sucesso!")

    # Prepara a estrutura de retorno com titulares, reservas e reservas de luxo
    escalacao_info = {
        'atletas': [],  # Lista de titulares
        'reservas': [],  # Lista de reservas
        'reservas_luxo': []  # Lista de reservas de luxo
    }

    pos_map = {
        1: 'Goleiro',
        2: 'Lateral',
        3: 'Zagueiro',
        4: 'Meia',
        5: 'Atacante',
        6: 'Técnico'
    }

    # Adiciona titulares
    cursor = conn.cursor()
    for atleta_id in time_para_escalacao.get('atletas', []):
        cursor.execute('''
            SELECT a.apelido, a.posicao_id
            FROM acf_atletas a
            WHERE a.atleta_id = %s
        ''', (atleta_id,))
        jogador = cursor.fetchone()
        if jogador:
            escalacao_info['atletas'].append({
                'nome': jogador[0],
                'posicao': pos_map[jogador[1]],
                'eh_capitao': atleta_id == time_para_escalacao.get('capitao')
            })

    # Adiciona reservas
    for posicao_id, atleta_id in time_para_escalacao.get('reservas', {}).items():
        cursor.execute('''
            SELECT a.apelido
            FROM acf_atletas a
            WHERE a.atleta_id = %s
        ''', (atleta_id,))
        jogador = cursor.fetchone()
        if jogador:
            escalacao_info['reservas'].append({
                'nome': jogador[0],
                'posicao': pos_map[int(posicao_id)]
            })

    # Busca reserva de luxo (apenas 1 jogador da posição do capitão)
    todos_ids = (time_para_escalacao.get('atletas', []) +
                list(time_para_escalacao.get('reservas', {}).values()))
    
    # Reserva de luxo é apenas 1 jogador da posição do capitão
    if reserva_de_luxo:
        escalacao_info['reservas_luxo'].append({
            'nome': reserva_de_luxo['apelido'],
            'posicao': pos_map[posicao_ids[posicao_capitao]]
        })

    close_db_connection(conn)
    printdbg(f"Cálculo de escalação ideal concluído para {nome_time}!")
    return bool(sucesso), escalacao_info

def main():
    printdbg("Iniciando main")
    status_data = fetch_status_data()
    if not status_data:
        printdbg("Erro ao obter dados de status.")
        return
    rodada_atual = status_data['rodada_atual']
    printdbg(f"Rodada atual: {rodada_atual}")

    # Carregar times a partir das credenciais no banco
    conn = get_db_connection()
    try:
        credenciais = get_all_credenciais(conn)
    finally:
        close_db_connection(conn)

    times = [{
        "nome": c.get("nome"),
        "env_key": c.get("env_key"),
        "token": c.get("access_token")
    } for c in credenciais]

    for time in times:
        nome = time["nome"]
        env_key = time["env_key"]
        token = time["token"]
        if not token:
            printdbg(f"Erro: Token não encontrado para {env_key} ({nome})")
            continue

        printdbg(f"Escalando {nome} com env_key: {env_key}")
        calcular_escalacao_ideal(rodada_atual, posicao_capitao='atacantes', access_token=token, env_key=env_key, nome_time=nome)

    printdbg("Cálculo da escalação ideal concluído para todos os times.")

if __name__ == "__main__":
    main()