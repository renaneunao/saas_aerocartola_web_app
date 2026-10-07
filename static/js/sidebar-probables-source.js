(() => {
  'use strict';

  const panel = document.getElementById('sidebarProbablesSource');
  if (!panel || !document.body.classList.contains('app-authenticated')) return;

  const buttons = [...panel.querySelectorAll('[data-source]')];
  const status = panel.querySelector('.sidebar-probables-status');
  const modules = ['goleiro', 'lateral', 'zagueiro', 'meia', 'atacante', 'treinador'];
  let activeSource = 'globo';
  let changing = false;

  function showStatus(message, isError = false) {
    if (!status) return;
    status.textContent = message || '';
    status.classList.toggle('is-error', isError);
  }

  function selectSource(source) {
    activeSource = source;
    buttons.forEach(button => {
      const selected = button.dataset.source === source;
      button.classList.toggle('is-selected', selected);
      button.setAttribute('aria-pressed', selected ? 'true' : 'false');
    });
  }

  function setBusy(busy) {
    changing = busy;
    buttons.forEach(button => { button.disabled = busy; });
    panel.setAttribute('aria-busy', busy ? 'true' : 'false');
  }

  async function requestConfig() {
    const response = await fetch(`/api/escalacao-ideal/config?sidebar_source=${Date.now()}`, {
      headers: { Accept: 'application/json' },
      cache: 'no-store'
    });
    const config = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(config.error || 'Não foi possível carregar a fonte de prováveis.');
    return config;
  }

  async function saveSource(source) {
    const config = await requestConfig();
    const payload = {
      formation: config.formation || '4-3-3',
      hack_goleiro: Boolean(config.hack_goleiro),
      fechar_defesa: Boolean(config.fechar_defesa),
      posicao_capitao: config.posicao_capitao || 'atacantes',
      posicao_reserva_luxo: config.posicao_reserva_luxo || 'atacantes',
      prioridades: config.prioridades || 'atacantes,laterais,meias,zagueiros,goleiros,treinadores',
      fonte_provaveis: source
    };
    const response = await fetch('/api/escalacao-ideal/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify(payload)
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(result.error || 'Não foi possível salvar a fonte de prováveis.');
  }

  function loadScript(path, isReady) {
    if (isReady()) return Promise.resolve();
    return new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = `/static/js/${path}`;
      script.async = false;
      script.onload = () => isReady()
        ? resolve()
        : reject(new Error(`O script ${path} carregou sem disponibilizar o cálculo esperado.`));
      script.onerror = () => reject(new Error(`Não foi possível carregar ${path}.`));
      document.head.appendChild(script);
    });
  }

  async function ensureCalculationRuntime() {
    const calculators = [
      ['calculo_goleiro.js', () => window.CalculoGoleiro],
      ['calculo_lateral.js', () => window.CalculoLateral],
      ['calculo_zagueiro.js', () => window.CalculoZagueiro],
      ['calculo_meia.js', () => window.CalculoMeia],
      ['calculo_atacante.js', () => window.CalculoAtacante],
      ['calculo_treinador.js', () => window.CalculoTreinador]
    ];
    for (const [path, ready] of calculators) await loadScript(path, ready);
    await loadScript('escalacao_ideal.js', () => window.EscalacaoIdeal);
    await loadScript('escalacao_rapida.js', () => window.EscalacaoRapida);
    await loadScript('modulos-calculo-todos.js', () => window.calcularModulosPendentes);
  }

  async function calculateAllModules() {
    await ensureCalculationRuntime();
    await window.calcularModulosPendentes(modules, {
      onProgress: ({ mensagem }) => { if (mensagem) showStatus(mensagem); }
    });

    const response = await fetch(`/api/modulos/status?sidebar_source=${Date.now()}`, { cache: 'no-store' });
    const result = await response.json().catch(() => ({}));
    if (!response.ok || !result.todos_calculados || result.fonte_provaveis !== activeSource) {
      const pendentes = Object.keys(result.status || {}).filter(module => !result.status[module]);
      throw new Error(`Os módulos não confirmaram a nova fonte${pendentes.length ? `: ${pendentes.join(', ')}` : '.'}`);
    }

    // Na escalação ideal, redesenha o campo. Nas demais páginas, executa o
    // mesmo cálculo da escalação sem enviar nada ao Cartola.
    if (typeof window.calcularEscalacao === 'function') {
      await window.calcularEscalacao(true);
      if (!window.ultimaEscalacao) throw new Error('A escalação ideal não foi atualizada.');
    } else {
      const runner = new window.EscalacaoRapida();
      await runner.calcularEscalacaoIdeal();
    }
  }

  async function restorePreviousSource(previousSource) {
    await saveSource(previousSource);
    selectSource(previousSource);
    await calculateAllModules();
  }

  async function changeSource(nextSource) {
    if (changing || nextSource === activeSource) return;
    const previousSource = activeSource;
    let saved = false;
    setBusy(true);
    showStatus('Salvando fonte…');
    if (typeof window.showLoader === 'function') window.showLoader('Recalculando módulos e escalação ideal…');

    try {
      await saveSource(nextSource);
      saved = true;
      selectSource(nextSource);
      showStatus('Recalculando todos os módulos…');
      await calculateAllModules();
      showStatus('Fonte aplicada; atualizando a página…');
      if (typeof window.showToast === 'function') window.showToast('Fonte atualizada e cálculos refeitos.', 'success');
      window.setTimeout(() => window.location.reload(), 700);
    } catch (error) {
      console.error('[AERO][Prováveis] Falha ao trocar a fonte:', error);
      if (saved) {
        showStatus('Falha no recálculo. Restaurando a fonte anterior…', true);
        try {
          await restorePreviousSource(previousSource);
          showStatus(`Falhou; fonte anterior restaurada. ${error.message}`, true);
        } catch (rollbackError) {
          console.error('[AERO][Prováveis] Falha ao restaurar fonte/rankings:', rollbackError);
          showStatus(`Erro: ${error.message}. A restauração também falhou; recarregue a página.`, true);
        }
      } else {
        selectSource(previousSource);
        showStatus(error.message, true);
      }
      if (typeof window.showToast === 'function') window.showToast(error.message || 'Não foi possível recalcular.', 'error');
    } finally {
      setBusy(false);
      if (typeof window.hideLoader === 'function') window.hideLoader();
    }
  }

  buttons.forEach(button => button.addEventListener('click', () => changeSource(button.dataset.source)));

  requestConfig().then(config => {
    selectSource(config.fonte_provaveis || 'globo');
    panel.hidden = false;
  }).catch(error => {
    panel.hidden = false;
    showStatus(error.message, true);
  });
})();
