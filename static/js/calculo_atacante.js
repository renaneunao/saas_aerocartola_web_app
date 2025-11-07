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
            FATOR_MEDIA: 2.5,
            FATOR_DS: 2.0,
            FATOR_FF: 1.2,
            FATOR_FS: 1.3,
            FATOR_FD: 1.3,
            FATOR_G: 2.5,
            FATOR_A: 2.5,
            FATOR_ESCALACAO: 10.0,
            FATOR_PESO_JOGO: 10.0
        };
        
        // LOG DETALHADO DOS PESOS RECEBIDOS
        console.log(`[DEBUG CONSTRUTOR] ========== PESOS RECEBIDOS ==========`);
        console.log(`[DEBUG CONSTRUTOR] data.pesos:`, data.pesos);
        console.log(`[DEBUG CONSTRUTOR] this.pesos após atribuição:`, this.pesos);
        console.log(`[DEBUG CONSTRUTOR] FATOR_ESCALACAO: ${this.pesos.FATOR_ESCALACAO}`);
        
        // 🔍 DIAGNÓSTICO: Armazenar globalmente para inspeção
        window.escalacoes_data_global = this.escalacoes_data;
        window.pesos_global = this.pesos;
        
        console.log('🔍 [DIAGNÓSTICO ESCALAÇÃO]');
        console.log('  escalacoes_data:', this.escalacoes_data);
        console.log('  Quantidade de atletas:', Object.keys(this.escalacoes_data).length);
        console.log('  FATOR_ESCALACAO:', this.pesos.FATOR_ESCALACAO);
        console.log(`[DEBUG CONSTRUTOR] Tipo do FATOR_ESCALACAO: ${typeof this.pesos.FATOR_ESCALACAO}`);
        console.log(`[DEBUG CONSTRUTOR] Total de atletas: ${this.atletas.length}`);
        console.log(`[DEBUG CONSTRUTOR] Total de itens em escalacoes_data: ${Object.keys(this.escalacoes_data).length}`);
        console.log(`[DEBUG CONSTRUTOR] ========================================`);
    }

    calcularMelhoresAtacantes(topN = 20) {
        const resultados = [];
        const totalEscalacoes = this.calcularTotalEscalacoes();
        console.log(`[DEBUG ATACANTE] Total de escalações: ${totalEscalacoes}`);

        for (let i = 0; i < this.atletas.length; i++) {
            const atleta = this.atletas[i];
            const resultado = this.calcularPontuacao(atleta, totalEscalacoes);
            resultados.push(resultado);
            
            // Debug apenas para os 3 primeiros
            if (i < 3) {
                console.log(`[DEBUG ATACANTE ${i+1}] ${atleta.apelido}: pontuacao_total = ${resultado.pontuacao_total}`);
            }
        }

        resultados.sort((a, b) => b.pontuacao_total - a.pontuacao_total);
        const topResultados = resultados.slice(0, topN);
        
        return topResultados;
    }

    calcularTotalEscalacoes() {
        if (!this.escalacoes_data || Object.keys(this.escalacoes_data).length === 0) {
            console.log('[DEBUG ESCALACAO] ⚠️ escalacoes_data está vazio ou indefinido');
            return 1.0;
        }
        const total = Object.values(this.escalacoes_data).reduce((sum, esc) => sum + (esc || 0), 0) || 1.0;
        console.log(`[DEBUG ESCALACAO] Total de escalações: ${total}`);
        console.log(`[DEBUG ESCALACAO] Número de atletas no escalacoes_data: ${Object.keys(this.escalacoes_data).length}`);
        console.log(`[DEBUG ESCALACAO] Primeiros 5 atletas:`, Object.entries(this.escalacoes_data).slice(0, 5));
        return total;
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

        // Fator 1: Média do jogador
        const pontos_media = media_num_val * this.pesos.FATOR_MEDIA;

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

        let peso_jogo_final = 0;
        let media_ds_cedidos = 0;

        // Encontrar o adversário na rodada atual
        if (adversario_id && this.adversarios_dict[clube_id] === adversario_id) {
            peso_jogo_final = peso_jogo_original * this.pesos.FATOR_PESO_JOGO;

            // Buscar média de desarmes cedidos pelo adversário
            const adversarioStats = this.pontuados_data[adversario_id] || {};
            media_ds_cedidos = adversarioStats.avg_ds_cedidos || 0;
        }

        // Calcular contribuição dos desarmes
        const pontos_ds = media_ds * media_ds_cedidos * this.pesos.FATOR_DS;

        // Calcular contribuição dos scouts ofensivos
        const pontos_ff = media_ff * this.pesos.FATOR_FF;
        const pontos_fs = media_fs * this.pesos.FATOR_FS;
        const pontos_fd = media_fd * this.pesos.FATOR_FD;
        const pontos_g = media_g * this.pesos.FATOR_G;
        const pontos_a = media_a * this.pesos.FATOR_A;

        // Calcular pontuação base (sem FATOR_SG para atacantes)
        const base_pontuacao = (pontos_media + peso_jogo_final + pontos_ds +
                               pontos_ff + pontos_fs + pontos_fd + pontos_g + pontos_a);
        let pontuacao_total = base_pontuacao;

        // DEBUG DETALHADO PARA TODOS OS ATLETAS
        console.log(`\n[DEBUG ATACANTE] ========== ${apelido} (ID: ${atleta_id}) ==========`);
        console.log(`  Dados recebidos:`, { atleta_id, media_num, peso_jogo, adversario_id, clube_id });
        console.log(`  Valores numéricos: media_num_val=${media_num_val}`);
        console.log(`  pontos_media: ${media_num_val} × ${this.pesos.FATOR_MEDIA} = ${pontos_media.toFixed(2)}`);
        console.log(`  peso_jogo_original: ${peso_jogo_original}, peso_jogo_final: ${peso_jogo_final.toFixed(2)}`);
        console.log(`  atletaStats:`, atletaStats);
        console.log(`  pontos_ds: ${pontos_ds.toFixed(2)}, pontos_ff: ${pontos_ff.toFixed(2)}, pontos_fs: ${pontos_fs.toFixed(2)}`);
        console.log(`  pontos_fd: ${pontos_fd.toFixed(2)}, pontos_g: ${pontos_g.toFixed(2)}, pontos_a: ${pontos_a.toFixed(2)}`);
        console.log(`  base_pontuacao: ${base_pontuacao.toFixed(2)}`);

        // Garantir que pontuacao_total seja não negativa antes de calcular a raiz quadrada
        if (pontuacao_total < 0) {
            pontuacao_total = 0;
        }

        // Calcular peso de escalação
        const escalacoes = this.escalacoes_data[atleta_id] || 0;
        const percentual_escalacoes = totalEscalacoes > 0 ? escalacoes / totalEscalacoes : 0;
        const peso_escalacao = 1 + percentual_escalacoes * this.pesos.FATOR_ESCALACAO;

        console.log(`  ===== CÁLCULO DE ESCALAÇÃO =====`);
        console.log(`  escalacoes[${atleta_id}]: ${escalacoes}`);
        console.log(`  totalEscalacoes: ${totalEscalacoes}`);
        console.log(`  percentual_escalacoes: ${escalacoes} / ${totalEscalacoes} = ${percentual_escalacoes.toFixed(6)}`);
        console.log(`  FATOR_ESCALACAO (do dicionário pesos): ${this.pesos.FATOR_ESCALACAO}`);
        console.log(`  peso_escalacao: 1 + ${percentual_escalacoes.toFixed(6)} * ${this.pesos.FATOR_ESCALACAO} = ${peso_escalacao.toFixed(6)}`);

        // Ajustar pontuação final: raiz quadrada multiplicada pelo peso
        const pontuacao_total_final = Math.sqrt(pontuacao_total) * peso_escalacao;

        console.log(`  pontuacao_total (antes raiz): ${pontuacao_total.toFixed(2)}`);
        console.log(`  sqrt(${pontuacao_total.toFixed(2)}) = ${Math.sqrt(pontuacao_total).toFixed(2)}`);
        console.log(`  pontuacao_total_final: ${Math.sqrt(pontuacao_total).toFixed(2)} * ${peso_escalacao.toFixed(6)} = ${pontuacao_total_final.toFixed(2)}`);
        console.log(`[DEBUG ATACANTE] ========================================\n`);

        // Buscar peso_sg do atleta (mesmo que não seja usado no cálculo)
        const peso_sg_final = atleta.peso_sg || 0;

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
            escalacoes: escalacoes  // 🔍 Adicionar número de escalações ao resultado
        };
    }
}

// Exportar para uso global
if (typeof module !== 'undefined' && module.exports) {
    module.exports = CalculoAtacante;
} else {
    window.CalculoAtacante = CalculoAtacante;
}

