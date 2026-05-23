/**
 * Cálculo de zagueiros - Implementação JavaScript
 * Baseado em calculo_posicoes/calculo_zagueiro.py
 */


class CalculoZagueiro {
    constructor(data) {
        // VERIFICAÇÃO CRÍTICA: Se o bloqueador estiver ativo, lançar erro
        if (window.BLOQUEAR_CALCULO_ZAGUEIRO === true) {
            console.warn(`[CALCULO ZAGUEIRO] ⚠️ AVISO: O cálculo em tempo real está BLOQUEADO porque um ranking salvo foi encontrado.`);
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
                console.log(`[DEBUG ZAGUEIRO ${i+1}] ${atleta.apelido}: pontuacao_total = ${resultado.pontuacao_total}`);
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
            media_num, 
            preco_num, 
            jogos_num, 
            peso_jogo, 
            peso_sg,
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
        const peso_sg_final = peso_sg || 0;
        const peso_jogo_original = peso_jogo || 0;

        // Buscar média de desarmes do atleta
        const atletaStats = this.pontuados_data[atleta_id] || {};
        const media_ds = atletaStats.avg_ds || 0;

        let peso_jogo_final = 0;
        let media_ds_cedidos = 0;
        let tem_adversario = false;

        // Encontrar o adversário na rodada atual
        if (adversario_id && this.adversarios_dict[clube_id] === adversario_id) {
            tem_adversario = true;
            peso_jogo_final = peso_jogo_original * this.pesos.FATOR_PESO_JOGO;

            // Buscar média de desarmes cedidos pelo adversário
            const adversarioStats = this.pontuados_data[adversario_id] || {};
            media_ds_cedidos = adversarioStats.avg_ds_cedidos || 0;
        }

        // Se não tem jogo na rodada, ignorar (retornar pontuação nula)
        if (!tem_adversario) {
            return {
                atleta_id,
                apelido,
                clube_id,
                clube_escudo_url,
                clube_nome,
                preco: parseFloat(preco_num.toFixed(2)),
                jogos: jogos_num,
                pontuacao_total: -999, // Força o jogador para o final da fila
                ignorado: true,
                motivo: 'Sem jogo na rodada'
            };
        }

        // LÓGICA ESTÁVEL 2.0
        // 1. Calcular a Base Bruta (Componentes fixos + Scouts)
        const base_bruta = media_num_val + (tem_adversario ? peso_jogo_original : 0) + (media_ds * media_ds_cedidos);
        
        // 2. Garantir que base_bruta seja não negativa antes de calcular a raiz quadrada
        const base_bruta_non_neg = Math.max(0, base_bruta);
        const base_raiz = Math.sqrt(base_bruta_non_neg);

        // 3. Calcular o Multiplicador Estável (Fator ponderado dos pesos)
        let soma_fatores_ponderada = 0;
        let divisor_estavel = 0;
        
        if (base_bruta_non_neg > 0) {
            if (media_num_val > 0) {
                soma_fatores_ponderada += media_num_val * this.pesos.FATOR_MEDIA;
                divisor_estavel += media_num_val;
            }
            
            if (tem_adversario && peso_jogo_original > 0) {
                soma_fatores_ponderada += peso_jogo_original * this.pesos.FATOR_PESO_JOGO;
                divisor_estavel += peso_jogo_original;
            }
            
            if (media_ds * media_ds_cedidos > 0) {
                soma_fatores_ponderada += (media_ds * media_ds_cedidos) * this.pesos.FATOR_DS;
                divisor_estavel += (media_ds * media_ds_cedidos);
            }

            if (divisor_estavel > 0) {
                soma_fatores_ponderada = soma_fatores_ponderada / divisor_estavel;
            } else {
                soma_fatores_ponderada = this.pesos.FATOR_MEDIA;
            }
        } else {
            soma_fatores_ponderada = this.pesos.FATOR_MEDIA;
        }
        
        // 4. Aplicar Fator SG (multiplicador adicional)
        const fator_sg = 1 + (peso_sg_final * this.pesos.FATOR_SG);
        
        // 5. Calcular Pontuação Inicial
        const pontuacao_inicial = base_raiz * soma_fatores_ponderada * fator_sg;

        // 6. Calcular peso de popularidade (Escalação)
        const escalacoes = this.escalacoes_data[atleta_id] || 0;
        const percentual_escalacoes = totalEscalacoes > 0 ? escalacoes / totalEscalacoes : 0;
        const peso_escalacao = 1 + percentual_escalacoes * this.pesos.FATOR_ESCALACAO;

        // 7. Resultado Final
        const pontuacao_total_final = pontuacao_inicial * peso_escalacao;

        // --- LOG DE CÁLCULO DETALHADO (F12) ---
        if (atleta_id === 77777 || pontuacao_total_final > 20) {
            console.group(`📊 CÁLCULO ZAGUEIRO: ${apelido} (ID: ${atleta_id})`);
            console.log(`1. Média Base: ${media_num_val.toFixed(2)}`);
            console.log(`2. Peso Jogo Bruto: ${peso_jogo_original.toFixed(2)}`);
            console.log(`3. Base Bruta: ${base_bruta.toFixed(2)}`);
            console.log(`4. Base Raiz: sqrt(${base_bruta_non_neg.toFixed(2)}) = ${base_raiz.toFixed(2)}`);
            console.log(`5. Multiplicador (Fator Médio): ${soma_fatores_ponderada.toFixed(4)}`);
            console.log(`6. Fator SG: ${fator_sg.toFixed(4)}`);
            console.log(`7. Peso Popularidade: ${peso_escalacao.toFixed(4)}`);
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
            adversario_id,
            adversario_nome,
            peso_escalacao: parseFloat(peso_escalacao.toFixed(4)),
            foto: atleta.foto || ''
        };
    }
}

// Exportar para uso global
if (typeof module !== 'undefined' && module.exports) {
    module.exports = CalculoZagueiro;
} else {
    window.CalculoZagueiro = CalculoZagueiro;
}


