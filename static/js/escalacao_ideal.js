/**
 * Cálculo de Escalação Ideal - Cartola FC
 * Lógica: Escala jogadores titulares respeitando orçamento
 * Reservas não têm custo e devem ser mais baratos que o titular mais barato
 */

class EscalacaoIdeal {
    constructor(dados) {
        // Dados básicos
        this.rodada = dados.rodada_atual;
        this.patrimonio = parseFloat(dados.patrimonio) || 0;
        this.rankings = dados.rankings_por_posicao || {};
        this.clubes_sg = dados.clubes_sg || [];
        this.todosGoleiros = dados.todos_goleiros || [];  // Lista completa de goleiros para hack
        
        // Log de debug para verificar goleiros recebidos
        console.log('[DEBUG] Goleiros recebidos no construtor:', this.todosGoleiros.length);
        if (this.todosGoleiros.length > 0) {
            const goleirosNulos = this.todosGoleiros.filter(g => g.status_id !== 7 && g.status_id !== 2);
            console.log('[DEBUG] Goleiros NULOS:', goleirosNulos.length);
            if (goleirosNulos.length > 0) {
                console.log('[DEBUG] Top 5 goleiros nulos:', goleirosNulos.slice(0, 5).map(g => 
                    `${g.apelido} - R$ ${g.preco_num} - status: ${g.status_id}`
                ));
            }
        } else {
            console.warn('[ATENÇÃO] Nenhum goleiro recebido do backend!');
        }
        
        // Configurações (podem ser passadas ou usar padrão)
        this.formacao = this.parseFormacao(dados.formacao || '4-3-3');
        this.posicaoCapitao = dados.posicao_capitao || 'atacantes';
        this.posicaoReservaLuxo = dados.posicao_reserva_luxo || 'atacantes';
        this.prioridades = dados.prioridades || ['atacantes', 'laterais', 'meias', 'zagueiros', 'goleiros', 'treinadores'];
        this.fecharDefesa = dados.fechar_defesa || false;
        this.hackGoleiro = dados.hack_goleiro || false;
        
        // Mapeamentos
        this.posicaoIds = {
            'goleiros': 1, 'laterais': 2, 'zagueiros': 3,
            'meias': 4, 'atacantes': 5, 'treinadores': 6
        };
        
        this.singularToPlural = {
            'goleiro': 'goleiros', 'lateral': 'laterais', 'zagueiro': 'zagueiros',
            'meia': 'meias', 'atacante': 'atacantes', 'treinador': 'treinadores'
        };
        
        // Ordem de desescalação (inverso das prioridades)
        this.ordemDesescalacao = [...this.prioridades].reverse();
        
        // Callback para logs (opcional)
        this.logCallback = null;
    }
    
    /**
     * Define callback para logs
     */
    setLogCallback(callback) {
        this.logCallback = callback;
    }
    
    /**
     * Log interno
     */
    log(mensagem) {
        if (this.logCallback && typeof this.logCallback === 'function') {
            this.logCallback(mensagem);
        }
    }
    
    /**
     * Parse da formação
     */
    parseFormacao(formacaoStr) {
        const formacoes = {
            '4-3-3': { goleiro: 1, zagueiro: 2, lateral: 2, meia: 3, atacante: 3, treinador: 1 },
            '4-4-2': { goleiro: 1, zagueiro: 2, lateral: 2, meia: 4, atacante: 2, treinador: 1 },
            '3-5-2': { goleiro: 1, zagueiro: 3, lateral: 0, meia: 5, atacante: 2, treinador: 1 },
            '3-4-3': { goleiro: 1, zagueiro: 3, lateral: 0, meia: 4, atacante: 3, treinador: 1 },
            '4-5-1': { goleiro: 1, zagueiro: 2, lateral: 2, meia: 5, atacante: 1, treinador: 1 },
            '5-4-1': { goleiro: 1, zagueiro: 3, lateral: 2, meia: 4, atacante: 1, treinador: 1 }
        };
        return formacoes[formacaoStr] || formacoes['4-3-3'];
    }
    
    /**
     * Obtém preço do jogador
     */
    getPreco(jogador) {
        return parseFloat(jogador.preco_num || jogador.preco || 0);
    }
    
    /**
     * Obtém pontuação do jogador
     */
    getPontuacao(jogador) {
        return parseFloat(jogador.pontuacao_total || 0);
    }
    
    /**
     * Busca melhores jogadores de uma posição
     */
    buscarMelhores(posicaoSingular, quantidade, maxPreco = null, excluirIds = []) {
        const posicaoPlural = this.singularToPlural[posicaoSingular];
        const ranking = this.rankings[posicaoSingular] || [];
        
        // Filtrar jogadores não escalados e dentro do orçamento
        let candidatos = ranking.filter(j => {
            if (excluirIds.includes(j.atleta_id)) return false;
            const preco = this.getPreco(j);
            if (maxPreco !== null && preco > maxPreco) return false;
            return true;
        });
        
        // Ordenar por pontuação (melhor primeiro)
        candidatos.sort((a, b) => this.getPontuacao(b) - this.getPontuacao(a));
        
        return candidatos.slice(0, quantidade);
    }
    
    /**
     * Tenta fechar defesa do melhor clube por SG
     * Se não conseguir completar todas as posições com o clube, completa com o ranking geral
     */
    fecharDefesaMelhorClube(escalacao, escaladosIds) {
        if (!this.fecharDefesa || !this.clubes_sg || this.clubes_sg.length === 0) {
            return { sucesso: false };
        }
        
        // Melhor clube por SG
        const melhorClube = this.clubes_sg[0];
        const clubeId = melhorClube.clube_id;
        const pesoSG = parseFloat(melhorClube.peso_sg || 0);
        
        this.log(`\n🛡️  Tentando fechar defesa do clube ${clubeId} (melhor SG: ${pesoSG.toFixed(2)})`);
        
        const qtGk = this.formacao.goleiro;
        const qtZag = this.formacao.zagueiro;
        const qtLat = this.formacao.lateral;
        
        // Buscar jogadores do clube para cada posição defensiva
        const buscarPorClube = (posicao) => {
            const ranking = this.rankings[posicao] || [];
            return ranking
                .filter(j => j.clube_id === clubeId && !escaladosIds.includes(j.atleta_id))
                .sort((a, b) => this.getPontuacao(b) - this.getPontuacao(a));
        };
        
        const gksClube = buscarPorClube('goleiro');
        const zagsClube = buscarPorClube('zagueiro');
        const latsClube = buscarPorClube('lateral');
        
        this.log(`   Disponíveis do clube: ${gksClube.length} goleiros, ${zagsClube.length} zagueiros, ${latsClube.length} laterais`);
        
        // Tentar escalar o máximo possível do clube
        let defesaEscalada = [];
        let custoDefesa = 0;
        
        // Pegar o máximo possível do clube respeitando orçamento
        const tentarEscalarPosicao = (jogadoresClube, quantidade, posicaoNome) => {
            const escalados = [];
            for (const j of jogadoresClube) {
                if (escalados.length >= quantidade) break;
                const preco = this.getPreco(j);
                if (custoDefesa + preco <= this.patrimonio) {
                    escalados.push(j);
                    custoDefesa += preco;
                    defesaEscalada.push({ jogador: j, posicao: posicaoNome });
                }
            }
            return escalados;
        };
        
        const gksEscalados = tentarEscalarPosicao(gksClube, qtGk, 'goleiros');
        const zagsEscalados = tentarEscalarPosicao(zagsClube, qtZag, 'zagueiros');
        const latsEscalados = tentarEscalarPosicao(latsClube, qtLat, 'laterais');
        
        // Completar com jogadores do ranking geral se necessário
        const completarComRanking = (escalados, quantidade, posicao, posicaoPlural) => {
            if (escalados.length >= quantidade) return escalados;
            
            const faltam = quantidade - escalados.length;
            const rankingGeral = this.rankings[posicao] || [];
            const candidatos = rankingGeral
                .filter(j => !escaladosIds.includes(j.atleta_id) && !escalados.includes(j))
                .sort((a, b) => this.getPontuacao(b) - this.getPontuacao(a));
            
            this.log(`   ⚠️  Faltam ${faltam} ${posicaoPlural}, completando com ranking geral...`);
            
            for (const j of candidatos) {
                if (escalados.length >= quantidade) break;
                const preco = this.getPreco(j);
                if (custoDefesa + preco <= this.patrimonio) {
                    escalados.push(j);
                    custoDefesa += preco;
                    defesaEscalada.push({ jogador: j, posicao: posicaoPlural });
                }
            }
            
            return escalados;
        };
        
        const gksFinal = completarComRanking(gksEscalados, qtGk, 'goleiro', 'goleiros');
        const zagsFinal = completarComRanking(zagsEscalados, qtZag, 'zagueiro', 'zagueiros');
        const latsFinal = completarComRanking(latsEscalados, qtLat, 'lateral', 'laterais');
        
        // Verificar se conseguimos escalar todos
        if (gksFinal.length === qtGk && zagsFinal.length === qtZag && latsFinal.length === qtLat) {
            this.log(`   ✅ Defesa montada! (${gksEscalados.length}/${qtGk} gol, ${zagsEscalados.length}/${qtZag} zag, ${latsEscalados.length}/${qtLat} lat do clube ${clubeId})`);
            this.log(`      Custo: R$ ${custoDefesa.toFixed(2)}`);
            
            // Aplicar na escalação
            escalacao.titulares.goleiros = gksFinal;
            escalacao.titulares.zagueiros = zagsFinal;
            escalacao.titulares.laterais = latsFinal;
            escalacao.custoTotal = custoDefesa;
            
            [...gksFinal, ...zagsFinal, ...latsFinal].forEach(j => escaladosIds.push(j.atleta_id));
            
            return { sucesso: true, custo: custoDefesa };
        }
        
        this.log(`   ❌ Não foi possível montar defesa completa`);
        return { sucesso: false };
    }
    
    /**
     * Escala uma posição
     */
    escalarPosicao(posicaoPlural, escalacao, escaladosIds) {
        const posicaoSingular = Object.keys(this.singularToPlural).find(k => this.singularToPlural[k] === posicaoPlural);
        const qtNecessaria = this.formacao[posicaoSingular];
        
        // Garantir que a posição existe no objeto
        if (!escalacao.titulares[posicaoPlural]) {
            escalacao.titulares[posicaoPlural] = [];
        }
        
        // Se já foi escalada (defesa fechada), pular
        if (escalacao.titulares[posicaoPlural].length >= qtNecessaria) {
            return true;
        }
        
        this.log(`\n📋 Escalando ${posicaoPlural} (necessário: ${qtNecessaria})`);
        
        // Se for posição do reserva de luxo, buscar N+1
        const buscarExtra = (posicaoPlural === this.posicaoReservaLuxo && posicaoPlural !== 'treinadores');
        const qtBuscar = buscarExtra ? qtNecessaria + 1 : qtNecessaria;
        
        // Buscar candidatos
        const candidatos = this.buscarMelhores(posicaoSingular, qtBuscar * 2, null, escaladosIds);
        
        this.log(`   Encontrados ${candidatos.length} candidatos`);
        
        // Filtrar por orçamento
        const validos = [];
        let custoTemp = escalacao.custoTotal;
        
        for (const candidato of candidatos) {
            const preco = this.getPreco(candidato);
            
            // Se for para reserva de luxo e já temos os titulares, não somar custo
            if (buscarExtra && validos.length === qtNecessaria) {
                validos.push(candidato);
                break;
            }
            
            if (custoTemp + preco <= this.patrimonio) {
                validos.push(candidato);
                custoTemp += preco;
            }
            
            if (validos.length >= qtBuscar) break;
        }
        
        if (validos.length < qtNecessaria) {
            this.log(`   ❌ Insuficiente: ${validos.length}/${qtNecessaria}`);
            return false;
        }
        
        // Ordenar por preço (mais caros primeiro) se for reserva de luxo
        if (buscarExtra) {
            validos.sort((a, b) => this.getPreco(b) - this.getPreco(a));
        }
        
        // Atribuir titulares
        const titulares = validos.slice(0, qtNecessaria);
        escalacao.titulares[posicaoPlural] = titulares;
        
        // Calcular custo APENAS dos titulares
        const custoTitulares = titulares.reduce((sum, j) => sum + this.getPreco(j), 0);
        escalacao.custoTotal += custoTitulares;
        titulares.forEach(j => escaladosIds.push(j.atleta_id));
        
        this.log(`   ✅ Escalados ${qtNecessaria} titulares. Custo: R$ ${custoTitulares.toFixed(2)}`);
        
        // Reserva de luxo (sem custo)
        if (buscarExtra && validos.length > qtNecessaria) {
            const reservaLuxo = validos[qtNecessaria];
            reservaLuxo.eh_reserva_luxo = true;
            escalacao.reservas[posicaoPlural] = [reservaLuxo];
            escaladosIds.push(reservaLuxo.atleta_id);
            
            this.log(`   💎 Reserva de luxo: ${reservaLuxo.apelido} (R$ ${this.getPreco(reservaLuxo).toFixed(2)}) - SEM CUSTO`);
        }
        
        return true;
    }
    
    /**
     * Gera todas as combinações de um array (como itertools.combinations do Python)
     * @param {Array} arr - Array de elementos
     * @param {number} size - Tamanho das combinações
     * @returns {Array} Array de combinações
     */
    combinations(arr, size) {
        if (size > arr.length || size <= 0) return [];
        if (size === arr.length) return [arr];
        if (size === 1) return arr.map(el => [el]);
        
        const result = [];
        for (let i = 0; i < arr.length - size + 1; i++) {
            const head = arr[i];
            const tailCombinations = this.combinations(arr.slice(i + 1), size - 1);
            for (const tail of tailCombinations) {
                result.push([head, ...tail]);
            }
        }
        return result;
    }
    
    /**
     * Gera o produto cartesiano de múltiplos arrays (como itertools.product do Python)
     * @param {Array} arrays - Array de arrays
     * @returns {Array} Array de combinações
     */
    product(...arrays) {
        if (arrays.length === 0) return [[]];
        if (arrays.length === 1) return arrays[0].map(el => [el]);
        
        return arrays.reduce((acc, curr) => {
            return acc.flatMap(x => curr.map(y => [...x, y]));
        }, [[]]);
    }
    
    /**
     * Tenta escalação completa
     */
    tentarEscalacao(posicoesDesescaladas = []) {
        this.log(`\n🎯 Tentativa de escalação. Desescaladas: [${posicoesDesescaladas.join(', ')}]`);
        
        const escalacao = {
            titulares: { goleiros: [], zagueiros: [], laterais: [], meias: [], atacantes: [], treinadores: [] },
            reservas: { goleiros: [], zagueiros: [], laterais: [], meias: [], atacantes: [] },
            custoTotal: 0,
            pontuacaoTotal: 0
        };
        
        const escaladosIds = [];
        
        // 1. Fechar defesa (se ativado)
        if (this.fecharDefesa) {
            this.fecharDefesaMelhorClube(escalacao, escaladosIds);
        }
        
        // 2. Escalar por prioridade (pular desescaladas)
        for (const posicao of this.prioridades) {
            if (posicoesDesescaladas.includes(posicao)) continue;
            
            if (!this.escalarPosicao(posicao, escalacao, escaladosIds)) {
                return null; // Falhou
            }
        }
        
        this.log(`\n💰 Custo total dos titulares: R$ ${escalacao.custoTotal.toFixed(2)} / R$ ${this.patrimonio.toFixed(2)}`);
        
        // 3. Se houver posições desescaladas, tentar combinações
        if (posicoesDesescaladas.length > 0) {
            const orcamentoRestante = this.patrimonio - escalacao.custoTotal;
            this.log(`\n🔄 Recombinando posições desescaladas`);
            this.log(`   Orçamento restante: R$ ${orcamentoRestante.toFixed(2)}`);
            
            // Filtrar apenas as posições efetivamente desescaladas (que não foram completadas pela defesa)
            const posDesescaladasEfetivas = posicoesDesescaladas.filter(pos => {
                const posicaoSingular = Object.keys(this.singularToPlural).find(k => this.singularToPlural[k] === pos);
                const qtNecessaria = this.formacao[posicaoSingular];
                return escalacao.titulares[pos].length < qtNecessaria;
            });
            
            if (posDesescaladasEfetivas.length === 0) {
                // Todas as posições desescaladas já foram preenchidas (ex: pela defesa fechada)
                this.log(`   ✅ Todas as posições desescaladas já foram preenchidas`);
                return escalacao;
            }
            
            this.log(`   📦 Recombinando ${posDesescaladasEfetivas.length} posição(ões): [${posDesescaladasEfetivas.join(', ')}]`);
            
            // Buscar candidatos para cada posição desescalada
            const candidatosPorPosicao = {};
            const top_n = 5; // Número de candidatos por posição para recombinações
            
            this.log(`\n📊 Buscando ${top_n} candidatos para cada posição desescalada...`);
            
            for (const posicao of posDesescaladasEfetivas) {
                const posicaoSingular = Object.keys(this.singularToPlural).find(k => this.singularToPlural[k] === posicao);
                
                candidatosPorPosicao[posicao] = this.buscarMelhores(posicaoSingular, top_n, null, escaladosIds);
                
                this.log(`\n📋 Candidatos para ${posicao}: ${candidatosPorPosicao[posicao].length}`);
                candidatosPorPosicao[posicao].forEach(c => {
                    this.log(`   - ${c.apelido} (R$ ${this.getPreco(c).toFixed(2)}, ${this.getPontuacao(c).toFixed(2)} pts)`);
                });
            }
            
            // Gerar combinações para cada posição
            const combinacoesPorPosicao = [];
            for (const posicao of posDesescaladasEfetivas) {
                const posicaoSingular = Object.keys(this.singularToPlural).find(k => this.singularToPlural[k] === posicao);
                const qtNecessaria = this.formacao[posicaoSingular];
                const candidatos = candidatosPorPosicao[posicao];
                
                if (candidatos.length < qtNecessaria) {
                    this.log(`\n❌ Candidatos insuficientes para ${posicao}: ${candidatos.length}/${qtNecessaria}`);
                    return null;
                }
                
                const combos = this.combinations(candidatos, qtNecessaria);
                combinacoesPorPosicao.push({
                    posicao: posicao,
                    combos: combos
                });
            }
            
            // Gerar produto cartesiano de todas as combinações
            this.log(`\n🔍 Gerando combinações possíveis...`);
            const todasCombinacoes = this.product(...combinacoesPorPosicao.map(item => 
                item.combos.map(combo => ({ posicao: item.posicao, jogadores: combo }))
            ));
            
            this.log(`   Total de combinações a testar: ${todasCombinacoes.length}`);
            
            // Testar combinações em ordem de maior pontuação
            let melhorCombinacao = null;
            let melhorPontuacao = -Infinity;
            
            for (const combinacao of todasCombinacoes) {
                // Extrair todos os jogadores da combinação
                const todosJogadores = combinacao.flatMap(item => item.jogadores);
                
                const custoTotal = todosJogadores.reduce((sum, j) => sum + this.getPreco(j), 0);
                const pontuacaoTotal = todosJogadores.reduce((sum, j) => sum + this.getPontuacao(j), 0);
                
                if (custoTotal <= orcamentoRestante && pontuacaoTotal > melhorPontuacao) {
                    melhorPontuacao = pontuacaoTotal;
                    melhorCombinacao = combinacao;
                }
            }
            
            if (melhorCombinacao) {
                this.log(`\n✅ Melhor combinação encontrada! Pontuação: ${melhorPontuacao.toFixed(2)}`);
                
                // Aplicar a melhor combinação
                for (const item of melhorCombinacao) {
                    const posicao = item.posicao;
                    const jogadores = item.jogadores;
                    
                    escalacao.titulares[posicao] = jogadores;
                    const custoPos = jogadores.reduce((sum, j) => sum + this.getPreco(j), 0);
                    escalacao.custoTotal += custoPos;
                    
                    jogadores.forEach(j => escaladosIds.push(j.atleta_id));
                    
                    this.log(`   ${posicao}: ${jogadores.map(j => `${j.apelido} (R$ ${this.getPreco(j).toFixed(2)})`).join(', ')}`);
                }
                
                this.log(`\n💰 Custo FINAL: R$ ${escalacao.custoTotal.toFixed(2)} / R$ ${this.patrimonio.toFixed(2)}`);
                return escalacao;
            } else {
                this.log(`\n❌ Nenhuma combinação válida com ${posDesescaladasEfetivas.length} posição(ões) desescalada(s)`);
                this.log(`   Será necessário desescalar mais uma posição e tentar novamente...`);
                return null;
            }
        }
        
        return escalacao;
    }
    
    /**
     * Aplica hack do goleiro
     */
    aplicarHackGoleiro(escalacao, escaladosIds) {
        if (!this.hackGoleiro || escalacao.titulares.goleiros.length === 0) {
            return;
        }
        
        this.log(`\n🔧 Aplicando hack do goleiro...`);
        
        const goleiroTitular = escalacao.titulares.goleiros[0];
        const precoTitular = this.getPreco(goleiroTitular);
        
        // Buscar goleiro nulo (que não vai jogar - não pode ser provável=7 nem dúvida=2) MAIS CARO
        // Usar a lista completa de goleiros (todos_goleiros) em vez do ranking
        const todosGoleiros = this.todosGoleiros || [];
        
        this.log(`   ✅ Total de goleiros na base: ${todosGoleiros.length}`);
        this.log(`   🎯 Buscando goleiros nulos (status_id != 7 e != 2) mais caros que R$ ${precoTitular.toFixed(2)}`);
        
        // Filtrar APENAS goleiros nulos (que não vão jogar)
        const goleirosNulos = todosGoleiros.filter(g => 
            !escaladosIds.includes(g.atleta_id) && 
            g.status_id !== 7 && g.status_id !== 2  // Nulos: qualquer status exceto provável=7 e dúvida=2
        );
        
        this.log(`   📋 Total de goleiros NULOS encontrados: ${goleirosNulos.length}`);
        
        // Mostrar os goleiros nulos e seus preços (ordenados por preço decrescente)
        if (goleirosNulos.length > 0) {
            const goleirosNulosOrdenados = goleirosNulos
                .map(g => ({ apelido: g.apelido, preco: this.getPreco(g), status_id: g.status_id }))
                .sort((a, b) => b.preco - a.preco);
            
            this.log(`\n   📊 LISTA DE GOLEIROS NULOS (ordenados por preço):`);
            goleirosNulosOrdenados.forEach((g, idx) => {
                const marcador = g.preco > precoTitular ? '✅' : '❌';
                this.log(`      ${marcador} ${idx + 1}. ${g.apelido} - R$ ${g.preco.toFixed(2)} (status_id: ${g.status_id})`);
            });
            
            // Filtrar apenas os mais caros que o titular
            const goleirosNulosMaisCaros = goleirosNulos.filter(g => this.getPreco(g) > precoTitular);
            
            this.log(`\n   🔍 Goleiros nulos MAIS CAROS que R$ ${precoTitular.toFixed(2)}: ${goleirosNulosMaisCaros.length}`);
            
            if (goleirosNulosMaisCaros.length > 0) {
                // Pegar o mais barato entre os mais caros (ordenar por preço crescente e pegar o primeiro)
                goleirosNulosMaisCaros.sort((a, b) => this.getPreco(a) - this.getPreco(b));
                const goleiroNulo = goleirosNulosMaisCaros[0];
                
                const precoNulo = this.getPreco(goleiroNulo);
                const diferenca = precoNulo - precoTitular;
                
                this.log(`   🎯 Goleiro nulo selecionado: ${goleiroNulo.apelido} (status_id=${goleiroNulo.status_id})`);
                
                if (escalacao.custoTotal + diferenca <= this.patrimonio) {
                    this.log(`   ✅ Hack aplicado!`);
                    this.log(`      Titular (nulo): ${goleiroNulo.apelido} (R$ ${precoNulo.toFixed(2)})`);
                    this.log(`      Reserva (joga): ${goleiroTitular.apelido} (R$ ${precoTitular.toFixed(2)}) - SEM CUSTO`);
                    
                    escalacao.titulares.goleiros = [goleiroNulo];
                    escalacao.reservas.goleiros = [goleiroTitular];
                    escalacao.custoTotal += diferenca;
                } else {
                    this.log(`   ❌ Hack não cabe no orçamento (diferença: R$ ${diferenca.toFixed(2)})`);
                }
            } else {
                this.log(`   ❌ Não existem goleiros nulos mais caros que R$ ${precoTitular.toFixed(2)}`);
            }
        } else {
            this.log(`   ❌ Nenhum goleiro nulo encontrado na base de dados!`);
            this.log(`      (Isto é estranho - verifique se a tabela acf_atletas tem goleiros com status_id != 7 e != 2)`);
        }
    }
    
    /**
     * Seleciona reservas para outras posições
     */
    selecionarReservas(escalacao, escaladosIds) {
        this.log(`\n👥 Selecionando reservas regulares...`);
        
        for (const posicao of Object.keys(escalacao.titulares)) {
            // Pular posições que já têm reserva (como reserva de luxo) ou são técnicos
            if (posicao === 'treinadores' || escalacao.reservas[posicao]?.length > 0) {
                this.log(`   ${posicao}: já possui reserva (pulando)`);
                continue;
            }
            
            const titulares = escalacao.titulares[posicao];
            if (titulares.length === 0) continue;
            
            // Preço mínimo dos titulares
            const precoMin = Math.min(...titulares.map(j => this.getPreco(j)));
            
            // Buscar reserva mais barata que o preço mínimo
            const posicaoSingular = Object.keys(this.singularToPlural).find(k => this.singularToPlural[k] === posicao);
            const candidatos = this.buscarMelhores(posicaoSingular, 5, precoMin - 0.01, escaladosIds);
            
            if (candidatos.length > 0) {
                const reserva = candidatos[0];
                reserva.eh_reserva_luxo = false;
                escalacao.reservas[posicao] = [reserva];
                escaladosIds.push(reserva.atleta_id);
                
                this.log(`   ${posicao}: ${reserva.apelido} (R$ ${this.getPreco(reserva).toFixed(2)}) - SEM CUSTO`);
            } else {
                this.log(`   ${posicao}: nenhum reserva disponível mais barato que R$ ${precoMin.toFixed(2)}`);
            }
        }
    }
    
    /**
     * Seleciona capitão
     */
    selecionarCapitao(escalacao) {
        const posicao = this.posicaoCapitao;
        const jogadores = escalacao.titulares[posicao] || [];
        
        if (jogadores.length > 0) {
            const capitao = jogadores.reduce((melhor, j) => 
                this.getPontuacao(j) > this.getPontuacao(melhor) ? j : melhor
            );
            
            capitao.eh_capitao = true;
            this.log(`\n👑 Capitão: ${capitao.apelido} (${posicao}, ${this.getPontuacao(capitao).toFixed(2)} pts)`);
            
            return capitao;
        }
        
        return null;
    }
    
    /**
     * Calcula escalação ideal
     */
    async calcular() {
        this.log('═'.repeat(60));
        this.log('🚀 CÁLCULO DA ESCALAÇÃO IDEAL');
        this.log('═'.repeat(60));
        this.log(`Patrimônio: R$ ${this.patrimonio.toFixed(2)}`);
        this.log(`Formação: ${Object.entries(this.formacao).map(([k,v]) => `${v} ${k}`).join(', ')}`);
        this.log(`Prioridades: ${this.prioridades.join(' → ')}`);
        this.log(`Reserva de luxo: ${this.posicaoReservaLuxo}`);
        this.log(`Capitão: ${this.posicaoCapitao}`);
        this.log(`Fechar defesa: ${this.fecharDefesa ? 'Sim' : 'Não'}`);
        this.log(`Hack goleiro: ${this.hackGoleiro ? 'Sim' : 'Não'}`);
        
        // Tentar com desescalação progressiva
        let escalacao = null;
        const posicoesDesescaladas = [];
        
        while (!escalacao && posicoesDesescaladas.length <= this.ordemDesescalacao.length) {
            escalacao = this.tentarEscalacao(posicoesDesescaladas);
            
            if (!escalacao && posicoesDesescaladas.length < this.ordemDesescalacao.length) {
                const proximaPosicao = this.ordemDesescalacao[posicoesDesescaladas.length];
                posicoesDesescaladas.push(proximaPosicao);
                this.log(`\n⚠️  Desescalando ${proximaPosicao}...`);
            }
        }
        
        if (!escalacao) {
            throw new Error('Não foi possível encontrar escalação válida');
        }
        
        // Hack do goleiro
        this.aplicarHackGoleiro(escalacao, []);
        
        // Reservas
        this.selecionarReservas(escalacao, []);
        
        // Capitão
        this.selecionarCapitao(escalacao);
        
        // Pontuação total
        escalacao.pontuacaoTotal = Object.values(escalacao.titulares)
            .flat()
            .reduce((sum, j) => sum + this.getPontuacao(j), 0);
        
        escalacao.patrimonio = this.patrimonio;
        
        // Validar número de jogadores por posição
        const validacao = {
            goleiros: { esperado: this.formacao.goleiro, atual: escalacao.titulares.goleiros.length },
            zagueiros: { esperado: this.formacao.zagueiro, atual: escalacao.titulares.zagueiros.length },
            laterais: { esperado: this.formacao.lateral, atual: escalacao.titulares.laterais.length },
            meias: { esperado: this.formacao.meia, atual: escalacao.titulares.meias.length },
            atacantes: { esperado: this.formacao.atacante, atual: escalacao.titulares.atacantes.length },
            treinadores: { esperado: this.formacao.treinador, atual: escalacao.titulares.treinadores.length }
        };
        
        const totalEsperado = Object.values(this.formacao).reduce((sum, v) => sum + v, 0);
        const totalAtual = Object.values(escalacao.titulares).reduce((sum, arr) => sum + arr.length, 0);
        
        if (totalAtual !== totalEsperado) {
            this.log('\n' + '⚠️'.repeat(30));
            this.log(`❌ ERRO: Escalação inválida!`);
            this.log(`Total de jogadores: ${totalAtual}/${totalEsperado}`);
            this.log(`\nDetalhamento por posição:`);
            for (const [posicao, info] of Object.entries(validacao)) {
                const status = info.atual === info.esperado ? '✅' : '❌';
                this.log(`  ${status} ${posicao}: ${info.atual}/${info.esperado}`);
            }
            this.log('⚠️'.repeat(30));
            throw new Error(`Escalação inválida: ${totalAtual} atletas. Esperado: ${totalEsperado}`);
        }
        
        this.log('\n' + '═'.repeat(60));
        this.log(`✅ ESCALAÇÃO CONCLUÍDA!`);
        this.log(`💰 Custo: R$ ${escalacao.custoTotal.toFixed(2)} / R$ ${this.patrimonio.toFixed(2)}`);
        this.log(`📊 Pontuação estimada: ${escalacao.pontuacaoTotal.toFixed(2)} pts`);
        this.log('═'.repeat(60));
        
        return escalacao;
    }
}

// Exportar para uso global
if (typeof window !== 'undefined') {
    window.EscalacaoIdeal = EscalacaoIdeal;
}

