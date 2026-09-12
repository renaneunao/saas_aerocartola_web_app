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
  const FORMATION_COUNTS = {
    '4-3-3': { goleiros: 1, zagueiros: 2, laterais: 2, meias: 3, atacantes: 3 },
    '4-4-2': { goleiros: 1, zagueiros: 2, laterais: 2, meias: 4, atacantes: 2 },
    '3-5-2': { goleiros: 1, zagueiros: 3, laterais: 0, meias: 5, atacantes: 2 },
    '3-4-3': { goleiros: 1, zagueiros: 3, laterais: 0, meias: 4, atacantes: 3 },
    '4-5-1': { goleiros: 1, zagueiros: 2, laterais: 2, meias: 5, atacantes: 1 },
    '5-3-2': { goleiros: 1, zagueiros: 3, laterais: 2, meias: 3, atacantes: 2 },
    '5-4-1': { goleiros: 1, zagueiros: 3, laterais: 2, meias: 4, atacantes: 1 }
  };
  const PRIORITY_LABELS = {
    atacantes: 'Atacantes', laterais: 'Laterais', meias: 'Meias',
    zagueiros: 'Zagueiros', goleiros: 'Goleiros', treinadores: 'Técnicos'
  };

  const state = {
    data: null,
    clubes: {},
    editing: true,
    draggedItem: null,
    availability: [],
    picker: null,
    teamChanged: false
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
  // Rankings antigos e respostas montadas manualmente podem usar nomes
  // diferentes para o identificador. O papel especial não pode depender do
  // índice do card, por isso sempre normalizamos o ID aqui.
  const idOf = (player) => String(player?.atleta_id ?? player?.id ?? player?.id_atleta ?? '');

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

  function teamIndicators(player, position) {
    const club = clubFor(player);
    const jogoMap = state.data?.peso_jogo_por_clube || {};
    const sgMap = state.data?.peso_sg_por_clube || {};
    const jogo = safeNumber(jogoMap[String(player?.clube_id)] ?? player?.peso_jogo);
    const sg = safeNumber(sgMap[String(player?.clube_id)] ?? player?.peso_sg);
    const sgPercent = Math.max(0, Math.min(100, sg <= 1 ? sg * 100 : sg));
    const shield = club.escudo_url || club.escudo || club.clube_escudo_url || player?.clube_escudo_url || '';
    const name = club.abreviacao || player?.clube_abrev || club.nome || player?.clube_nome || '—';
    const defense = ['goleiros', 'laterais', 'zagueiros'].includes(position);
    return `<span class="ideal-player-team-badge"><span>${shield ? `<img src="${escapeHtml(shield)}" alt="">` : '<i class="fas fa-shield-alt"></i>'}${escapeHtml(name)}</span><b>F ${jogo.toFixed(2)}</b></span>${defense ? `<span class="ideal-player-sg-badge"><i class="fas fa-shield-heart"></i> SG ${sgPercent.toFixed(0)}%</span>` : ''}`;
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
    if (position === 'goleiros') source.push(...(state.data?.todos_goleiros || []));
    if (current && !source.some(player => idOf(player) === idOf(current))) source.unshift(current);
    const unique = new Map(source.filter(player => idOf(player)).map(player => [idOf(player), player]));
    return [...unique.values()];
  }

  function playerCard(player, position, index) {
    const badges = player?.eh_capitao ? '<span class="ideal-badge ideal-badge-captain">CAP</span>' : '';
    return `<div class="ideal-player ideal-player-card" title="Trocar ${escapeHtml(player?.apelido || 'jogador')}" data-picker-kind="starter" data-picker-position="${position}" data-picker-index="${index}" role="button" tabindex="0">${badges}${avatar(player)}<span class="ideal-player-name">${escapeHtml(player?.apelido || 'N/A')}</span><span class="ideal-player-chips"><span>${money(price(player))}</span><span>${points(player).toFixed(1)} pts</span></span>${teamIndicators(player, position)}<button type="button" class="ideal-special-action" data-special-role="captain" data-athlete-id="${escapeHtml(idOf(player))}" title="Definir ${escapeHtml(player?.apelido || 'jogador')} como capitão"><i class="fas fa-crown"></i><span>Capitão</span></button><button type="button" class="ideal-player-unavailable" data-availability-action="poupar" data-athlete-id="${escapeHtml(idOf(player))}" title="Marcar como não joga"><i class="fas fa-ban"></i><span>não joga</span></button></div>`;
  }

  function emptySlot(position, index) {
    return `<button type="button" class="ideal-player ideal-player-empty" data-picker-kind="starter" data-picker-position="${position}" data-picker-index="${index}"><span class="ideal-empty-plus"><i class="fas fa-plus"></i></span><span class="ideal-player-name">Escolher</span><span class="ideal-player-action">adicionar</span></button>`;
  }

  function playerSlots(result, position) {
    const count = FORMATION_COUNTS[$('formationSelect')?.value] || FORMATION_COUNTS['4-3-3'];
    const players = (result.titulares?.[position] || []).filter(Boolean);
    const total = Math.max(count[position] || 0, players.length);
    return Array.from({ length: total }, (_, index) => playerSlot(result, position, index)).join('');
  }

  function playerSlot(result, position, index) {
    const players = (result.titulares?.[position] || []).filter(Boolean);
    return players[index] ? playerCard(players[index], position, index) : emptySlot(position, index);
  }

  function defenseLane(result, position, index, label) {
    const count = FORMATION_COUNTS[$('formationSelect')?.value] || FORMATION_COUNTS['4-3-3'];
    const player = result.titulares?.[position]?.[index];
    if (position === 'laterais' && !(count.laterais > index) && !player) return '';
    return `<div class="ideal-field-defense-lane"><div class="ideal-field-pos">${label}</div><div class="ideal-field-players">${playerSlot(result, position, index)}</div></div>`;
  }

  function fieldGroup(result, position, className = '') {
    const count = FORMATION_COUNTS[$('formationSelect')?.value] || FORMATION_COUNTS['4-3-3'];
    if (!count[position] && !(result.titulares?.[position] || []).length) return '';
    return `<div class="ideal-field-group ${className}"><div class="ideal-field-pos">${POSITIONS[position].label}</div><div class="ideal-field-players">${playerSlots(result, position)}</div></div>`;
  }

  function fieldSubmitButton() {
    if (!can('podeEscalar')) return '<button id="fieldSubmitBtn" type="button" class="ideal-field-submit ideal-field-submit-locked" disabled><i class="fas fa-lock"></i> Enviar escalação</button>';
    return '<button id="fieldSubmitBtn" type="button" class="ideal-field-submit" data-submit-lineup><i class="fas fa-paper-plane"></i><span>Enviar escalação</span></button>';
  }

  function defenseLayout(result) {
    const count = FORMATION_COUNTS[$('formationSelect')?.value] || FORMATION_COUNTS['4-3-3'];
    const center = fieldGroup(result, 'zagueiros', 'ideal-field-group-center');
    const left = count.laterais > 0 ? defenseLane(result, 'laterais', 0, 'Lateral esquerdo') : '';
    const right = count.laterais > 1 ? defenseLane(result, 'laterais', 1, 'Lateral direito') : '';
    if (!center && !left && !right) return '';
    return `<div class="ideal-field-row ideal-field-row-defense"><div class="ideal-field-defense-layout"><div class="ideal-field-defense-side ideal-field-defense-side-left">${left}</div><div class="ideal-field-defense-center">${center}</div><div class="ideal-field-defense-side ideal-field-defense-side-right">${right}</div></div></div>`;
  }

  function renderField(result) {
    const formation = $('formationSelect')?.value || '4-3-3';
    return `<div class="ideal-field ideal-field--${formation.replace('-', '')}"><div class="ideal-field-line"></div><div class="ideal-field-circle"></div><div class="ideal-field-goal ideal-field-goal-top"><span></span></div><div class="ideal-field-goal ideal-field-goal-bottom"><span></span></div><div class="ideal-field-tag"><span>titulares</span><span>${escapeHtml(formation)}</span></div><div class="ideal-field-rows"><div class="ideal-field-row ideal-field-row-attack">${fieldGroup(result, 'atacantes')}</div><div class="ideal-field-row ideal-field-row-midfield">${fieldGroup(result, 'meias')}</div>${defenseLayout(result)}<div class="ideal-field-row ideal-field-row-goalkeeper">${fieldGroup(result, 'goleiros')}</div></div><div class="ideal-field-coach">${fieldGroup(result, 'treinadores', 'ideal-field-group-coach')}</div>${fieldSubmitButton()}</div>`;
  }

  function renderBench(result) {
    const positions = POSITION_ORDER.filter(position => position !== 'treinadores');
    const groups = positions.map(position => {
      const players = (result.reservas?.[position] || []).filter(Boolean);
      const player = players[0];
      const card = player ? `<div class="ideal-bench-player ideal-player-card" data-picker-kind="reserve" data-picker-position="${position}" data-picker-index="0" role="button" tabindex="0">${player.eh_reserva_luxo ? '<span class="ideal-badge ideal-badge-luxury">LUXO</span>' : ''}${avatar(player)}<span class="ideal-bench-copy"><span class="ideal-player-name">${escapeHtml(player.apelido || 'N/A')}</span><span class="ideal-player-chips"><span>${money(price(player))}</span><span>${points(player).toFixed(1)} pts</span></span></span><span class="ideal-bench-signals">${teamIndicators(player, position)}</span><button type="button" class="ideal-special-action" data-special-role="luxury" data-athlete-id="${escapeHtml(idOf(player))}" title="Definir ${escapeHtml(player.apelido || 'jogador')} como reserva de luxo"><i class="fas fa-gem"></i><span>Luxo</span></button><button type="button" class="ideal-player-unavailable" data-availability-action="poupar" data-athlete-id="${escapeHtml(idOf(player))}" title="Marcar como não joga"><i class="fas fa-ban"></i><span>não joga</span></button></div>` : `<button type="button" class="ideal-bench-player ideal-bench-empty" data-picker-kind="reserve" data-picker-position="${position}" data-picker-index="0"><i class="fas fa-plus"></i><span>Adicionar reserva</span></button>`;
      return `<div class="ideal-bench-group"><div class="ideal-bench-label">${POSITIONS[position].label}<small>mais barata que o titular</small></div>${card}</div>`;
    }).join('');
    return `<aside class="ideal-bench"><div class="ideal-bench-head"><span class="ideal-bench-title"><i class="fas fa-exchange-alt"></i>Reservas</span><span class="ideal-bench-note">sem custo</span></div>${groups}</aside>`;
  }

  function recomputeResult() {
    if (!window.ultimaEscalacao) return;
    const result = window.ultimaEscalacao;
    result.titulares ||= {};
    result.reservas ||= {};
    POSITION_ORDER.forEach(position => {
      result.titulares[position] = (result.titulares[position] || []).filter(Boolean);
      result.reservas[position] = (result.reservas[position] || []).filter(Boolean);
      if (result.titulares[position].length && result.reservas[position].length) {
        const minimumStarterPrice = Math.min(...result.titulares[position].map(price));
        result.reservas[position] = result.reservas[position].filter((player) => price(player) < minimumStarterPrice);
      }
      result.titulares[position].forEach(player => { player.eh_capitao = false; player.eh_reserva_luxo = false; });
      result.reservas[position].forEach(player => { player.eh_capitao = false; player.eh_reserva_luxo = false; });
    });
    const captainPosition = $('posicaoCapitao')?.value || 'atacantes';
    const captainPool = result.titulares[captainPosition] || [];
    const allStarters = POSITION_ORDER.flatMap(position => result.titulares[position] || []);
    const manualCaptain = allStarters.find(player => idOf(player) === String(result.manualCaptainId || ''));
    const captain = manualCaptain || (captainPool.length ? captainPool.reduce((best, player) => points(player) > points(best) ? player : best) : null);
    if (captain) captain.eh_capitao = true;
    const luxuryPosition = $('posicaoReservaLuxo')?.value || 'atacantes';
    const allReserves = POSITION_ORDER.flatMap(position => result.reservas[position] || []);
    const manualLuxury = allReserves.find(player => idOf(player) === String(result.manualLuxuryId || ''));
    const luxury = manualLuxury || result.reservas[luxuryPosition]?.[0];
    if (luxury && luxuryPosition !== 'treinadores') luxury.eh_reserva_luxo = true;
    result.custoTotal = POSITION_ORDER.flatMap(position => result.titulares[position] || []).reduce((total, player) => total + price(player), 0);
    // No Cartola, o capitão pontua em dobro. A base é recalculada para que a
    // troca manual do capitão atualize imediatamente a projeção exibida.
    const pontuacaoBase = POSITION_ORDER.flatMap(position => result.titulares[position] || []).reduce((total, player) => total + points(player), 0);
    result.pontuacaoTotal = pontuacaoBase + (captain ? points(captain) : 0);
  }

  function renderManualEditor(result) {
    const editor = $('manualEditor');
    if (editor) editor.innerHTML = `<p><i class="fas fa-circle-info"></i> Clique em qualquer atleta ou vaga no campo e nos reservas para trocar. O saldo, capitão e reserva de luxo são recalculados a cada alteração.</p>`;
  }

  function setSpecialRole(role, target) {
    if (!window.ultimaEscalacao) return;
    if (!target) return;
    const card = target.closest('[data-picker-kind]');
    const groupName = role === 'luxury' ? 'reservas' : 'titulares';
    const group = window.ultimaEscalacao[groupName] || {};
    const position = card?.dataset.pickerPosition || '';
    const players = (group[position] || []).filter(Boolean);
    const selectedId = target.dataset.athleteId || '';
    const player = players.find((item) => idOf(item) === String(selectedId)) || players[Number(card?.dataset.pickerIndex)] || null;
    if (!player) return;
    const playerId = idOf(player);
    if (!playerId) return notify('Este atleta não tem um identificador válido para a troca.', 'warning');
    if (role === 'captain') {
      window.ultimaEscalacao.manualCaptainId = playerId;
      adicionarLog(`♛ Capitão alterado para ${player.apelido || player.nome || 'atleta'}.`, 'info');
    } else {
      window.ultimaEscalacao.manualLuxuryId = playerId;
      adicionarLog(`◆ Reserva de luxo alterada para ${player.apelido || player.nome || 'atleta'}.`, 'info');
    }
    state.teamChanged = true;
    recomputeResult();
    exibirResultado(window.ultimaEscalacao, state.clubes);
  }

  function refreshSubmitButton() {
    const buttons = [$('escalarBtn'), $('fieldSubmitBtn')].filter(Boolean);
    if (!buttons.length || !can('podeEscalar')) return;
    const label = state.teamChanged
      ? '<i class="fas fa-paper-plane"></i> Enviar time alterado'
      : '<i class="fas fa-paper-plane"></i> Enviar escalação';
    buttons.forEach((button) => {
      button.innerHTML = button.id === 'fieldSubmitBtn'
        ? (state.teamChanged ? '<i class="fas fa-paper-plane"></i><span>Enviar time alterado</span>' : '<i class="fas fa-paper-plane"></i><span>Enviar escalação</span>')
        : label;
    });
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
    content.innerHTML = `<div class="ideal-metrics"><div class="ideal-metric cost"><span>Investimento</span><strong>${money(result.custoTotal)}</strong><em>titulares</em></div><div class="ideal-metric balance"><span>Saldo disponível</span><strong>${money(balance)}</strong><em>patrimônio ${money(patrimonio)}</em></div><div class="ideal-metric points"><span>Projeção</span><strong>${safeNumber(result.pontuacaoTotal).toFixed(2)} pts</strong><em>${captain ? `capitão em dobro: ${escapeHtml(captain.apelido)}` : 'sem capitão definido'}</em></div></div><div class="ideal-field-layout">${renderField(result)}${renderBench(result)}</div><div id="manualEditor" class="ideal-manual-editor ${state.editing ? 'is-open' : ''}"></div>`;
    renderManualEditor(result);
    panel.classList.remove('hidden');
    refreshSubmitButton();
    const expected = Object.values(FORMATION_COUNTS[$('formationSelect')?.value] || FORMATION_COUNTS['4-3-3']).reduce((sum, value) => sum + value, 0) + 1;
    const actual = POSITION_ORDER.flatMap(position => result.titulares?.[position] || []).length;
    const canSend = actual === expected;
    $('escalarBtn').disabled = !canSend;
    if ($('fieldSubmitBtn')) $('fieldSubmitBtn').disabled = !canSend;
  }

  async function calcularEscalacao(recarregarDados = true) {
    const button = $('calcularBtn');
    if (button) button.disabled = true;
    limparConsole();
    $('resultadoPanel')?.classList.add('hidden');
    showLoading('Calculando escalação ideal...');
    try {
      const data = recarregarDados || !state.data ? await loadData() : state.data;
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
    const buttons = [$('escalarBtn'), $('fieldSubmitBtn')].filter(Boolean);
    buttons.forEach((button) => {
      button.disabled = true;
      button.innerHTML = button.id === 'fieldSubmitBtn'
        ? '<i class="fas fa-spinner fa-spin"></i><span>Enviando...</span>'
        : '<i class="fas fa-spinner fa-spin"></i> Enviando...';
    });
    showLoading('Escalando time no Cartola FC...');
    try {
      const response = await fetch('/api/escalacao-ideal/escalar', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ escalacao: window.ultimaEscalacao, formacao: $('formationSelect').value }) });
      const data = await response.json();
      if (!response.ok || !data.success) throw new Error(data.error || 'Não foi possível escalar o time.');
      state.teamChanged = false;
      adicionarLog(`✓ ${data.mensagem || 'Time escalado com sucesso.'}`, 'success');
      notify('Time escalado com sucesso! Boa sorte na rodada.', 'success');
    } catch (error) {
      adicionarLog(`ERRO ao escalar: ${error.message}`, 'error');
      notify(error.message, 'error');
    } finally {
      hideLoading();
      buttons.forEach((button) => { button.disabled = false; });
      refreshSubmitButton();
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
    const used = POSITION_ORDER.flatMap(item => [
      ...(window.ultimaEscalacao.titulares?.[item] || []),
      ...(window.ultimaEscalacao.reservas?.[item] || [])
    ]).filter(player => player && idOf(player) !== idOf(current));
    if (used.some(player => idOf(player) === idOf(candidate))) return notify('Este atleta já está em outra vaga.', 'warning');
    const replacement = { ...candidate };
    window.ultimaEscalacao.titulares[position][index] = replacement;
    state.teamChanged = true;
    recomputeResult();
    exibirResultado(window.ultimaEscalacao, state.clubes);
    if (state.editing) $('manualEditor')?.classList.add('is-open');
    adicionarLog(`↻ ${POSITIONS[position].short}: ${replacement.apelido} selecionado manualmente.`, 'info');
  }

  function currentPickerPlayer() {
    const picker = state.picker;
    if (!picker || !window.ultimaEscalacao) return null;
    const group = picker.kind === 'reserve' ? window.ultimaEscalacao.reservas : window.ultimaEscalacao.titulares;
    return group?.[picker.position]?.[picker.index] || null;
  }

  function scoutValue(player, scout) {
    if (!scout) return 0;
    return safeNumber(player?.[`media_${scout}`] ?? player?.[`avg_${scout}`] ?? player?.[`scout_${scout}`] ?? player?.[scout]);
  }

  function statusLabel(player) {
    if (player?.availability_rule === 'cravado') return 'Cravado';
    return ({ 2: 'Dúvida', 3: 'Improvável', 5: 'Suspenso', 6: 'Nulo', 7: 'Provável' })[Number(player?.status_id)] || 'Status indisponível';
  }

  function pickerPool() {
    return candidatesFor(state.picker.position, currentPickerPlayer());
  }

  function renderPickerFilters(pool) {
    const club = $('pickerClub');
    const scout = $('pickerScout');
    if (club) {
      const clubs = new Map(pool.map(player => [String(player.clube_id || ''), clubFor(player).nome || player.clube_nome || `Clube #${player.clube_id}`]).filter(([id]) => id));
      club.innerHTML = '<option value="">Todos os times</option>' + [...clubs.entries()].sort((a, b) => a[1].localeCompare(b[1])).map(([id, name]) => `<option value="${escapeHtml(id)}">${escapeHtml(name)}</option>`).join('');
    }
    if (scout) {
      const keys = new Set();
      pool.forEach(player => Object.keys(player || {}).forEach(key => { if (/^(media|avg|scout)_/.test(key)) keys.add(key.replace(/^(media|avg|scout)_/, '')); }));
      ['ds', 'fs', 'ff', 'fd', 'g', 'a', 'sg', 'de'].forEach(key => keys.add(key));
      scout.innerHTML = '<option value="">Escolha o scout</option>' + [...keys].sort().map(key => `<option value="${escapeHtml(key)}">${escapeHtml(key.toUpperCase())}</option>`).join('');
    }
  }

  function renderPickerResults() {
    if (!state.picker) return;
    const target = $('playerPickerResults');
    if (!target) return;
    const current = currentPickerPlayer();
    const used = new Set(POSITION_ORDER.flatMap(position => [
      ...(window.ultimaEscalacao?.titulares?.[position] || []),
      ...(window.ultimaEscalacao?.reservas?.[position] || [])
    ]).filter(Boolean).filter(player => idOf(player) !== idOf(current)).map(idOf));
    const name = ($('pickerName')?.value || '').trim().toLocaleLowerCase();
    const clubId = $('pickerClub')?.value || '';
    const sort = $('pickerSort')?.value || 'expected';
    const scout = $('pickerScout')?.value || '';
    const statusFilter = state.picker.statusFilter || 'provaveis';
    const starterPool = window.ultimaEscalacao?.titulares?.[state.picker.position] || [];
    const reserveLimit = state.picker.kind === 'reserve' && starterPool.length ? Math.min(...starterPool.map(price)) : Infinity;
    const candidates = pickerPool().filter(player => {
      const status = Number(player.status_id);
      if (status === 6 || player.availability_rule === 'poupar') return false;
      if (statusFilter === 'provaveis' && status !== 7 && player.availability_rule !== 'cravado') return false;
      if (statusFilter === 'cravados' && player.availability_rule !== 'cravado') return false;
      if (statusFilter === 'duvidas' && ![2, 3, 5].includes(status)) return false;
      const playerName = `${player.apelido || ''} ${player.nome || ''}`.toLocaleLowerCase();
      if (name && !playerName.includes(name)) return false;
      if (clubId && String(player.clube_id) !== clubId) return false;
      if (state.picker.kind === 'reserve' && price(player) >= reserveLimit) return false;
      return !used.has(idOf(player));
    }).sort((a, b) => {
      if (sort === 'average') return safeNumber(b.media_num) - safeNumber(a.media_num);
      if (sort === 'price_asc') return price(a) - price(b);
      if (sort === 'price_desc') return price(b) - price(a);
      if (sort === 'scout') return scoutValue(b, scout) - scoutValue(a, scout);
      if (sort === 'name') return String(a.apelido || a.nome || '').localeCompare(String(b.apelido || b.nome || ''), 'pt-BR');
      return points(b) - points(a);
    }).slice(0, 80);
    const rule = $('playerPickerRule');
    if (rule) rule.textContent = state.picker.kind === 'reserve' ? `Reserva: preço abaixo de ${reserveLimit === Infinity ? '—' : money(reserveLimit)} do titular mais barato.` : 'Titular: escolha um atleta da posição com os filtros abaixo.';
    const priceLimit = $('playerPickerPriceLimit');
    if (priceLimit) {
      const value = priceLimit.querySelector('strong');
      if (value) value.textContent = state.picker.kind === 'reserve'
        ? (reserveLimit === Infinity ? 'Aguardando titular' : `${money(reserveLimit)} (abaixo deste valor)`)
        : 'Sem limite de reserva';
    }
    target.innerHTML = candidates.length ? candidates.map(player => `<button type="button" class="ideal-picker-player" data-picker-athlete="${escapeHtml(idOf(player))}">${avatar(player, 'ideal-picker-avatar')}<span><strong>${escapeHtml(player.apelido || player.nome || 'Jogador')}</strong><small>${escapeHtml(clubFor(player).nome || player.clube_nome || 'Clube')} · ${money(price(player))} · ${points(player).toFixed(2)} pts · ${escapeHtml(statusLabel(player))}</small></span><em>${scout ? scoutValue(player, scout).toFixed(2) : 'selecionar'}</em></button>`).join('') : '<div class="ideal-picker-empty">Nenhum atleta atende aos filtros e às regras desta vaga.</div>';
    target.querySelectorAll('[data-picker-athlete]').forEach(button => button.addEventListener('click', () => applyPicker(button.dataset.pickerAthlete)));
  }

  function setPickerStatus(status) {
    if (!state.picker) return;
    state.picker.statusFilter = status;
    document.querySelectorAll('[data-picker-status]').forEach(button => {
      const active = button.dataset.pickerStatus === status;
      button.classList.toggle('is-active', active);
      button.setAttribute('aria-pressed', String(active));
    });
    renderPickerResults();
  }

  function openPicker(position, kind, index) {
    if (!window.ultimaEscalacao) return notify('Calcule a escalação antes de editar.', 'warning');
    state.picker = { position, kind, index: Number(index) || 0, statusFilter: 'provaveis' };
    const current = currentPickerPlayer();
    $('playerPickerContext').textContent = `${kind === 'reserve' ? 'Reserva' : 'Titular'} · ${POSITIONS[position].label}`;
    $('playerPickerTitle').textContent = current ? `Trocar ${current.apelido || 'atleta'}` : `Adicionar ${POSITIONS[position].singular}`;
    ['pickerName'].forEach(id => { if ($(id)) $(id).value = ''; });
    if ($('pickerSort')) $('pickerSort').value = 'expected';
    if ($('pickerScout')) $('pickerScout').value = '';
    setPickerStatus('provaveis');
    const pool = pickerPool();
    renderPickerFilters(pool);
    renderPickerResults();
    const picker = $('playerPicker');
    picker.hidden = false; picker.setAttribute('aria-hidden', 'false');
    document.body.classList.add('ideal-picker-open');
  }

  function closePicker() {
    const picker = $('playerPicker');
    if (!picker) return;
    picker.hidden = true; picker.setAttribute('aria-hidden', 'true'); state.picker = null;
    document.body.classList.remove('ideal-picker-open');
  }

  async function confirmCandidateAvailability(candidate) {
    const status = Number(candidate?.status_id);
    if (![2, 3, 5].includes(status) || candidate.availability_rule === 'cravado') return true;
    const label = escapeHtml(candidate.apelido || candidate.nome || 'este atleta');
    let confirmed = false;
    if (typeof showConfirm === 'function') {
      confirmed = await showConfirm(`${label} está marcado como ${escapeHtml(candidate.status_nome || 'não provável')}. Deseja cravar que ele joga nesta rodada?`, 'Confirmar disponibilidade', { confirmText: 'Sim, cravar que joga', cancelText: 'Voltar' });
    } else {
      confirmed = window.confirm(`${candidate.apelido || candidate.nome || 'Este atleta'} está como não provável. Deseja cravar que joga nesta rodada?`);
    }
    if (!confirmed) return false;
    if (!state.data?.team_id) return true;
    const response = await fetch('/api/player-availability', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ team_id: state.data.team_id, season: state.data.temporada_atual, round_number: state.data.rodada_atual, athlete_id: Number(idOf(candidate)), rule: 'cravado' })
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Não foi possível cravar a disponibilidade.');
    candidate.availability_rule = 'cravado';
    return true;
  }

  async function applyPicker(athleteId) {
    if (!state.picker || !window.ultimaEscalacao) return;
    const current = currentPickerPlayer();
    const candidate = pickerPool().find(player => idOf(player) === String(athleteId));
    if (!candidate) return;
    const all = POSITION_ORDER.flatMap(position => [
      ...(window.ultimaEscalacao.titulares?.[position] || []),
      ...(window.ultimaEscalacao.reservas?.[position] || [])
    ]).filter(Boolean).filter(player => idOf(player) !== idOf(current));
    if (all.some(player => idOf(player) === idOf(candidate))) return notify('Este atleta já está em outra vaga.', 'warning');
    if (state.picker.kind === 'reserve') {
      const starters = window.ultimaEscalacao.titulares?.[state.picker.position] || [];
      const limit = starters.length ? Math.min(...starters.map(price)) : Infinity;
      if (price(candidate) >= limit) return notify(`A reserva precisa custar menos que ${money(limit)}.`, 'warning');
    }
    try {
      if (!(await confirmCandidateAvailability(candidate))) return;
    } catch (error) {
      return notify(error.message, 'error');
    }
    const group = state.picker.kind === 'reserve' ? window.ultimaEscalacao.reservas : window.ultimaEscalacao.titulares;
    group[state.picker.position] ||= [];
    group[state.picker.position][state.picker.index] = { ...candidate, eh_capitao: false, eh_reserva_luxo: false };
    state.teamChanged = true;
    recomputeResult();
    const selectedPosition = state.picker.position;
    closePicker();
    exibirResultado(window.ultimaEscalacao, state.clubes);
    adicionarLog(`↻ ${POSITIONS[selectedPosition].short}: ${candidate.apelido || candidate.nome} atualizado manualmente.`, 'info');
  }

  function removePickerPlayer() {
    if (!state.picker || !window.ultimaEscalacao) return;
    const removedPosition = state.picker.position;
    const group = state.picker.kind === 'reserve' ? window.ultimaEscalacao.reservas : window.ultimaEscalacao.titulares;
    (group[removedPosition] || []).splice(state.picker.index, 1);
    state.teamChanged = true;
    recomputeResult();
    closePicker();
    exibirResultado(window.ultimaEscalacao, state.clubes);
    adicionarLog(`↘ ${POSITIONS[removedPosition]?.short || 'Atleta'} removido para revisão.`, 'warning');
  }

  async function loadAvailabilityCandidates() {
    if (!state.data?.team_id) return;
    try {
      const params = new URLSearchParams({
        team_id: state.data.team_id,
        season: state.data.temporada_atual || '',
        round_number: state.data.rodada_atual || ''
      });
      const response = await fetch(`/api/player-availability/candidates?${params}`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Disponibilidade indisponível.');
      state.availability = data.items || [];
      const list = $('availabilityAthletes');
      if (list) list.innerHTML = state.availability.map(item => `<option value="${escapeHtml(item.apelido)}">${escapeHtml(item.clube_nome || '')} · ${escapeHtml(item.status_nome || '')}</option>`).join('');
    } catch (error) {
      const hint = $('availabilityHint');
      if (hint) hint.textContent = error.message;
    }
  }

  function selectedAvailabilityAthlete() {
    const value = ($('availabilityAthleteInput')?.value || '').trim().toLocaleLowerCase();
    if (!value) return null;
    return state.availability.find(item => String(item.atleta_id) === value || String(item.apelido || '').toLocaleLowerCase() === value) || null;
  }

  async function applyAvailability(rule) {
    const athlete = selectedAvailabilityAthlete();
    if (!athlete || !state.data?.team_id) return notify('Escolha um atleta da lista de disponibilidade.', 'warning');
    const hint = $('availabilityHint');
    if (hint) hint.textContent = 'Salvando regra e atualizando cálculos...';
    try {
      const response = await fetch('/api/player-availability', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ team_id: state.data.team_id, season: state.data.temporada_atual, round_number: state.data.rodada_atual, athlete_id: athlete.atleta_id, rule })
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Não foi possível salvar a disponibilidade.');
      state.teamChanged = true;
      if (hint) hint.textContent = `${athlete.apelido} marcado como ${rule === 'poupar' ? 'não joga' : 'joga'}. Recalculando...`;
      await calcularEscalacao();
      await loadAvailabilityCandidates();
    } catch (error) {
      if (hint) hint.textContent = error.message;
      notify(error.message, 'error');
    }
  }

  async function applyAvailabilityForAthlete(athleteId) {
    if (!state.data?.team_id || !athleteId) return;
    const athlete = state.availability.find((item) => String(item.atleta_id) === String(athleteId));
    const label = athlete?.apelido || 'Jogador';
    try {
      const response = await fetch('/api/player-availability', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ team_id: state.data.team_id, season: state.data.temporada_atual, round_number: state.data.rodada_atual, athlete_id: Number(athleteId), rule: 'poupar' })
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Não foi possível salvar a disponibilidade.');
      state.teamChanged = true;
      adicionarLog(`↘ ${label} marcado como não joga. Recalculando a rodada.`, 'warning');
      await calcularEscalacao();
      await loadAvailabilityCandidates();
    } catch (error) {
      notify(error.message, 'error');
    }
  }

  async function aoMudarConfiguracao(fromPriority = false) {
    if (!window.configCarregada) return;
    state.teamChanged = true;
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
    $('escalacaoContent')?.addEventListener('click', (event) => {
      const submitButton = event.target.closest('[data-submit-lineup]');
      if (submitButton) {
        event.preventDefault();
        event.stopPropagation();
        escalarTime();
        return;
      }
      const specialRole = event.target.closest('[data-special-role]');
      if (specialRole) {
        event.preventDefault();
        event.stopPropagation();
        setSpecialRole(specialRole.dataset.specialRole, specialRole);
        return;
      }
      const availabilityButton = event.target.closest('[data-availability-action]');
      if (availabilityButton) {
        event.preventDefault();
        event.stopPropagation();
        applyAvailabilityForAthlete(availabilityButton.dataset.athleteId);
        return;
      }
      const target = event.target.closest('[data-picker-kind]');
      if (target) openPicker(target.dataset.pickerPosition, target.dataset.pickerKind, target.dataset.pickerIndex);
    });
    $('escalacaoContent')?.addEventListener('keydown', (event) => {
      const target = event.target.closest('[data-picker-kind]');
      if (target && (event.key === 'Enter' || event.key === ' ')) {
        event.preventDefault();
        openPicker(target.dataset.pickerPosition, target.dataset.pickerKind, target.dataset.pickerIndex);
      }
    });
    document.querySelectorAll('[data-picker-close]').forEach(element => element.addEventListener('click', closePicker));
    $('removePlayerBtn')?.addEventListener('click', removePickerPlayer);
    ['pickerName', 'pickerClub', 'pickerSort', 'pickerScout'].forEach(id => $(id)?.addEventListener('input', renderPickerResults));
    ['pickerClub', 'pickerSort', 'pickerScout'].forEach(id => $(id)?.addEventListener('change', renderPickerResults));
    document.querySelectorAll('[data-picker-status]').forEach(button => button.addEventListener('click', () => setPickerStatus(button.dataset.pickerStatus)));
    $('markUnavailableBtn')?.addEventListener('click', () => applyAvailability('poupar'));
    $('markAvailableBtn')?.addEventListener('click', () => applyAvailability('cravado'));
    $('availabilityRecalculateBtn')?.addEventListener('click', calcularEscalacao);
    document.addEventListener('keydown', event => { if (event.key === 'Escape') closePicker(); });
  }

  async function init() {
    showLoading('Carregando painel de escalação...');
    try {
      if (!(await verificarStatusModulos())) return;
      await carregarConfiguracoes();
      await loadData();
      await loadAvailabilityCandidates();
      bindEvents();
      adicionarLog('Dados da rodada carregados. Calculando a escalação inicial...', 'info');
      await calcularEscalacao(false);
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
