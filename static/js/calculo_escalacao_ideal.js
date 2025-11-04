/**
 * Classe para calcular escalação ideal baseada nos rankings salvos
 */
class CalculoEscalacaoIdeal {
    constructor(data) {
        this.rodada_atual = data.rodada_atual;
        this.rankings_por_posicao = data.rankings_por_posicao || {};
        // Garantir que patrimônio seja sempre um número
        this.patrimonio = parseFloat(data.patrimonio) || 0;
        this.clubes_sg = data.clubes_sg || [];
        this.config = data.config || {};
        this.patrimonio_error = data.patrimonio_error || null;
        
        // Log para debug
        console.log('[DEBUG] CalculoEscalacaoIdeal - Patrimônio recebido:', this.patrimonio, 'Erro:', this.patrimonio_error);
        
        // Formação padrão (será ajustada dinamicamente)
        this.formacao = this.parseFormation(data.config?.formation || '4-3-3');
        
        // Mapeamento de posições
        this.posicao_ids = {
            'goleiros': 1,
            'zagueiros': 3,
            'laterais': 2,
            'meias': 4,
            'atacantes': 5,
            'tecnicos': 6
        };
        
        this.plural_to_singular = {
            'goleiros': 'goleiro',
            'zagueiros': 'zagueiro',
            'laterais': 'lateral',
            'meias': 'meia',
            'atacantes': 'atacante',
            'tecnicos': 'tecnico'
        };
        
        // Prioridades de escalação
        this.prioridades = ['atacantes', 'laterais', 'meias', 'zagueiros', 'goleiros', 'tecnicos'];
        this.ordem_desescalacao = this.prioridades.slice().reverse();
        
        this.logCallback = null;
    }
    
    parseFormation(formationStr) {
        // Formações suportadas: 4-3-3, 4-4-2, 3-5-2, 3-4-3, 4-5-1, 5-4-1
        const formationMap = {
            '4-3-3': { 'qt_goleiro': 1, 'qt_zagueiro': 2, 'qt_lateral': 2, 'qt_meia': 3, 'qt_atacante': 3, 'qt_tecnico': 1 },
            '4-4-2': { 'qt_goleiro': 1, 'qt_zagueiro': 2, 'qt_lateral': 2, 'qt_meia': 4, 'qt_atacante': 2, 'qt_tecnico': 1 },
            '3-5-2': { 'qt_goleiro': 1, 'qt_zagueiro': 3, 'qt_lateral': 0, 'qt_meia': 5, 'qt_atacante': 2, 'qt_tecnico': 1 },
            '3-4-3': { 'qt_goleiro': 1, 'qt_zagueiro': 3, 'qt_lateral': 0, 'qt_meia': 4, 'qt_atacante': 3, 'qt_tecnico': 1 },
            '4-5-1': { 'qt_goleiro': 1, 'qt_zagueiro': 2, 'qt_lateral': 2, 'qt_meia': 5, 'qt_atacante': 1, 'qt_tecnico': 1 },
            '5-4-1': { 'qt_goleiro': 1, 'qt_zagueiro': 3, 'qt_lateral': 2, 'qt_meia': 4, 'qt_atacante': 1, 'qt_tecnico': 1 }
        };
        
        return formationMap[formationStr] || formationMap['4-3-3'];
    }
    
    log(message) {
        if (this.logCallback) {
            this.logCallback(message);
        } else {
            console.log(message);
        }
    }
    
    setLogCallback(callback) {
        this.logCallback = callback;
    }
    
    /**
     * Helper para normalizar preço (pode estar como 'preco' ou 'preco_num')
     */
    _getPreco(jogador) {
        return parseFloat(jogador.preco_num || jogador.preco || 0);
    }
    
    /**
     * Busca os melhores jogadores de uma posição dos rankings salvos
     */
    fetchMelhoresJogadoresPorPosicao(posicao_nome, quantidade, max_preco = null, escalados_ids = []) {
        const ranking = this.rankings_por_posicao[posicao_nome] || [];
        
        let candidatos = ranking.filter(j => {
            if (escalados_ids.includes(j.atleta_id)) {
                return false;
            }
            const preco = this._getPreco(j);
            if (max_preco !== null && preco > max_preco) {
                return false;
            }
            return true;
        });
        
        // Garantir que todos tenham preco_num normalizado
        candidatos = candidatos.map(j => ({
            ...j,
            preco_num: this._getPreco(j)
        }));
        
        // Ordenar por pontuacao_total decrescente
        candidatos.sort((a, b) => (b.pontuacao_total || 0) - (a.pontuacao_total || 0));
        
        return candidatos.slice(0, quantidade);
    }
    
    /**
     * Busca jogadores de uma posição de um clube específico
     */
    fetchByClubePos(posicao_nome, clube_id, limit) {
        const ranking = this.rankings_por_posicao[posicao_nome] || [];
        
        let candidatos = ranking.filter(j => j.clube_id === clube_id);
        
        // Ordenar por pontuacao_total decrescente
        candidatos.sort((a, b) => (b.pontuacao_total || 0) - (a.pontuacao_total || 0));
        
        return candidatos.slice(0, limit);
    }
    
    /**
     * Tenta criar uma escalação válida
     */
    tryEscalacao(posicoes_desescaladas = [], hackGoleiro = false, fecharDefesa = false, posicaoCapitao = 'atacantes') {
        const escalacao = {
            titulares: {},
            reservas: {},
            custo_total: 0,
            pontuacao_total: 0
        };
        
        // Inicializar estruturas
        for (const pos of Object.keys(this.posicao_ids)) {
            escalacao.titulares[pos] = [];
            if (pos !== 'tecnicos') {
                escalacao.reservas[pos] = [];
            }
        }
        
        let escalados_ids = [];
        const predefinido_defesa = { goleiros: [], zagueiros: [], laterais: [] };
        
        // Fechar defesa se solicitado
        if (fecharDefesa && this.clubes_sg.length > 0) {
            const top_clube_id = this.clubes_sg[0].clube_id;
            this.log(`Fechando defesa do clube_id ${top_clube_id} (melhor SG)...`);
            
            const gks = this.fetchByClubePos('goleiro', top_clube_id, 5);
            const zgs = this.fetchByClubePos('zagueiro', top_clube_id, 8);
            const lts = this.fetchByClubePos('lateral', top_clube_id, 8);
            
            if (gks.length > 0 && zgs.length >= 2 && lts.length >= 2) {
                // Tentar encontrar melhor combinação dentro do orçamento
                let best_combo = null;
                let best_score = -1;
                const patrimonio_atual = this.patrimonio;
                
                for (const gk of gks) {
                    for (let i = 0; i < zgs.length - 1; i++) {
                        for (let j = i + 1; j < zgs.length; j++) {
                            for (let k = 0; k < lts.length - 1; k++) {
                                for (let l = k + 1; l < lts.length; l++) {
                                    const combo = [gk, zgs[i], zgs[j], lts[k], lts[l]];
                                    const custo = combo.reduce((sum, j) => sum + this._getPreco(j), 0);
                                    
                                    if (custo <= patrimonio_atual) {
                                        const score = combo.reduce((sum, j) => sum + (j.pontuacao_total || 0), 0);
                                        if (score > best_score) {
                                            best_score = score;
                                            best_combo = combo;
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
                
                if (best_combo) {
                    // Separar por posição
                    const gk_combo = best_combo.filter(j => gks.includes(j))[0];
                    const zgs_combo = best_combo.filter(j => zgs.includes(j)).slice(0, 2);
                    const lts_combo = best_combo.filter(j => lts.includes(j)).slice(0, 2);
                    
                    if (gk_combo) predefinido_defesa.goleiros = [gk_combo];
                    if (zgs_combo.length === 2) predefinido_defesa.zagueiros = zgs_combo;
                    if (lts_combo.length === 2) predefinido_defesa.laterais = lts_combo;
                    
                    // Aplicar à escalação
                    for (const pos of ['goleiros', 'zagueiros', 'laterais']) {
                        if (predefinido_defesa[pos].length > 0) {
                            escalacao.titulares[pos] = predefinido_defesa[pos];
                            escalacao.custo_total += predefinido_defesa[pos].reduce((sum, j) => sum + this._getPreco(j), 0);
                            escalados_ids.push(...predefinido_defesa[pos].map(j => j.atleta_id));
                        }
                    }
                    
                    this.log(`Defesa fechada aplicada. Custo: R$ ${escalacao.custo_total.toFixed(2)}`);
                }
            }
        }
        
        // Escalar outras posições
        for (const posicao of this.prioridades) {
            if (posicoes_desescaladas.includes(posicao)) {
                // Se defesa foi pré-definida e está completa, continuar
                if (fecharDefesa && ['goleiros', 'zagueiros', 'laterais'].includes(posicao)) {
                    const qt = this.formacao[`qt_${this.plural_to_singular[posicao]}`];
                    if (escalacao.titulares[posicao].length >= qt) {
                        continue;
                    }
                } else {
                    continue;
                }
            }
            
            // Se defesa foi pré-definida parcialmente, completar
            const existentes = escalacao.titulares[posicao] || [];
            const qt_titulares = this.formacao[`qt_${this.plural_to_singular[posicao]}`];
            
            if (fecharDefesa && ['goleiros', 'zagueiros', 'laterais'].includes(posicao) && existentes.length > 0) {
                const restantes = qt_titulares - existentes.length;
                if (restantes <= 0) {
                    continue;
                }
            }
            
            const alvo = existentes.length > 0 ? (qt_titulares - existentes.length) : qt_titulares;
            
            // Para posição do capitão, buscar 1 a mais (reserva de luxo)
            const quantidade_busca = (posicao === posicaoCapitao && posicao !== 'tecnicos') ? (alvo + 1) : alvo;
            
            const candidatos = this.fetchMelhoresJogadoresPorPosicao(
                this.plural_to_singular[posicao],
                quantidade_busca * 2,
                null,
                escalados_ids
            );
            
            // Filtrar por orçamento - usar mesma lógica do Python
            // Python: custo_temp = escalacao['custo_total'] e compara com patrimonio total
            const candidatos_validos = [];
            let custo_temp = escalacao.custo_total;  // Começar do custo total atual (como no Python)
            
            this.log(`Filtrando jogadores para ${posicao} com custo total atual: R$ ${custo_temp.toFixed(2)}`);
            
            for (const candidato of candidatos) {
                const preco_candidato = this._getPreco(candidato);
                // Comparar custo_temp + preco com patrimonio total (como no Python)
                if (custo_temp + preco_candidato <= this.patrimonio && candidatos_validos.length < quantidade_busca) {
                    candidatos_validos.push(candidato);
                    custo_temp += preco_candidato;  // Atualizar custo temporário acumulado
                }
                // Se já temos candidatos suficientes, parar
                if (candidatos_validos.length >= quantidade_busca) {
                    break;
                }
            }
            
            if (candidatos_validos.length < alvo) {
                const orcamento_restante = this.patrimonio - escalacao.custo_total;
                this.log(`[ERRO] Não há jogadores suficientes para ${posicao} (necessários: ${alvo}, encontrados: ${candidatos_validos.length})`);
                this.log(`Custo atual da escalação: R$ ${escalacao.custo_total.toFixed(2)}`);
                this.log(`Orçamento restante: R$ ${orcamento_restante.toFixed(2)}`);
                this.log(`Total de candidatos no ranking: ${candidatos.length}`);
                if (candidatos.length > 0) {
                    const preco_medio = candidatos.slice(0, Math.min(10, candidatos.length)).reduce((sum, j) => sum + this._getPreco(j), 0) / Math.min(10, candidatos.length);
                    const preco_min = Math.min(...candidatos.slice(0, 10).map(j => this._getPreco(j)));
                    const preco_max = Math.max(...candidatos.slice(0, 10).map(j => this._getPreco(j)));
                    this.log(`Preço médio dos top 10 candidatos: R$ ${preco_medio.toFixed(2)} (min: R$ ${preco_min.toFixed(2)}, max: R$ ${preco_max.toFixed(2)})`);
                    // Ver quantos jogadores cabem no orçamento
                    let qtd_cabem = 0;
                    for (const c of candidatos.slice(0, 10)) {
                        if (this._getPreco(c) <= orcamento_restante) {
                            qtd_cabem++;
                        }
                    }
                    this.log(`Quantos dos top 10 cabem no orçamento: ${qtd_cabem}`);
                } else {
                    this.log(`Nenhum candidato encontrado no ranking para ${posicao}`);
                }
                return null;
            }
            
            // Atribuir titulares e reserva de luxo (se aplicável)
            if (posicao === posicaoCapitao && posicao !== 'tecnicos' && candidatos_validos.length >= alvo) {
                // Ordenar por preço (mais caros primeiro para titulares)
                candidatos_validos.sort((a, b) => this._getPreco(b) - this._getPreco(a));
                
                if (existentes.length > 0) {
                    escalacao.titulares[posicao] = [...existentes, ...candidatos_validos.slice(0, alvo)];
                } else {
                    escalacao.titulares[posicao] = candidatos_validos.slice(0, alvo);
                }
                
                // Reserva de luxo é o próximo candidato (mais caro que não foi titular)
                if (candidatos_validos.length > alvo) {
                    escalacao.reservas[posicao] = [candidatos_validos[alvo]];
                }
            } else {
                // Posição normal, sem reserva de luxo
                if (existentes.length > 0) {
                    escalacao.titulares[posicao] = [...existentes, ...candidatos_validos.slice(0, alvo)];
                } else {
                    escalacao.titulares[posicao] = candidatos_validos.slice(0, alvo);
                }
            }
            
            // Calcular custo da posição e atualizar custo total (como no Python)
            const custo_posicao = escalacao.titulares[posicao].reduce((sum, j) => sum + this._getPreco(j), 0);
            escalacao.custo_total += custo_posicao;
            escalados_ids.push(...escalacao.titulares[posicao].map(j => j.atleta_id));
            
            this.log(`Custo da posição ${posicao}: R$ ${custo_posicao.toFixed(2)}. IDs escalados: ${escalados_ids.join(', ')}`);
            this.log(`Escalados ${alvo} titulares para ${posicao}: ${escalacao.titulares[posicao].map(j => j.apelido).join(', ')}`);
        }
        
        // Processar posições desescaladas (se houver)
        const efetivas_desescaladas = posicoes_desescaladas.filter(pos => {
            const qt = this.formacao[`qt_${this.plural_to_singular[pos]}`];
            return (escalacao.titulares[pos] || []).length < qt;
        });
        
        if (efetivas_desescaladas.length > 0) {
            // Buscar candidatos para posições desescaladas
            const candidatos = {};
            for (const pos of efetivas_desescaladas) {
                const qt = this.formacao[`qt_${this.plural_to_singular[pos]}`];
                const quantidade_candidatos = ['goleiros', 'tecnicos', 'zagueiros'].includes(pos) ? 5 : 10;
                
                candidatos[pos] = this.fetchMelhoresJogadoresPorPosicao(
                    this.plural_to_singular[pos],
                    quantidade_candidatos,
                    null,
                    escalados_ids
                );
            }
            
            // Gerar combinações (simplificado - apenas primeira válida)
            const orcamento_restante = this.patrimonio - escalacao.custo_total;
            
            // Tentar primeira combinação válida (simplificado - apenas primeira válida)
            // Gerar todas as combinações possíveis (simplificado para performance)
            let melhor_combo = null;
            let melhor_score = -1;
            
            // Gerar combinações simples (primeira válida)
            const combos_por_pos = {};
            for (const pos of efetivas_desescaladas) {
                const qt = this.formacao[`qt_${this.plural_to_singular[pos]}`];
                const faltam = qt - (escalacao.titulares[pos] || []).length;
                if (faltam > 0 && candidatos[pos].length >= faltam) {
                    // Usar apenas a primeira combinação válida
                    combos_por_pos[pos] = candidatos[pos].slice(0, faltam);
                }
            }
            
            // Verificar se todas as posições têm combinações
            if (Object.keys(combos_por_pos).length === efetivas_desescaladas.length) {
                const combo = [];
                for (const pos of efetivas_desescaladas) {
                    combo.push(...combos_por_pos[pos]);
                }
                
                const custo_combo = combo.reduce((sum, j) => sum + this._getPreco(j), 0);
                
                if (custo_combo <= orcamento_restante) {
                    melhor_combo = combo;
                }
            }
            
            if (melhor_combo) {
                // Aplicar combinação
                for (const pos of efetivas_desescaladas) {
                    const qt = this.formacao[`qt_${this.plural_to_singular[pos]}`];
                    const faltam = qt - (escalacao.titulares[pos] || []).length;
                    if (faltam > 0 && combos_por_pos[pos]) {
                        const jogadores = combos_por_pos[pos];
                        
                        if (escalacao.titulares[pos].length > 0) {
                            escalacao.titulares[pos] = [...escalacao.titulares[pos], ...jogadores];
                        } else {
                            escalacao.titulares[pos] = jogadores;
                        }
                        
                        escalacao.custo_total += jogadores.reduce((sum, j) => sum + this._getPreco(j), 0);
                        escalados_ids.push(...jogadores.map(j => j.atleta_id));
                    }
                }
            } else {
                this.log(`[ERRO] Nenhuma combinação válida encontrada para posições desescaladas: ${efetivas_desescaladas.join(', ')}`);
                this.log(`Orçamento restante: R$ ${orcamento_restante.toFixed(2)}`);
                for (const pos of efetivas_desescaladas) {
                    const qt = this.formacao[`qt_${this.plural_to_singular[pos]}`];
                    const faltam = qt - (escalacao.titulares[pos] || []).length;
                    const cand = candidatos[pos] || [];
                    this.log(`Posição ${pos}: faltam ${faltam}, candidatos disponíveis: ${cand.length}`);
                    if (cand.length > 0) {
                        const custo_cand = cand.slice(0, faltam).reduce((sum, j) => sum + this._getPreco(j), 0);
                        this.log(`Custo dos primeiros ${faltam} candidatos: R$ ${custo_cand.toFixed(2)}`);
                    }
                }
                return null;
            }
        }
        
        // Validar número de jogadores
        for (const pos of Object.keys(this.posicao_ids)) {
            const qt_esperada = this.formacao[`qt_${this.plural_to_singular[pos]}`];
            const qt_atual = (escalacao.titulares[pos] || []).length;
            if (qt_atual !== qt_esperada) {
                this.log(`Erro: Quantidade inválida para ${pos}. Esperado: ${qt_esperada}, Encontrado: ${qt_atual}`);
                return null;
            }
        }
        
        // Selecionar reservas para outras posições (exceto posição do capitão e técnicos)
        for (const posicao of this.prioridades) {
            if (posicao === posicaoCapitao || posicao === 'tecnicos' || posicao === 'goleiros') {
                continue; // Goleiros serão tratados separadamente, capitão já tem reserva de luxo
            }
            
            if (escalacao.titulares[posicao] && escalacao.titulares[posicao].length > 0) {
                const min_preco_titular = Math.min(...escalacao.titulares[posicao].map(j => this._getPreco(j)));
                
                const candidatos_reserva = this.fetchMelhoresJogadoresPorPosicao(
                    this.plural_to_singular[posicao],
                    5,
                    min_preco_titular,
                    escalados_ids
                );
                
                if (candidatos_reserva.length > 0) {
                    escalacao.reservas[posicao] = [candidatos_reserva[0]];
                    this.log(`Reserva para ${posicao}: ${candidatos_reserva[0].apelido} (R$ ${this._getPreco(candidatos_reserva[0]).toFixed(2)})`);
                }
            }
        }
        
        // Aplicar hack do goleiro se solicitado
        if (hackGoleiro && escalacao.titulares.goleiros && escalacao.titulares.goleiros.length > 0) {
            this.log('Aplicando hack do goleiro...');
            // Lógica simplificada: manter o goleiro atual como reserva e buscar um goleiro mais caro que não joga
            // Por enquanto, apenas marcar como hack aplicado
            // Nota: Esta lógica completa requer acesso a dados de status dos jogadores da API
            this.log('Hack do goleiro: Lógica completa requer dados adicionais de status dos jogadores');
        }
        
        // Calcular pontuação total
        escalacao.pontuacao_total = 0;
        for (const pos of Object.keys(escalacao.titulares)) {
            for (const jogador of escalacao.titulares[pos]) {
                escalacao.pontuacao_total += jogador.pontuacao_total || 0;
            }
        }
        
        return escalacao;
    }
    
    /**
     * Calcula a escalação ideal
     */
    async calcular(hackGoleiro = false, fecharDefesa = false, posicaoCapitao = 'atacantes') {
        this.posicaoCapitao = posicaoCapitao; // Armazenar para uso em outros métodos
        this.log('Iniciando cálculo da escalação ideal...');
        this.log(`Hack do goleiro: ${hackGoleiro ? 'Sim' : 'Não'}`);
        this.log(`Fechar defesa: ${fecharDefesa ? 'Sim' : 'Não'}`);
        this.log(`Posição do capitão: ${posicaoCapitao}`);
        this.log(`Patrimônio disponível: R$ ${this.patrimonio.toFixed(2)}`);
        
        // Verificar se há rankings suficientes
        const posicoes_necessarias = ['goleiro', 'zagueiro', 'lateral', 'meia', 'atacante', 'treinador'];
        const posicoes_faltando = [];
        
        for (const pos of posicoes_necessarias) {
            const ranking = this.rankings_por_posicao[pos] || [];
            if (ranking.length === 0) {
                posicoes_faltando.push(pos);
            } else {
                this.log(`Ranking ${pos}: ${ranking.length} jogadores disponíveis`);
            }
        }
        
        if (posicoes_faltando.length > 0) {
            throw new Error(`Rankings faltando para as posições: ${posicoes_faltando.join(', ')}. Calcule os rankings das posições primeiro.`);
        }
        
        if (!this.patrimonio || this.patrimonio <= 0) {
            const errorMsg = this.patrimonio_error || 'Patrimônio não disponível. Verifique suas credenciais do Cartola.';
            throw new Error(errorMsg);
        }
        
        // Tentar escalação com desescalação progressiva
        let posicoes_desescaladas = [];
        let escalacao = null;
        let tentativa = 0;
        
        while (!escalacao && posicoes_desescaladas.length <= this.ordem_desescalacao.length) {
            tentativa++;
            this.log(`Tentativa ${tentativa}: Tentando escalação${posicoes_desescaladas.length > 0 ? ` (desescaladas: ${posicoes_desescaladas.join(', ')})` : ''}...`);
            
            escalacao = this.tryEscalacao(posicoes_desescaladas, hackGoleiro, fecharDefesa, posicaoCapitao);
            
            if (!escalacao) {
                if (posicoes_desescaladas.length < this.ordem_desescalacao.length) {
                    const proxima_posicao = this.ordem_desescalacao[posicoes_desescaladas.length];
                    posicoes_desescaladas.push(proxima_posicao);
                    this.log(`Sem escalação válida. Desescalando ${proxima_posicao}...`);
                } else {
                    this.log(`Todas as posições foram desescaladas e ainda não foi possível encontrar uma escalação válida.`);
                    break;
                }
            }
        }
        
        if (!escalacao) {
            // Tentar fornecer mais informações sobre o problema
            let debug_info = [];
            debug_info.push(`Patrimônio: R$ ${this.patrimonio.toFixed(2)}`);
            for (const pos of posicoes_necessarias) {
                const ranking = this.rankings_por_posicao[pos] || [];
                if (ranking.length > 0) {
                    const preco_medio = ranking.slice(0, 5).reduce((sum, j) => sum + this._getPreco(j), 0) / Math.min(5, ranking.length);
                    const preco_total_top5 = ranking.slice(0, 5).reduce((sum, j) => sum + this._getPreco(j), 0);
                    debug_info.push(`${pos}: ${ranking.length} jogadores, preço médio top 5: R$ ${preco_medio.toFixed(2)}, custo total top 5: R$ ${preco_total_top5.toFixed(2)}`);
                } else {
                    debug_info.push(`${pos}: Nenhum jogador disponível`);
                }
            }
            const msg = `Não foi possível encontrar uma escalação válida mesmo após desescalar todas as posições.\n\n` +
                       `Informações de debug:\n${debug_info.join('\n')}\n\n` +
                       `Possíveis causas:\n` +
                       `- Patrimônio insuficiente para escalar os jogadores disponíveis\n` +
                       `- Rankings não têm jogadores suficientes\n` +
                       `- Tente calcular os rankings novamente ou verificar se o patrimônio está correto`;
            throw new Error(msg);
        }
        
        // Selecionar capitão
        if (escalacao.titulares[posicaoCapitao] && escalacao.titulares[posicaoCapitao].length > 0) {
            const capitao = escalacao.titulares[posicaoCapitao].reduce((max, j) => 
                (j.pontuacao_total || 0) > (max.pontuacao_total || 0) ? j : max
            );
            
            // Marcar capitão
            for (const pos of Object.keys(escalacao.titulares)) {
                for (const jogador of escalacao.titulares[pos]) {
                    if (jogador.atleta_id === capitao.atleta_id) {
                        jogador.eh_capitao = true;
                    }
                }
            }
            
            this.log(`Capitão selecionado: ${capitao.apelido} (${posicaoCapitao})`);
        }
        
        // Marcar reserva de luxo
        if (escalacao.reservas[posicaoCapitao] && escalacao.reservas[posicaoCapitao].length > 0) {
            escalacao.reservas[posicaoCapitao][0].eh_reserva_luxo = true;
            this.log(`Reserva de luxo: ${escalacao.reservas[posicaoCapitao][0].apelido} (${posicaoCapitao})`);
        }
        
        escalacao.patrimonio = this.patrimonio;
        this.log(`Escalação calculada com sucesso! Custo: R$ ${escalacao.custo_total.toFixed(2)}, Pontuação: ${escalacao.pontuacao_total.toFixed(2)}`);
        
        return escalacao;
    }
}

