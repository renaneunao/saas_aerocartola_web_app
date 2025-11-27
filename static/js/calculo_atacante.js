/**
 * Cálculo de atacantes - Implementação JavaScript
 * Baseado em calculo_posicoes/calculo_atacante.py
 */

class CalculoAtacante {
    constructor(data) {
        // VERIFICAÇÃO CRÍTICA: Se o bloqueador estiver ativo, lançar erro
        if (window.BLOQUEAR_CALCULO_ATACANTE === true) {
            console.error(`[CALCULO ATACANTE] 🚫🚫🚫 ERRO: Tentativa de criar CalculoAtacante com bloqueador ativo!`);
            console.trace('[CALCULO ATACANTE] Stack trace do construtor bloqueado:');
            throw new Error('Cálculo bloqueado: ranking salvo encontrado');
        }

        this.rodada_atual = data.rodada_atual;
        this.perfil_peso_jogo = data.perfil_peso_jogo;
        this.perfil_peso_sg = data.perfil_peso_sg;
        this.atletas = data.atletas;
        this.adversarios_dict = data.adversarios_dict || {};
        this.pontuados_data = data.pontuados_data || {};
        this.escalacoes_data = data.escalacoes_data || {};
        this.clubes_dict = data.clubes_dict || {};
        this.pesos = data.pesos || {
            FATOR_MEDIA: 2.4,
            FATOR_DS: 2.0,
            FATOR_FF: 3.3,
            FATOR_FS: 3.0,
            FATOR_FD: 3.7,
            FATOR_G: 6.5,
            FATOR_A: 4.0,
            FATOR_ESCALACAO: 3.5,
            FATOR_PESO_JOGO: 4.0
        };
    }

    calcularMelhoresAtacantes(topN = 20) {
        console.log(`[DEBUG ATACANTE] escalacoes_data recebido:`, this.escalacoes_data);
        console.log(`[DEBUG ATACANTE] Total de keys em escalacoes_data:`, Object.keys(this.escalacoes_data || {}).length);
        const resultados = [];
        const totalEscalacoes = this.calcularTotalEscalacoes();
        console.log(`[DEBUG ATACANTE] Total de escalações: ${totalEscalacoes}`);

        for (let i = 0; i < this.atletas.length; i++) {
            const atleta = this.atletas[i];
            const resultado = this.calcularPontuacao(atleta, totalEscalacoes);
            resultados.push(resultado);

            // Debug apenas para os 3 primeiros
            if (i < 3) {
                console.log(`[DEBUG ATACANTE ${i + 1}] ${atleta.apelido}: pontuacao_total = ${resultado.pontuacao_total}`);
            }
        }

        resultados.sort((a, b) => b.pontuacao_total - a.pontuacao_total);
        const topResultados = resultados.slice(0, topN);

        return topResultados;
    }

    calcularTotalEscalacoes() {
        if (!this.escalacoes_data || Object.keys(this.escalacoes_data).length === 0) {
            return 1.0;
        }
        return Object.values(this.escalacoes_data).reduce((sum, esc) => sum + (esc || 0), 0) || 1.0;
    }

    calcularPontuacao(atleta, totalEscalacoes) {
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
            adversario_id,
            adversario_nome
        } = atleta;

        // Garantir valores numéricos válidos
        const media_num_val = parseFloat(media_num) || 0;
        const preco_num_val = parseFloat(preco_num) || 0;
        const jogos_num_val = parseInt(jogos_num) || 0;

        // Valores padrão
        const peso_jogo_original = peso_jogo || 0;

        // Buscar médias do atleta
        const atletaStats = this.pontuados_data[atleta_id] || {};
        const media_ds = atletaStats.avg_ds || 0;
        const media_ff = atletaStats.avg_ff || 0;
        const media_fs = atletaStats.avg_fs || 0;
        const media_fd = atletaStats.avg_fd || 0;
        const media_g = atletaStats.avg_g || 0;
        const media_a = atletaStats.avg_a || 0;

        let media_ds_cedidos = 0;
        let media_ff_cedidos = 0;
        let media_fs_cedidos = 0;
        let media_fd_cedidos = 0;
        let media_g_cedidos = 0;
        let media_a_cedidos = 0;
        let tem_adversario = false;

        // Encontrar o adversário na rodada atual
        if (adversario_id && this.adversarios_dict[clube_id] === adversario_id) {
            tem_adversario = true;

            // Buscar médias de scouts cedidos pelo adversário
            const adversarioStats = this.pontuados_data[adversario_id] || {};
            media_ds_cedidos = adversarioStats.avg_ds_cedidos || 0;
            media_ff_cedidos = adversarioStats.avg_ff_cedidos || 0;
            media_fs_cedidos = adversarioStats.avg_fs_cedidos || 0;
            media_fd_cedidos = adversarioStats.avg_fd_cedidos || 0;
            media_g_cedidos = adversarioStats.avg_g_cedidos || 0;
            media_a_cedidos = adversarioStats.avg_a_cedidos || 0;
        }

        // Calcular base BRUTA (sem fatores) - apenas valores brutos multiplicados
        const base_bruta = media_num_val + 
            (tem_adversario ? peso_jogo_original : 0) +
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

        // DEBUG DETALHADO PARA TODOS OS ATLETAS
        console.log(`\n[DEBUG ATACANTE] ========== ${apelido} (ID: ${atleta_id}) ==========`);
        console.log(`  Dados recebidos:`, { atleta_id, media_num, peso_jogo, adversario_id, clube_id });
        console.log(`  Valores numéricos: media_num_val=${media_num_val}`);
        console.log(`  base_bruta: ${base_bruta.toFixed(2)} (sem fatores)`);
        console.log(`  base_raiz: sqrt(${base_bruta_non_neg.toFixed(2)}) = ${base_raiz.toFixed(2)}`);

        // Aplicar TODOS os fatores DEPOIS da raiz quadrada para ter impacto proporcional
        // Calcular soma ponderada dos fatores baseada na proporção de cada componente
        let soma_fatores_ponderada = 0;
        
        if (base_bruta_non_neg > 0) {
            // Cada componente contribui proporcionalmente ao seu peso na base
            if (media_num_val > 0) {
                const peso_media = media_num_val / base_bruta_non_neg;
                soma_fatores_ponderada += peso_media * this.pesos.FATOR_MEDIA;
            }
            
            if (tem_adversario && peso_jogo_original > 0) {
                const peso_jogo_na_base = peso_jogo_original / base_bruta_non_neg;
                soma_fatores_ponderada += peso_jogo_na_base * this.pesos.FATOR_PESO_JOGO;
            }
            
            const contrib_ds = (media_ds * media_ds_cedidos) / base_bruta_non_neg;
            const contrib_ff = (media_ff * media_ff_cedidos) / base_bruta_non_neg;
            const contrib_fs = (media_fs * media_fs_cedidos) / base_bruta_non_neg;
            const contrib_fd = (media_fd * media_fd_cedidos) / base_bruta_non_neg;
            const contrib_g = (media_g * media_g_cedidos) / base_bruta_non_neg;
            const contrib_a = (media_a * media_a_cedidos) / base_bruta_non_neg;
            
            soma_fatores_ponderada += contrib_ds * this.pesos.FATOR_DS;
            soma_fatores_ponderada += contrib_ff * this.pesos.FATOR_FF;
            soma_fatores_ponderada += contrib_fs * this.pesos.FATOR_FS;
            soma_fatores_ponderada += contrib_fd * this.pesos.FATOR_FD;
            soma_fatores_ponderada += contrib_g * this.pesos.FATOR_G;
            soma_fatores_ponderada += contrib_a * this.pesos.FATOR_A;
        } else {
            // Se base_bruta é 0, usar apenas o fator da média como mínimo
            soma_fatores_ponderada = this.pesos.FATOR_MEDIA;
        }
        
        // O fator multiplicador é a média ponderada dos fatores
        const fator_multiplicador = soma_fatores_ponderada;

        // Calcular peso de escalação
        const escalacoes = this.escalacoes_data[atleta_id] || 0;
        console.log(`[DEBUG ATACANTE] ${apelido} (ID: ${atleta_id}): escalacoes_data[${atleta_id}] = ${escalacoes}, tipo: ${typeof escalacoes}`);
        console.log(`[DEBUG ATACANTE] escalacoes_data keys disponíveis:`, Object.keys(this.escalacoes_data || {}).slice(0, 10));
        const percentual_escalacoes = totalEscalacoes > 0 ? escalacoes / totalEscalacoes : 0;
        // Usar raiz quadrada do percentual para amplificar a influência (valores pequenos têm impacto maior)
        // Exemplo: 3.90% → sqrt(0.039) = 0.197 = 19.7% (amplificado)
        const percentual_ajustado = Math.sqrt(percentual_escalacoes);
        const peso_escalacao = 1 + percentual_ajustado * this.pesos.FATOR_ESCALACAO;

        // Aplicar todos os fatores DEPOIS da raiz
        const pontuacao_total_final = base_raiz * fator_multiplicador * peso_escalacao;

        console.log(`  fator_multiplicador (soma ponderada): ${fator_multiplicador.toFixed(4)}`);
        console.log(`  escalacoes: ${escalacoes}, totalEscalacoes: ${totalEscalacoes}, percentual: ${percentual_escalacoes.toFixed(4)}`);
        console.log(`  peso_escalacao: ${peso_escalacao.toFixed(4)}`);
        console.log(`  pontuacao_total_final: ${base_raiz.toFixed(2)} × ${fator_multiplicador.toFixed(4)} × ${peso_escalacao.toFixed(4)} = ${pontuacao_total_final.toFixed(2)}`);
        console.log(`[DEBUG ATACANTE] ========================================\n`);

        // Buscar peso_sg do atleta (mesmo que não seja usado no cálculo)
        const peso_sg_final = atleta.peso_sg || 0;
        const peso_jogo_final = tem_adversario ? peso_jogo_original * this.pesos.FATOR_PESO_JOGO : 0;

        return {
            atleta_id,
            apelido,
            clube_id,
            clube_nome,
            clube_abrev,
            clube_escudo_url,
            pontuacao_total: isNaN(pontuacao_total_final) ? 0 : parseFloat(pontuacao_total_final.toFixed(2)),
            media: isNaN(media_num_val) ? 0 : parseFloat(media_num_val.toFixed(2)),
            preco: isNaN(preco_num_val) ? 0 : parseFloat(preco_num_val.toFixed(2)),
            jogos: jogos_num_val,
            peso_jogo: parseFloat(peso_jogo_final.toFixed(2)),
            peso_sg: parseFloat(peso_sg_final.toFixed(2)),
            media_ds: parseFloat(media_ds.toFixed(2)),
            media_ds_cedidos: parseFloat(media_ds_cedidos.toFixed(2)),
            media_ff: parseFloat(media_ff.toFixed(2)),
            media_fs: parseFloat(media_fs.toFixed(2)),
            media_fd: parseFloat(media_fd.toFixed(2)),
            media_g: parseFloat(media_g.toFixed(2)),
            media_a: parseFloat(media_a.toFixed(2)),
            adversario_id,
            adversario_nome,
            peso_escalacao: parseFloat(peso_escalacao.toFixed(4)),
            escalacoes: escalacoes
        };
    }
}

// Exportar para uso global
if (typeof module !== 'undefined' && module.exports) {
    module.exports = CalculoAtacante;
} else {
    window.CalculoAtacante = CalculoAtacante;
}

