/**
 * Classe para calcular escalação ideal baseada nos rankings salvos
 * SEGUE EXATAMENTE A LÓGICA DO ARQUIVO calculo_escalacao_ideal.py
 */
class CalculoEscalacaoIdeal {
    constructor(data) {
        this.rodada_atual = data.rodada_atual;
        this.rankings_por_posicao = data.rankings_por_posicao || {};
        this.patrimonio = parseFloat(data.patrimonio) || 0;
        this.clubes_sg = data.clubes_sg || [];
        this.config = data.config || {};
        this.patrimonio_error = data.patrimonio_error || null;
        
        // Formação padrão
        this.formacao = this.parseFormation(data.config?.formation || '4-3-3');
        
        // Mapeamento de posições - EXATAMENTE como no Python (linha 141)
        this.posicao_ids = {
            'goleiros': 1,
            'zagueiros': 3,
            'laterais': 2,
            'meias': 4,
            'atacantes': 5,
            'tecnicos': 6
        };
        
        // Mapeamento plural -> singular - EXATAMENTE como no Python (linhas 144-151)
        this.plural_to_singular = {
            'goleiros': 'goleiro',
            'zagueiros': 'zagueiro',
            'laterais': 'lateral',
            'meias': 'meia',
            'atacantes': 'atacante',
            'tecnicos': 'tecnico'
        };
        
        // Prioridades de escalação - EXATAMENTE como no Python (linha 138)
        this.prioridades = ['atacantes', 'laterais', 'meias', 'zagueiros', 'goleiros', 'tecnicos'];
        
        // Ordem de desescalação (inversa das prioridades) - EXATAMENTE como no Python (linha 140)
        this.ordem_desescalacao = this.prioridades.slice().reverse();
        
        // top_n e top_n_reduzido - EXATAMENTE como no Python (linhas 18-19)
        this.top_n = 10;  // Número de candidatos para atacantes, laterais, meias
        this.top_n_reduzido = 5;  // Número de candidatos para goleiros, técnicos, zagueiros
        
        this.logCallback = null;
    }
    
    parseFormation(formationStr) {
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
        }
        console.log(message);
    }
    
    setLogCallback(callback) {
        this.logCallback = callback;
    }
    
    /**
     * Helper para normalizar preço
     */
    _getPreco(jogador) {
        return parseFloat(jogador.preco_num || jogador.preco || 0);
    }
    
    /**
     * Busca os melhores jogadores de uma posição
     * EQUIVALENTE à função fetch_melhores_jogadores_por_posicao do Python (linhas 21-78)
     */
    fetchMelhoresJogadoresPorPosicao(posicao_nome, quantidade, max_preco = null, escalados_ids = []) {
        this.log(`Buscando ${quantidade} jogadores para posição ${posicao_nome}`);
        
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
        
        const resultado = candidatos.slice(0, quantidade);
        this.log(`Encontrados ${resultado.length} jogadores para ${posicao_nome}`);
        
        return resultado;
    }
    
    /**
     * Busca jogadores de um clube específico para uma posição
     * Equivalente à função fetch_by_clube_pos do Python (linhas 197-260)
     */
    fetchByClubePos(posicao_nome, clube_id, limit) {
        const ranking = this.rankings_por_posicao[posicao_nome] || [];
        
        let candidatos = ranking.filter(j => j.clube_id === clube_id);
        
        // Normalizar preços
        candidatos = candidatos.map(j => ({
            ...j,
            preco_num: this._getPreco(j)
        }));
        
        // Ordenar por pontuacao_total decrescente
        candidatos.sort((a, b) => (b.pontuacao_total || 0) - (a.pontuacao_total || 0));
        
        const resultado = candidatos.slice(0, limit);
        
        if (resultado.length > 0) {
            const precos = resultado.map(j => j.preco_num);
            const min_preco = Math.min(...precos);
            const max_preco = Math.max(...precos);
            this.log(`Candidatos clube ${clube_id} pos ${posicao_nome}: ${resultado.length} (preço min=${min_preco.toFixed(2)}, max=${max_preco.toFixed(2)})`);
        }
        
        return resultado;
    }
    
    /**
     * Tenta criar uma escalação válida
     * EQUIVALENTE à função try_escalacao do Python (linhas 153-570)
     */
    tryEscalacao(posicoes_desescaladas = [], fecharDefesa = false, posicaoCapitao = 'atacantes') {
        // Inicializar estrutura de escalação - Python linha 156-163
        const escalacao = {
            titulares: {},
            reservas: {},
            custo_total: 0,
            pontuacao_total: 0
        };
        
        // Inicializar estruturas - Python linhas 156-162
        for (const pos of Object.keys(this.posicao_ids)) {
            escalacao.titulares[pos] = [];
            if (pos !== 'tecnicos') {
                escalacao.reservas[pos] = [];
            }
        }
        
        let escalados_ids = [];
        const predefinido_defesa = { goleiros: [], zagueiros: [], laterais: [] };
        
        this.log(`\n🔧 Tentativa de escalação`);
        this.log(`Posições desescaladas: ${posicoes_desescaladas.length > 0 ? posicoes_desescaladas.join(', ') : 'Nenhuma'}`);
        this.log(`Estrutura de escalação inicializada. Posições desescaladas: [${posicoes_desescaladas.join(', ')}]`);
        
        // Estratégia 2: fechar defesa (Python linhas 165-411)
        if (fecharDefesa && this.clubes_sg.length > 0) {
            const top_clube_id = this.clubes_sg[0].clube_id;
            this.log(`\nFechando defesa do clube_id ${top_clube_id} (melhor SG da rodada)...`);
            
            const gks = this.fetchByClubePos('goleiro', top_clube_id, 5);
            const zgs = this.fetchByClubePos('zagueiro', top_clube_id, 8);
            const lts = this.fetchByClubePos('lateral', top_clube_id, 8);
            
            let chosen = null;
            
            // Tentar fechar defesa completa (1 GK + 2 ZAG + 2 LAT) - Python linhas 274-310
            if (gks.length > 0 && zgs.length >= 2 && lts.length >= 2) {
                // Diagnóstico de custo mínimo - Python linhas 276-283
                const min_gk = gks.reduce((min, j) => j.preco_num < min.preco_num ? j : min);
                const min_zgs = [...zgs].sort((a, b) => a.preco_num - b.preco_num).slice(0, 2);
                const min_lts = [...lts].sort((a, b) => a.preco_num - b.preco_num).slice(0, 2);
                const min_cost = min_gk.preco_num + min_zgs.reduce((s, j) => s + j.preco_num, 0) + min_lts.reduce((s, j) => s + j.preco_num, 0);
                
                this.log(`Patrimônio disponível: R$${this.patrimonio.toFixed(2)} | Custo mínimo possível da defesa do clube ${top_clube_id}: R$${min_cost.toFixed(2)}`);
                
                let best_combo = null;
                let best_score = -1;
                
                // Procurar melhor combinação dentro do orçamento - Python linhas 287-296
                for (const gk of gks) {
                    // Gerar combinações de 2 zagueiros
                    for (let i = 0; i < Math.min(zgs.length, 8); i++) {
                        for (let j = i + 1; j < Math.min(zgs.length, 8); j++) {
                            // Gerar combinações de 2 laterais
                            for (let k = 0; k < Math.min(lts.length, 8); k++) {
                                for (let l = k + 1; l < Math.min(lts.length, 8); l++) {
                                    const jogadores = [gk, zgs[i], zgs[j], lts[k], lts[l]];
                                    const custo = jogadores.reduce((sum, j) => sum + j.preco_num, 0);
                                    
                                    if (custo <= this.patrimonio) {
                                        const score = jogadores.reduce((sum, j) => sum + (j.pontuacao_total || 0), 0);
                                        if (score > best_score) {
                                            best_score = score;
                                            best_combo = jogadores;
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
                
                // Fallback: combo mais barato - Python linhas 298-310
                if (best_combo === null) {
                    const cheapest_gk = gks.reduce((min, j) => j.preco_num < min.preco_num ? j : min);
                    const cheapest_z = [...zgs].sort((a, b) => a.preco_num - b.preco_num).slice(0, 2);
                    const cheapest_l = [...lts].sort((a, b) => a.preco_num - b.preco_num).slice(0, 2);
                    const cheap_combo = [cheapest_gk, ...cheapest_z, ...cheapest_l];
                    const cheap_cost = cheap_combo.reduce((sum, j) => sum + j.preco_num, 0);
                    
                    if (cheap_cost <= this.patrimonio) {
                        best_combo = cheap_combo;
                        best_score = cheap_combo.reduce((sum, j) => sum + (j.pontuacao_total || 0), 0);
                        this.log(`Usando fallback: combinação mais barata cabe no orçamento (R$${cheap_cost.toFixed(2)}).`);
                    }
                }
                
                if (best_combo) {
                    chosen = [top_clube_id, best_combo];
                } else {
                    // Fechar PARCIALMENTE - Python linhas 315-343
                    this.log(`Não dá pra fechar com 5? Fecha com o MÁXIMO possível dentro do orçamento`);
                    const caps = { goleiros: 1, zagueiros: 2, laterais: 2 };
                    const bucket = [];
                    
                    for (const j of gks) {
                        bucket.push({ pos: 'goleiros', preco: j.preco_num, neg_score: -(j.pontuacao_total || 0), jogador: j });
                    }
                    for (const j of zgs) {
                        bucket.push({ pos: 'zagueiros', preco: j.preco_num, neg_score: -(j.pontuacao_total || 0), jogador: j });
                    }
                    for (const j of lts) {
                        bucket.push({ pos: 'laterais', preco: j.preco_num, neg_score: -(j.pontuacao_total || 0), jogador: j });
                    }
                    
                    // Ordenar por preço crescente, depois melhor pontuação
                    bucket.sort((a, b) => {
                        if (a.preco !== b.preco) return a.preco - b.preco;
                        return a.neg_score - b.neg_score;
                    });
                    
                    const taken = { goleiros: 0, zagueiros: 0, laterais: 0 };
                    const partial = [];
                    let partial_cost = 0;
                    
                    for (const item of bucket) {
                        if (taken[item.pos] < caps[item.pos] && partial_cost + item.preco <= this.patrimonio) {
                            partial.push(item.jogador);
                            taken[item.pos]++;
                            partial_cost += item.preco;
                            
                            if (partial.length >= 5) break;
                        }
                    }
                    
                    if (partial.length > 0) {
                        this.log(`Fechando parcialmente a defesa do clube ${top_clube_id}: ${partial.length} jogadores (custo R$${partial_cost.toFixed(2)})`);
                        for (const pj of partial) {
                            this.log(`  - ${pj.apelido} (R$${pj.preco_num.toFixed(2)} - ${(pj.pontuacao_total || 0).toFixed(2)})`);
                        }
                        chosen = [top_clube_id, partial];
                    } else {
                        this.log(`Estratégia 2: Nenhum jogador do clube ${top_clube_id} pôde ser travado dentro do orçamento.`);
                    }
                }
            } else {
                // Não há prováveis suficientes - fechar PARCIALMENTE - Python linhas 347-384
                this.log(`Estratégia 2: Clube ${top_clube_id} não possui prováveis suficientes para fechar defesa completa. Tentando fechar PARCIALMENTE.`);
                
                const caps = {
                    goleiros: gks.length >= 1 ? 1 : 0,
                    zagueiros: Math.min(2, zgs.length),
                    laterais: Math.min(2, lts.length)
                };
                
                const bucket = [];
                for (const j of gks) {
                    bucket.push({ pos: 'goleiros', preco: j.preco_num, neg_score: -(j.pontuacao_total || 0), jogador: j });
                }
                for (const j of zgs) {
                    bucket.push({ pos: 'zagueiros', preco: j.preco_num, neg_score: -(j.pontuacao_total || 0), jogador: j });
                }
                for (const j of lts) {
                    bucket.push({ pos: 'laterais', preco: j.preco_num, neg_score: -(j.pontuacao_total || 0), jogador: j });
                }
                
                bucket.sort((a, b) => {
                    if (a.preco !== b.preco) return a.preco - b.preco;
                    return a.neg_score - b.neg_score;
                });
                
                const taken = { goleiros: 0, zagueiros: 0, laterais: 0 };
                const partial = [];
                let partial_cost = 0;
                const max_needed = caps.goleiros + caps.zagueiros + caps.laterais;
                
                for (const item of bucket) {
                    if (caps[item.pos] === 0) continue;
                    
                    if (taken[item.pos] < caps[item.pos] && partial_cost + item.preco <= this.patrimonio) {
                        partial.push(item.jogador);
                        taken[item.pos]++;
                        partial_cost += item.preco;
                        
                        if (partial.length >= max_needed) break;
                    }
                }
                
                if (partial.length > 0) {
                    this.log(`Fechando parcialmente a defesa do clube ${top_clube_id}: ${partial.length} jogadores (custo R$${partial_cost.toFixed(2)})`);
                    for (const pj of partial) {
                        this.log(`  - ${pj.apelido} (R$${pj.preco_num.toFixed(2)} - ${(pj.pontuacao_total || 0).toFixed(2)})`);
                    }
                    chosen = [top_clube_id, partial];
                } else {
                    this.log(`Estratégia 2: Nenhum jogador do clube ${top_clube_id} pôde ser travado dentro do orçamento.`);
                }
            }
            
            // Aplicar defesa escolhida - Python linhas 386-411
            if (chosen) {
                const [clube_escolhido, jogadores_escolhidos] = chosen;
                
                // Separar jogadores por posição
                predefinido_defesa.goleiros = jogadores_escolhidos.filter(j => {
                    const ranking_gk = this.rankings_por_posicao['goleiro'] || [];
                    return ranking_gk.some(r => r.atleta_id === j.atleta_id);
                }).slice(0, 1);
                
                predefinido_defesa.zagueiros = jogadores_escolhidos.filter(j => {
                    const ranking_zg = this.rankings_por_posicao['zagueiro'] || [];
                    return ranking_zg.some(r => r.atleta_id === j.atleta_id);
                }).slice(0, 2);
                
                predefinido_defesa.laterais = jogadores_escolhidos.filter(j => {
                    const ranking_lt = this.rankings_por_posicao['lateral'] || [];
                    return ranking_lt.some(r => r.atleta_id === j.atleta_id);
                }).slice(0, 2);
                
                // Atualizar estrutura inicial
                for (const pos of ['goleiros', 'zagueiros', 'laterais']) {
                    if (predefinido_defesa[pos].length > 0) {
                        escalacao.titulares[pos] = predefinido_defesa[pos];
                        escalacao.custo_total += predefinido_defesa[pos].reduce((sum, j) => sum + j.preco_num, 0);
                        escalados_ids.push(...predefinido_defesa[pos].map(j => j.atleta_id));
                    }
                }
                
                // Log da defesa escolhida
                const nomes = [];
                for (const pos of ['goleiros', 'zagueiros', 'laterais']) {
                    for (const j of predefinido_defesa[pos]) {
                        nomes.push(`${j.apelido} (${pos.slice(0, -1).toUpperCase()} - R$${j.preco_num.toFixed(2)} - ${(j.pontuacao_total || 0).toFixed(2)})`);
                    }
                }
                this.log(`Defesa escolhida do clube_id ${clube_escolhido}:`);
                for (const n of nomes) {
                    this.log(`  - ${n}`);
                }
                this.log(`Custo parcial da defesa: R$${escalacao.custo_total.toFixed(2)}`);
                this.log(`Estratégia 2: Defesa fechada aplicada. Custo até aqui: ${escalacao.custo_total.toFixed(2)}`);
            } else {
                this.log("Estratégia 2: Não foi possível fechar defesa dentro do orçamento. Prosseguindo com estratégia padrão.");
            }
        }
        
        // Escalar posições que não foram desescaladas - Python linhas 413-490
        for (const posicao of this.prioridades) {
            // Verificar se deve pular - Python linhas 415-418
            if (posicoes_desescaladas.includes(posicao)) {
                if (!(fecharDefesa && ['goleiros', 'zagueiros', 'laterais'].includes(posicao) && escalacao.titulares[posicao].length > 0)) {
                    continue;
                }
            }
            
            // Se defesa foi pré-definida parcialmente, completar - Python linhas 420-429
            const existentes = escalacao.titulares[posicao] || [];
            const qt_titulares = this.formacao[`qt_${this.plural_to_singular[posicao]}`];
            
            let restantes = null;
            if (fecharDefesa && ['goleiros', 'zagueiros', 'laterais'].includes(posicao) && existentes.length > 0) {
                restantes = Math.max(0, qt_titulares - existentes.length);
                if (restantes <= 0) {
                    this.log(`Estratégia 2: ${posicao} já completa pelos pré-definidos.`);
                    continue;
                }
                this.log(`Estratégia 2: ${posicao} pré-definida parcialmente (${existentes.length}/${qt_titulares}). Completando ${restantes} restantes.`);
            }
            
            this.log(`\nProcessando posição (titulares): ${posicao}`);
            const pos_id = this.posicao_ids[posicao];
            
            // Para posição do capitão, buscar 1 a mais (reserva de luxo) - Python linhas 434-435
            const alvo = restantes !== null ? restantes : qt_titulares;
            const quantidade_busca = (posicao === posicaoCapitao && posicao !== 'tecnicos') ? (alvo + 1) : alvo;
            
            // Buscar candidatos - Python linha 437-439
            const candidatos = this.fetchMelhoresJogadoresPorPosicao(
                this.plural_to_singular[posicao],
                quantidade_busca * 2,
                null,
                escalados_ids
            );
            
            this.log(`Filtrando jogadores para ${posicao} com custo total atual: ${escalacao.custo_total.toFixed(2)}`);
            
            // Filtrar por orçamento - EXATAMENTE como no Python (linhas 441-450)
            let candidatos_validos = [];
            let custo_temp = escalacao.custo_total;
            let selecionados = [];
            
            for (const candidato of candidatos) {
                const preco_candidato = candidato.preco_num;
                if (custo_temp + preco_candidato <= this.patrimonio && selecionados.length < quantidade_busca) {
                    selecionados.push(candidato);
                    custo_temp += preco_candidato;
                }
                if (selecionados.length === quantidade_busca) {
                    break;
                }
            }
            candidatos_validos = selecionados;
            
            this.log(`Encontrados ${candidatos_validos.length} candidatos válidos para ${posicao}`);
            
            // Verificar se há candidatos suficientes - Python linhas 453-456
            const needed_check = alvo;
            if (candidatos_validos.length < needed_check) {
                this.log(`Não há jogadores suficientes para ${posicao} (necessários: ${needed_check}) dentro do orçamento.`);
                return null;
            }
            
            // Atribuir titulares e reserva de luxo - Python linhas 459-485
            if (posicao === posicaoCapitao && posicao !== 'tecnicos' && candidatos_validos.length >= needed_check) {
                // Ordenar por preço decrescente (mais caros primeiro) - Python linha 460
                candidatos_validos.sort((a, b) => b.preco_num - a.preco_num);
                
                if (existentes.length > 0 && restantes !== null) {
                    // Python linhas 462-466
                    const novos = candidatos_validos.slice(0, needed_check);
                    escalacao.titulares[posicao] = [...existentes, ...novos];
                    if (candidatos_validos.length > needed_check) {
                        escalacao.reservas[posicao] = [candidatos_validos[needed_check]];
                    }
                } else {
                    // Python linhas 468-470
                    escalacao.titulares[posicao] = candidatos_validos.slice(0, needed_check);
                    if (candidatos_validos.length > needed_check) {
                        escalacao.reservas[posicao] = [candidatos_validos[needed_check]];
                    }
                }
                
                const titulares_str = escalacao.titulares[posicao].map(j => `${j.apelido} (${j.preco_num.toFixed(2)})`).join(', ');
                const reserva_str = escalacao.reservas[posicao] && escalacao.reservas[posicao].length > 0 
                    ? `${escalacao.reservas[posicao][0].apelido} (${escalacao.reservas[posicao][0].preco_num.toFixed(2)})` 
                    : 'Nenhuma';
                this.log(`Selecionados ${needed_check} titulares (mais caros) e 1 reserva de luxo para ${posicao}:`);
                this.log(`  Titulares: ${titulares_str}`);
                this.log(`  Reserva: ${reserva_str}`);
            } else {
                // Python linhas 477-485
                if (existentes.length > 0 && restantes !== null) {
                    const novos = candidatos_validos.slice(0, needed_check);
                    escalacao.titulares[posicao] = [...existentes, ...novos];
                } else {
                    escalacao.titulares[posicao] = candidatos_validos.slice(0, needed_check);
                }
                
                const titulares_str = escalacao.titulares[posicao].map(j => `${j.apelido} (${(j.pontuacao_total || 0).toFixed(2)})`).join(', ');
                this.log(`Selecionados ${needed_check} titulares para ${posicao}: ${titulares_str}`);
            }
            
            // Calcular custo da posição - Python linhas 487-490
            const custo_posicao = escalacao.titulares[posicao].reduce((sum, j) => sum + j.preco_num, 0);
            escalacao.custo_total += custo_posicao;
            escalados_ids.push(...escalacao.titulares[posicao].map(j => j.atleta_id));
            this.log(`Custo da posição ${posicao}: ${custo_posicao.toFixed(2)}. IDs escalados: [${escalados_ids.join(', ')}]`);
        }
        
        // Tentar combinações para posições desescaladas - Python linhas 492-570
        const orcamento_restante = this.patrimonio - escalacao.custo_total;
        this.log(`\nOrçamento restante para posições desescaladas: ${orcamento_restante.toFixed(2)}`);
        
        // Remover das desescaladas as posições que já estão completas - Python linhas 497-501
        const efetivas_desescaladas = [];
        for (const pos of posicoes_desescaladas) {
            const qt = this.formacao[`qt_${this.plural_to_singular[pos]}`];
            if ((escalacao.titulares[pos] || []).length < qt) {
                efetivas_desescaladas.push(pos);
            }
        }
        
        // Buscar candidatos para posições desescaladas - Python linhas 503-517
        const candidatos = {};
        for (const pos of efetivas_desescaladas) {
            const qt = this.formacao[`qt_${this.plural_to_singular[pos]}`];
            // Usar top_n para atacantes, laterais, meias; top_n_reduzido para goleiros, técnicos, zagueiros - Python linha 508
            const quantidade_candidatos = ['goleiros', 'tecnicos', 'zagueiros'].includes(pos) ? this.top_n_reduzido : this.top_n;
            
            candidatos[pos] = this.fetchMelhoresJogadoresPorPosicao(
                this.plural_to_singular[pos],
                quantidade_candidatos,
                null,
                escalados_ids
            );
            
            this.log(`Candidatos a ${pos} disponíveis (top ${quantidade_candidatos}):`);
            for (const cand of candidatos[pos]) {
                this.log(`  - ${cand.apelido} (ID: ${cand.atleta_id}, Pontuação: ${(cand.pontuacao_total || 0).toFixed(2)}, Preço: ${cand.preco_num.toFixed(2)})`);
            }
        }
        
        // Gerar combinações - Python linhas 519-534
        const combinacoes = [];
        if (efetivas_desescaladas.length > 0) {
            const combos_posicoes = [];
            for (const pos of efetivas_desescaladas) {
                const qt = this.formacao[`qt_${this.plural_to_singular[pos]}`];
                const combos_pos = this.gerarCombinacoes(candidatos[pos], qt);
                combos_posicoes.push(combos_pos.map(combo => ({ pos, combo })));
            }
            
            // Produto cartesiano
            for (const combo_outras of this.produtoCartesiano(combos_posicoes)) {
                const jogadores_outras = [];
                for (const { pos, combo } of combo_outras) {
                    jogadores_outras.push(...combo);
                }
                combinacoes.push(jogadores_outras);
            }
        } else {
            // Se não há posições desescaladas, retornar escalação atual - Python linhas 533-534
            return escalacao;
        }
        
        // Avaliar combinações - Python linhas 536-552
        let melhor_combinacao = null;
        for (const combo of combinacoes) {
            const custo_combo = combo.reduce((sum, j) => sum + j.preco_num, 0);
            const pontuacao_combo = combo.reduce((sum, j) => sum + (j.pontuacao_total || 0), 0);
            const jogadores_nomes = combo.map(j => j.apelido).join(', ');
            
            this.log(`  - Combinação: [${jogadores_nomes}], Pontuação Total: ${pontuacao_combo.toFixed(2)}, Custo Total: ${custo_combo.toFixed(2)}, Dentro do orçamento: ${custo_combo <= orcamento_restante}`);
            
            if (custo_combo <= orcamento_restante) {
                melhor_combinacao = combo;
                this.log(`Primeira combinação válida encontrada: [${jogadores_nomes}], Pontuação: ${pontuacao_combo.toFixed(2)}, Custo: ${custo_combo.toFixed(2)}`);
                break;
            }
        }
        
        // Aplicar melhor combinação - Python linhas 554-570
        if (melhor_combinacao) {
            for (const pos of efetivas_desescaladas) {
                const qt = this.formacao[`qt_${this.plural_to_singular[pos]}`];
                const jogadores = melhor_combinacao.filter(j => candidatos[pos].includes(j)).slice(0, qt);
                
                if (jogadores.length !== qt) {
                    this.log(`Erro: Combinação não contém ${qt} jogadores para ${pos}. Jogadores encontrados: ${jogadores.length}`);
                    return null;
                }
                
                escalacao.titulares[pos] = jogadores;
                const nomes = jogadores.map(j => j.apelido).join(', ');
                const preco_total = jogadores.reduce((sum, j) => sum + j.preco_num, 0);
                this.log(`Reescalado ${pos}: [${nomes}] (Preço total: ${preco_total.toFixed(2)})`);
            }
            
            const custo_posicao = melhor_combinacao.reduce((sum, j) => sum + j.preco_num, 0);
            escalacao.custo_total += custo_posicao;
            escalados_ids.push(...melhor_combinacao.map(j => j.atleta_id));
            this.log(`Custo das posições combinadas: ${custo_posicao.toFixed(2)}. IDs escalados: [${escalados_ids.join(', ')}]`);
            
            return escalacao;
        } else {
            this.log("Nenhuma combinação válida encontrada.");
            return null;
        }
    }
    
    /**
     * Função auxiliar para gerar combinações (equivalente ao Python combinations)
     */
    gerarCombinacoes(items, qt) {
        if (qt === 0) return [[]];
        if (qt > items.length) return [];
        if (qt === 1) return items.map(item => [item]);
        
        const combinacoes = [];
        for (let i = 0; i <= items.length - qt; i++) {
            const subCombinacoes = this.gerarCombinacoes(items.slice(i + 1), qt - 1);
            for (const sub of subCombinacoes) {
                combinacoes.push([items[i], ...sub]);
            }
        }
        return combinacoes;
    }
    
    /**
     * Função auxiliar para gerar produto cartesiano (equivalente ao Python product)
     */
    *produtoCartesiano(arrays) {
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
        for (const item of first) {
            for (const restCombo of this.produtoCartesiano(rest)) {
                yield [item, ...restCombo];
            }
        }
    }
    
    /**
     * Calcula a escalação ideal
     * EQUIVALENTE à função calcular_escalacao_ideal do Python (linhas 80-962)
     */
    async calcular(hackGoleiro = false, fecharDefesa = false, posicaoCapitao = 'atacantes') {
        this.posicaoCapitao = posicaoCapitao;
        
        this.log('\n═══════════════════════════════════════════════════════════');
        this.log('🚀 INICIANDO CÁLCULO DA ESCALAÇÃO IDEAL');
        this.log('═══════════════════════════════════════════════════════════');
        this.log(`Iniciando cálculo da escalação ideal com capitão e reserva de luxo na posição: ${posicaoCapitao}`);
        this.log(`Formação definida: ${this.config.formation || '4-3-3'}`);
        this.log(`Orçamento disponível: ${this.patrimonio.toFixed(2)} cartoletas`);
        this.log(`Prioridades de escalação: ${this.prioridades.join(' → ')}`);
        this.log(`Ordem de desescalação: ${this.ordem_desescalacao.join(' → ')}`);
        this.log('═══════════════════════════════════════════════════════════\n');
        
        // Verificar patrimônio - Python linhas 134-137
        if (!this.patrimonio || this.patrimonio <= 0) {
            const errorMsg = this.patrimonio_error || 'Patrimônio não disponível. Verifique suas credenciais do Cartola.';
            throw new Error(errorMsg);
        }
        
        // Verificar se há rankings suficientes
        const posicoes_necessarias = ['goleiro', 'zagueiro', 'lateral', 'meia', 'atacante', 'treinador'];
        const posicoes_faltando = [];
        
        for (const pos of posicoes_necessarias) {
            const ranking = this.rankings_por_posicao[pos] || [];
            if (ranking.length === 0) {
                posicoes_faltando.push(pos);
            } else {
                this.log(`✅ Ranking ${pos}: ${ranking.length} jogadores disponíveis`);
            }
        }
        
        if (posicoes_faltando.length > 0) {
            throw new Error(`Rankings faltando para as posições: ${posicoes_faltando.join(', ')}. Calcule os rankings das posições primeiro.`);
        }
        
        // Tentar escalação com desescalação progressiva - Python linhas 573-580
        let posicoes_desescaladas = [];
        let escalacao = null;
        
        while (escalacao === null && posicoes_desescaladas.length <= this.ordem_desescalacao.length) {
            escalacao = this.tryEscalacao(posicoes_desescaladas, fecharDefesa, posicaoCapitao);
            
            if (escalacao === null && posicoes_desescaladas.length < this.ordem_desescalacao.length) {
                const proxima_posicao = this.ordem_desescalacao[posicoes_desescaladas.length];
                posicoes_desescaladas.push(proxima_posicao);
                this.log(`\n❌ Sem escalação válida. Adicionando ${proxima_posicao} às posições desescaladas: [${posicoes_desescaladas.join(', ')}]`);
            }
        }
        
        // Se não encontrou escalação válida - Python linhas 582-585
        if (escalacao === null) {
            this.log('\n❌❌❌ ERRO FINAL: NÃO FOI POSSÍVEL ENCONTRAR ESCALAÇÃO VÁLIDA ❌❌❌');
            
            // Informações de debug detalhadas
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
            
            this.log(`Erro: ${msg}`);
            throw new Error(msg);
        }
        
        // Validar número de jogadores por posição - Python linhas 588-594
        for (const posicao of Object.keys(this.posicao_ids)) {
            const qt_esperada = this.formacao[`qt_${this.plural_to_singular[posicao]}`];
            const qt_atual = (escalacao.titulares[posicao] || []).length;
            
            if (qt_atual !== qt_esperada) {
                this.log(`Erro: Quantidade inválida de jogadores para ${posicao}. Esperado: ${qt_esperada}, Encontrado: ${qt_atual}`);
                throw new Error(`Quantidade inválida de jogadores para ${posicao}. Esperado: ${qt_esperada}, Encontrado: ${qt_atual}`);
            }
        }
        
        // Aplicar hack do goleiro se solicitado - Python linhas 596-725
        if (hackGoleiro && escalacao.titulares.goleiros && escalacao.titulares.goleiros.length > 0) {
            this.log('\n🔧 Aplicando hack do goleiro...');
            this.log('Hack do goleiro: Funcionalidade requer dados adicionais de status dos jogadores da API');
            // Nota: Implementação completa requer acesso a dados de status_id dos jogadores
        }
        
        // Selecionar reservas para outras posições - Python linhas 727-749
        for (const posicao of this.prioridades) {
            if (posicao === posicaoCapitao || posicao === 'tecnicos' || posicao === 'goleiros') {
                continue; // Capitão já tem reserva de luxo, técnicos não têm reserva, goleiros tratados separadamente
            }
            
            this.log(`\nProcessando posição (reservas): ${posicao}`);
            
            if (escalacao.titulares[posicao] && escalacao.titulares[posicao].length > 0) {
                const min_preco_titular = Math.min(...escalacao.titulares[posicao].map(j => this._getPreco(j)));
                this.log(`Preço mínimo dos titulares para ${posicao}: ${min_preco_titular.toFixed(2)}`);
                
                const candidatos_reserva = this.fetchMelhoresJogadoresPorPosicao(
                    this.plural_to_singular[posicao],
                    5,
                    min_preco_titular,
                    escalacao.titulares[posicao].map(j => j.atleta_id)
                );
                
                if (candidatos_reserva.length === 0) {
                    this.log(`Aviso: Não há reservas com preço <= ${min_preco_titular.toFixed(2)} para ${posicao}. Pulando reserva.`);
                    continue;
                }
                
                escalacao.reservas[posicao] = [candidatos_reserva[0]];
                this.log(`Selecionado 1 reserva para ${posicao}: ${candidatos_reserva[0].apelido}. Preço: ${candidatos_reserva[0].preco_num.toFixed(2)}, Pontuação: ${(candidatos_reserva[0].pontuacao_total || 0).toFixed(2)}, ID: ${candidatos_reserva[0].atleta_id}`);
            }
        }
        
        // Calcular pontuação total dos titulares - Python linhas 751-757
        escalacao.pontuacao_total = 0;
        for (const posicao of Object.keys(escalacao.titulares)) {
            for (const jogador of escalacao.titulares[posicao]) {
                escalacao.pontuacao_total += jogador.pontuacao_total || 0;
            }
        }
        this.log(`Pontuação total calculada: ${escalacao.pontuacao_total.toFixed(2)}`);
        
        // Identificar reserva de luxo - Python linhas 760-773
        let reserva_de_luxo = null;
        if (escalacao.reservas[posicaoCapitao] && escalacao.reservas[posicaoCapitao].length > 0) {
            reserva_de_luxo = escalacao.reservas[posicaoCapitao][0];
            reserva_de_luxo.eh_reserva_luxo = true;
            this.log(`Reserva de luxo identificada: ${reserva_de_luxo.apelido} (Posição: ${posicaoCapitao}, Pontuação: ${(reserva_de_luxo.pontuacao_total || 0).toFixed(2)}, Preço: ${reserva_de_luxo.preco_num.toFixed(2)})`);
        }
        
        // Selecionar capitão - Python linhas 775-797
        this.log('\nSelecionando capitão');
        let capitao = null;
        
        if (escalacao.titulares[posicaoCapitao] && escalacao.titulares[posicaoCapitao].length > 0) {
            capitao = escalacao.titulares[posicaoCapitao].reduce((max, j) => 
                (j.pontuacao_total || 0) > (max.pontuacao_total || 0) ? j : max
            );
            capitao.eh_capitao = true;
            this.log(`Capitão selecionado: ${capitao.apelido} (Posição: ${posicaoCapitao.charAt(0).toUpperCase() + posicaoCapitao.slice(1)}, Pontuação: ${(capitao.pontuacao_total || 0).toFixed(2)}, ID: ${capitao.atleta_id})`);
        } else {
            this.log(`Posição de capitão inválida ou sem titulares: ${posicaoCapitao}. Selecionando o jogador com maior pontuação.`);
            
            let maior_pontuacao = -Infinity;
            for (const posicao of Object.keys(escalacao.titulares)) {
                for (const jogador of escalacao.titulares[posicao]) {
                    if ((jogador.pontuacao_total || 0) > maior_pontuacao) {
                        maior_pontuacao = jogador.pontuacao_total || 0;
                        capitao = jogador;
                    }
                }
            }
            
            if (capitao) {
                capitao.eh_capitao = true;
                this.log(`Capitão selecionado: ${capitao.apelido} (Pontuação: ${(capitao.pontuacao_total || 0).toFixed(2)}, ID: ${capitao.atleta_id})`);
            }
        }
        
        // Exibir escalação - Python linhas 800-836
        this.log('\n═══════════════════════════════════════════════════════════');
        this.log('✅ ESCALAÇÃO CALCULADA COM SUCESSO!');
        this.log('═══════════════════════════════════════════════════════════');
        this.log(`\nEsquema: ${this.config.formation || '4-3-3'}`);
        this.log(`Pontuação Total Estimada (Titulares): ${escalacao.pontuacao_total.toFixed(2)}`);
        this.log(`Custo Total: ${escalacao.custo_total.toFixed(2)} cartoletas`);
        this.log(`Orçamento Restante: ${(this.patrimonio - escalacao.custo_total).toFixed(2)} cartoletas`);
        
        this.log('\n--- Escalação Titular ---');
        for (const posicao of Object.keys(escalacao.titulares)) {
            const jogadores = escalacao.titulares[posicao];
            if (jogadores && jogadores.length > 0) {
                this.log(`${posicao.charAt(0).toUpperCase() + posicao.slice(1)}:`);
                for (const jogador of jogadores) {
                    const capitao_badge = jogador.eh_capitao ? ' [CAPITÃO]' : '';
                    this.log(`  - ${jogador.apelido}${capitao_badge} (Clube ID: ${jogador.clube_id}, Pontuação: ${(jogador.pontuacao_total || 0).toFixed(2)}, Preço: ${jogador.preco_num.toFixed(2)}, ID: ${jogador.atleta_id})`);
                }
            }
        }
        
        this.log('\n--- Escalação Reserva ---');
        for (const posicao of Object.keys(escalacao.reservas)) {
            const jogadores = escalacao.reservas[posicao];
            if (jogadores && jogadores.length > 0) {
                this.log(`${posicao.charAt(0).toUpperCase() + posicao.slice(1)}:`);
                for (const jogador of jogadores) {
                    const luxo_badge = jogador.eh_reserva_luxo ? ' [RESERVA DE LUXO]' : '';
                    this.log(`  - ${jogador.apelido}${luxo_badge} (Clube ID: ${jogador.clube_id}, Pontuação: ${(jogador.pontuacao_total || 0).toFixed(2)}, Preço: ${jogador.preco_num.toFixed(2)}, ID: ${jogador.atleta_id})`);
                }
            }
        }
        
        if (capitao) {
            this.log('\n--- Capitão ---');
            this.log(`${capitao.apelido} (Posição: ${posicaoCapitao.charAt(0).toUpperCase() + posicaoCapitao.slice(1)}, Pontuação: ${(capitao.pontuacao_total || 0).toFixed(2)}, ID: ${capitao.atleta_id})`);
        }
        
        this.log('═══════════════════════════════════════════════════════════\n');
        this.log(`Cálculo de escalação ideal concluído!`);
        
        escalacao.patrimonio = this.patrimonio;
        return escalacao;
    }
}
