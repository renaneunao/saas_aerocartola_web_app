/**
 * Cálculo de goleiros - Implementação JavaScript
 * Baseado em calculo_posicoes/calculo_goleiro.py
 */


class CalculoGoleiro {
    constructor(data) {
        if (window.BLOQUEAR_CALCULO_GOLEIRO === true) {
            console.warn(`[CALCULO GOLEIRO] ⚠️ AVISO: O cálculo em tempo real está BLOQUEADO porque um ranking salvo foi encontrado.`);
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

    calcularMelhoresGoleiros(topN = 20) {
        const resultados = [];
        for (const atleta of this.atletas) {
            const resultado = this.calcularPontuacao(atleta);
            resultados.push(resultado);
        }
        resultados.sort((a, b) => b.pontuacao_total - a.pontuacao_total);
        return resultados.slice(0, topN);
    }

    calcularPontuacao(atleta) {
        const {
            atleta_id, apelido, clube_id, clube_nome, clube_abrev, clube_escudo_url,
            media_num, preco_num, jogos_num, peso_jogo, peso_sg, adversario_id, adversario_nome
        } = atleta;

        const media_num_val = parseFloat(media_num) || 0;
        const peso_sg_final = peso_sg || 0;
        const peso_jogo_original = peso_jogo || 0;

        let peso_jogo_final = 0;
        let ff_avg_adversario = 0;
        let fd_avg_adversario = 0;
        let media_gols_adversario = 0;
        let tem_adversario = false;

        if (adversario_id && this.adversarios_dict[clube_id] === adversario_id) {
            tem_adversario = true;
            peso_jogo_final = peso_jogo_original * this.pesos.FATOR_PESO_JOGO;

            const adversarioStats = this.pontuados_data[adversario_id];
            if (adversarioStats) {
                ff_avg_adversario = adversarioStats.avg_ff || 0;
                fd_avg_adversario = adversarioStats.avg_fd || 0;
            }

            const adversarioGols = this.gols_data[adversario_id];
            if (adversarioGols) {
                media_gols_adversario = adversarioGols.media_gols || 0;
            }
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
        const base_bruta = media_num_val + (tem_adversario ? (peso_jogo_original + ff_avg_adversario + fd_avg_adversario) : 0);
        const base_bruta_non_neg = Math.max(0, base_bruta);
        const base_raiz = Math.sqrt(base_bruta_non_neg);

        let soma_fatores_ponderada = 0;
        let divisor_estavel = 0;
        
        if (base_bruta_non_neg > 0) {
            if (media_num_val > 0) {
                soma_fatores_ponderada += media_num_val * this.pesos.FATOR_MEDIA;
                divisor_estavel += media_num_val;
            }
            if (tem_adversario) {
                if (peso_jogo_original > 0) {
                    soma_fatores_ponderada += peso_jogo_original * this.pesos.FATOR_PESO_JOGO;
                    divisor_estavel += peso_jogo_original;
                }
                if (ff_avg_adversario > 0) {
                    soma_fatores_ponderada += ff_avg_adversario * this.pesos.FATOR_FF;
                    divisor_estavel += ff_avg_adversario;
                }
                if (fd_avg_adversario > 0) {
                    soma_fatores_ponderada += fd_avg_adversario * this.pesos.FATOR_FD;
                    divisor_estavel += fd_avg_adversario;
                }
                // Penalização por gols sofridos (reduz o multiplicador)
                if (media_gols_adversario > 0) {
                    soma_fatores_ponderada -= media_gols_adversario * (this.pesos.FATOR_GOL_ADVERSARIO || 0);
                    divisor_estavel += media_gols_adversario;
                }
            }
            soma_fatores_ponderada = divisor_estavel > 0 ? (soma_fatores_ponderada / divisor_estavel) : this.pesos.FATOR_MEDIA;
        } else {
            soma_fatores_ponderada = this.pesos.FATOR_MEDIA;
        }
        
        const fator_sg = 1 + (peso_sg_final * this.pesos.FATOR_SG);
        const pontuacao_total_final = base_raiz * soma_fatores_ponderada * fator_sg;

        return {
            atleta_id, apelido, clube_id, clube_nome, clube_abrev, clube_escudo_url,
            pontuacao_total: isNaN(pontuacao_total_final) ? 0 : parseFloat(pontuacao_total_final.toFixed(2)),
            media: media_num_val,
            preco: parseFloat(preco_num.toFixed(2)),
            jogos: jogos_num,
            peso_jogo: parseFloat(peso_jogo_final.toFixed(2)),
            peso_sg: parseFloat(peso_sg_final.toFixed(2)),
            media_gols_adversario: parseFloat(media_gols_adversario.toFixed(2)),
            adversario_id, adversario_nome: adversario_nome || 'N/A',
            foto: atleta.foto || '',
            media_basica: atleta.media_basica || 0
        };
    }
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = CalculoGoleiro;
} else {
    window.CalculoGoleiro = CalculoGoleiro;
}


