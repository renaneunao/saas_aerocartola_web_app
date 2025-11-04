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
        
        // Prioridades de escalação (exatamente como no Python)
        this.prioridades = ['atacantes', 'laterais', 'meias', 'zagueiros', 'goleiros', 'tecnicos'];
        // Ordem de desescalação (inversa das prioridades, como no Python)
        this.ordem_desescalacao = this.prioridades.slice().reverse();
        
        // top_n e top_n_reduzido (exatamente como no Python)
        this.top_n = 10;  // Número de candidatos para atacantes, laterais, meias
        this.top_n_reduzido = 5;  // Número de candidatos para goleiros, técnicos, zagueiros
        
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
            custo_total: 0,  // Começa do zero e vai incrementando posição por posição
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
        
        this.log(`\n🔧 Iniciando tentativa de escalação`);
        this.log(`Posições desescaladas: ${posicoes_desescaladas.length > 0 ? posicoes_desescaladas.join(', ') : 'Nenhuma'}`);
        this.log(`Ordem de prioridades: ${this.prioridades.join(' → ')}`);
        this.log(`Custo inicial: R$ ${escalacao.custo_total.toFixed(2)}\n`);
        
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
        
        // Escalar posições que não foram desescaladas (como no Python)
        // Processa posição por posição na ordem de prioridades
        for (const posicao of this.prioridades) {
            if (posicoes_desescaladas.includes(posicao)) {
                // Se for defesa com pré-definição pela estratégia 2, não pular: vamos completar as vagas
                if (fecharDefesa && ['goleiros', 'zagueiros', 'laterais'].includes(posicao)) {
                    const qt = this.formacao[`qt_${this.plural_to_singular[posicao]}`];
                    if (escalacao.titulares[posicao].length >= qt) {
                        this.log(`⏭️ Pulando ${posicao}: já completa pelos pré-definidos`);
                        continue;
                    }
                } else {
                    // Pular posições que serão tratadas nas combinações
                    this.log(`⏭️ Pulando ${posicao}: será tratada nas combinações`);
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
            
            // Buscar candidatos - EXATAMENTE como no Python: quantidade_busca * 2
            const candidatos = this.fetchMelhoresJogadoresPorPosicao(
                this.plural_to_singular[posicao],
                quantidade_busca * 2,
                null,
                escalados_ids
            );
            
            // Filtrar por orçamento - EXATAMENTE como no Python
            // Python: custo_temp = escalacao['custo_total']
            // Python: for candidato in candidatos: if custo_temp + candidato['preco_num'] <= patrimonio and len(selecionados) < quantidade_busca
            let candidatos_validos = [];
            let custo_temp = escalacao.custo_total;  // Começar do custo total atual
            let selecionados = [];
            
            // Filtrar candidatos - EXATAMENTE como no Python
            // Python: for candidato in candidatos:
            //   if custo_temp + candidato['preco_num'] <= patrimonio and len(selecionados) < quantidade_busca:
            //       selecionados.append(candidato)
            //       custo_temp += candidato['preco_num']
            //   if len(selecionados) == quantidade_busca: break
            // candidatos_validos = selecionados
            for (const candidato of candidatos) {
                const preco_candidato = this._getPreco(candidato);
                if (custo_temp + preco_candidato <= this.patrimonio && selecionados.length < quantidade_busca) {
                    selecionados.push(candidato);
                    custo_temp += preco_candidato;
                }
                if (selecionados.length === quantidade_busca) {
                    break;
                }
            }
            candidatos_validos = selecionados;
            
            // Verificar se há candidatos suficientes - EXATAMENTE como no Python
            // Python: needed_check = alvo
            // Python: if len(candidatos_validos) < needed_check: return None
            const needed_check = alvo;
            if (candidatos_validos.length < needed_check) {
                this.log(`Não há jogadores suficientes para ${posicao} (necessários: ${needed_check}) dentro do orçamento.`);
                return null;
            }
            
            // Atribuir titulares e reserva de luxo - EXATAMENTE como no Python
            if (posicao === posicaoCapitao && posicao !== 'tecnicos' && candidatos_validos.length >= needed_check) {
                // Python: candidatos_validos.sort(key=lambda x: x['preco_num'], reverse=True)
                candidatos_validos.sort((a, b) => this._getPreco(b) - this._getPreco(a));
                
                // Python: escalacao['titulares'][posicao] = candidatos_validos[:needed_check]
                if (existentes.length > 0 && restantes !== null) {
                    const novos = candidatos_validos.slice(0, needed_check);
                    escalacao.titulares[posicao] = [...existentes, ...novos];
                    if (candidatos_validos.length > needed_check) {
                        escalacao.reservas[posicao] = [candidatos_validos[needed_check]];
                    }
                } else {
                    escalacao.titulares[posicao] = candidatos_validos.slice(0, needed_check);
                    if (candidatos_validos.length > needed_check) {
                        escalacao.reservas[posicao] = [candidatos_validos[needed_check]];
                    }
                }
            } else {
                // Python: escalacao['titulares'][posicao] = candidatos_validos[:needed_check]
                if (existentes.length > 0 && restantes !== null) {
                    const novos = candidatos_validos.slice(0, needed_check);
                    escalacao.titulares[posicao] = [...existentes, ...novos];
                } else {
                    escalacao.titulares[posicao] = candidatos_validos.slice(0, needed_check);
                }
            }
            
            // Calcular custo da posição - EXATAMENTE como no Python
            // Python: custo_posicao = sum(j['preco_num'] for j in escalacao['titulares'][posicao])
            // Python: escalacao['custo_total'] += custo_posicao
            const custo_posicao = escalacao.titulares[posicao].reduce((sum, j) => sum + this._getPreco(j), 0);
            escalacao.custo_total += custo_posicao;
            escalados_ids.push(...escalacao.titulares[posicao].map(j => j.atleta_id));
        }
        
        // Tentar combinações para posições desescaladas - EXATAMENTE como no Python
        const orcamento_restante = this.patrimonio - escalacao.custo_total;
        
        // Remover das desescaladas as posições que já estão completas - EXATAMENTE como no Python
        const efetivas_desescaladas = [];
        for (const pos of posicoes_desescaladas) {
            const qt = this.formacao[`qt_${this.plural_to_singular[pos]}`];
            if ((escalacao.titulares[pos] || []).length < qt) {
                efetivas_desescaladas.push(pos);
            }
        }
        
        // Se não há posições desescaladas, todas as posições já foram escaladas - EXATAMENTE como no Python
        if (efetivas_desescaladas.length === 0) {
            return escalacao;
        }
        
        // Buscar candidatos para posições desescaladas - EXATAMENTE como no Python
        // Python: quantidade_candidatos = top_n_reduzido if pos in ['goleiros', 'tecnicos', 'zagueiros'] else top_n
        const candidatos = {};
        for (const pos of efetivas_desescaladas) {
            const quantidade_candidatos = ['goleiros', 'tecnicos', 'zagueiros'].includes(pos) ? this.top_n_reduzido : this.top_n;
            candidatos[pos] = this.fetchMelhoresJogadoresPorPosicao(
                this.plural_to_singular[pos],
                quantidade_candidatos,
                null,
                escalados_ids
            );
        }
        
        // Gerar combinações - EXATAMENTE como no Python
        // Python: combos_pos = list(combinations(candidatos[pos], qt))
        // Python: combos_posicoes.append([(pos, combo) for combo in combos_pos])
        // Python: for combo_outras in product(*combos_posicoes):
        
        // Função auxiliar para gerar combinações (equivalente ao Python combinations)
        const gerarCombinacoes = (items, qt) => {
            if (qt === 0) return [[]];
            if (qt > items.length) return [];
            if (qt === 1) return items.map(item => [item]);
            
            const combinacoes = [];
            for (let i = 0; i <= items.length - qt; i++) {
                const subCombinacoes = gerarCombinacoes(items.slice(i + 1), qt - 1);
                for (const sub of subCombinacoes) {
                    combinacoes.push([items[i], ...sub]);
                }
            }
            return combinacoes;
        };
        
        // Função auxiliar para gerar produto cartesiano (equivalente ao Python product)
        const produtoCartesiano = function*(arrays) {
            if (arrays.length === 0) {
                yield [];
                return;
            }
            if (arrays.length === 1) {
                for (const item of arrays[0]) {
                    yield [item];
                }
                return;
            }
            
            const [first, ...rest] = arrays;
            const restProduct = produtoCartesiano(rest);
            
            for (const item of first) {
                for (const restCombo of restProduct) {
                    yield [item, ...restCombo];
                }
            }
        };
        
        // Gerar combinações por posição - EXATAMENTE como no Python
        const combos_posicoes = [];
        for (const pos of efetivas_desescaladas) {
            const qt = this.formacao[`qt_${this.plural_to_singular[pos]}`];
            const combos_pos = gerarCombinacoes(candidatos[pos], qt);
            combos_posicoes.push(combos_pos.map(combo => ({ pos, combo })));
        }
        
        // Gerar produto cartesiano e avaliar combinações - EXATAMENTE como no Python
        // Python: for combo_outras in product(*combos_posicoes):
        // Python:   jogadores_outras = []
        // Python:   for pos, combo_pos in combo_outras: jogadores_outras.extend(combo_pos)
        // Python:   combinacoes.append(jogadores_outras)
        // Python: for combo in combinacoes:
        // Python:   if custo_combo <= orcamento_restante: melhor_combinacao = combo; break
        
        let melhor_combinacao = null;
        for (const combo_outras of produtoCartesiano(combos_posicoes)) {
            const jogadores_outras = [];
            for (const { combo } of combo_outras) {
                jogadores_outras.push(...combo);
            }
            
            const custo_combo = jogadores_outras.reduce((sum, j) => sum + this._getPreco(j), 0);
            
            if (custo_combo <= orcamento_restante) {
                melhor_combinacao = jogadores_outras;
                break; // Usar primeira válida (como no Python)
            }
        }
        
        if (melhor_combinacao) {
            // Aplicar combinação - EXATAMENTE como no Python
            // Python: for pos in efetivas_desescaladas:
            // Python:   jogadores = [j for j in melhor_combinacao if j in candidatos[pos]][:qt]
            // Python:   escalacao['titulares'][pos] = jogadores
            for (const pos of efetivas_desescaladas) {
                const qt = this.formacao[`qt_${this.plural_to_singular[pos]}`];
                const jogadores = melhor_combinacao.filter(j => candidatos[pos].includes(j)).slice(0, qt);
                
                if (jogadores.length !== qt) {
                    this.log(`Erro: Combinação não contém ${qt} jogadores para ${pos}. Jogadores encontrados: ${jogadores.length}`);
                    return null;
                }
                
                escalacao.titulares[pos] = jogadores;
            }
            
            const custo_posicao = melhor_combinacao.reduce((sum, j) => sum + this._getPreco(j), 0);
            escalacao.custo_total += custo_posicao;
            escalados_ids.push(...melhor_combinacao.map(j => j.atleta_id));
            
            return escalacao;
        } else {
            this.log("Nenhuma combinação válida encontrada.");
            return null;
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
        this.log('\n═══════════════════════════════════════════════════════════');
        this.log('🚀 INICIANDO CÁLCULO DA ESCALAÇÃO IDEAL');
        this.log('═══════════════════════════════════════════════════════════');
        this.log(`Patrimônio disponível: R$ ${this.patrimonio.toFixed(2)}`);
        this.log(`Hack do goleiro: ${hackGoleiro ? 'Sim' : 'Não'}`);
        this.log(`Fechar defesa: ${fecharDefesa ? 'Sim' : 'Não'}`);
        this.log(`Posição do capitão: ${posicaoCapitao}`);
        this.log(`Formação: ${JSON.stringify(this.formacao)}`);
        this.log('═══════════════════════════════════════════════════════════\n');
        
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
            this.log('\n❌❌❌ ERRO FINAL: NÃO FOI POSSÍVEL ENCONTRAR ESCALAÇÃO VÁLIDA ❌❌❌');
            this.log(`Tentativas realizadas: ${tentativa}`);
            this.log(`Posições desescaladas: ${posicoes_desescaladas.join(', ')}`);
            this.log('\n--- Informações de debug detalhadas: ---');
            let debug_info = [];
            debug_info.push(`Patrimônio: R$ ${this.patrimonio.toFixed(2)}`);
            for (const pos of posicoes_necessarias) {
                const ranking = this.rankings_por_posicao[pos] || [];
                if (ranking.length > 0) {
                    const top5 = ranking.slice(0, 5);
                    const preco_medio = top5.reduce((sum, j) => sum + this._getPreco(j), 0) / top5.length;
                    const preco_total_top5 = top5.reduce((sum, j) => sum + this._getPreco(j), 0);
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
                       `- Tente calcular os rankings novamente ou verificar se o patrimônio está correto.`;
            throw new Error(msg);
        }
        
        // Validar número de jogadores por posição - EXATAMENTE como no Python
        for (const posicao of Object.keys(this.posicao_ids)) {
            const qt_esperada = this.formacao[`qt_${this.plural_to_singular[posicao]}`];
            const qt_atual = (escalacao.titulares[posicao] || []).length;
            if (qt_atual !== qt_esperada) {
                this.log(`Erro: Quantidade inválida de jogadores para ${posicao}. Esperado: ${qt_esperada}, Encontrado: ${qt_atual}`);
                throw new Error(`Quantidade inválida de jogadores para ${posicao}. Esperado: ${qt_esperada}, Encontrado: ${qt_atual}`);
            }
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
        
        this.log('\n═══════════════════════════════════════════════════════════');
        this.log('✅ ESCALAÇÃO CALCULADA COM SUCESSO!');
        this.log('═══════════════════════════════════════════════════════════');
        this.log(`Custo total: R$ ${escalacao.custo_total.toFixed(2)}`);
        this.log(`Patrimônio: R$ ${this.patrimonio.toFixed(2)}`);
        this.log(`Orçamento restante: R$ ${(this.patrimonio - escalacao.custo_total).toFixed(2)}`);
        this.log(`Pontuação total: ${escalacao.pontuacao_total.toFixed(2)}`);
        this.log('\n--- Resumo por posição: ---');
        Object.keys(escalacao.titulares).forEach(pos => {
            const jogadores = escalacao.titulares[pos] || [];
            if (jogadores.length > 0) {
                const custo_pos = jogadores.reduce((sum, j) => sum + this._getPreco(j), 0);
                const pontuacao_pos = jogadores.reduce((sum, j) => sum + (j.pontuacao_total || 0), 0);
                this.log(`  ${pos}: ${jogadores.length} jogador(es) - Custo: R$ ${custo_pos.toFixed(2)}, Pontuação: ${pontuacao_pos.toFixed(2)}`);
            }
        });
        this.log('═══════════════════════════════════════════════════════════\n');
        
        return escalacao;
    }
}

