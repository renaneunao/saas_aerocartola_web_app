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

        // Fator 1: Média do jogador
        const pontos_media = media_num * this.pesos.FATOR_MEDIA;
        console.log(`[DEBUG CALCULO] pontos_media = ${media_num} * ${this.pesos.FATOR_MEDIA} = ${pontos_media}`);

        // Valores padrão se weights estiverem faltando
        const peso_sg_final = peso_sg || 0;
        const peso_jogo_original = peso_jogo || 0;
        console.log(`[DEBUG CALCULO] peso_sg_final = ${peso_sg_final}, peso_jogo_original = ${peso_jogo_original}`);

        let peso_jogo_final = 0;
        let peso_finalizacoes = 0;
        let media_gols_adversario = 0;
        let adversario_nome = atleta.adversario_nome || 'N/A';

        // Encontrar o adversário na rodada atual
        console.log(`[DEBUG CALCULO] Verificando adversário: adversario_id=${adversario_id}, clube_id=${clube_id}`);
        console.log(`[DEBUG CALCULO] adversarios_dict[${clube_id}] =`, this.adversarios_dict[clube_id]);
        
        if (adversario_id && this.adversarios_dict[clube_id] === adversario_id) {
            console.log(`[DEBUG CALCULO] ✅ Adversário encontrado!`);
            peso_jogo_final = peso_jogo_original * this.pesos.FATOR_PESO_JOGO;
            console.log(`[DEBUG CALCULO] peso_jogo_final = ${peso_jogo_original} * ${this.pesos.FATOR_PESO_JOGO} = ${peso_jogo_final}`);

            // Calcular finalizações esperadas do adversário (média das últimas rodadas)
            const adversarioStats = this.pontuados_data[adversario_id];
            console.log(`[DEBUG CALCULO] adversarioStats para ${adversario_id}:`, adversarioStats);
            if (adversarioStats) {
                const ff_avg = adversarioStats.avg_ff || 0;
                const fd_avg = adversarioStats.avg_fd || 0;
                peso_finalizacoes = (ff_avg * this.pesos.FATOR_FF) + (fd_avg * this.pesos.FATOR_FD);
                console.log(`[DEBUG CALCULO] peso_finalizacoes = (${ff_avg} * ${this.pesos.FATOR_FF}) + (${fd_avg} * ${this.pesos.FATOR_FD}) = ${peso_finalizacoes}`);
            } else {
                console.log(`[DEBUG CALCULO] ⚠️ adversarioStats não encontrado para ${adversario_id}`);
            }

            // Calcular média de gols do adversário
            const adversarioGols = this.gols_data[adversario_id];
            console.log(`[DEBUG CALCULO] adversarioGols para ${adversario_id}:`, adversarioGols);
            if (adversarioGols) {
                media_gols_adversario = adversarioGols.media_gols || 0;
                console.log(`[DEBUG CALCULO] media_gols_adversario = ${media_gols_adversario}`);
            } else {
                console.log(`[DEBUG CALCULO] ⚠️ adversarioGols não encontrado para ${adversario_id}`);
            }
        } else {
            console.log(`[DEBUG CALCULO] ❌ Adversário NÃO encontrado ou não corresponde`);
            console.log(`[DEBUG CALCULO] Condição: adversario_id=${adversario_id} && adversarios_dict[${clube_id}]=${this.adversarios_dict[clube_id]} === ${adversario_id}`);
        }

        // Calcular pontuação total
        // Fórmula: ((pontos_media + peso_jogo + peso_finalizacoes - (media_gols_adversario * FATOR_GOL_ADVERSARIO)) * (FATOR_SG + peso_sg))
        const base_pontuacao = pontos_media + peso_jogo_final + peso_finalizacoes - (media_gols_adversario * this.pesos.FATOR_GOL_ADVERSARIO);
        console.log(`[DEBUG CALCULO] base_pontuacao = ${pontos_media} + ${peso_jogo_final} + ${peso_finalizacoes} - (${media_gols_adversario} * ${this.pesos.FATOR_GOL_ADVERSARIO}) = ${base_pontuacao}`);
        
        let pontuacao_total = base_pontuacao * (this.pesos.FATOR_SG + peso_sg_final);
        console.log(`[DEBUG CALCULO] pontuacao_total = ${base_pontuacao} * (${this.pesos.FATOR_SG} + ${peso_sg_final}) = ${pontuacao_total}`);

        // Garantir que pontuacao_total seja não negativa antes de calcular a raiz quadrada
        if (pontuacao_total < 0) {
            console.log(`[DEBUG CALCULO] ⚠️ pontuacao_total é negativa (${pontuacao_total}), definindo como 0`);
            pontuacao_total = 0;
        }

        // Calcular pontuação final: raiz quadrada (sem fator de escalação para goleiros)
        const pontuacao_total_final = Math.sqrt(pontuacao_total);
        console.log(`[DEBUG CALCULO] pontuacao_total_final = sqrt(${pontuacao_total}) = ${pontuacao_total_final}`);
        
        // Verificar se o resultado final é válido
        if (isNaN(pontuacao_total_final) || !isFinite(pontuacao_total_final)) {
            console.error(`[DEBUG CALCULO] ⚠️⚠️⚠️ ERRO: pontuacao_total_final é NaN ou inválido!`);
            console.error(`[DEBUG CALCULO] pontuacao_total = ${pontuacao_total}`);
        }
        
        console.log(`[DEBUG CALCULO] ========== FIM do cálculo para ${apelido} ==========`);

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
            peso_jogo: parseFloat(peso_jogo_final.toFixed(2)),
            peso_sg: parseFloat(peso_sg_final.toFixed(2)),
            peso_finalizacoes: parseFloat(peso_finalizacoes.toFixed(2)),
            media_gols_adversario: parseFloat(media_gols_adversario.toFixed(2)),
            adversario_id,
            adversario_nome
        };
    }
}

// Exportar para uso global
if (typeof module !== 'undefined' && module.exports) {
    module.exports = CalculoGoleiro;
} else {
    window.CalculoGoleiro = CalculoGoleiro;
}

