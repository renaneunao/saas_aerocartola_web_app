/**
 * Cálculo de meias - Implementação JavaScript
 * Baseado em calculo_posicoes/calculo_meia.py
 */


class CalculoMeia {
    constructor(data) {
        if (window.BLOQUEAR_CALCULO_MEIA === true) {
            console.warn(`[CALCULO MEIA] ⚠️ AVISO: O cálculo em tempo real está BLOQUEADO porque um ranking salvo foi encontrado.`);
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
            FATOR_MEDIA: 1.0,
            FATOR_DS: 3.6,
            FATOR_FF: 0.7,
            FATOR_FS: 0.8,
            FATOR_FD: 0.9,
            FATOR_G: 2.5,
            FATOR_A: 2.0,
            FATOR_ESCALACAO: 10.0,
            FATOR_PESO_JOGO: 9.5
        };
    }

    calcularMelhoresMeias(topN = 20) {
        const resultados = [];
        const totalEscalacoes = this.calcularTotalEscalacoes();

        for (let i = 0; i < this.atletas.length; i++) {
            const atleta = this.atletas[i];
            const resultado = this.calcularPontuacao(atleta, totalEscalacoes);
            resultados.push(resultado);
        }

        resultados.sort((a, b) => b.pontuacao_total - a.pontuacao_total);
        return resultados.slice(0, topN);
    }

    calcularTotalEscalacoes() {
        if (!this.escalacoes_data || Object.keys(this.escalacoes_data).length === 0) return 1.0;
        return Object.values(this.escalacoes_data).reduce((sum, esc) => sum + (esc || 0), 0) || 1.0;
    }

    calcularPontuacao(atleta, totalEscalacoes) {
        const { 
            atleta_id, apelido, clube_id, clube_nome, clube_abrev, clube_escudo_url,
            media_num, preco_num, jogos_num, peso_jogo, adversario_id, adversario_nome
        } = atleta;

        const media_num_val = parseFloat(media_num) || 0;
        const preco_num_val = parseFloat(preco_num) || 0;
        const jogos_num_val = parseInt(jogos_num) || 0;
        const peso_jogo_original = peso_jogo || 0;

        const atletaStats = this.pontuados_data[atleta_id] || {};
        const media_ds = atletaStats.avg_ds || 0;
        const media_ff = atletaStats.avg_ff || 0;
        const media_fs = atletaStats.avg_fs || 0;
        const media_fd = atletaStats.avg_fd || 0;
        const media_g = atletaStats.avg_g || 0;
        const media_a = atletaStats.avg_a || 0;

        let peso_jogo_final = 0;
        let media_ds_cedidos = 0;
        let tem_adversario = false;

        if (adversario_id && this.adversarios_dict[clube_id] === adversario_id) {
            tem_adversario = true;
            peso_jogo_final = peso_jogo_original * this.pesos.FATOR_PESO_JOGO;
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

        // LÓGICA ESTÁVEL 2.1
        const base_bruta = media_num_val + (tem_adversario ? peso_jogo_original : 0) + 
                          (media_ds * media_ds_cedidos) + media_ff + media_fs + media_fd + media_g + media_a;
        
        const base_bruta_non_neg = Math.max(0, base_bruta);
        const base_raiz = Math.sqrt(base_bruta_non_neg);

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
            const scouts = [
                { val: media_ds * media_ds_cedidos, peso: this.pesos.FATOR_DS },
                { val: media_ff, peso: this.pesos.FATOR_FF },
                { val: media_fs, peso: this.pesos.FATOR_FS },
                { val: media_fd, peso: this.pesos.FATOR_FD },
                { val: media_g, peso: this.pesos.FATOR_G },
                { val: media_a, peso: this.pesos.FATOR_A }
            ];
            scouts.forEach(s => {
                if (s.val > 0) {
                    soma_fatores_ponderada += s.val * s.peso;
                    divisor_estavel += s.val;
                }
            });

            soma_fatores_ponderada = divisor_estavel > 0 ? (soma_fatores_ponderada / divisor_estavel) : this.pesos.FATOR_MEDIA;
        } else {
            soma_fatores_ponderada = this.pesos.FATOR_MEDIA;
        }
        
        const pontuacao_inicial = base_raiz * soma_fatores_ponderada;

        const escalacoes = this.escalacoes_data[atleta_id] || 0;
        const peso_escalacao = 1 + (totalEscalacoes > 0 ? (escalacoes / totalEscalacoes) : 0) * this.pesos.FATOR_ESCALACAO;
        const pontuacao_total_final = pontuacao_inicial * peso_escalacao;

        return {
            atleta_id, apelido, clube_id, clube_nome, clube_abrev, clube_escudo_url,
            pontuacao_total: isNaN(pontuacao_total_final) ? 0 : parseFloat(pontuacao_total_final.toFixed(2)),
            media: parseFloat(media_num_val.toFixed(2)),
            preco: parseFloat(preco_num_val.toFixed(2)),
            jogos: jogos_num_val,
            peso_jogo: parseFloat(peso_jogo_final.toFixed(2)),
            media_ds: parseFloat(media_ds.toFixed(2)),
            media_ds_cedidos: parseFloat(media_ds_cedidos.toFixed(2)),
            media_ff: parseFloat(media_ff.toFixed(2)),
            media_fs: parseFloat(media_fs.toFixed(2)),
            media_fd: parseFloat(media_fd.toFixed(2)),
            media_g: parseFloat(media_g.toFixed(2)),
            media_a: parseFloat(media_a.toFixed(2)),
            adversario_id, adversario_nome,
            peso_escalacao: parseFloat(peso_escalacao.toFixed(4))
        };
    }
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = CalculoMeia;
} else {
    window.CalculoMeia = CalculoMeia;
}


