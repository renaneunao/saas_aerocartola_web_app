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

        // Buscar médias do atleta (padrão)
        const atletaStats = this.pontuados_data[atleta_id] || {};
        const media_ds = atletaStats.avg_ds || 0;
        const media_ff = atletaStats.avg_ff || 0;
        const media_fs = atletaStats.avg_fs || 0;
        const media_fd = atletaStats.avg_fd || 0;
        const media_g = atletaStats.avg_g || 0;
        const media_a = atletaStats.avg_a || 0;

        let peso_jogo_final = 0;
        let peso_finalizacoes = 0;
        let media_gols_adversario = 0;
        let adversario_nome = atleta.adversario_nome || 'N/A';

        // Variáveis para scouts cedidos
        let media_ds_cedidos = 0;
        let media_ff_cedidos = 0;
        let media_fs_cedidos = 0;
        let media_fd_cedidos = 0;
        let media_g_cedidos = 0;
        let media_a_cedidos = 0;

        // Encontrar o adversário na rodada atual
        console.log(`[DEBUG CALCULO] Verificando adversário: adversario_id=${adversario_id}, clube_id=${clube_id}`);

        if (adversario_id && this.adversarios_dict[clube_id] === adversario_id) {
            console.log(`[DEBUG CALCULO] ✅ Adversário encontrado!`);
            peso_jogo_final = peso_jogo_original * this.pesos.FATOR_PESO_JOGO;

            // Calcular finalizações esperadas do adversário (média das últimas rodadas)
            const adversarioStats = this.pontuados_data[adversario_id];
            if (adversarioStats) {
                // Aqui usamos o que o adversário PRODUZ (avg_ff, avg_fd) para o peso_finalizacoes
                // ATENÇÃO: Se o backend não retornar avg_ff/avg_fd produzidos para adversários, isso será 0.
                // Mas o foco agora é adicionar os CEDIDOS para o cruzamento padrão.
                const ff_avg = adversarioStats.avg_ff || 0;
                const fd_avg = adversarioStats.avg_fd || 0;
                peso_finalizacoes = (ff_avg * this.pesos.FATOR_FF) + (fd_avg * this.pesos.FATOR_FD);

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

        // Calcular contribuição dos scouts padrão (com pesos opcionais)
        // Goleiros podem não ter esses pesos definidos, então default para 0
        const fator_ds = this.pesos.FATOR_DS || 0;
        // FATOR_FF e FATOR_FD já existem mas são usados para peso_finalizacoes (produzidos pelo adversário).
        // Se quisermos usar para o goleiro fazendo FF/FD (raro), teríamos que ter cuidado para não duplicar.
        // Mas a lógica do usuário é "cruzamento com cedidos".
        // Vamos assumir que se o goleiro tem media_ff, ele deve ser premiado se o adversário cede FF.
        // Porém, FATOR_FF no Goleiro é alto (4.5) porque é usado para finalizações SOFRIDAS.
        // Se usarmos o mesmo peso para finalizações FEITAS pelo goleiro, pode ficar desproporcional.
        // Mas seguindo a instrução estrita: "conserte cada calculo... cruzamento seja feito com todos os cedidos".
        // Vou usar os fatores se existirem.

        const pontos_ds = media_ds * media_ds_cedidos * fator_ds;

        // Para FF e FD, o peso atual é para "Finalizações Sofridas" (peso_finalizacoes).
        // Não devemos usar esse peso para "Finalizações Feitas" pelo goleiro.
        // Vou verificar se existem pesos específicos ou usar 0 se não houver distinção.
        // Como não há pesos distintos no objeto padrão, e usar 4.5 para um chute do goleiro seria estranho,
        // vou usar 0 se não houver um peso explícito para "Goleiro Atacando", ou usar o peso genérico se o usuário quiser.
        // Dado o risco, vou adicionar mas comentar que depende de pesos novos, ou usar pesos pequenos padrão se não existirem.
        // Melhor: usar os pesos existentes mas sabendo que media_ff do goleiro é quase 0.

        const pontos_ff = media_ff * media_ff_cedidos * (this.pesos.FATOR_FF_ATAQUE || 0);
        const pontos_fs = media_fs * media_fs_cedidos * (this.pesos.FATOR_FS || 0);
        const pontos_fd = media_fd * media_fd_cedidos * (this.pesos.FATOR_FD_ATAQUE || 0);
        const pontos_g = media_g * media_g_cedidos * (this.pesos.FATOR_G || 0);
        const pontos_a = media_a * media_a_cedidos * (this.pesos.FATOR_A || 0);

        // Calcular pontuação total
        // Fórmula: ((pontos_media + peso_jogo + peso_finalizacoes - (media_gols_adversario * FATOR_GOL_ADVERSARIO)) * (FATOR_SG + peso_sg))
        // AGORA ADICIONANDO SCOUTS PADRÃO AO BASE_PONTUACAO
        const base_pontuacao = (pontos_media + peso_jogo_final + peso_finalizacoes - (media_gols_adversario * this.pesos.FATOR_GOL_ADVERSARIO)) +
            (pontos_ds + pontos_ff + pontos_fs + pontos_fd + pontos_g + pontos_a);

        console.log(`[DEBUG CALCULO] base_pontuacao = (${pontos_media} + ${peso_jogo_final} + ${peso_finalizacoes} - (${media_gols_adversario} * ${this.pesos.FATOR_GOL_ADVERSARIO})) + (${pontos_ds} + ${pontos_ff} + ${pontos_fs} + ${pontos_fd} + ${pontos_g} + ${pontos_a}) = ${base_pontuacao}`);

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

