/**
 * Calcula somente os módulos de posição que ainda estão pendentes.
 *
 * A escalação rápida já possui toda a lógica de cálculo e persistência dos
 * rankings. Este adaptador reutiliza essa implementação para que a página de
 * módulos e a escalação ideal não tenham versões diferentes do cálculo.
 */
(function () {
  'use strict';

  const MODULES = ['goleiro', 'lateral', 'zagueiro', 'meia', 'atacante', 'treinador'];

  function report(callback, payload) {
    if (typeof callback === 'function') callback(payload);
  }

  async function calcularModulosPendentes(modulos, options = {}) {
    if (window.__aeroCalculoModulosPromise) {
      return window.__aeroCalculoModulosPromise;
    }

    const requested = Array.isArray(modulos) && modulos.length
      ? modulos.filter((modulo) => MODULES.includes(modulo))
      : MODULES.slice();

    if (!requested.length) {
      return { success: true, calculados: [], falhas: [] };
    }

    window.__aeroCalculoModulosPromise = (async () => {
      if (typeof window.EscalacaoRapida !== 'function') {
        throw new Error('Motor de cálculo dos módulos ainda não foi carregado.');
      }

      const runner = new window.EscalacaoRapida();
      const calculados = [];
      const falhas = [];

      for (let index = 0; index < requested.length; index += 1) {
        const modulo = requested[index];
        const percentual = Math.round((index / requested.length) * 100);
        report(options.onProgress, {
          modulo,
          index,
          total: requested.length,
          percentual,
          mensagem: `Calculando ${modulo}...`
        });

        try {
          const dados = await runner.carregarDadosModulo(modulo);
          await runner.verificarESalvarPesos(modulo, dados);
          const ranking = await runner.calcularRankingModulo(modulo, dados);
          await runner.salvarRankingModulo(modulo, ranking);
          calculados.push(modulo);
          report(options.onProgress, {
            modulo,
            index,
            total: requested.length,
            percentual: Math.round(((index + 1) / requested.length) * 100),
            mensagem: `${modulo} calculado`,
            concluido: true
          });
        } catch (error) {
          falhas.push({ modulo, error: error?.message || String(error) });
          report(options.onProgress, {
            modulo,
            index,
            total: requested.length,
            percentual,
            mensagem: `Erro em ${modulo}: ${error?.message || error}`,
            erro: true
          });
          throw error;
        }
      }

      return { success: true, calculados, falhas };
    })();

    try {
      return await window.__aeroCalculoModulosPromise;
    } finally {
      window.__aeroCalculoModulosPromise = null;
    }
  }

  window.calcularModulosPendentes = calcularModulosPendentes;
})();
