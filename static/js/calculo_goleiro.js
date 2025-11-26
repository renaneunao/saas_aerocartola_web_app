/**
 * Cálculo de goleiros - Implementação JavaScript
 * Baseado em calculo_posicoes/calculo_goleiro.py
 */

class CalculoGoleiro {
    constructor(data) {
        // VERIFICAÇÃO CRÍTICA: Se o bloqueador estiver ativo, lançar erro
        if (window.BLOQUEAR_CALCULO_GOLEIRO === true) {
            console.error(`[CALCULO GOLEIRO] 🚫🚫🚫 ERRO: Tentativa de criar CalculoGoleiro com bloqueador ativo!`);
            console.trace('[CALCULO GOLEIRO] Stack trace do construtor bloqueado:');
            throw new Error('Cálculo bloqueado: ranking salvo encontrado');
        }

        this.rodada_atual = data.rodada_atual;
        this.perfil_peso_jogo = data.perfil_peso_jogo;
        this.perfil_peso_sg = data.perfil_peso_sg;
        this.atletas = data.atletas;
        this.adversarios_dict = data.adversarios_dict || {};
        this.pontuados_data = data.pontuados_data || {};
        this.gols_data = data.gols_data || {};
        this.escalacoes_data = data.escalacoes_data || {};
        this.pesos = data.pesos || {
            FATOR_MEDIA: 0.2,
            FATOR_FF: 4.5,
            FATOR_FD: 6.5,
            FATOR_SG: 1.5,
            FATOR_PESO_JOGO: 1.5,
            FATOR_GOL_ADVERSARIO: 2.0
        };
    }

    /**
     * Calcula os melhores goleiros
     * @param {number} topN - Número de goleiros a retornar
     * @returns {Array} Array de goleiros ordenados por pontuação
     */
    calcularMelhoresGoleiros(topN = 20) {
        console.log(`[DEBUG GOLEIRO] escalacoes_data recebido:`, this.escalacoes_data);
        console.log(`[DEBUG GOLEIRO] Total de keys em escalacoes_data:`, Object.keys(this.escalacoes_data || {}).length);
        const resultados = [];

        for (const atleta of this.atletas) {
            const resultado = this.calcularPontuacao(atleta);
            resultados.push(resultado);
        }

        // Ordenar por pontuação total (decrescente) e pegar top N
        resultados.sort((a, b) => b.pontuacao_total - a.pontuacao_total);
        const topResultados = resultados.slice(0, topN);

        return topResultados;
    }

    /**
     * Calcula a pontuação de um goleiro específico
     * @param {Object} atleta - Dados do atleta
     * @returns {Object} Resultado com pontuação e métricas
     */
    calcularPontuacao(atleta) {
        const {
            atleta_id,
            apelido,
            clube_id,
            clube_nome,
            clube_abrev,
            clube_escudo_url,
            pontos_num,
            media_num,
            preco_num,
            jogos_num,
            peso_jogo,
            peso_sg,
            adversario_id
        } = atleta;

        console.log(`[DEBUG CALCULO] ========== Calculando pontuação para ${apelido} (ID: ${atleta_id}) ==========`);
        console.log(`[DEBUG CALCULO] Dados do atleta:`, {
            atleta_id,
            apelido,
            clube_id,
            media_num,
            peso_jogo,
            peso_sg,
            adversario_id
        });
        console.log(`[DEBUG CALCULO] Pesos configurados:`, this.pesos);

        // Valores padrão se weights estiverem faltando
        const peso_sg_final = peso_sg || 0;
        const peso_jogo_original = peso_jogo || 0;
        console.log(`[DEBUG CALCULO] peso_sg_final = ${peso_sg_final}, peso_jogo_original = ${peso_jogo_original}`);

        // Buscar médias do atleta (padrão)
        const atletaStats = this.pontuados_data[atleta_id] || {};
        const media_ds = atletaStats.avg_ds || 0;
        const media_ff = atletaStats.avg_ff || 0;
        const media_fs = atletaStats.avg_fs || 0;
        const media_fd = atletaStats.avg_fd || 0;
        const media_g = atletaStats.avg_g || 0;
        const media_a = atletaStats.avg_a || 0;

        let media_gols_adversario = 0;
        let adversario_nome = atleta.adversario_nome || 'N/A';
        let tem_adversario = false;

        // Variáveis para scouts cedidos
        let media_ds_cedidos = 0;
        let media_ff_cedidos = 0;
        let media_fs_cedidos = 0;
        let media_fd_cedidos = 0;
        let media_g_cedidos = 0;
        let media_a_cedidos = 0;
        
        // Variáveis para finalizações produzidas pelo adversário (para peso_finalizacoes)
        let ff_avg_adversario = 0;
        let fd_avg_adversario = 0;

        // Encontrar o adversário na rodada atual
        console.log(`[DEBUG CALCULO] Verificando adversário: adversario_id=${adversario_id}, clube_id=${clube_id}`);

        if (adversario_id && this.adversarios_dict[clube_id] === adversario_id) {
            tem_adversario = true;
            console.log(`[DEBUG CALCULO] ✅ Adversário encontrado!`);

            // Calcular finalizações esperadas do adversário (média das últimas rodadas)
            const adversarioStats = this.pontuados_data[adversario_id];
            if (adversarioStats) {
                // O que o adversário PRODUZ (avg_ff, avg_fd) para o peso_finalizacoes
                ff_avg_adversario = adversarioStats.avg_ff || 0;
                fd_avg_adversario = adversarioStats.avg_fd || 0;

                // Buscar scouts CEDIDOS pelo adversário para o cruzamento padrão
                media_ds_cedidos = adversarioStats.avg_ds_cedidos || 0;
                media_ff_cedidos = adversarioStats.avg_ff_cedidos || 0;
                media_fs_cedidos = adversarioStats.avg_fs_cedidos || 0;
                media_fd_cedidos = adversarioStats.avg_fd_cedidos || 0;
                media_g_cedidos = adversarioStats.avg_g_cedidos || 0;
                media_a_cedidos = adversarioStats.avg_a_cedidos || 0;
            }

            // Calcular média de gols do adversário
            const adversarioGols = this.gols_data[adversario_id];
            if (adversarioGols) {
                media_gols_adversario = adversarioGols.media_gols || 0;
            }
        } else {
            console.log(`[DEBUG CALCULO] ❌ Adversário NÃO encontrado ou não corresponde`);
        }

        // Calcular base BRUTA (sem fatores) - apenas valores brutos
        const base_bruta = media_num + 
            (tem_adversario ? peso_jogo_original : 0) +
            (tem_adversario ? (ff_avg_adversario + fd_avg_adversario) : 0) +
            (tem_adversario ? media_gols_adversario : 0) +
            (media_ds * media_ds_cedidos) +
            (media_ff * media_ff_cedidos) +
            (media_fs * media_fs_cedidos) +
            (media_fd * media_fd_cedidos) +
            (media_g * media_g_cedidos) +
            (media_a * media_a_cedidos);

        // Garantir que base_bruta seja não negativa antes de calcular a raiz quadrada
        const base_bruta_non_neg = Math.max(0, base_bruta);

        // Aplicar raiz quadrada na base bruta PRIMEIRO
        const base_raiz = Math.sqrt(base_bruta_non_neg);

        console.log(`[DEBUG CALCULO] base_bruta: ${base_bruta.toFixed(2)} (sem fatores)`);
        console.log(`[DEBUG CALCULO] base_raiz: sqrt(${base_bruta_non_neg.toFixed(2)}) = ${base_raiz.toFixed(2)}`);

        // Aplicar TODOS os fatores DEPOIS da raiz quadrada para ter impacto proporcional
        // Calcular soma ponderada dos fatores baseada na proporção de cada componente
        let soma_fatores_ponderada = 0;
        
        if (base_bruta_non_neg > 0) {
            // Cada componente contribui proporcionalmente ao seu peso na base
            if (media_num > 0) {
                const peso_media = media_num / base_bruta_non_neg;
                soma_fatores_ponderada += peso_media * this.pesos.FATOR_MEDIA;
            }
            
            if (tem_adversario && peso_jogo_original > 0) {
                const peso_jogo_na_base = peso_jogo_original / base_bruta_non_neg;
                soma_fatores_ponderada += peso_jogo_na_base * this.pesos.FATOR_PESO_JOGO;
            }
            
            // Finalizações produzidas pelo adversário (FATOR_FF e FATOR_FD)
            if (tem_adversario) {
                const contrib_ff_adv = ff_avg_adversario / base_bruta_non_neg;
                const contrib_fd_adv = fd_avg_adversario / base_bruta_non_neg;
                soma_fatores_ponderada += contrib_ff_adv * this.pesos.FATOR_FF;
                soma_fatores_ponderada += contrib_fd_adv * this.pesos.FATOR_FD;
            }
            
            // Penalização por gols do adversário (subtração)
            if (tem_adversario && media_gols_adversario > 0) {
                const peso_gols_adv = media_gols_adversario / base_bruta_non_neg;
                soma_fatores_ponderada -= peso_gols_adv * this.pesos.FATOR_GOL_ADVERSARIO;
            }
            
            // Scouts padrão (com fatores opcionais)
            const fator_ds = this.pesos.FATOR_DS || 0;
            const contrib_ds = (media_ds * media_ds_cedidos) / base_bruta_non_neg;
            const contrib_ff = (media_ff * media_ff_cedidos) / base_bruta_non_neg;
            const contrib_fs = (media_fs * media_fs_cedidos) / base_bruta_non_neg;
            const contrib_fd = (media_fd * media_fd_cedidos) / base_bruta_non_neg;
            const contrib_g = (media_g * media_g_cedidos) / base_bruta_non_neg;
            const contrib_a = (media_a * media_a_cedidos) / base_bruta_non_neg;
            
            soma_fatores_ponderada += contrib_ds * fator_ds;
            soma_fatores_ponderada += contrib_ff * (this.pesos.FATOR_FF_ATAQUE || 0);
            soma_fatores_ponderada += contrib_fs * (this.pesos.FATOR_FS || 0);
            soma_fatores_ponderada += contrib_fd * (this.pesos.FATOR_FD_ATAQUE || 0);
            soma_fatores_ponderada += contrib_g * (this.pesos.FATOR_G || 0);
            soma_fatores_ponderada += contrib_a * (this.pesos.FATOR_A || 0);
        } else {
            // Se base_bruta é 0, usar apenas o fator da média como mínimo
            soma_fatores_ponderada = this.pesos.FATOR_MEDIA;
        }
        
        // Aplicar FATOR_SG (multiplicador adicional)
        const fator_sg = 1 + peso_sg_final * this.pesos.FATOR_SG;
        const fator_multiplicador = Math.max(0, soma_fatores_ponderada) * fator_sg; // Garantir não negativo

        // Aplicar todos os fatores DEPOIS da raiz
        const pontuacao_total_final = base_raiz * fator_multiplicador;
        
        console.log(`[DEBUG CALCULO] fator_multiplicador (soma ponderada): ${soma_fatores_ponderada.toFixed(4)}`);
        console.log(`[DEBUG CALCULO] fator_sg: ${fator_sg.toFixed(4)}`);
        console.log(`[DEBUG CALCULO] fator_multiplicador_total: ${fator_multiplicador.toFixed(4)}`);
        console.log(`[DEBUG CALCULO] pontuacao_total_final: ${base_raiz.toFixed(2)} × ${fator_multiplicador.toFixed(4)} = ${pontuacao_total_final.toFixed(2)}`);

        // Verificar se o resultado final é válido
        if (isNaN(pontuacao_total_final) || !isFinite(pontuacao_total_final)) {
            console.error(`[DEBUG CALCULO] ⚠️⚠️⚠️ ERRO: pontuacao_total_final é NaN ou inválido!`);
            console.error(`[DEBUG CALCULO] pontuacao_total = ${pontuacao_total}`);
        }

        console.log(`[DEBUG CALCULO] ========== FIM do cálculo para ${apelido} ==========`);

        // Buscar escalações do atleta
        const escalacoes = this.escalacoes_data[atleta_id] || 0;
        console.log(`[DEBUG GOLEIRO] ${apelido} (ID: ${atleta_id}): escalacoes_data[${atleta_id}] = ${escalacoes}, tipo: ${typeof escalacoes}`);
        console.log(`[DEBUG GOLEIRO] escalacoes_data keys disponíveis:`, Object.keys(this.escalacoes_data || {}).slice(0, 10));

        return {
            atleta_id,
            apelido,
            clube_id,
            clube_nome,
            clube_abrev,
            clube_escudo_url,
            pontuacao_total: isNaN(pontuacao_total_final) ? 0 : parseFloat(pontuacao_total_final.toFixed(2)),
            media: parseFloat(media_num.toFixed(2)),
            preco: parseFloat(preco_num.toFixed(2)),
            jogos: jogos_num,
            peso_jogo: parseFloat((tem_adversario ? peso_jogo_original * this.pesos.FATOR_PESO_JOGO : 0).toFixed(2)),
            peso_sg: parseFloat(peso_sg_final.toFixed(2)),
            peso_finalizacoes: parseFloat((tem_adversario ? (ff_avg_adversario * this.pesos.FATOR_FF + fd_avg_adversario * this.pesos.FATOR_FD) : 0).toFixed(2)),
            media_gols_adversario: parseFloat(media_gols_adversario.toFixed(2)),
            adversario_id,
            adversario_nome,
            escalacoes: escalacoes
        };
    }
}

// Exportar para uso global
if (typeof module !== 'undefined' && module.exports) {
    module.exports = CalculoGoleiro;
} else {
    window.CalculoGoleiro = CalculoGoleiro;
}

