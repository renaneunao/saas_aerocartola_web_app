/**
 * Cálculo de treinadores - Implementação JavaScript
 * Baseado em calculo_posicoes/calculo_treinador.py
 */

class CalculoTreinador {
    constructor(data) {
        // VERIFICAÇÃO CRÍTICA: Se o bloqueador estiver ativo, lançar erro
        if (window.BLOQUEAR_CALCULO_TREINADOR === true) {
            console.error(`[CALCULO TREINADOR] 🚫🚫🚫 ERRO: Tentativa de criar CalculoTreinador com bloqueador ativo!`);
            console.trace('[CALCULO TREINADOR] Stack trace do construtor bloqueado:');
            throw new Error('Cálculo bloqueado: ranking salvo encontrado');
        }
        
        this.rodada_atual = data.rodada_atual;
        this.perfil_peso_jogo = data.perfil_peso_jogo;
        this.perfil_peso_sg = data.perfil_peso_sg;
        this.atletas = data.atletas;
        this.adversarios_dict = data.adversarios_dict || {};
        this.clubes_dict = data.clubes_dict || {};
        this.pesos = data.pesos || {
            FATOR_PESO_JOGO: 3.5
        };
    }

    calcularMelhoresTreinadores(topN = 20) {
        const resultados = [];

        for (const atleta of this.atletas) {
            const resultado = this.calcularPontuacao(atleta);
            resultados.push(resultado);
        }

        resultados.sort((a, b) => b.pontuacao_total - a.pontuacao_total);
        const topResultados = resultados.slice(0, topN);
        
        return topResultados;
    }

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
            adversario_id,
            adversario_nome
        } = atleta;

        // Valores padrão
        const peso_jogo_original = peso_jogo || 0;
        const peso_sg_final = peso_sg || 0;

        // Calcular pontuação total (apenas peso de jogo)
        const pontuacao_total = peso_jogo_original * this.pesos.FATOR_PESO_JOGO;

        // Para treinadores, não há cálculo de adversário específico aqui
        // O peso_sg_adversario seria calculado no backend se necessário

        return {
            atleta_id,
            apelido,
            clube_id,
            clube_nome,
            clube_abrev,
            clube_escudo_url,
            pontuacao_total: parseFloat(pontuacao_total.toFixed(2)),
            media: parseFloat(media_num.toFixed(2)),
            preco: parseFloat(preco_num.toFixed(2)),
            jogos: jogos_num,
            peso_jogo: parseFloat(peso_jogo_original.toFixed(2)),
            peso_sg: parseFloat(peso_sg_final.toFixed(2)),
            adversario_id: adversario_id || null,
            adversario_nome: adversario_nome || 'N/A'
        };
    }
}

// Exportar para uso global
if (typeof module !== 'undefined' && module.exports) {
    module.exports = CalculoTreinador;
} else {
    window.CalculoTreinador = CalculoTreinador;
}

