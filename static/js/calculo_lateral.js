/**
 * Cálculo de laterais - Implementação JavaScript
 * Baseado em calculo_posicoes/calculo_lateral.py
 */

class CalculoLateral {
    constructor(data) {
        // VERIFICAÇÃO CRÍTICA: Se o bloqueador estiver ativo, lançar erro
        if (window.BLOQUEAR_CALCULO_LATERAL === true) {
            console.error(`[CALCULO LATERAL] 🚫🚫🚫 ERRO: Tentativa de criar CalculoLateral com bloqueador ativo!`);
            console.trace('[CALCULO LATERAL] Stack trace do construtor bloqueado:');
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
            FATOR_MEDIA: 3.0,
            FATOR_DS: 8.0,
            FATOR_SG: 2.0,
            FATOR_ESCALACAO: 10.0,
            FATOR_FF: 2.0,
            FATOR_FS: 1.0,
            FATOR_FD: 2.0,
            FATOR_G: 4.0,
            FATOR_A: 4.0,
            FATOR_PESO_JOGO: 1.0
        };
    }

    calcularMelhoresLaterais(topN = 20) {
        const resultados = [];
        const totalEscalacoes = this.calcularTotalEscalacoes();
        console.log(`[DEBUG LATERAL] ========== INÍCIO DO CÁLCULO ==========`);
        console.log(`[DEBUG LATERAL] FATOR_ESCALACAO: ${this.pesos.FATOR_ESCALACAO}`);
        console.log(`[DEBUG LATERAL] Total de escalações: ${totalEscalacoes}`);
        console.log(`[DEBUG LATERAL] Número de atletas com escalação: ${Object.keys(this.escalacoes_data).length}`);
        console.log(`[DEBUG LATERAL] Escalações (primeiros 5):`, Object.entries(this.escalacoes_data).slice(0, 5));

        for (let i = 0; i < this.atletas.length; i++) {
            const atleta = this.atletas[i];
            const resultado = this.calcularPontuacao(atleta, totalEscalacoes);
            resultados.push(resultado);
            
            // Debug apenas para os 3 primeiros
            if (i < 3) {
                console.log(`[DEBUG LATERAL ${i+1}] ${atleta.apelido}: pontuacao_total = ${resultado.pontuacao_total}`);
            }
        }

        resultados.sort((a, b) => b.pontuacao_total - a.pontuacao_total);
        const topResultados = resultados.slice(0, topN);
        
        return topResultados;
    }

    calcularTotalEscalacoes() {
        if (!this.escalacoes_data || Object.keys(this.escalacoes_data).length === 0) {
            return 1.0; // Evitar divisão por zero
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
        console.log(`\n[DEBUG LATERAL] ========== ${apelido} (ID: ${atleta_id}) ==========`);
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

        // Buscar médias do atleta (precisa vir da API)
        const atletaStats = this.pontuados_data[atleta_id] || {};
        console.log(`  atletaStats (pontuados_data[${atleta_id}]):`, atletaStats);
        
        const media_ds = atletaStats.avg_ds || 0;
        const media_ff = atletaStats.avg_ff || 0;
        const media_fs = atletaStats.avg_fs || 0;
        const media_fd = atletaStats.avg_fd || 0;
        const media_g = atletaStats.avg_g || 0;
        const media_a = atletaStats.avg_a || 0;

        console.log(`  Médias do atleta: ds=${media_ds}, ff=${media_ff}, fs=${media_fs}, fd=${media_fd}, g=${media_g}, a=${media_a}`);

        let peso_jogo_final = 0;
        let media_ds_cedidos = 0;

        console.log(`  Verificando adversário: adversario_id=${adversario_id}, adversarios_dict[${clube_id}]=${this.adversarios_dict[clube_id]}`);

        // Encontrar o adversário na rodada atual
        if (adversario_id && this.adversarios_dict[clube_id] === adversario_id) {
            // No Python: peso_jogo = peso_jogo_original * FATOR_PESO_JOGO
            peso_jogo_final = peso_jogo_original * this.pesos.FATOR_PESO_JOGO;
            console.log(`  ✅ Adversário encontrado! peso_jogo_final = ${peso_jogo_original} × ${this.pesos.FATOR_PESO_JOGO} = ${peso_jogo_final.toFixed(2)}`);

            // Buscar média de desarmes cedidos pelo adversário
            const adversarioStats = this.pontuados_data[adversario_id] || {};
            console.log(`  adversarioStats (pontuados_data[${adversario_id}]):`, adversarioStats);
            media_ds_cedidos = adversarioStats.avg_ds_cedidos || 0;
            console.log(`  media_ds_cedidos: ${media_ds_cedidos}`);
        } else {
            // Se não houver adversário, peso_jogo_final permanece 0
            peso_jogo_final = 0;
            console.log(`  ❌ Adversário NÃO encontrado ou não corresponde`);
        }

        // Calcular contribuição dos desarmes
        const pontos_ds = media_ds * media_ds_cedidos * this.pesos.FATOR_DS;
        console.log(`  pontos_ds: ${media_ds} × ${media_ds_cedidos} × ${this.pesos.FATOR_DS} = ${pontos_ds.toFixed(2)}`);

        // Calcular contribuição dos scouts
        const pontos_ff = media_ff * this.pesos.FATOR_FF;
        const pontos_fs = media_fs * this.pesos.FATOR_FS;
        const pontos_fd = media_fd * this.pesos.FATOR_FD;
        const pontos_g = media_g * this.pesos.FATOR_G;
        const pontos_a = media_a * this.pesos.FATOR_A;

        console.log(`  pontos_ff: ${pontos_ff.toFixed(2)}, pontos_fs: ${pontos_fs.toFixed(2)}, pontos_fd: ${pontos_fd.toFixed(2)}`);
        console.log(`  pontos_g: ${pontos_g.toFixed(2)}, pontos_a: ${pontos_a.toFixed(2)}`);

        // Calcular pontuação base
        // No Python: base_pontuacao = (pontos_media + (peso_jogo * FATOR_PESO_JOGO) + pontos_ds + ...)
        // Onde peso_jogo já foi multiplicado por FATOR_PESO_JOGO, então multiplica novamente!
        // Replicando o comportamento do Python:
        const peso_jogo_na_base = peso_jogo_final * this.pesos.FATOR_PESO_JOGO;
        console.log(`  peso_jogo_na_base: ${peso_jogo_final.toFixed(2)} × ${this.pesos.FATOR_PESO_JOGO} = ${peso_jogo_na_base.toFixed(2)}`);
        
        const base_pontuacao = (pontos_media + peso_jogo_na_base + pontos_ds +
                               pontos_ff + pontos_fs + pontos_fd + pontos_g + pontos_a);
        console.log(`  base_pontuacao: ${pontos_media.toFixed(2)} + ${peso_jogo_na_base.toFixed(2)} + ${pontos_ds.toFixed(2)} + ${pontos_ff.toFixed(2)} + ${pontos_fs.toFixed(2)} + ${pontos_fd.toFixed(2)} + ${pontos_g.toFixed(2)} + ${pontos_a.toFixed(2)} = ${base_pontuacao.toFixed(2)}`);
        
        const pontuacao_total = base_pontuacao * (1 + peso_sg_final * this.pesos.FATOR_SG);
        console.log(`  pontuacao_total (antes raiz): ${base_pontuacao.toFixed(2)} × (1 + ${peso_sg_final} × ${this.pesos.FATOR_SG}) = ${pontuacao_total.toFixed(2)}`);

        // Garantir que pontuacao_total seja não negativa antes de calcular a raiz quadrada
        const pontuacao_total_non_neg = Math.max(0, pontuacao_total);
        console.log(`  pontuacao_total_non_neg: ${pontuacao_total_non_neg.toFixed(2)}`);

        // Calcular peso de escalação
        const escalacoes = this.escalacoes_data[atleta_id] || 0;
        console.log(`  escalacoes: ${escalacoes}, totalEscalacoes: ${totalEscalacoes}`);
        const percentual_escalacoes = totalEscalacoes > 0 ? escalacoes / totalEscalacoes : 0;
        const peso_escalacao = 1 + percentual_escalacoes * this.pesos.FATOR_ESCALACAO;
        console.log(`  percentual_escalacoes: ${percentual_escalacoes.toFixed(4)}, peso_escalacao: ${peso_escalacao.toFixed(4)}`);

        // Ajustar pontuação final: raiz quadrada multiplicada pelo peso
        const sqrt_value = Math.sqrt(pontuacao_total_non_neg);
        const pontuacao_total_final = sqrt_value * peso_escalacao;
        console.log(`  sqrt(${pontuacao_total_non_neg.toFixed(2)}) = ${sqrt_value.toFixed(2)}`);
        console.log(`  pontuacao_total_final: ${sqrt_value.toFixed(2)} × ${peso_escalacao.toFixed(4)} = ${pontuacao_total_final.toFixed(2)}`);
        console.log(`[DEBUG LATERAL] ========================================\n`);

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
            peso_escalacao: parseFloat(peso_escalacao.toFixed(4))
        };
    }
}

// Exportar para uso global
if (typeof module !== 'undefined' && module.exports) {
    module.exports = CalculoLateral;
} else {
    window.CalculoLateral = CalculoLateral;
}

