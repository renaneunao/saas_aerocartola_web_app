/**
 * Cálculo de laterais - Implementação JavaScript
 * Baseado em calculo_posicoes/calculo_lateral.py
 */

console.log('%c [CALCULO LATERAL] VERSÃO 2.0 CARREGADA - LÓGICA ESTÁVEL ATIVA', 'background: #222; color: #33aaff; font-size: 16px;');

class CalculoLateral {
    constructor(data) {
        // VERIFICAÇÃO CRÍTICA: Se o bloqueador estiver ativo, lançar erro
        if (window.BLOQUEAR_CALCULO_LATERAL === true) {
            console.warn(`[CALCULO LATERAL] ⚠️ AVISO: O cálculo em tempo real está BLOQUEADO porque um ranking salvo foi encontrado no banco.`);
            // throw new Error('Cálculo bloqueado: ranking salvo encontrado');
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
        console.log(`[DEBUG LATERAL] Total de escalações: ${totalEscalacoes}`);

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

        console.log(`  base_bruta: ${base_bruta.toFixed(2)} (sem fatores)`);
        console.log(`  base_raiz: sqrt(${base_bruta_non_neg.toFixed(2)}) = ${base_raiz.toFixed(2)}`);

        // Aplicar TODOS os fatores DEPOIS da raiz quadrada para ter impacto proporcional
        // Calcular soma ponderada dos fatores baseada na proporção de cada componente
        let soma_fatores_ponderada = 0;
        let divisor_estavel = 0;
        
        if (base_bruta_non_neg > 0) {
            // 1. Somar contribuições (numerador) e componentes (divisor estável)
            if (media_num_val > 0) {
                soma_fatores_ponderada += media_num_val * this.pesos.FATOR_MEDIA;
                divisor_estavel += media_num_val;
            }
            
            if (tem_adversario && peso_jogo_original > 0) {
                soma_fatores_ponderada += peso_jogo_original * this.pesos.FATOR_PESO_JOGO;
                divisor_estavel += peso_jogo_original;
            }
            
            // Scouts
            const componentes_scouts = [
                { val: media_ds * media_ds_cedidos, peso: this.pesos.FATOR_DS },
                { val: media_ff * media_ff_cedidos, peso: this.pesos.FATOR_FF },
                { val: media_fs * media_fs_cedidos, peso: this.pesos.FATOR_FS },
                { val: media_fd * media_fd_cedidos, peso: this.pesos.FATOR_FD },
                { val: media_g * media_g_cedidos, peso: this.pesos.FATOR_G },
                { val: media_a * media_a_cedidos, peso: this.pesos.FATOR_A }
            ];

            componentes_scouts.forEach(comp => {
                if (comp.val > 0) {
                    soma_fatores_ponderada += comp.val * comp.peso;
                    divisor_estavel += comp.val;
                }
            });

            // 2. Calcular o fator final usando o divisor estável (soma das partes positivas)
            if (divisor_estavel > 0) {
                soma_fatores_ponderada = soma_fatores_ponderada / divisor_estavel;
            } else {
                soma_fatores_ponderada = this.pesos.FATOR_MEDIA;
            }
        } else {
            // Se base_bruta é 0, usar apenas o fator da média como mínimo
            soma_fatores_ponderada = this.pesos.FATOR_MEDIA;
        }
        
        const pontuacao_total = base_pontuacao * (1 + peso_sg_final * this.pesos.FATOR_SG);
        console.log(`  pontuacao_total (antes raiz): ${base_pontuacao.toFixed(2)} × (1 + ${peso_sg_final} × ${this.pesos.FATOR_SG}) = ${pontuacao_total.toFixed(2)}`);

        // Garantir que pontuacao_total seja não negativa antes de calcular a raiz quadrada
        const pontuacao_total_non_neg = Math.max(0, pontuacao_total);
        console.log(`  pontuacao_total_non_neg: ${pontuacao_total_non_neg.toFixed(2)}`);

        // Calcular peso de escalação
        const escalacoes = this.escalacoes_data[atleta_id] || 0;
        const percentual_escalacoes = totalEscalacoes > 0 ? escalacoes / totalEscalacoes : 0;
        // Usar raiz quadrada do percentual para amplificar a influência
        const percentual_ajustado = Math.sqrt(percentual_escalacoes);
        const peso_escalacao = 1 + percentual_ajustado * this.pesos.FATOR_ESCALACAO;

        // Aplicar todos os fatores DEPOIS da raiz
        const pontuacao_total_final = base_raiz * fator_multiplicador * peso_escalacao;
        
        // --- LOG DE CÁLCULO DETALHADO (F12) ---
        if (atleta_id === 77777 || pontuacao_total_final > 20 || (clube_nome && clube_nome.toLowerCase().includes('cruzeiro'))) {
            console.group(`📊 CÁLCULO LATERAL: ${apelido} (ID: ${atleta_id})`);
            console.log(`1. Média Base: ${media_num_val.toFixed(2)}`);
            console.log(`2. Peso Jogo Bruto: ${peso_jogo_original.toFixed(2)}`);
            console.log(`3. Lado: ${is_esquerdo ? 'ESQUERDO' : 'DIREITO'}`);
            console.log(`4. Base Bruta: ${base_bruta.toFixed(2)}`);
            console.log(`5. Base Raiz: sqrt(${Math.max(0, base_bruta).toFixed(2)}) = ${base_raiz.toFixed(2)}`);
            console.log(`6. Multiplicador (Fator Médio): ${soma_fatores_ponderada.toFixed(4)}`);
            console.log(`7. Fator SG: ${fator_sg.toFixed(4)}`);
            console.log(`8. Peso Popularidade: ${peso_escalacao.toFixed(4)}`);
            console.log(`🚀 RESULTADO FINAL: ${pontuacao_total_final.toFixed(2)}`);
            console.groupEnd();
        }

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

