/* Interface da página de Escalação Ideal.
 * Os endpoints e o contrato do calculador permanecem no formato legado.
 */
(function () {
  'use strict';

  const POSITIONS = {
    goleiros: { singular: 'goleiro', label: 'Goleiros', short: 'GOL', icon: 'fa-hands', color: 'amber' },
    zagueiros: { singular: 'zagueiro', label: 'Zagueiros', short: 'ZAG', icon: 'fa-shield-alt', color: 'green' },
    laterais: { singular: 'lateral', label: 'Laterais', short: 'LAT', icon: 'fa-arrows-alt-h', color: 'cyan' },
    meias: { singular: 'meia', label: 'Meias', short: 'MEI', icon: 'fa-running', color: 'purple' },
    atacantes: { singular: 'atacante', label: 'Atacantes', short: 'ATA', icon: 'fa-futbol', color: 'red' },
    treinadores: { singular: 'treinador', label: 'Técnicos', short: 'TÉC', icon: 'fa-clipboard-list', color: 'slate' }
  };
  const POSITION_ORDER = ['goleiros', 'zagueiros', 'laterais', 'meias', 'atacantes', 'treinadores'];
  const FIELD_ROWS = [
    ['atacantes'],
    ['meias'],
    ['zagueiros', 'laterais'],
    ['goleiros'],
    ['treinadores']
  ];
  const PRIORITY_LABELS = {
    atacantes: 'Atacantes', laterais: 'Laterais', meias: 'Meias',
    zagueiros: 'Zagueiros', goleiros: 'Goleiros', treinadores: 'Técnicos'
  };

  const state = {
    data: null,
    clubes: {},
    editing: false,
    draggedItem: null
  };

  window.prioridadesOrdenadas = ['atacantes', 'laterais', 'meias', 'zagueiros', 'goleiros', 'treinadores'];
  window.configCarregada = false;
  window.ultimaEscalacao = null;

  const $ = (id) => document.getElementById(id);
  const page = () => $('escalacaoIdealPage');
  const can = (name) => {
    const key = name.replace(/[A-Z]/g, letter => `-${letter.toLowerCase()}`);
    return page()?.dataset[key] === 'true';
  };
  const safeNumber = (value) => Number.isFinite(Number(value)) ? Number(value) : 0;
  const money = (value) => `R$ ${safeNumber(value).toFixed(2).replace('.', ',')}`;
  const points = (player) => safeNumber(player?.pontuacao_total);
  const price = (player) => safeNumber(player?.preco_num || player?.preco);
  const idOf = (player) => String(player?.atleta_id ?? '');

  function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>'"]/g, (char) => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#039;', '"': '&quot;'
    }[char]));
  }

  function notify(message, type = 'info') {
    if (typeof showToast === 'function') showToast(message, type, 2600);
  }

  function showLoading(message) {
    if (typeof showLoader === 'function') showLoader(message);
  }

  function hideLoading() {
    if (typeof hideLoader === 'function') hideLoader();
  }

  function clubFor(player) {
    return state.clubes[player?.clube_id] || state.clubes[String(player?.clube_id)] || {};
  }

  function avatar(player, className = '') {
    const name = escapeHtml(player?.apelido || 'Jogador');
    const initials = escapeHtml((player?.apelido || '?').slice(0, 2).toUpperCase());
    const photo = player?.foto || player?.foto_url || '';
    return `<div class="ideal-player-avatar ${className}">${photo ? `<img src="${escapeHtml(photo)}" alt="${name}" onerror="this.parentElement.innerHTML='${initials}'">` : initials}</div>`;
  }

  function renderTeamSummary(data) {
    const container = $('infoInicialContent');
    if (!container) return;
    if ($('heroRound')) $('heroRound').textContent = data.rodada_atual || '—';
    const teamName = data.team_name || `Time #${data.team_id || 'N/A'}`;
    const shield = data.team_shield_url ? `<img src="${escapeHtml(data.team_shield_url)}" alt="Escudo de ${escapeHtml(teamName)}" onerror="this.style.display='none'; this.nextElementSibling.style.display='grid'">` : '';
    container.innerHTML = `
      <div class="ideal-team-identity">
        ${shield}<span class="ideal-team-shield-fallback" style="${shield ? 'display:none' : ''}"><i class="fas fa-futbol"></i></span>
        <div><span class="ideal-eyebrow">Time selecionado</span><strong class="ideal-team-name">${escapeHtml(teamName)}</strong></div>
      </div>
      <div class="ideal-stat"><i class="fas fa-calendar-alt"></i><div><span class="ideal-eyebrow">Rodada</span><strong>${escapeHtml(data.rodada_atual || '—')}</strong></div></div>
      <div class="ideal-stat"><i class="fas fa-wallet"></i><div><span class="ideal-eyebrow">Patrimônio</span><strong>${money(data.patrimonio)}</strong><small>${escapeHtml(data.patrimonio_error || 'disponível para montar o time')}</small></div></div>
      <div class="ideal-stat"><i class="fas fa-layer-group"></i><div><span class="ideal-eyebrow">Base de análise</span><strong>${Object.values(data.rankings_por_posicao || {}).reduce((total, list) => total + list.length, 0)}</strong><small>atletas ranqueados</small></div></div>`;
  }

  function rankingPlayer(player) {
    const club = clubFor(player);
    return `<div class="ideal-ranking-item">
      ${avatar(player)}
      <span class="ideal-player-name">${escapeHtml(player.apelido || 'N/A')}</span>
      <span class="ideal-ranking-values">${money(price(player))}<small>${points(player).toFixed(1)} pts</small></span>
    </div>`;
  }

  function renderTop5(data) {
    const container = $('top5CardsContent');
    if (!container) return;
    const singular = [
      ['goleiro', 'Goleiros', 'fa-hands'], ['zagueiro', 'Zagueiros', 'fa-shield-alt'],
      ['lateral', 'Laterais', 'fa-arrows-alt-h'], ['meia', 'Meias', 'fa-running'],
      ['atacante', 'Atacantes', 'fa-futbol'], ['treinador', 'Técnicos', 'fa-clipboard-list']
    ];
    let html = singular.map(([key, label, icon]) => {
      const top = (data.rankings_por_posicao?.[key] || []).slice(0, 4);
      return `<article class="ideal-ranking-card"><h4><i class="fas ${icon}"></i>${label}</h4>${top.length ? top.map(rankingPlayer).join('') : '<span class="ideal-bench-note">Sem dados disponíveis</span>'}</article>`;
    }).join('');
    const weightCard = (title, icon, list, field, color) => `<article class="ideal-ranking-card"><h4><i class="fas ${icon}"></i>${title}</h4>${(list || []).slice(0, 4).map(item => {
      const club = state.clubes[item.clube_id] || {};
      return `<div class="ideal-ranking-item"><div class="ideal-player-avatar"><i class="fas fa-shield-alt"></i></div><span class="ideal-player-name">${escapeHtml(club.nome || `Clube #${item.clube_id}`)}</span><span class="ideal-ranking-values">${safeNumber(item[field]).toFixed(2)}<small>peso</small></span></div>`;
    }).join('') || '<span class="ideal-bench-note">Sem dados disponíveis</span>'}</article>`;
    html += weightCard('Peso de jogo', 'fa-fire', data.top5_peso_jogo, 'peso_jogo', 'orange');
    html += weightCard('Peso de SG', 'fa-chart-line', data.top5_peso_sg, 'peso_sg', 'green');
    container.innerHTML = `<div class="ideal-rankings-grid">${html}</div>`;
  }

  async function loadData() {
    const response = await fetch('/api/escalacao-ideal/dados');
    const data = await response.json();
    if (!response.ok || data.error) throw new Error(data.error || 'Não foi possível carregar os dados da rodada.');
    state.data = data;
    state.clubes = data.clubes_dict || {};
    renderTeamSummary(data);
    renderTop5(data);
    return data;
  }

  window.carregarCardsTop5 = loadData;

  async function verificarStatusModulos() {
    const response = await fetch('/api/modulos/status');
    const data = await response.json();
    if (data.todos_calculados) return true;
    const names = { goleiro: 'Goleiros', lateral: 'Laterais', zagueiro: 'Zagueiros', meia: 'Meias', atacante: 'Atacantes', treinador: 'Técnicos' };
    const pending = Object.keys(data.status || {}).filter(key => !data.status[key]).map(key => names[key] || key).join(', ');
    const message = `Calcule os módulos de posição antes de montar a escalação. Pendentes: ${pending || 'verifique os módulos'}.`;
    if (typeof showAlert === 'function') await showAlert('Módulos incompletos', `${message}\n\nVocê será redirecionado para a página de módulos.`);
    window.location.href = '/modulos';
    return false;
  }

  async function carregarConfiguracoes() {
    const response = await fetch('/api/escalacao-ideal/config');
    const config = await response.json();
    $('formationSelect').value = config.formation || '4-3-3';
    $('hackGoleiroToggle').checked = can('hackGoleiro') ? Boolean(config.hack_goleiro) : false;
    $('fecharDefesaToggle').checked = can('fecharDefesa') ? Boolean(config.fechar_defesa) : false;
    $('posicaoCapitao').value = config.posicao_capitao || 'atacantes';
    $('posicaoReservaLuxo').value = config.posicao_reserva_luxo || 'atacantes';
    if (config.prioridades) {
      window.prioridadesOrdenadas = config.prioridades.split(',').map(pos => pos === 'tecnicos' ? 'treinadores' : pos).filter(pos => PRIORITY_LABELS[pos]);
    }
    renderizarPrioridades();
    window.configCarregada = true;
  }

  function renderizarPrioridades() {
    const container = $('prioridadesLista');
    if (!container) return;
    const canReorder = can('reordenarPrioridades');
    container.innerHTML = window.prioridadesOrdenadas.map((position, index) => `<div class="ideal-priority-item" draggable="${canReorder}" data-posicao="${position}" data-index="${index}"><i class="fas fa-grip-vertical grip"></i><span class="rank">${index + 1}</span><span>${PRIORITY_LABELS[position]}</span></div>`).join('');
    if (!canReorder) return;
    container.querySelectorAll('.ideal-priority-item').forEach(item => {
      item.addEventListener('dragstart', () => { state.draggedItem = item; item.style.opacity = '.45'; });
      item.addEventListener('dragover', event => event.preventDefault());
      item.addEventListener('drop', event => {
        event.preventDefault();
        if (!state.draggedItem || state.draggedItem === item) return;
        const from = Number(state.draggedItem.dataset.index);
        const to = Number(item.dataset.index);
        const moved = window.prioridadesOrdenadas.splice(from, 1)[0];
        window.prioridadesOrdenadas.splice(to, 0, moved);
        renderizarPrioridades();
        if (window.configCarregada) aoMudarConfiguracao(true);
      });
      item.addEventListener('dragend', () => { state.draggedItem = null; item.style.opacity = '1'; });
    });
  }

  async function salvarConfiguracoes() {
    const payload = {
      formation: $('formationSelect').value,
      hack_goleiro: $('hackGoleiroToggle').checked,
      fechar_defesa: $('fecharDefesaToggle').checked,
      posicao_capitao: $('posicaoCapitao').value,
      posicao_reserva_luxo: $('posicaoReservaLuxo').value,
      prioridades: window.prioridadesOrdenadas.join(',')
    };
    const response = await fetch('/api/escalacao-ideal/config', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload)
    });
    if (!response.ok) throw new Error('Não foi possível salvar as configurações.');
    adicionarLog('✓ Configurações salvas.', 'success');
  }

  function limparConsole() {
    const log = $('progressLog');
    if (log) log.innerHTML = '<div id="waitingMessage" class="ideal-log-entry">Aguardando cálculo...</div>';
    const status = $('consoleStatus');
    if (status) status.textContent = 'aguardando execução';
  }

  function adicionarLog(message, type = 'log') {
    const log = $('progressLog');
    if (!log) return;
    $('waitingMessage')?.remove();
    const entry = document.createElement('div');
    entry.className = `ideal-log-entry ${type}`;
    entry.textContent = message;
    log.appendChild(entry);
    log.scrollTop = log.scrollHeight;
    const status = $('consoleStatus');
    if (status) status.textContent = type === 'error' ? 'erro no cálculo' : type === 'success' ? 'concluído' : 'processando';
  }

  function candidatesFor(position, current) {
    const singular = POSITIONS[position].singular;
    const source = [...(state.data?.rankings_por_posicao?.[singular] || [])];
    if (current && !source.some(player => idOf(player) === idOf(current))) source.unshift(current);
    return source.slice(0, 28);
  }

  function manualSelect(position, index, current) {
    if (!state.editing) return '';
    const options = candidatesFor(position, current).map(player => `<option value="${escapeHtml(idOf(player))}" ${idOf(player) === idOf(current) ? 'selected' : ''}>${escapeHtml(player.apelido || 'Jogador')} · ${money(price(player))}</option>`).join('');
    return `<select class="ideal-manual-select" aria-label="Editar jogador" onchange="manualSelecionarJogador('${position}', ${index}, this.value)">${options}</select>`;
  }

  function playerCard(player, position, index) {
    const club = clubFor(player);
    const badges = `${player?.eh_capitao ? '<span class="ideal-badge ideal-badge-captain">CAP</span>' : ''}${player?.eh_reserva_luxo ? '<span class="ideal-badge ideal-badge-luxury">LUXO</span>' : ''}`;
    return `<div class="ideal-player" title="${escapeHtml(club.nome || '')}">${badges}${avatar(player)}<span class="ideal-player-name">${escapeHtml(player?.apelido || 'N/A')}</span><span class="ideal-player-data">${money(price(player))} · ${points(player).toFixed(1)}</span>${manualSelect(position, index, player)}</div>`;
  }

  function renderField(result) {
    return `<div class="ideal-field"><div class="ideal-field-line"></div><div class="ideal-field-circle"></div><div class="ideal-field-tag"><span>titulares</span><span>${escapeHtml($('formationSelect').value)}</span></div><div class="ideal-field-rows">${FIELD_ROWS.map(row => `<div class="ideal-field-row">${row.map(position => {
      const players = result.titulares?.[position] || [];
      if (!players.length) return '';
      return `<div class="ideal-field-group"><div class="ideal-field-pos">${POSITIONS[position].label}</div>${players.map((player, index) => playerCard(player, position, index)).join('')}</div>`;
    }).join('')}</div>`).join('')}</div></div>`;
  }

  function renderBench(result) {
    const groups = POSITION_ORDER.filter(position => (result.reservas?.[position] || []).length).map(position => {
      const players = result.reservas[position];
      return `<div class="ideal-bench-group"><div class="ideal-bench-label">${POSITIONS[position].label}</div>${players.map(player => {
        const isLuxury = Boolean(player.eh_reserva_luxo);
        return `<div class="ideal-bench-player">${avatar(player)}<span class="ideal-player-name">${escapeHtml(player.apelido || 'N/A')}</span><span class="ideal-player-data">${isLuxury ? 'LUXO · ' : ''}${money(price(player))}</span></div>`;
      }).join('')}</div>`;
    }).join('');
    return `<aside class="ideal-bench"><div class="ideal-bench-head"><span class="ideal-bench-title"><i class="fas fa-exchange-alt"></i>Reservas</span><span class="ideal-bench-note">sem custo</span></div>${groups || '<div class="ideal-bench-note">Nenhuma reserva disponível para esta combinação.</div>'}</aside>`;
  }

  function recomputeResult() {
    if (!window.ultimaEscalacao) return;
    window.ultimaEscalacao.custoTotal = POSITION_ORDER.flatMap(position => window.ultimaEscalacao.titulares?.[position] || []).reduce((total, player) => total + price(player), 0);
    window.ultimaEscalacao.pontuacaoTotal = POSITION_ORDER.flatMap(position => window.ultimaEscalacao.titulares?.[position] || []).reduce((total, player) => total + points(player), 0);
  }

  function renderManualEditor(result) {
    const rows = POSITION_ORDER.flatMap(position => (result.titulares?.[position] || []).map((player, index) => `<div class="ideal-manual-row"><label>${POSITIONS[position].short} · ${escapeHtml(player.apelido || 'N/A')}</label><select onchange="manualSelecionarJogador('${position}', ${index}, this.value)">${candidatesFor(position, player).map(candidate => `<option value="${escapeHtml(idOf(candidate))}" ${idOf(candidate) === idOf(player) ? 'selected' : ''}>${escapeHtml(candidate.apelido || 'Jogador')}</option>`).join('')}</select></div>`));
    const editor = $('manualEditor');
    if (editor) editor.innerHTML = `<p>Troque atletas individualmente e revise o saldo. A escalação manual continua sendo enviada pelo contrato atual.</p><div class="ideal-manual-list">${rows.join('')}</div>`;
  }

  function exibirResultado(result, clubesDict = {}) {
    state.clubes = clubesDict || state.clubes;
    const panel = $('resultadoPanel');
    const content = $('escalacaoContent');
    if (!panel || !content) return;
    recomputeResult();
    const patrimonio = safeNumber(result.patrimonio || state.data?.patrimonio);
    const balance = patrimonio - safeNumber(result.custoTotal);
    const captain = POSITION_ORDER.flatMap(position => result.titulares?.[position] || []).find(player => player.eh_capitao);
    content.innerHTML = `<div class="ideal-metrics"><div class="ideal-metric cost"><span>Investimento</span><strong>${money(result.custoTotal)}</strong><em>titulares</em></div><div class="ideal-metric balance"><span>Saldo disponível</span><strong>${money(balance)}</strong><em>patrimônio ${money(patrimonio)}</em></div><div class="ideal-metric points"><span>Projeção</span><strong>${safeNumber(result.pontuacaoTotal).toFixed(2)} pts</strong><em>${captain ? `capitão: ${escapeHtml(captain.apelido)}` : 'sem capitão definido'}</em></div></div><div class="ideal-field-layout">${renderField(result)}${renderBench(result)}</div><div id="manualEditor" class="ideal-manual-editor ${state.editing ? 'is-open' : ''}"></div>`;
    renderManualEditor(result);
    panel.classList.remove('hidden');
    $('escalarBtn').disabled = false;
  }

  async function calcularEscalacao() {
    const button = $('calcularBtn');
    if (button) button.disabled = true;
    limparConsole();
    $('resultadoPanel')?.classList.add('hidden');
    showLoading('Calculando escalação ideal...');
    try {
      const data = state.data || await loadData();
      const escalador = new window.EscalacaoIdeal({
        rodada_atual: data.rodada_atual,
        patrimonio: data.patrimonio,
        rankings_por_posicao: data.rankings_por_posicao,
        todos_goleiros: data.todos_goleiros || [],
        clubes_sg: data.clubes_sg || [],
        adversarios_dict: data.adversarios_dict || {},
        formacao: $('formationSelect').value,
        posicao_capitao: $('posicaoCapitao').value,
        posicao_reserva_luxo: $('posicaoReservaLuxo').value,
        prioridades: window.prioridadesOrdenadas,
        fechar_defesa: $('fecharDefesaToggle').checked,
        hack_goleiro: $('hackGoleiroToggle').checked
      });
      escalador.setLogCallback(message => adicionarLog(message, 'log'));
      window.ultimaEscalacao = await escalador.calcular();
      exibirResultado(window.ultimaEscalacao, data.clubes_dict);
      adicionarLog('✓ Escalação pronta para revisão ou envio.', 'success');
    } catch (error) {
      window.ultimaEscalacao = null;
      $('escalarBtn').disabled = true;
      adicionarLog(`ERRO: ${error.message}`, 'error');
      notify(error.message, 'error');
    } finally {
      hideLoading();
      if (button) button.disabled = false;
    }
  }

  async function escalarTime() {
    if (!window.ultimaEscalacao) return notify('Calcule a escalação ideal primeiro.', 'warning');
    let confirmed = true;
    if (typeof showConfirm === 'function') confirmed = await showConfirm('Confirma escalar este time no Cartola FC?', 'Escalar time', { confirmText: 'Sim, escalar', cancelText: 'Cancelar' });
    if (!confirmed) return;
    const button = $('escalarBtn');
    const original = button.innerHTML;
    button.disabled = true;
    button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Enviando...';
    showLoading('Escalando time no Cartola FC...');
    try {
      const response = await fetch('/api/escalacao-ideal/escalar', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ escalacao: window.ultimaEscalacao, formacao: $('formationSelect').value }) });
      const data = await response.json();
      if (!response.ok || !data.success) throw new Error(data.error || 'Não foi possível escalar o time.');
      adicionarLog(`✓ ${data.mensagem || 'Time escalado com sucesso.'}`, 'success');
      notify('Time escalado com sucesso! Boa sorte na rodada.', 'success');
    } catch (error) {
      adicionarLog(`ERRO ao escalar: ${error.message}`, 'error');
      notify(error.message, 'error');
    } finally {
      hideLoading();
      button.disabled = false;
      button.innerHTML = original;
    }
  }

  function toggleManualEdit() {
    if (!window.ultimaEscalacao) return notify('Calcule uma escalação antes de editar.', 'warning');
    state.editing = !state.editing;
    const button = $('manualEditBtn');
    if (button) button.innerHTML = state.editing ? '<i class="fas fa-check"></i> Concluir edição' : '<i class="fas fa-pen"></i> Editar manualmente';
    exibirResultado(window.ultimaEscalacao, state.clubes);
  }

  function manualSelecionarJogador(position, index, athleteId) {
    if (!window.ultimaEscalacao) return;
    const current = window.ultimaEscalacao.titulares?.[position]?.[index];
    const candidate = candidatesFor(position, current).find(player => idOf(player) === String(athleteId));
    if (!candidate) return;
    const replacement = { ...candidate, eh_capitao: Boolean(current?.eh_capitao) };
    window.ultimaEscalacao.titulares[position][index] = replacement;
    recomputeResult();
    exibirResultado(window.ultimaEscalacao, state.clubes);
    if (state.editing) $('manualEditor')?.classList.add('is-open');
    adicionarLog(`↻ ${POSITIONS[position].short}: ${replacement.apelido} selecionado manualmente.`, 'info');
  }

  async function aoMudarConfiguracao(fromPriority = false) {
    if (!window.configCarregada) return;
    window.ultimaEscalacao = null;
    $('escalarBtn').disabled = true;
    try {
      await salvarConfiguracoes();
      if (!fromPriority) notify('Configuração salva. Recalculando...', 'info');
      await calcularEscalacao();
    } catch (error) {
      adicionarLog(`ERRO ao salvar configuração: ${error.message}`, 'error');
      notify(error.message, 'error');
    }
  }

  function bindEvents() {
    ['formationSelect', 'hackGoleiroToggle', 'fecharDefesaToggle', 'posicaoCapitao', 'posicaoReservaLuxo'].forEach(id => $(id)?.addEventListener('change', () => aoMudarConfiguracao()));
    $('manualEditBtn')?.addEventListener('click', toggleManualEdit);
  }

  async function init() {
    showLoading('Carregando painel de escalação...');
    try {
      if (!(await verificarStatusModulos())) return;
      await carregarConfiguracoes();
      await loadData();
      bindEvents();
      adicionarLog('Dados da rodada carregados. Ajuste as opções e calcule quando estiver pronto.', 'info');
    } catch (error) {
      adicionarLog(`ERRO ao carregar: ${error.message}`, 'error');
      notify(error.message, 'error');
      $('infoInicialContent').innerHTML = `<div class="ideal-empty"><div><i class="fas fa-triangle-exclamation"></i><p>${escapeHtml(error.message)}</p></div></div>`;
    } finally {
      hideLoading();
    }
  }

  window.calcularEscalacao = calcularEscalacao;
  window.escalarTime = escalarTime;
  window.limparConsole = limparConsole;
  window.adicionarLog = adicionarLog;
  window.exibirResultado = exibirResultado;
  window.toggleManualEdit = toggleManualEdit;
  window.manualSelecionarJogador = manualSelecionarJogador;
  window.aoMudarConfiguracao = aoMudarConfiguracao;
  window.renderizarPrioridades = renderizarPrioridades;

  document.addEventListener('DOMContentLoaded', init);
})();
