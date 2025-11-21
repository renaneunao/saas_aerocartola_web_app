/**
 * Cálculo de zagueiros - Implementação JavaScript
 * Baseado em calculo_posicoes/calculo_zagueiro.py
 */

class CalculoZagueiro {
    constructor(data) {
        // VERIFICAÇÃO CRÍTICA: Se o bloqueador estiver ativo, lançar erro
        if (window.BLOQUEAR_CALCULO_ZAGUEIRO === true) {
            console.error(`[CALCULO ZAGUEIRO] 🚫🚫🚫 ERRO: Tentativa de criar CalculoZagueiro com bloqueador ativo!`);
            console.trace('[CALCULO ZAGUEIRO] Stack trace do construtor bloqueado:');
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
            FATOR_MEDIA: 1.5,
            FATOR_DS: 4.5,
            FATOR_SG: 4.0,
            FATOR_ESCALACAO: 5.0,
            FATOR_PESO_JOGO: 5.0
        };
    }

    calcularMelhoresZagueiros(topN = 20) {
        const resultados = [];
        const totalEscalacoes = this.calcularTotalEscalacoes();
        console.log(`[DEBUG ZAGUEIRO] Total de escalações: ${totalEscalacoes}`);

        for (let i = 0; i < this.atletas.length; i++) {
            const atleta = this.atletas[i];
            const resultado = this.calcularPontuacao(atleta, totalEscalacoes);
            resultados.push(resultado);

            // Debug apenas para os 3 primeiros
            if (i < 3) {
                console.log(`[DEBUG ZAGUEIRO ${i + 1}] ${atleta.apelido}: pontuacao_total = ${resultado.pontuacao_total}`);
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
            peso_sg,
            adversario_id,
            adversario_nome
        } = atleta;

        // DEBUG DETALHADO PARA TODOS OS ATLETAS
        console.log(`\n[DEBUG ZAGUEIRO] ========== ${apelido} (ID: ${atleta_id}) ==========`);
        console.log(`  Dados recebidos:`, {
            atleta_id,
            media_num,
            peso_jogo,
            peso_sg,
            adversario_id,
            clube_id
        });

        // Garantir valores numéricos válidos
        const media_num_val = parseFloat(media_num) || 0;
        const preco_num_val = parseFloat(preco_num) || 0;
        const jogos_num_val = parseInt(jogos_num) || 0;

        console.log(`  Valores numéricos: media_num_val=${media_num_val}, preco_num_val=${preco_num_val}, jogos_num_val=${jogos_num_val}`);

        // Fator 1: Média do jogador
        const pontos_media = media_num_val * this.pesos.FATOR_MEDIA;
        console.log(`  pontos_media: ${media_num_val} × ${this.pesos.FATOR_MEDIA} = ${pontos_media.toFixed(2)}`);

        // Valores padrão
        const peso_sg_final = peso_sg || 0;
        const peso_jogo_original = peso_jogo || 0;
        console.log(`  peso_sg_final: ${peso_sg_final}, peso_jogo_original: ${peso_jogo_original}`);

        // Buscar médias do atleta
        const atletaStats = this.pontuados_data[atleta_id] || {};
        console.log(`  atletaStats (pontuados_data[${atleta_id}]):`, atletaStats);
        const media_ds = atletaStats.avg_ds || 0;
        const media_ff = atletaStats.avg_ff || 0;
        const media_fs = atletaStats.avg_fs || 0;
        const media_fd = atletaStats.avg_fd || 0;
        const media_g = atletaStats.avg_g || 0;
        const media_a = atletaStats.avg_a || 0;
        console.log(`  media_ds: ${media_ds}`);

        let peso_jogo_final = 0;
        let media_ds_cedidos = 0;
        let media_ff_cedidos = 0;
        let media_fs_cedidos = 0;
        let media_fd_cedidos = 0;
        let media_g_cedidos = 0;
        let media_a_cedidos = 0;

        console.log(`  Verificando adversário: adversario_id=${adversario_id}, adversarios_dict[${clube_id}]=${this.adversarios_dict[clube_id]}`);

        // Encontrar o adversário na rodada atual
        if (adversario_id && this.adversarios_dict[clube_id] === adversario_id) {
            peso_jogo_final = peso_jogo_original * this.pesos.FATOR_PESO_JOGO;
            console.log(`  ✅ Adversário encontrado! peso_jogo_final = ${peso_jogo_original} × ${this.pesos.FATOR_PESO_JOGO} = ${peso_jogo_final.toFixed(2)}`);

            // Buscar médias de scouts cedidos pelo adversário
            const adversarioStats = this.pontuados_data[adversario_id] || {};
            console.log(`  adversarioStats (pontuados_data[${adversario_id}]):`, adversarioStats);
            media_ds_cedidos = adversarioStats.avg_ds_cedidos || 0;
            media_ff_cedidos = adversarioStats.avg_ff_cedidos || 0;
            media_fs_cedidos = adversarioStats.avg_fs_cedidos || 0;
            media_fd_cedidos = adversarioStats.avg_fd_cedidos || 0;
            media_g_cedidos = adversarioStats.avg_g_cedidos || 0;
            media_a_cedidos = adversarioStats.avg_a_cedidos || 0;
            console.log(`  media_ds_cedidos: ${media_ds_cedidos}`);
        } else {
            console.log(`  ❌ Adversário NÃO encontrado ou não corresponde`);
        }

        // Calcular contribuição dos desarmes
        const pontos_ds = media_ds * media_ds_cedidos * this.pesos.FATOR_DS;
        console.log(`  pontos_ds: ${media_ds} × ${media_ds_cedidos} × ${this.pesos.FATOR_DS} = ${pontos_ds.toFixed(2)}`);

        // Calcular contribuição dos outros scouts (com pesos opcionais)
        const fator_ff = this.pesos.FATOR_FF || 0;
        const fator_fs = this.pesos.FATOR_FS || 0;
        const fator_fd = this.pesos.FATOR_FD || 0;
        const fator_g = this.pesos.FATOR_G || 0;
        const fator_a = this.pesos.FATOR_A || 0;

        const pontos_ff = media_ff * media_ff_cedidos * fator_ff;
        const pontos_fs = media_fs * media_fs_cedidos * fator_fs;
        const pontos_fd = media_fd * media_fd_cedidos * fator_fd;
        const pontos_g = media_g * media_g_cedidos * fator_g;
        const pontos_a = media_a * media_a_cedidos * fator_a;

        console.log(`  pontos_ff: ${pontos_ff.toFixed(2)}, pontos_fs: ${pontos_fs.toFixed(2)}, pontos_fd: ${pontos_fd.toFixed(2)}`);
        console.log(`  pontos_g: ${pontos_g.toFixed(2)}, pontos_a: ${pontos_a.toFixed(2)}`);

        // Calcular pontuação base
        // No Python: peso_jogo já foi multiplicado por FATOR_PESO_JOGO (linha 149)
        // E na fórmula usa peso_jogo diretamente (linha 172): base_pontuacao = pontos_media + peso_jogo + pontos_ds
        const base_pontuacao = pontos_media + peso_jogo_final + pontos_ds +
            pontos_ff + pontos_fs + pontos_fd + pontos_g + pontos_a;
        console.log(`  base_pontuacao: ${pontos_media.toFixed(2)} + ${peso_jogo_final.toFixed(2)} + ${pontos_ds.toFixed(2)} + ${pontos_ff.toFixed(2)} + ${pontos_fs.toFixed(2)} + ${pontos_fd.toFixed(2)} + ${pontos_g.toFixed(2)} + ${pontos_a.toFixed(2)} = ${base_pontuacao.toFixed(2)}`);

        const pontuacao_total = base_pontuacao * (1 + peso_sg_final * this.pesos.FATOR_SG);
        console.log(`  pontuacao_total (antes raiz): ${base_pontuacao.toFixed(2)} × (1 + ${peso_sg_final} × ${this.pesos.FATOR_SG}) = ${pontuacao_total.toFixed(2)}`);

        // Garantir que pontuacao_total seja não negativa
        const pontuacao_total_non_neg = Math.max(0, pontuacao_total);
        console.log(`  pontuacao_total_non_neg: ${pontuacao_total_non_neg.toFixed(2)}`);

        // Calcular peso de escalação
        const escalacoes = this.escalacoes_data[atleta_id] || 0;
        console.log(`  escalacoes: ${escalacoes}, totalEscalacoes: ${totalEscalacoes}`);
        const percentual_escalacoes = totalEscalacoes > 0 ? escalacoes / totalEscalacoes : 0;
        const peso_escalacao = 1 + percentual_escalacoes * this.pesos.FATOR_ESCALACAO;
        console.log(`  percentual_escalacoes: ${percentual_escalacoes.toFixed(4)}, peso_escalacao: ${peso_escalacao.toFixed(4)}`);

        // Ajustar pontuação final com peso de escalação e aplicar raiz quadrada
        // No Python: math.sqrt(max(0, pontuacao_total * peso_escalacao))
        const pontuacao_com_escalacao = pontuacao_total_non_neg * peso_escalacao;
        console.log(`  pontuacao_com_escalacao: ${pontuacao_total_non_neg.toFixed(2)} × ${peso_escalacao.toFixed(4)} = ${pontuacao_com_escalacao.toFixed(2)}`);

        const pontuacao_total_final = Math.sqrt(Math.max(0, pontuacao_com_escalacao));
        console.log(`  sqrt(${pontuacao_com_escalacao.toFixed(2)}) = ${pontuacao_total_final.toFixed(2)}`);
        console.log(`[DEBUG ZAGUEIRO] ========================================\n`);

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
            adversario_id,
            adversario_nome,
            peso_escalacao: parseFloat(peso_escalacao.toFixed(4))
        };
    }
}

// Exportar para uso global
if (typeof module !== 'undefined' && module.exports) {
    module.exports = CalculoZagueiro;
} else {
    window.CalculoZagueiro = CalculoZagueiro;
}

