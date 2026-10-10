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
  const CARTOLA_CAPTAIN_ICON = '/static/img/cartola-capitao.svg';
  const CARTOLA_LUXURY_ICON = '/static/img/cartola-reserva-luxo.svg';

  const state = {
    data: null,
    clubes: {},
    draggedItem: null,
    availability: [],
    selectedAvailabilityId: '',
    picker: null,
    teamChanged: false,
    availabilityBusy: false,
    probablesSource: 'globo',
    currentLineup: null,
    isShowingCurrent: false,
    currentComparison: null,
    idealEscalacao: null
  };
  let pitchResizeObserver = null;
  const pickerDetailCache = new Map();
  const PICKER_POS_IDS = { goleiros: 1, laterais: 2, zagueiros: 3, meias: 4, atacantes: 5, treinadores: 6 };

  window.prioridadesOrdenadas = ['atacantes', 'laterais', 'meias', 'zagueiros', 'goleiros', 'treinadores'];
  window.configCarregada = false;
  window.ultimaEscalacao = null;

  const $ = (id) => document.getElementById(id);
  const page = () => $('escalacaoIdealPage');
  const can = (name) => {
    const element = page();
    if (!element) return false;
    const key = name.replace(/[A-Z]/g, letter => `-${letter.toLowerCase()}`);
    // DOMStringMap usa camelCase (dataset.podeEscalar), enquanto o HTML
    // declara data-pode-escalar. O acesso anterior pelo nome com hífen
    // retornava undefined e deixava todos os controles de envio bloqueados.
    return element.dataset[name] === 'true' || element.getAttribute(`data-${key}`) === 'true';
  };
  const safeNumber = (value) => Number.isFinite(Number(value)) ? Number(value) : 0;
  const money = (value) => `C$ ${safeNumber(value).toFixed(2).replace('.', ',')}`;
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

  function opponentFor(player) {
    const clubId = String(player?.clube_id || '');
    const opponentId = state.data?.adversarios_dict?.[clubId]
      ?? state.data?.adversarios_dict?.[Number(clubId)]
      ?? null;
    if (!opponentId) return null;
    return state.clubes[opponentId] || state.clubes[String(opponentId)] || { id: opponentId };
  }

  function fixtureTeamMarkup(club, active, side) {
    const name = club?.abreviacao || club?.nome || 'Time';
    const shield = club?.escudo_url || club?.escudo || club?.clube_escudo_url || '';
    return `<span class="ideal-fixture-team ${active ? 'is-active' : 'is-opponent'} ${side}" title="${escapeHtml(name)}">${shield ? `<img src="${escapeHtml(shield)}" alt="Escudo de ${escapeHtml(name)}">` : '<i class="fas fa-shield-alt"></i>'}</span>`;
  }

  function fixtureIndicators(player) {
    const opponent = opponentFor(player);
    if (!opponent) return '';
    const own = clubFor(player);
    const ownId = String(player?.clube_id || '');
    const side = state.data?.mando_por_clube?.[ownId] || state.data?.mando_por_clube?.[Number(ownId)] || '';
    const ownIsAway = side === 'fora';
    const home = ownIsAway ? opponent : own;
    const away = ownIsAway ? own : opponent;
    const homeMarkup = fixtureTeamMarkup(home, !ownIsAway, 'home');
    const awayMarkup = fixtureTeamMarkup(away, ownIsAway, 'away');
    return `<span class="ideal-player-fixture-badge" title="${escapeHtml(side === 'fora' ? 'Joga fora' : 'Joga em casa')} contra ${escapeHtml(opponent.nome || opponent.abreviacao || 'adversário')}">${homeMarkup}${awayMarkup}</span>`;
  }

  function pickerClubMatchMarkup(player) {
    if (!player || !opponentFor(player)) return '<span class="ideal-picker-club-empty">Confronto indisponível</span>';
    const own = clubFor(player);
    const opponent = opponentFor(player);
    const ownId = String(player.clube_id || '');
    const side = state.data?.mando_por_clube?.[ownId] || state.data?.mando_por_clube?.[Number(ownId)] || '';
    const ownIsAway = side === 'fora';
    const home = ownIsAway ? opponent : own;
    const away = ownIsAway ? own : opponent;
    const homeName = home.abreviacao || home.nome || 'CASA';
    const awayName = away.abreviacao || away.nome || 'FORA';
    return `<span class="ideal-picker-club-match" title="${escapeHtml(homeName)} em casa contra ${escapeHtml(awayName)} fora"><span class="ideal-picker-club-side"><small>CASA</small>${fixtureTeamMarkup(home, !ownIsAway, 'home')}<b>${escapeHtml(homeName)}</b></span><i>×</i><span class="ideal-picker-club-side"><small>FORA</small>${fixtureTeamMarkup(away, ownIsAway, 'away')}<b>${escapeHtml(awayName)}</b></span></span>`;
  }

  function progressBar(label, percent, kind, title) {
    const safePercent = Math.max(0, Math.min(100, safeNumber(percent)));
    return `<span class="ideal-player-bar ideal-player-bar-${kind}" title="${escapeHtml(title)}" aria-label="${escapeHtml(title)}"><b>${label}</b><span class="ideal-player-bar-track"><span class="ideal-player-bar-fill" style="width:${safePercent.toFixed(0)}%"></span></span></span>`;
  }

  function playerIndicatorValues(player, position) {
    const jogoMap = state.data?.peso_jogo_por_clube || {};
    const sgMap = state.data?.peso_sg_por_clube || {};
    const jogo = safeNumber(jogoMap[String(player?.clube_id)] ?? player?.peso_jogo);
    const sg = safeNumber(sgMap[String(player?.clube_id)] ?? player?.peso_sg);
    const sgPercent = Math.max(0, Math.min(100, sg <= 1 ? sg * 100 : sg));
    const maxJogo = Math.max(1, ...Object.values(jogoMap).map(safeNumber));
    const defense = ['goleiros', 'laterais', 'zagueiros'].includes(position);
    return {
      jogo,
      sg,
      sgPercent,
      defense,
      favoritePercent: jogo > 0 ? Math.min(100, (jogo / maxJogo) * 100) : 0,
    };
  }

  function teamIndicators(player, position) {
    const club = clubFor(player);
    const indicators = playerIndicatorValues(player, position);
    const shield = club.escudo_url || club.escudo || club.clube_escudo_url || player?.clube_escudo_url || '';
    const name = club.abreviacao || player?.clube_abrev || club.nome || player?.clube_nome || '—';
    const ownMarkup = `<span class="ideal-fixture-team ideal-fixture-team-solo is-active" title="${escapeHtml(name)}">${shield ? `<img src="${escapeHtml(shield)}" alt="Escudo de ${escapeHtml(name)}">` : '<i class="fas fa-shield-alt"></i>'}</span>`;
    const fixtureMarkup = opponentFor(player) ? fixtureIndicators(player) : ownMarkup;
    const bars = `${progressBar('F', indicators.favoritePercent, 'favorite', `Favoritismo ${indicators.jogo.toFixed(2)}`)}${indicators.defense ? progressBar('SG', indicators.sgPercent, 'sg', `Saldo de gols ${indicators.sgPercent.toFixed(0)}%`) : ''}`;
    return `<span class="ideal-player-indicators">${fixtureMarkup}<span class="ideal-player-bars">${bars}</span></span>`;
  }

  function avatar(player, className = '') {
    const name = escapeHtml(player?.apelido || 'Jogador');
    const initials = escapeHtml((player?.apelido || '?').slice(0, 2).toUpperCase());
    const playerId = idOf(player);
    const goalie = (state.data?.todos_goleiros || []).find(candidate => idOf(candidate) === playerId);
    const photo = player?.foto_custom || player?.foto || player?.foto_url || goalie?.foto_custom || goalie?.foto || goalie?.foto_url || '';
    return `<div class="ideal-player-avatar ${className}" title="Foto de ${name}">${photo ? `<img src="${escapeHtml(photo)}" alt="${name}" onerror="this.parentElement.innerHTML='${initials}'">` : initials}</div>`;
  }

  function cardHoverDetails(player, position, kind) {
    const name = player?.apelido || player?.nome || 'Atleta';
    const role = kind === 'reserve' ? 'Reserva' : 'Titular';
    const indicators = playerIndicatorValues(player, position);
    const average = safeNumber(player?.media_num ?? player?.media);
    const games = safeNumber(player?.jogos_num ?? player?.jogos);
    const projection = points(player);
    const status = player?.availability_rule === 'cravado'
      ? 'Cravado para jogar'
      : player?.availability_rule === 'poupar'
        ? 'Marcado para não jogar'
        : 'Disponibilidade da rodada';
    const interactionHint = position === 'treinadores'
      ? 'Detalhes do treinador'
      : 'Passe o mouse para manter as ações';
    const favoritismTitle = `Favoritismo do time · ${indicators.jogo.toFixed(2)}`;
    return `
      <div class="ideal-card-hover-detail ideal-card-hover-detail-top">
        <div class="ideal-card-hover-identity">
          ${avatar(player, 'ideal-card-hover-avatar')}
          <span><strong>${escapeHtml(name)}</strong><small>${escapeHtml(POSITIONS[position]?.label || position)} · ${role}</small></span>
        </div>
        <div class="ideal-card-hover-match">${teamIndicators(player, position)}</div>
      </div>
      <div class="ideal-card-hover-stats">
        <span><small>Preço</small><b>${money(price(player))}</b></span>
        <span><small>Projeção</small><b>${projection.toFixed(2)} pts</b></span>
        <span><small>Média</small><b>${average.toFixed(2)}</b></span>
        <span><small>Jogos</small><b>${games.toFixed(0)}</b></span>
      </div>
      <div class="ideal-card-hover-indices">
        <div class="ideal-card-hover-index ideal-card-hover-index-favorite" title="${escapeHtml(favoritismTitle)}">
          <div class="ideal-card-hover-index-head"><small>Favoritismo do time</small><b>${indicators.jogo.toFixed(2)}</b></div>
          <i class="ideal-card-hover-meter"><em style="width:${indicators.favoritePercent.toFixed(0)}%"></em></i>
        </div>
        ${indicators.defense ? `<div class="ideal-card-hover-index ideal-card-hover-index-sg" title="Chance de saldo de gols do perfil de saldo"><div class="ideal-card-hover-index-head"><small>Saldo de gols</small><b>${indicators.sgPercent.toFixed(0)}%</b></div></div>` : ''}
      </div>
      <div class="ideal-card-hover-detail ideal-card-hover-detail-bottom">
        <span class="ideal-card-hover-status"><i class="fas fa-circle"></i>${status}</span>
        <span class="ideal-card-hover-hint">${interactionHint}</span>
      </div>`;
  }

  function cardActionRail(player, position, kind) {
    const playerId = escapeHtml(idOf(player));
    const name = escapeHtml(player?.apelido || player?.nome || 'atleta');
    const captainIcon = `<img class="ideal-cartola-role-icon" src="${CARTOLA_CAPTAIN_ICON}" alt="Ícone capitão">`;
    const luxuryIcon = `<img class="ideal-cartola-role-icon" src="${CARTOLA_LUXURY_ICON}" alt="Ícone reserva de luxo">`;
    const actions = [];
    if (kind === 'starter' && position !== 'treinadores') {
      actions.push(`<button type="button" class="ideal-card-action ideal-card-action-captain" data-special-role="captain" data-athlete-id="${playerId}" title="Definir ${name} como capitão"><span class="ideal-card-action-icon">${captainIcon}</span><span>Capitão</span></button>`);
    }
    if (kind === 'reserve' && !player?.eh_reserva_luxo) {
      actions.push(`<button type="button" class="ideal-card-action ideal-card-action-luxury" data-special-role="luxury" data-athlete-id="${playerId}" title="Definir ${name} como reserva de luxo"><span class="ideal-card-action-icon">${luxuryIcon}</span><span>Reserva de luxo</span><small>entra como melhor reserva</small></button>`);
    }
    if (position !== 'treinadores') {
      actions.push(`<button type="button" class="ideal-card-action ideal-card-action-unavailable" data-availability-action="poupar" data-athlete-id="${playerId}" title="Marcar ${name} como não joga"><span class="ideal-card-action-icon"><i class="fas fa-user-slash"></i></span><span>Não joga</span><small>remove das próximas escolhas</small></button>`);
    }
    const closeButton = `<button type="button" class="ideal-card-actions-close" data-card-hover-close aria-label="Fechar detalhes de ${name}" title="Fechar"><i class="fas fa-xmark"></i></button>`;
    if (position === 'treinadores') {
      return `<div class="ideal-card-actions ideal-card-actions-details-only" aria-label="Detalhes de ${name}">${closeButton}${cardHoverDetails(player, position, kind)}</div>`;
    }
    return `<div class="ideal-card-actions" aria-label="Detalhes e ações de ${name}">${closeButton}${cardHoverDetails(player, position, kind)}<div class="ideal-card-actions-head"><i class="fas fa-sliders"></i><span>Ações rápidas</span></div>${actions.join('')}<div class="ideal-card-hover-foot"><i class="fas fa-hand-pointer"></i><span>Detalhes do atleta e comandos rápidos</span></div></div>`;
  }

  function replaceHintMarkup() {
    return '<span class="ideal-player-replace-hint" aria-hidden="true" title="Clique para trocar"><i class="fas fa-arrows-rotate"></i></span>';
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
      <div class="ideal-stat"><i class="fas fa-wallet"></i><div><span class="ideal-eyebrow">Patrimônio</span><strong>${money(data.patrimonio)}</strong><small>${escapeHtml(data.patrimonio_error || 'para montar o time')}</small></div></div>`;
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
    if (!response.ok || data.error) {
      throw new Error(data.error || 'Não foi possível verificar os módulos.');
    }
    if (data.todos_calculados) return true;
    const names = { goleiro: 'Goleiros', lateral: 'Laterais', zagueiro: 'Zagueiros', meia: 'Meias', atacante: 'Atacantes', treinador: 'Técnicos' };
    const pendingModules = Object.keys(data.status || {}).filter(key => !data.status[key]);
    const pending = pendingModules.map(key => names[key] || key).join(', ');

    if (typeof window.calcularModulosPendentes !== 'function') {
      throw new Error(`Módulos pendentes: ${pending || 'verifique os módulos'}. O motor de cálculo não foi carregado.`);
    }

    adicionarLog(`Módulos pendentes detectados: ${pending || 'nenhum'}. Iniciando cálculo automático...`, 'info');
    await window.calcularModulosPendentes(pendingModules, {
      onProgress: ({ mensagem, concluido, erro }) => {
        if (mensagem) adicionarLog(mensagem, erro ? 'error' : concluido ? 'success' : 'info');
      }
    });

    const statusResponse = await fetch('/api/modulos/status');
    const statusAtualizado = await statusResponse.json();
    if (!statusResponse.ok || !statusAtualizado.todos_calculados) {
      throw new Error('O cálculo terminou, mas ainda existem módulos sem ranking salvo.');
    }
    adicionarLog('Todos os módulos foram calculados. Carregando a escalação ideal...', 'success');
    return true;
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
    const responseData = await response.json().catch(() => ({}));
    if (!response.ok) {
      console.error('[AERO][Config] Falha ao salvar configuração', { status: response.status, response: responseData, payload });
      throw new Error(responseData.error || `Não foi possível salvar as configurações (HTTP ${response.status}).`);
    }
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
    const unique = new Map();
    source.filter(player => idOf(player)).forEach(player => {
      const id = idOf(player);
      const existing = unique.get(id);
      if (!existing) {
        unique.set(id, player);
        return;
      }
      // A lista de goleiros para o hack é propositalmente enxuta. Mesclá-la
      // sem prioridade apagava foto e projeção dos goleiros já ranqueados.
      const photo = existing.foto || existing.foto_url || player.foto || player.foto_url || '';
      unique.set(id, {
        ...player,
        ...existing,
        foto: photo,
        foto_url: existing.foto_url || photo
      });
    });
    return [...unique.values()];
  }

  function playerCard(player, position, index, result) {
    const playerName = escapeHtml(player?.apelido || 'N/A');
    const priceLabel = money(price(player));
    const pointsLabel = `${points(player).toFixed(1)} pts`;
    const badges = player?.eh_capitao ? `<span class="ideal-badge ideal-badge-captain" title="Capitão atual"><img class="ideal-cartola-role-icon" src="${CARTOLA_CAPTAIN_ICON}" alt="Capitão"></span>` : '';
    const isGoalkeeperHack = position === 'goleiros' && Boolean(player?.eh_goleiro_hack);
    const playerChips = isGoalkeeperHack
      ? `<span class="ideal-player-chips"><span title="Preço do jogador: ${priceLabel}">${priceLabel}</span><span class="ideal-goalkeeper-hack-chip" title="Hack de goleiro: não há pontuação prevista para este atleta">Hack</span></span>`
      : `<span class="ideal-player-chips"><span title="Preço do jogador: ${priceLabel}">${priceLabel}</span><span title="Pontuação prevista: ${pointsLabel}">${pointsLabel}</span></span>`;
    const statusMarkup = isGoalkeeperHack ? '' : statusIndicator(player);
    const card = `<div class="ideal-player ideal-player-card${isGoalkeeperHack ? ' is-goalkeeper-hack-target' : ''}" title="Clique para trocar ${playerName}" data-picker-kind="starter" data-picker-position="${position}" data-picker-index="${index}" role="button" tabindex="0">${badges}${replaceHintMarkup()}${cardActionRail(player, position, 'starter')}<div class="ideal-player-visual">${avatar(player)}${teamIndicators(player, position)}</div><span class="ideal-player-name" title="Jogador: ${playerName}">${playerName}</span>${playerChips}${statusMarkup}</div>`;
    return isGoalkeeperHack ? `<div class="ideal-goalkeeper-hack-slot" title="Este goleiro não está como provável na fonte selecionada; o goleiro que entra está nas reservas.">${card}<span class="ideal-goalkeeper-hack-label">Hack</span></div>` : card;
  }

  function statusIndicator(player) {
    const status = Number(player?.status_id);
    const cravado = player?.availability_rule === 'cravado';
    let indicator = { className: 'is-unlikely', symbol: '×', label: 'Improvável' };
    if (cravado || status === 7) indicator = { className: 'is-probable', symbol: '✓', label: 'Provável' };
    else if (status === 2) indicator = { className: 'is-doubt', symbol: '?', label: 'Dúvida' };
    else if (status === 6) indicator = { className: 'is-null', symbol: '×', label: 'Nulo' };
    else if (status === 5) indicator.label = 'Suspenso';
    else if (!Number.isFinite(status) || status === 0) indicator = { className: 'is-unknown', symbol: '—', label: 'Status não informado pela fonte selecionada' };
    const label = escapeHtml(indicator.label);
    return `<span class="ideal-player-status ${indicator.className}" title="${label}" aria-label="${label}">${indicator.symbol}</span>`;
  }

  function emptySlot(position, index) {
    return `<button type="button" class="ideal-player ideal-player-empty" title="Escolher jogador" data-picker-kind="starter" data-picker-position="${position}" data-picker-index="${index}"><span class="ideal-empty-plus"><i class="fas fa-plus"></i></span><span class="ideal-player-name">Escolher</span><span class="ideal-player-action">adicionar</span></button>`;
  }

  function playerSlots(result, position) {
    const count = FORMATION_COUNTS[$('formationSelect')?.value] || FORMATION_COUNTS['4-3-3'];
    const players = (result.titulares?.[position] || []).filter(Boolean);
    const total = Math.max(count[position] || 0, players.length);
    return Array.from({ length: total }, (_, index) => playerSlot(result, position, index)).join('');
  }

  function playerSlot(result, position, index) {
    const players = (result.titulares?.[position] || []).filter(Boolean);
    return players[index] ? playerCard(players[index], position, index, result) : emptySlot(position, index);
  }

  function defenseLane(result, position, index, label) {
    const count = FORMATION_COUNTS[$('formationSelect')?.value] || FORMATION_COUNTS['4-3-3'];
    const player = result.titulares?.[position]?.[index];
    if (position === 'laterais' && !(count.laterais > index) && !player) return '';
    const lateralClass = position === 'laterais' ? ' is-lateral' : '';
    return `<div class="ideal-field-defense-lane${lateralClass}"><div class="ideal-field-pos">${label}</div><div class="ideal-field-players">${playerSlot(result, position, index)}</div></div>`;
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
    const slots = [];
    if (count.laterais > 0) slots.push(defenseLane(result, 'laterais', 0, 'Lateral esquerdo'));
    for (let index = 0; index < count.zagueiros; index += 1) {
      slots.push(defenseLane(result, 'zagueiros', index, 'Zagueiro'));
    }
    if (count.laterais > 1) slots.push(defenseLane(result, 'laterais', 1, 'Lateral direito'));
    if (!slots.length) return '';
    return `<div class="ideal-field-row ideal-field-row-defense"><div class="ideal-field-defense-layout"><div class="ideal-field-defense-line" style="--defender-count:${slots.length}">${slots.join('')}</div></div></div>`;
  }

  function renderField(result) {
    const formation = $('formationSelect')?.value || '4-3-3';
    const counts = FORMATION_COUNTS[formation] || FORMATION_COUNTS['4-3-3'];
    const denseFormation = Math.max(counts.meias, counts.atacantes, counts.zagueiros + counts.laterais) >= 5;
    return '<div class="ideal-field ideal-field--' + formation.replace('-', '') + '" role="group" aria-label="Escalação no campo, formação ' + escapeHtml(formation) + '">' +
      '<div class="bg" aria-hidden="true"></div><div class="vignette" aria-hidden="true"></div>' +
      '<div class="ai-fx" aria-hidden="true"><div class="ai-grid"></div><div class="ai-scan"></div><div class="ai-radar"></div><div class="ai-dots"></div></div>' +
      '<svg class="pass-svg" viewBox="0 0 1000 1000" preserveAspectRatio="none" aria-hidden="true"><defs><filter id="idealPassGlow"><feGaussianBlur stdDeviation="2" result="b"></feGaussianBlur><feMerge><feMergeNode in="b"></feMergeNode><feMergeNode in="SourceGraphic"></feMergeNode></feMerge></filter></defs><line class="pl" x1="0" y1="0" x2="0" y2="0"></line><line class="pl" x1="0" y1="0" x2="0" y2="0"></line><line class="pl" x1="0" y1="0" x2="0" y2="0"></line></svg>' +
      '<div class="ideal-field-tag"><span>titulares</span><span>' + escapeHtml(formation) + '</span></div>' +
      '<div class="ideal-field-canvas' + (denseFormation ? ' is-dense-formation' : '') + '"><div class="ideal-field-rows">' +
        '<div class="ideal-field-row ideal-field-row-attack">' + fieldGroup(result, 'atacantes') + '</div>' +
        '<div class="ideal-field-row ideal-field-row-midfield">' + fieldGroup(result, 'meias') + '</div>' +
        defenseLayout(result) +
        '<div class="ideal-field-row ideal-field-row-goalkeeper">' + fieldGroup(result, 'goleiros') + '</div>' +
      '</div><div class="ideal-field-coach">' + fieldGroup(result, 'treinadores', 'ideal-field-group-coach') + '</div>' +
      fieldSubmitButton() + '</div></div>';
  }

  function syncPitchScale() {
    const field = $('escalacaoContent')?.querySelector('.ideal-field');
    if (field) field.style.setProperty('--ideal-pitch-scale', String(field.clientWidth / 720));
  }

  function observePitchSize() {
    pitchResizeObserver?.disconnect();
    const field = $('escalacaoContent')?.querySelector('.ideal-field');
    if (!field) return;
    syncPitchScale();
    if (typeof ResizeObserver === 'function') {
      pitchResizeObserver = new ResizeObserver(syncPitchScale);
      pitchResizeObserver.observe(field);
    }
  }

  function renderBench(result) {
    const positions = POSITION_ORDER.filter(position => position !== 'treinadores');
    const groups = positions.map(position => {
      const players = (result.reservas?.[position] || []).filter(Boolean);
      const player = players[0];
      const reserveName = escapeHtml(player?.apelido || 'N/A');
      const reservePrice = player ? money(price(player)) : '';
      const reservePoints = player ? `${points(player).toFixed(1)} pts` : '';
      const card = player ? `<div class="ideal-bench-player ideal-player-card" title="Clique para trocar a reserva ${reserveName}" data-picker-kind="reserve" data-picker-position="${position}" data-picker-index="0" role="button" tabindex="0">${player.eh_reserva_luxo ? `<span class="ideal-badge ideal-badge-luxury" title="Reserva de luxo atual"><img class="ideal-cartola-role-icon" src="${CARTOLA_LUXURY_ICON}" alt="Reserva de luxo"></span>` : ''}${replaceHintMarkup()}${cardActionRail(player, position, 'reserve')}${avatar(player)}<span class="ideal-bench-copy"><span class="ideal-player-name" title="Jogador: ${reserveName}">${reserveName}</span><span class="ideal-player-chips"><span title="Preço da reserva: ${reservePrice}">${reservePrice}</span><span title="Pontuação prevista da reserva: ${reservePoints}">${reservePoints}</span></span></span><span class="ideal-bench-signals">${teamIndicators(player, position)}</span>${statusIndicator(player)}</div>` : `<button type="button" class="ideal-bench-player ideal-bench-empty" title="Adicionar reserva" data-picker-kind="reserve" data-picker-position="${position}" data-picker-index="0"><i class="fas fa-plus"></i><span>Adicionar reserva</span></button>`;
      return `<div class="ideal-bench-group"><div class="ideal-bench-label">${POSITIONS[position].label}</div>${card}</div>`;
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
    // A projeção do capitão usa o fator oficial de 1,5.
    const pontuacaoBase = POSITION_ORDER.flatMap(position => result.titulares[position] || []).reduce((total, player) => total + points(player), 0);
    result.pontuacaoTotal = pontuacaoBase + (captain ? points(captain) * 0.5 : 0);
  }

  function setSpecialRole(role, target) {
    if (!window.ultimaEscalacao) return;
    if (!target) return;
    const card = target.closest('[data-picker-kind]');
    const groupName = role === 'luxury' ? 'reservas' : 'titulares';
    const group = window.ultimaEscalacao[groupName] || {};
    const position = card?.dataset.pickerPosition || target.dataset.pickerPosition || '';
    if (position === 'treinadores' && (role === 'captain' || role === 'unavailable')) {
      return notify('Treinadores não podem ser capitães nem marcados como não jogadores.', 'warning');
    }
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
    console.debug('[AERO][Escalação] alteração manual de papel especial', {
      papel: role,
      atletaId: playerId,
      atleta: player.apelido || player.nome || 'atleta',
      timeAlterado: state.teamChanged
    });
    if (state.isShowingCurrent) {
      result.titulares ||= {};
      result.reservas ||= {};
      result.custoTotal = POSITION_ORDER.flatMap(position => result.titulares[position] || []).reduce((total, player) => total + price(player), 0);
      result.pontuacaoTotal = POSITION_ORDER.flatMap(position => result.titulares[position] || []).reduce((total, player) => total + points(player) * (player.eh_capitao ? 1.5 : 1), 0);
    } else {
      recomputeResult();
    }
    exibirResultado(window.ultimaEscalacao, state.clubes);
  }

  function getSubmissionDiagnostics(result) {
    const count = FORMATION_COUNTS[$('formationSelect')?.value] || FORMATION_COUNTS['4-3-3'];
    const starters = result?.titulares || {};
    const expected = Object.values(count).reduce((total, value) => total + value, 0) + 1;
    const byPosition = {};
    const players = POSITION_ORDER.flatMap(position => {
      const list = Array.isArray(starters[position]) ? starters[position].filter(Boolean) : [];
      byPosition[position] = list.length;
      return list;
    });
    const invalidIds = players.filter(player => !idOf(player)).map(player => player?.apelido || player?.nome || 'sem nome');
    return {
      permission: can('podeEscalar'),
      formation: $('formationSelect')?.value || '4-3-3',
      expected,
      actual: players.length,
      validIds: players.length - invalidIds.length,
      invalidIds,
      byPosition,
      teamChanged: state.teamChanged,
      complete: Boolean(result) && players.length === expected && invalidIds.length === 0
    };
  }

  function refreshSubmitButton() {
    const buttons = [$('escalarBtn'), $('fieldSubmitBtn')].filter(Boolean);
    const diagnostics = getSubmissionDiagnostics(window.ultimaEscalacao);
    console.debug('[AERO][Escalação] estado do envio', {
      ...diagnostics,
      botoes: buttons.map(button => ({ id: button.id, disabled: button.disabled, classe: button.className }))
    });
    if (!buttons.length || !diagnostics.permission) {
      console.warn('[AERO][Escalação] envio bloqueado por permissão ou botão ausente', diagnostics);
      return;
    }
    const canSend = diagnostics.complete && !state.isShowingCurrent;
    const label = state.teamChanged
      ? '<i class="fas fa-paper-plane"></i> Enviar time alterado'
      : '<i class="fas fa-paper-plane"></i> Enviar escalação';
    buttons.forEach((button) => {
      button.innerHTML = state.isShowingCurrent
        ? '<i class="fas fa-check"></i><span>Escalação atual</span>'
        : button.id === 'fieldSubmitBtn'
        ? (state.teamChanged ? '<i class="fas fa-paper-plane"></i><span>Enviar time alterado</span>' : '<i class="fas fa-paper-plane"></i><span>Enviar escalação</span>')
        : label;
      button.disabled = !canSend;
      button.title = state.isShowingCurrent ? 'Esta é a escalação já salva no Cartola' : canSend ? 'Enviar esta escalação para o Cartola FC' : 'Complete todas as posições antes de enviar';
    });
    console.debug('[AERO][Escalação] botões após atualização', buttons.map(button => ({ id: button.id, disabled: button.disabled, texto: button.textContent.trim() })));
  }

  function exibirResultado(result, clubesDict = {}) {
    state.clubes = clubesDict || state.clubes;
    const panel = $('resultadoPanel');
    const content = $('escalacaoContent');
    if (!panel || !content) return;
    recomputeResult();
    const patrimonio = safeNumber(result.patrimonio || state.data?.patrimonio);
    const balance = patrimonio - safeNumber(result.custoTotal);
    const currentNotice = state.isShowingCurrent ? `<div class="ideal-lineup-state ${state.currentComparison?.matches ? 'is-matching' : 'is-different'}"><strong>${state.currentComparison?.matches ? 'Sua escalação atual corresponde ao ideal calculado.' : 'Sua escalação atual está diferente do ideal calculado.'}</strong><span>${state.currentComparison?.matches ? 'Você já está com o time recomendado nesta rodada.' : 'O campo mostra seu time salvo no Cartola. Recalcule para conferir e enviar uma nova escalação ideal.'}</span></div>` : '';
    content.innerHTML = `${currentNotice}<div class="ideal-metrics"><section class="ideal-financial-card" aria-label="Resumo financeiro da escalação"><div class="ideal-financial-item patrimonio"><span>Patrimônio</span><strong>${money(patrimonio)}</strong></div><i aria-hidden="true">|</i><div class="ideal-financial-item cost"><span>Preço do time</span><strong>${money(result.custoTotal)}</strong></div><i aria-hidden="true">|</i><div class="ideal-financial-item balance"><span>Saldo restante</span><strong>${money(balance)}</strong></div></section><section class="ideal-metric points" title="Estimativa com base nas projeções dos titulares e do treinador"><span>${state.isShowingCurrent ? 'Pontuação da escalação atual (estimada)' : 'Pontuação projetada'}</span><strong>${safeNumber(result.pontuacaoTotal).toFixed(2)} pts</strong><em>${state.isShowingCurrent ? 'Estimativa com as médias disponíveis' : 'Estimativa da escalação'}</em></section></div><div class="ideal-field-layout">${renderField(result)}${renderBench(result)}</div>`;
    const title = document.querySelector('.ideal-result-title');
    if (title) title.innerHTML = `<i class="fas fa-futbol"></i> ${state.isShowingCurrent ? 'Escalação atual do Cartola' : 'Escalação ideal'}`;
    const meta = document.querySelector('.ideal-result-meta');
    if (meta) meta.textContent = state.isShowingCurrent ? `Time salvo na rodada ${state.data?.rodada_atual}.` : 'Revise o campo, o saldo e os sinais antes de enviar.';
    panel.classList.remove('hidden');
    observePitchSize();
    refreshSubmitButton();
  }

  function makeCurrentLineup(data) {
    const current = data.current_lineup;
    const positions = { 1: 'goleiros', 2: 'laterais', 3: 'zagueiros', 4: 'meias', 5: 'atacantes', 6: 'treinadores' };
    const rankingPosition = { goleiros: 'goleiro', laterais: 'lateral', zagueiros: 'zagueiro', meias: 'meia', atacantes: 'atacante', treinadores: 'treinador' };
    const lineup = { titulares: {}, reservas: {}, custoTotal: 0, pontuacaoTotal: 0, patrimonio: data.patrimonio, manualCaptainId: String(current?.captain_id || ''), formation_id: Number(current?.formation_id || 0), luxuryReserveId: String(current?.luxury_reserve_id || '') };
    POSITION_ORDER.forEach(position => { lineup.titulares[position] = []; lineup.reservas[position] = []; });
    const starterIds = new Set((current?.athlete_ids || []).map(String));
    const reserveIds = new Set(Object.values(current?.reserve_ids || {}).map(String));
    if (current?.luxury_reserve_id) reserveIds.add(String(current.luxury_reserve_id));
    (current?.players || []).forEach(player => {
      const position = positions[Number(player.posicao_id)];
      if (!position) return;
      const playerId = String(player.atleta_id);
      const positionRanking = data.rankings_por_posicao?.[rankingPosition[position]] || [];
      const projectedPlayer = positionRanking.find(candidate => idOf(candidate) === playerId);
      const displayPlayer = projectedPlayer
        ? { ...player, ...projectedPlayer, status_id: player.status_id, probables_source: player.probables_source }
        : { ...player, pontuacao_total: safeNumber(player.media), projection_missing: true };
      if (starterIds.has(playerId)) {
        lineup.titulares[position].push({ ...displayPlayer, eh_capitao: playerId === String(current.captain_id || '') });
      } else if (reserveIds.has(playerId)) {
        lineup.reservas[position].push({
          ...displayPlayer,
          eh_reserva_luxo: playerId === String(current.luxury_reserve_id || '')
        });
      }
    });
    const selectedGoalkeeper = lineup.titulares.goleiros[0];
    const enteringGoalkeeper = lineup.reservas.goleiros[0];
    // O Hack de goleiro depende da fonte de prováveis ativa: qualquer status
    // diferente de provável (incluindo dúvida, nulo e status ausente) indica
    // que o titular escolhido não deve entrar; o reserva fica como opção real.
    if (selectedGoalkeeper && enteringGoalkeeper && Number(selectedGoalkeeper.status_id) !== 7) {
      selectedGoalkeeper.eh_goleiro_hack = true;
    }
    lineup.custoTotal = POSITION_ORDER.flatMap(position => lineup.titulares[position]).reduce((sum, player) => sum + price(player), 0);
    lineup.pontuacaoTotal = POSITION_ORDER.flatMap(position => lineup.titulares[position]).reduce((sum, player) => sum + points(player) * (player.eh_capitao ? 1.5 : 1), 0);
    if (current?.formation_id) {
      const formation = ({ 3: '4-3-3', 1: '4-4-2', 2: '3-5-2', 4: '3-4-3', 5: '4-5-1', 7: '5-3-2', 6: '5-4-1' })[Number(current.formation_id)];
      if (formation && $('formationSelect')) $('formationSelect').value = formation;
    }
    return lineup;
  }

  function compareLineups(current, ideal) {
    if (!current || !ideal) return null;
    const idsByPosition = lineup => POSITION_ORDER.map(position => `${position}:${(lineup.titulares?.[position] || []).map(idOf).sort().join(',')}|r:${(lineup.reservas?.[position] || []).map(idOf).sort().join(',')}`).join('|');
    const captainId = lineup => POSITION_ORDER.flatMap(position => lineup.titulares?.[position] || []).find(player => player.eh_capitao)?.atleta_id;
    const luxuryReserveId = lineup => String(lineup.luxuryReserveId || POSITION_ORDER.flatMap(position => lineup.reservas?.[position] || []).find(player => player.eh_reserva_luxo)?.atleta_id || '');
    return {
      matches: idsByPosition(current) === idsByPosition(ideal)
        && String(captainId(current) || '') === String(captainId(ideal) || '')
        && luxuryReserveId(current) === luxuryReserveId(ideal)
        && Number(current.formation_id || 0) === Number(ideal.formation_id || 0)
    };
  }

  async function calcularEscalacao(recarregarDados = true, options = {}) {
    const button = $('calcularBtn');
    if (button) button.disabled = true;
    if (!options.background) {
      state.isShowingCurrent = false;
      button?.classList.remove('ideal-needs-recalculation');
      limparConsole();
      $('resultadoPanel')?.classList.add('hidden');
      showLoading('Calculando escalação ideal...');
    }
    try {
      const data = recarregarDados || !state.data ? await loadData() : state.data;
      const escalador = new window.EscalacaoIdeal({
        rodada_atual: data.rodada_atual,
        probables_source: data.probables_source || 'globo',
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
      escalador.setLogCallback(message => { if (!options.background) adicionarLog(message, 'log'); });
      const ideal = await escalador.calcular();
      state.idealEscalacao = ideal;
      if (options.background) return ideal;
      window.ultimaEscalacao = ideal;
      exibirResultado(ideal, data.clubes_dict);
      adicionarLog('✓ Escalação ideal pronta para revisão ou envio.', 'success');
    } catch (error) {
      if (!options.background) window.ultimaEscalacao = null;
      $('escalarBtn').disabled = true;
      if (!options.background) {
        adicionarLog(`ERRO: ${error.message}`, 'error');
        notify(error.message, 'error');
      }
      return null;
    } finally {
      if (!options.background) hideLoading();
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
    if (player?.availability_rule === 'cravado' || player?.rule === 'cravado') return 'Cravado';
    if (player?.probables_source === 'provaveisdocartola') {
      const sourceStatus = String(player?.source_status || '').toLocaleLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');
      const sourceLabels = { provavel: 'Provável', duvida: 'Dúvida', improvavel: 'Improvável', suspenso: 'Suspenso', lesionado: 'Lesionado', fora: 'Fora', nulo: 'Nulo' };
      if (sourceLabels[sourceStatus]) return sourceLabels[sourceStatus];
      return ({ 0: 'Sem status na fonte externa', 2: 'Dúvida', 3: 'Improvável', 5: 'Suspenso', 6: 'Nulo', 7: 'Provável' })[Number(player?.status_id)] || 'Sem status na fonte externa';
    }
    if (player?.status_nome) return player.status_nome;
    return ({ 2: 'Dúvida', 3: 'Improvável', 5: 'Suspenso', 6: 'Nulo', 7: 'Provável' })[Number(player?.status_id)] || 'Status indisponível';
  }

  function pickerStatusCategory(player) {
    if (player?.probables_source === 'provaveisdocartola') {
      const raw = String(player?.source_status || '').toLocaleLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');
      const aliases = { provavel: 'provaveis', duvida: 'duvidas', improvavel: 'improvaveis', suspenso: 'suspensos', lesionado: 'lesionados', fora: 'fora', nulo: 'nulos' };
      if (aliases[raw]) return aliases[raw];
    }
    const status = Number(player?.status_id);
    return ({ 7: 'provaveis', 2: 'duvidas', 3: 'improvaveis', 5: 'contundidos', 6: 'nulos' })[status] || 'sem_status';
  }

  function renderPickerStatusOptions() {
    const target = $('pickerStatusOptions');
    if (!target) return;
    const statuses = [['provaveis','Prováveis'],['duvidas','Dúvidas'],['lesionados','Lesionados'],['suspensos','Suspensos'],['nulos','Nulos']];
    const options = [['todos','Todos'], ...statuses];
    target.innerHTML = options.map(([key,label]) => `<button type="button" data-picker-status="${key}" aria-pressed="${(state.picker?.statusFilter || 'todos') === key}">${label}</button>`).join('');
    target.querySelectorAll('[data-picker-status]').forEach(button => {
      button.classList.toggle('is-active', button.getAttribute('aria-pressed') === 'true');
      button.addEventListener('click', () => setPickerStatus(button.dataset.pickerStatus));
    });
    const cravados = $('pickerStatusCravados');
    if (cravados) {
      const active = (state.picker?.statusFilter || 'todos') === 'cravados';
      cravados.classList.toggle('is-active', active);
      cravados.setAttribute('aria-pressed', String(active));
    }
  }

  const PICKER_SCOUT_LABELS = { A:'Assistências', CA:'Cartões amarelos', CV:'Cartões vermelhos', DE:'Defesas', DS:'Desarmes', FC:'Faltas cometidas', FD:'Faltas sofridas', FF:'Finalizações para fora', FS:'Finalizações no gol', G:'Gols', GC:'Gols contra', I:'Impedimentos', PC:'Pênaltis cometidos', PP:'Pênaltis perdidos', PS:'Pênaltis sofridos', SG:'Saldo de gols', V:'Vitórias', DP:'Defesas de pênalti', FT:'Finalizações na trave' };

  function renderPickerDetail(player, payload) {
    const matches = Array.isArray(payload?.ultimas_pontuacoes) ? payload.ultimas_pontuacoes : [];
    const played = matches.filter(match => match.entrou_em_campo);
    const totals = {};
    played.forEach(match => Object.entries(match.scouts || {}).forEach(([key,value]) => { totals[key.toUpperCase()] = (totals[key.toUpperCase()] || 0) + safeNumber(value); }));
    const scoutRows = Object.entries(totals).filter(([,value]) => value !== 0).sort((a,b) => Math.abs(b[1]) - Math.abs(a[1]));
    const roundNow = Number(payload?.filtros?.rodada || state.data?.rodada_atual || 1);
    const fromRound = Math.max(1, roundNow - 10);
    const pointsByRound = new Map(played.map(match => [Number(match.rodada), safeNumber(match.pontuacao)]));
    const scores = Array.from({length: Math.max(1, roundNow - fromRound)}, (_,index) => fromRound + index);
    const maxAbs = Math.max(1, ...scores.map(round => Math.abs(pointsByRound.get(round) || 0)));
    const chart = scores.map(round => {
      const score = pointsByRound.get(round) || 0;
      const height = score === 0 ? 3 : Math.max(5, Math.round(Math.abs(score) / maxAbs * 34));
      const tone = score < 0 ? 'is-negative' : score > 0 ? 'is-positive' : 'is-zero';
      return `<div class="ideal-picker-chart-column" title="Rodada ${round}: ${pointsByRound.has(round) ? score.toFixed(2) + ' pts' : 'não atuou'}"><span class="ideal-picker-chart-score">${score.toFixed(2)}</span><i class="${tone}" style="--bar-height:${height}px"></i><small>R${round}</small></div>`;
    }).join('');
    const summary = payload?.resumo || {};
    const mando = Object.fromEntries((summary.mando || []).map(item => [item.tipo, item.media]));
    const scouts = scoutRows.length ? scoutRows.map(([key,total]) => `<div class="ideal-picker-scout-row"><b>${escapeHtml(PICKER_SCOUT_LABELS[key] || key)}</b><span>${(total / Math.max(1,played.length)).toFixed(2)}</span><small>Total ${total > 0 ? '+' : ''}${total.toFixed(0)} · ${played.length} jogo(s)</small></div>`).join('') : '<p class="ideal-picker-detail-muted">Sem scouts registrados nas partidas disputadas.</p>';
    const compare = new URL('/cruzamento-scouts/', window.location.origin);
    compare.searchParams.set('posicao_id', String(player.posicao_id || PICKER_POS_IDS[state.picker?.position] || ''));
    compare.searchParams.set('atleta_id', String(idOf(player)));
    return `<section class="ideal-picker-inline-detail"><div class="ideal-picker-detail-head"><strong>Resumo do jogador</strong><a class="ideal-btn ideal-btn-quiet" href="${escapeHtml(compare.pathname + compare.search)}"><i class="fas fa-scale-balanced"></i> Comparar scouts</a></div><div class="ideal-picker-detail-metrics"><span><small>Média geral</small><b>${safeNumber(summary.media).toFixed(2)}</b></span><span><small>Média em casa</small><b>${safeNumber(mando.casa).toFixed(2)}</b></span><span><small>Média fora</small><b>${safeNumber(mando.fora).toFixed(2)}</b></span><span><small>Jogos</small><b>${safeNumber(summary.jogos || played.length)}</b></span><span><small>Maior</small><b>${safeNumber(summary.maior_pontuacao).toFixed(2)}</b></span><span><small>Total de pontos</small><b>${safeNumber(summary.pontos_total).toFixed(2)}</b></span></div><div class="ideal-picker-detail-section"><b>Pontuações por rodada</b><div class="ideal-picker-score-chart">${chart}</div></div><div class="ideal-picker-detail-section"><b>Scouts: média por jogo <small>· total no período abaixo</small></b><div class="ideal-picker-scout-grid">${scouts}</div></div></section>`;
  }

  async function togglePickerDetail(button, player) {
    const panel = button.closest('.ideal-picker-player-entry')?.querySelector('.ideal-picker-inline-slot');
    if (!panel) return;
    const expanded = button.getAttribute('aria-expanded') === 'true';
    button.setAttribute('aria-expanded', String(!expanded));
    button.querySelector('i')?.classList.toggle('fa-chevron-down', expanded);
    button.querySelector('i')?.classList.toggle('fa-chevron-up', !expanded);
    if (expanded) { panel.hidden = true; return; }
    panel.hidden = false;
    const athleteId = idOf(player);
    if (pickerDetailCache.has(athleteId)) { panel.innerHTML = renderPickerDetail(player, pickerDetailCache.get(athleteId)); return; }
    panel.innerHTML = '<div class="ideal-picker-detail-loading">Carregando histórico e scouts…</div>';
    try {
      const positionId = player.posicao_id || PICKER_POS_IDS[state.picker?.position];
      const response = await fetch(`/cruzamento-scouts/api/cruzar?atleta_id=${encodeURIComponent(athleteId)}&posicao_id=${encodeURIComponent(positionId)}`, { credentials: 'same-origin' });
      if (!response.ok) throw new Error('Não foi possível carregar o histórico deste atleta.');
      const payload = await response.json();
      pickerDetailCache.set(athleteId, payload);
      if (panel.isConnected && !panel.hidden) panel.innerHTML = renderPickerDetail(player, payload);
    } catch (error) { panel.innerHTML = `<div class="ideal-picker-detail-muted">${escapeHtml(error.message || 'Falha ao carregar detalhes.')}</div>`; }
  }

  function pickerPool() {
    return candidatesFor(state.picker.position, currentPickerPlayer());
  }

  function renderPickerFilters(pool) {
    const clubOptions = $('pickerClubOptions');
    const scout = $('pickerScout');
    if (clubOptions) renderPickerClubOptions(pool);
    if (scout) {
      const keys = new Set();
      pool.forEach(player => Object.keys(player || {}).forEach(key => { if (/^(media|avg|scout)_/.test(key)) keys.add(key.replace(/^(media|avg|scout)_/, '')); }));
      ['ds', 'fs', 'ff', 'fd', 'g', 'a', 'sg', 'de'].forEach(key => keys.add(key));
      scout.innerHTML = '<option value="">Escolha o scout</option>' + [...keys].sort().map(key => `<option value="${escapeHtml(key)}">${escapeHtml(key.toUpperCase())}</option>`).join('');
    }
    updatePickerSortControls();
  }

  function renderPickerClubOptions(pool = pickerPool()) {
    const target = $('pickerClubOptions');
    if (!target) return;
    const fixtures = state.data?.confrontos_rodada || [];
    const selected = new Set((state.picker?.clubIds || []).map(String));
    const teamButton = (team, side) => {
      const id = String(team?.id || '');
      const name = team?.abreviacao || team?.nome || 'Time';
      const shield = team?.escudo_url || '';
      return `<button type="button" class="ideal-picker-match-team ${selected.has(id) ? 'is-selected' : ''}" data-picker-club="${escapeHtml(id)}" aria-pressed="${selected.has(id)}" title="${selected.has(id) ? 'Remover' : 'Adicionar'} filtro do ${side.toLowerCase()}: ${escapeHtml(name)}">${shield ? `<img src="${escapeHtml(shield)}" alt="Escudo de ${escapeHtml(name)}">` : '<i class="fas fa-shield-alt"></i>'}<b>${escapeHtml(name)}</b></button>`;
    };
    const cards = fixtures.map(fixture => {
      const home = fixture.casa || {};
      const away = fixture.visitante || {};
      const side = fixture.favoritismo_lado || 'equilibrado';
      const favoritism = Math.max(0, Math.min(50, Number(fixture.favoritismo_bar_percent) || 0));
      const valid = fixture.valida !== false;
      const scoreHome = Number(home.favoritismo) || 0;
      const scoreAway = Number(away.favoritismo) || 0;
      const sgHome = Math.max(0, Math.min(100, Number(home.saldo_percent) || 0));
      const sgAway = Math.max(0, Math.min(100, Number(away.saldo_percent) || 0));
      const status = valid ? '' : '<span class="ideal-picker-invalid-badge"><i class="fas fa-triangle-exclamation"></i> Confronto inválido · selecionável</span>';
      return `<article class="ideal-picker-match-card${valid ? '' : ' is-invalid'}" aria-label="${escapeHtml(home.nome || '')} contra ${escapeHtml(away.nome || '')}"><div class="ideal-picker-matchup">${teamButton(home, 'CASA')}<span class="ideal-picker-match-vs">×</span>${teamButton(away, 'FORA')}</div>${status}<div class="ideal-picker-favoritism"><div class="ideal-picker-favoritism-heading"><b>Favoritismo do confronto</b><span>${side === 'casa' ? 'Casa favorita' : side === 'visitante' ? 'Fora favorito' : 'Equilibrado'}</span></div><div class="ideal-picker-favoritism-meter is-${side}" style="--favoritismo-width:${favoritism}%"><i></i></div><div class="ideal-picker-favoritism-values"><span>Casa <strong>${scoreHome.toFixed(2)}</strong></span><span>Fora <strong>${scoreAway.toFixed(2)}</strong></span></div></div><div class="ideal-picker-sg-bars"><div title="Chance de SG do mandante"><span>SG casa</span><b>${sgHome.toFixed(0)}%</b><i><em style="width:${sgHome}%"></em></i></div><div title="Chance de SG do visitante"><span>SG fora</span><b>${sgAway.toFixed(0)}%</b><i><em style="width:${sgAway}%"></em></i></div></div></article>`;
    }).join('');
    target.innerHTML = cards || '<span class="ideal-picker-club-empty">Nenhum confronto disponível nesta rodada.</span>';
    target.querySelectorAll('[data-picker-club]').forEach(button => button.addEventListener('click', () => {
      const id = String(button.dataset.pickerClub || '');
      const next = new Set(state.picker.clubIds || []);
      if (next.has(id)) next.delete(id); else next.add(id);
      state.picker.clubIds = [...next];
      renderPickerClubOptions(pool);
      renderPickerResults();
    }));
    $('pickerAllClubs')?.classList.toggle('is-active', selected.size === 0);
    $('pickerAllClubs')?.setAttribute('aria-pressed', String(selected.size === 0));
    if ($('pickerAllClubs')) $('pickerAllClubs').onclick = () => {
      state.picker.clubIds = [];
      renderPickerClubOptions(pool);
      renderPickerResults();
    };
  }

  function updatePickerSortControls() {
    const sort = state.picker?.sort || 'expected';
    document.querySelectorAll('[data-picker-sort]').forEach(button => {
      const active = button.dataset.pickerSort === sort;
      button.classList.toggle('is-active', active);
      button.setAttribute('aria-pressed', String(active));
    });
    const scoutWrap = $('pickerScoutWrap');
    if (scoutWrap) scoutWrap.hidden = sort !== 'scout';
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
    const clubIds = new Set((state.picker.clubIds || []).map(String));
    const sort = state.picker.sort || 'expected';
    const scout = $('pickerScout')?.value || '';
    const statusFilter = state.picker.statusFilter || 'provaveis';
    const starterPool = window.ultimaEscalacao?.titulares?.[state.picker.position] || [];
    const reserveLimit = state.picker.kind === 'reserve' && starterPool.length ? Math.min(...starterPool.map(price)) : Infinity;
    const candidates = pickerPool().filter(player => {
      const category = pickerStatusCategory(player);
      if (player.availability_rule === 'poupar') return false;
      if (statusFilter === 'provaveis' && category !== 'provaveis' && player.availability_rule !== 'cravado') return false;
      if (statusFilter === 'cravados' && player.availability_rule !== 'cravado') return false;
      if (!['todos','provaveis','cravados'].includes(statusFilter) && category !== statusFilter) return false;
      if (clubIds.size && !clubIds.has(String(player.clube_id))) return false;
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
    if (rule) {
      const instruction = state.picker.kind === 'reserve'
        ? `Reserva: preço abaixo de ${reserveLimit === Infinity ? '—' : money(reserveLimit)} do titular mais barato.`
        : 'Titular: abra a linha para ver detalhes ou use Escolher para trocar.';
      rule.textContent = `${instruction} ${candidates.length} jogador(es) encontrado(s).`;
    }
    const priceLimit = $('playerPickerPriceLimit');
    if (priceLimit) {
      priceLimit.hidden = state.picker.kind !== 'reserve';
      const value = priceLimit.querySelector('strong');
      if (value) value.textContent = state.picker.kind === 'reserve'
        ? (reserveLimit === Infinity ? 'Aguardando titular' : `${money(reserveLimit)} (abaixo deste valor)`)
        : 'Sem limite de reserva';
    }
    target.innerHTML = candidates.length ? candidates.map(player => {
      const playerName = escapeHtml(player.apelido || player.nome || 'Jogador');
      const playerPrice = money(price(player));
      const playerPoints = `${points(player).toFixed(2)} pts`;
      const clubName = escapeHtml(clubFor(player).nome || player.clube_nome || 'Clube');
      const scoutMarkup = scout ? `<span class="ideal-picker-metric ideal-picker-scout" title="${escapeHtml(scout.toUpperCase())}: ${scoutValue(player, scout).toFixed(2)}"><small>${escapeHtml(scout.toUpperCase())}</small><strong>${scoutValue(player, scout).toFixed(2)}</strong></span>` : '';
      const athleteId = escapeHtml(idOf(player));
      return `<article class="ideal-picker-player-entry"><div class="ideal-picker-player-row"><button type="button" class="ideal-picker-player" data-picker-detail="${athleteId}" aria-expanded="false" title="Abrir detalhes de ${playerName}"><span class="ideal-picker-player-visual">${avatar(player, 'ideal-picker-avatar')}${fixtureIndicators(player)}</span><span class="ideal-picker-player-copy"><strong title="Jogador: ${playerName}">${playerName}</strong><small>${clubName} · ${escapeHtml(statusLabel(player))}</small></span><span class="ideal-picker-metrics"><span class="ideal-picker-metric" title="Preço do jogador: ${playerPrice}"><small>Preço</small><strong>${playerPrice}</strong></span><span class="ideal-picker-metric" title="Pontuação prevista: ${playerPoints}"><small>Prevista</small><strong>${playerPoints}</strong></span>${scoutMarkup}</span><i class="ideal-picker-row-chevron fas fa-chevron-down" aria-hidden="true"></i></button><button type="button" class="ideal-picker-select-player" data-picker-athlete="${athleteId}" title="Escalar ${playerName}"><i class="fas fa-plus"></i><span>Escolher</span></button></div><div class="ideal-picker-inline-slot" hidden></div></article>`;
    }).join('') : '<div class="ideal-picker-empty">Nenhum atleta atende aos filtros e às regras desta vaga.</div>';
    target.querySelectorAll('[data-picker-athlete]').forEach(button => button.addEventListener('click', () => applyPicker(button.dataset.pickerAthlete)));
    target.querySelectorAll('[data-picker-detail]').forEach(button => {
      const player = pickerPool().find(item => idOf(item) === button.dataset.pickerDetail);
      if (player) button.addEventListener('click', () => {
        togglePickerDetail(button, player);
        button.closest('.ideal-picker-player-entry')?.classList.toggle('is-expanded', button.getAttribute('aria-expanded') === 'true');
      });
    });
  }

  function setPickerStatus(status) {
    if (!state.picker) return;
    state.picker.statusFilter = status;
    document.querySelectorAll('[data-picker-status]').forEach(button => {
      const active = button.dataset.pickerStatus === status;
      button.classList.toggle('is-active', active);
      button.setAttribute('aria-pressed', String(active));
    });
    renderPickerStatusOptions();
    renderPickerResults();
  }

  function openPicker(position, kind, index) {
    if (!window.ultimaEscalacao) return notify('Calcule a escalação antes de editar.', 'warning');
    const currentGroup = kind === 'reserve' ? window.ultimaEscalacao.reservas : window.ultimaEscalacao.titulares;
    const current = currentGroup?.[position]?.[Number(index) || 0];
    if (position === 'goleiros' && kind === 'starter' && current?.eh_goleiro_hack && $('hackGoleiroToggle')?.checked) {
      return notify('Este goleiro foi escolhido pelo hack. Para trocá-lo, desabilite o hack do goleiro e recalcule a escalação.', 'warning');
    }
    state.picker = { position, kind, index: Number(index) || 0, statusFilter: 'todos', clubIds: [], sort: 'expected' };
    $('playerPickerContext').textContent = `${kind === 'reserve' ? 'Reserva' : 'Titular'} · ${POSITIONS[position].label}`;
    $('playerPickerTitle').textContent = current ? `Trocar ${current.apelido || 'atleta'}` : `Adicionar ${POSITIONS[position].singular}`;
    if ($('pickerScout')) $('pickerScout').value = '';
    const controls = $('pickerControls');
    if (controls) controls.open = window.matchMedia('(min-width: 761px)').matches;
    const pool = pickerPool();
    renderPickerStatusOptions();
    renderPickerFilters(pool);
    renderPickerResults();
    const picker = $('playerPicker');
    // Retirar o modal de dentro do container de layout (que cria stacking
    // context e o deixava parcialmente coberto pela sidebar fixa).
    if (picker.parentElement !== document.body) document.body.appendChild(picker);
    picker.hidden = false; picker.setAttribute('aria-hidden', 'false');
    document.body.classList.add('ideal-picker-open');
    // No PC, levar o foco para a busca evita deixar o hover preso no card
    // quando a troca é fechada. Em touch, preserve a abertura sem teclado.
    if (window.matchMedia('(hover: hover) and (pointer: fine)').matches && controls?.open) {
      $('pickerSortOptions [data-picker-sort="expected"]')?.focus({ preventScroll: true });
    }
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
      // A regra de cravar/não jogar vale para atletas de linha. O treinador
      // não participa desse fluxo de disponibilidade especial.
      if (state.picker.position !== 'treinadores' && !(await confirmCandidateAvailability(candidate))) return;
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
      renderAvailabilityChoices();
    } catch (error) {
      const hint = $('availabilityHint');
      if (hint) hint.textContent = error.message;
    }
  }

  function renderAvailabilityChoices() {
    const target = $('availabilityChoices');
    const selected = $('availabilitySelected');
    if (!target) return;
    const normalize = (candidate) => String(candidate || '').trim().toLocaleLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');
    const query = normalize($('availabilityAthleteInput')?.value || '');
    const matches = state.availability.filter(item => !query || normalize(`${item.apelido || ''} ${item.nome || ''} ${item.clube_nome || ''}`).includes(query)).slice(0, 8);
    target.innerHTML = matches.length ? matches.map(item => {
      const id = String(item.atleta_id ?? item.id ?? '');
      const name = escapeHtml(item.apelido || item.nome || 'Jogador');
      const clubName = escapeHtml(clubFor(item).nome || item.clube_nome || 'Time');
      const fixture = fixtureIndicators(item);
      const isSelected = id && id === String(state.selectedAvailabilityId);
      return `<button type="button" class="ideal-availability-choice${isSelected ? ' is-selected' : ''}" data-availability-choice="${escapeHtml(id)}"><span class="ideal-availability-choice-avatar">${avatar(item)}</span><span class="ideal-availability-choice-copy"><strong>${name}</strong><small>${clubName} · ${escapeHtml(statusLabel(item))}</small></span><span class="ideal-availability-choice-fixture">${fixture || '<span class="ideal-picker-club-empty">Sem confronto</span>'}</span></button>`;
    }).join('') : '<div class="ideal-picker-club-empty">Nenhum jogador encontrado</div>';
    const athlete = state.availability.find(item => String(item.atleta_id ?? item.id) === String(state.selectedAvailabilityId));
    if (selected) {
      selected.innerHTML = athlete ? `<span class="ideal-availability-selected-avatar">${avatar(athlete)}</span><span class="ideal-availability-selected-copy"><strong>${escapeHtml(athlete.apelido || athlete.nome || 'Jogador')}</strong><small>${escapeHtml(clubFor(athlete).nome || athlete.clube_nome || 'Time')} · ${escapeHtml(statusLabel(athlete))}</small></span><span class="ideal-availability-choice-fixture">${fixtureIndicators(athlete) || ''}</span>` : '';
      selected.hidden = !athlete;
    }
    target.hidden = Boolean(athlete) || !query;
  }

  function selectedAvailabilityAthlete() {
    if (state.selectedAvailabilityId) {
      const selected = state.availability.find(item => String(item.atleta_id ?? item.id) === String(state.selectedAvailabilityId));
      if (selected) return selected;
    }
    const value = ($('availabilityAthleteInput')?.value || '').trim().toLocaleLowerCase();
    if (!value) return null;
    const normalize = (candidate) => String(candidate || '').trim().toLocaleLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');
    const normalizedValue = normalize(value);
    return state.availability.find(item => String(item.atleta_id) === value || normalize(item.apelido) === normalizedValue || normalize(item.nome) === normalizedValue) || null;
  }

  async function applyAvailability(rule) {
    if (state.availabilityBusy) return;
    const athlete = selectedAvailabilityAthlete();
    if (!athlete || !state.data?.team_id) return notify('Escolha um atleta da lista de disponibilidade.', 'warning');
    if (Number(athlete.posicao_id) === 6 || athlete.posicao_slug === 'treinador') {
      return notify('Treinadores não podem ser marcados como não jogadores nem cravados.', 'warning');
    }
    const hint = $('availabilityHint');
    const buttons = [$('markUnavailableBtn'), $('markAvailableBtn'), $('availabilityRecalculateBtn')].filter(Boolean);
    state.availabilityBusy = true;
    buttons.forEach((button) => { button.disabled = true; button.classList.add('opacity-60'); });
    if (hint) hint.textContent = 'Salvando regra e atualizando cálculos...';
    try {
      const response = await fetch('/api/player-availability', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ team_id: state.data.team_id, season: state.data.temporada_atual, round_number: state.data.rodada_atual, athlete_id: athlete.atleta_id, rule })
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Não foi possível salvar a disponibilidade.');
      state.teamChanged = true;
      athlete.rule = rule;
      if (hint) hint.textContent = `${athlete.apelido} marcado como ${rule === 'poupar' ? 'não joga' : 'joga'}. Recalculando...`;
      await calcularEscalacao();
      await loadAvailabilityCandidates();
    } catch (error) {
      if (hint) hint.textContent = error.message;
      notify(error.message, 'error');
    } finally {
      state.availabilityBusy = false;
      buttons.forEach((button) => { button.disabled = false; button.classList.remove('opacity-60'); });
    }
  }

  async function applyAvailabilityForAthlete(athleteId) {
    if (!state.data?.team_id || !athleteId) return;
    const athlete = state.availability.find((item) => String(item.atleta_id) === String(athleteId));
    if (Number(athlete?.posicao_id) === 6 || athlete?.posicao_slug === 'treinador') {
      return notify('Treinadores não podem ser marcados como não jogadores.', 'warning');
    }
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
    window.addEventListener('resize', syncPitchScale, { passive: true });
    const isTouchSurface = () => Boolean(window.matchMedia?.('(hover: none), (pointer: coarse)').matches);
    const closeTouchCards = (except = null) => {
      document.querySelectorAll('.ideal-card-actions.is-touch-portal').forEach(panel => {
        const origin = panel._idealOriginCard;
        if (origin?.isConnected) origin.appendChild(panel);
        else panel.remove();
        panel.classList.remove('is-touch-portal');
        delete panel._idealOriginCard;
      });
      document.querySelectorAll('.ideal-player-card.is-touch-open').forEach(card => {
        if (card !== except) card.classList.remove('is-touch-open');
      });
    };
    ['formationSelect', 'hackGoleiroToggle', 'fecharDefesaToggle', 'posicaoCapitao', 'posicaoReservaLuxo'].forEach(id => $(id)?.addEventListener('change', () => aoMudarConfiguracao()));
    $('availabilityAthleteInput')?.addEventListener('input', () => { state.selectedAvailabilityId = ''; renderAvailabilityChoices(); });
    $('availabilityAthleteInput')?.addEventListener('focus', renderAvailabilityChoices);
    $('availabilityChoices')?.addEventListener('click', event => {
      const choice = event.target.closest('[data-availability-choice]');
      if (!choice) return;
      state.selectedAvailabilityId = choice.dataset.availabilityChoice;
      const athlete = state.availability.find(item => String(item.atleta_id ?? item.id) === state.selectedAvailabilityId);
      if ($('availabilityAthleteInput')) $('availabilityAthleteInput').value = athlete?.apelido || athlete?.nome || '';
      renderAvailabilityChoices();
    });
    document.addEventListener('click', (event) => {
      const touchReplace = event.target.closest('[data-touch-replace]');
      if (touchReplace) {
        event.preventDefault();
        const card = touchReplace.closest('.ideal-card-actions')?._idealOriginCard;
        if (!card) return;
        closeTouchCards();
        openPicker(card.dataset.pickerPosition, card.dataset.pickerKind, card.dataset.pickerIndex);
        return;
      }
      const hoverClose = event.target.closest('[data-card-hover-close]');
      if (hoverClose) {
        event.preventDefault();
        event.stopPropagation();
        const panel = hoverClose.closest('.ideal-card-actions');
        const card = panel?._idealOriginCard || hoverClose.closest('.ideal-player-card');
        closeTouchCards();
        card?.classList.add('is-hover-closed');
        card?.classList.remove('is-touch-open');
        return;
      }
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
        closeTouchCards();
        setSpecialRole(specialRole.dataset.specialRole, specialRole);
        return;
      }
      const availabilityButton = event.target.closest('[data-availability-action]');
      if (availabilityButton) {
        event.preventDefault();
        event.stopPropagation();
        closeTouchCards();
        applyAvailabilityForAthlete(availabilityButton.dataset.athleteId);
        return;
      }
      const target = event.target.closest('[data-picker-kind]');
      if (!target || event.target.closest('.ideal-card-actions')) return;
      if (isTouchSurface()) {
        closeTouchCards();
        openPicker(target.dataset.pickerPosition, target.dataset.pickerKind, target.dataset.pickerIndex);
        return;
      }
      openPicker(target.dataset.pickerPosition, target.dataset.pickerKind, target.dataset.pickerIndex);
    });
    $('escalacaoContent')?.addEventListener('pointerover', (event) => {
      if (event.pointerType === 'touch') return;
      const card = event.target.closest('.ideal-player-card');
      if (card && !card.contains(event.relatedTarget)) card.classList.remove('is-hover-closed');
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
    ['pickerScout'].forEach(id => $(id)?.addEventListener('input', renderPickerResults));
    $('pickerScout')?.addEventListener('change', renderPickerResults);
    document.querySelectorAll('[data-picker-sort]').forEach(button => button.addEventListener('click', () => {
      if (!state.picker) return;
      state.picker.sort = button.dataset.pickerSort;
      updatePickerSortControls();
      renderPickerResults();
    }));
    document.querySelectorAll('[data-picker-status]').forEach(button => button.addEventListener('click', () => setPickerStatus(button.dataset.pickerStatus)));
    $('pickerStatusCravados')?.addEventListener('click', () => setPickerStatus('cravados'));
    $('markUnavailableBtn')?.addEventListener('click', () => applyAvailability('poupar'));
    $('markAvailableBtn')?.addEventListener('click', () => applyAvailability('cravado'));
    $('availabilityRecalculateBtn')?.addEventListener('click', calcularEscalacao);
    document.addEventListener('keydown', event => {
      if (event.key === 'Escape') {
        closePicker();
        closeTouchCards();
      }
    });
    document.addEventListener('click', event => {
      if (isTouchSurface() && !event.target.closest('.ideal-player-card, .ideal-card-actions.is-touch-portal')) closeTouchCards();
    });
  }

  async function init() {
    showLoading('Carregando painel de escalação...');
    try {
      console.debug('[AERO][Escalação] permissões da página', {
        podeEscalar: can('podeEscalar'),
        atributoPodeEscalar: page()?.getAttribute('data-pode-escalar'),
        verEscalacao: can('verEscalacaoIdealCompleta'),
        atributoVerEscalacao: page()?.getAttribute('data-ver-escalacao')
      });
      if (!(await verificarStatusModulos())) return;
      await carregarConfiguracoes();
      const data = await loadData();
      await loadAvailabilityCandidates();
      bindEvents();
      const current = data.current_lineup;
      if (current?.status === 'scaled' && current.players?.length) {
        state.currentLineup = makeCurrentLineup(data);
        state.isShowingCurrent = true;
        window.ultimaEscalacao = state.currentLineup;
        exibirResultado(state.currentLineup, data.clubes_dict);
        adicionarLog('Escalação atual carregada do Cartola. Conferindo contra o cálculo ideal...', 'info');
        const currentFormation = $('formationSelect').value;
        $('formationSelect').value = data.config?.formation || '4-3-3';
        const ideal = await calcularEscalacao(false, { background: true });
        if (ideal) ideal.formation_id = ({ '4-4-2': 1, '3-5-2': 2, '4-3-3': 3, '3-4-3': 4, '4-5-1': 5, '5-4-1': 6, '5-3-2': 7 })[$('formationSelect').value] || 0;
        $('formationSelect').value = currentFormation;
        state.currentComparison = compareLineups(state.currentLineup, ideal);
        window.ultimaEscalacao = state.currentLineup;
        state.isShowingCurrent = true;
        exibirResultado(state.currentLineup, data.clubes_dict);
        if (state.currentComparison?.matches) refreshSubmitButton();
        else $('calcularBtn')?.classList.add('ideal-needs-recalculation');
      } else {
        const content = $('escalacaoContent');
        const panel = $('resultadoPanel');
        const message = current?.status === 'not_scaled'
          ? `Ainda não há escalação salva na rodada ${data.rodada_atual}. Calcule a escalação ideal e envie ao Cartola.`
          : 'Não foi possível confirmar a escalação atual do Cartola. Calcule uma escalação ideal para continuar.';
        if (content && panel) {
          content.innerHTML = `<div class="ideal-empty ideal-current-empty"><div><i class="fas fa-clipboard-list"></i><h3>${current?.status === 'not_scaled' ? 'Você ainda não escalou nesta rodada' : 'Escalação atual indisponível'}</h3><p>${escapeHtml(message)}</p><button type="button" class="ideal-btn ideal-btn-primary" onclick="calcularEscalacao()"><i class="fas fa-calculator"></i> Calcular escalação ideal</button></div></div>`;
          panel.classList.remove('hidden');
          const title = document.querySelector('.ideal-result-title');
          if (title) title.innerHTML = '<i class="fas fa-futbol"></i> Escalação da rodada';
          const meta = document.querySelector('.ideal-result-meta');
          if (meta) meta.textContent = `Rodada ${data.rodada_atual}`;
        }
        adicionarLog(current?.status === 'not_scaled' ? 'O Cartola ainda não registra escalação para a rodada atual.' : 'Não foi possível ler o estado da escalação no Cartola.', current?.status === 'not_scaled' ? 'info' : 'warning');
      }
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
  window.manualSelecionarJogador = manualSelecionarJogador;
  window.aoMudarConfiguracao = aoMudarConfiguracao;
  window.renderizarPrioridades = renderizarPrioridades;

  document.addEventListener('DOMContentLoaded', init);
})();
