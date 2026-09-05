(function () {
    'use strict';

    const page = document.getElementById('scoutCrossingPage');
    const state = { temporada: Number(page?.dataset.currentSeason || 0), rodada: Number(page?.dataset.currentRound || 0), teamId: null, posicaoId: null, atletaId: null, adversarioId: null, matches: [] };
    const shortScouts = { a: 'A', ca: 'CA', cv: 'CV', de: 'DEF', ds: 'DS', fc: 'FC', fd: 'FD', ff: 'FF', fs: 'FS', g: 'G', gs: 'GS', i: 'IMP', sg: 'SG' };
    const scoutLabels = { a: 'Assistências', ca: 'Cartões amarelos', cv: 'Cartões vermelhos', de: 'Defesas', ds: 'Desarmes', fc: 'Faltas cometidas', fd: 'Finalizações defendidas', ff: 'Finalizações para fora', fs: 'Faltas sofridas', g: 'Gols', gs: 'Gols sofridos', i: 'Impedimentos', sg: 'Saldo de gols' };

    const escapeHtml = (value) => String(value ?? '').replace(/[&<>'"]/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#039;', '"': '&quot;' }[char]));
    const number = (value, digits = 2) => Number.isFinite(Number(value)) ? Number(value).toLocaleString('pt-BR', { minimumFractionDigits: digits, maximumFractionDigits: digits }) : '0,00';
    const integer = (value) => Number.isFinite(Number(value)) ? Math.round(Number(value)).toLocaleString('pt-BR') : '0';
    const $ = (id) => document.getElementById(id);

    function setAlert(message, error = false) {
        const alert = $('scoutCrossingAlert');
        if (!alert) return;
        alert.hidden = !message; alert.textContent = message || '';
        alert.classList.toggle('scx-alert-error', error);
    }

    function normalizedPhoto(value, athleteId) {
        let photo = value || (typeof getPlayerImage === 'function' ? getPlayerImage(Number(athleteId)) : '') || '';
        if (photo.startsWith('//')) photo = `https:${photo}`;
        return photo;
    }

    function teamButton(team) {
        const selected = Number(state.teamId) === Number(team.id);
        const image = team.escudo ? `<img src="${escapeHtml(team.escudo)}" alt="" loading="lazy">` : '<span class="scx-team-fallback"><i class="fas fa-shield-halved"></i></span>';
        return `<button type="button" class="scx-team${selected ? ' is-selected' : ''}" data-team="${team.id}" role="option" aria-selected="${selected}">${image}<b>${escapeHtml(team.abreviacao || team.nome)}</b></button>`;
    }

    function renderTeams(teams) {
        const rail = $('scoutCrossingTeams');
        if (!rail) return;
        rail.innerHTML = teams.length ? teams.map(teamButton).join('') : '<span class="scx-muted">Nenhum time encontrado na rodada atual.</span>';
        rail.querySelectorAll('[data-team]').forEach((button) => button.addEventListener('click', () => {
            state.teamId = Number(button.dataset.team); state.atletaId = null; state.adversarioId = null; renderTeams(teams); loadOptions();
        }));
    }

    function renderPlayers(players) {
        const select = $('scoutCrossingPlayer');
        if (!select) return;
        select.innerHTML = '<option value="">Selecione o jogador</option>' + players.map((player) => `<option value="${player.id}">${escapeHtml(player.nome)} · ${escapeHtml(player.clube_nome)}</option>`).join('');
        select.disabled = !players.length;
        if (state.atletaId && players.some((player) => Number(player.id) === Number(state.atletaId))) select.value = String(state.atletaId);
        $('scoutCrossingSelectionHint').textContent = players.length ? 'Agora escolha o jogador e o confronto abaixo.' : 'Nenhum jogador encontrado nessa combinação.';
    }

    function matchButton(match) {
        const selected = Number(state.adversarioId) === Number(match.adversario.id);
        return `<button type="button" class="scx-match${selected ? ' is-selected' : ''}" data-opponent="${match.adversario.id}" role="option" aria-selected="${selected}">
            <img src="${escapeHtml(match.casa.escudo || '')}" alt="${escapeHtml(match.casa.nome)}" loading="lazy"><span class="scx-match-copy"><strong>${escapeHtml(match.casa.nome)}</strong><small>${match.mando === 'casa' ? 'Você joga em casa' : 'Você joga fora'}</small></span><span class="scx-match-vs">x</span><img src="${escapeHtml(match.fora.escudo || '')}" alt="${escapeHtml(match.fora.nome)}" loading="lazy">
        </button>`;
    }

    function renderMatches(matches) {
        state.matches = matches || [];
        const section = $('scoutCrossingMatches'); const rail = $('scoutCrossingMatchRail');
        if (!section || !rail) return;
        section.hidden = !state.atletaId || !state.matches.length;
        rail.innerHTML = state.matches.length ? state.matches.map(matchButton).join('') : '<span class="scx-muted">Esse time não tem confronto válido nesta rodada.</span>';
        rail.querySelectorAll('[data-opponent]').forEach((button) => button.addEventListener('click', () => {
            state.adversarioId = Number(button.dataset.opponent); renderMatches(state.matches); runCrossing();
        }));
    }

    async function loadOptions() {
        if (!page) return;
        const position = document.querySelector('.scx-position.is-selected')?.dataset.position || state.posicaoId || 5;
        state.posicaoId = Number(position);
        if (!state.teamId) { $('scoutCrossingPlayer').disabled = true; return; }
        const params = new URLSearchParams({ clube_id: state.teamId, posicao_id: state.posicaoId });
        const select = $('scoutCrossingPlayer'); select.disabled = true; select.innerHTML = '<option>Carregando jogadores...</option>';
        try {
            const response = await fetch(`${page.dataset.optionsUrl}?${params}`); const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Não foi possível carregar as opções.');
            state.temporada = Number(data.temporada); state.rodada = Number(data.rodada);
            renderTeams(data.times || []); renderPlayers(data.jogadores || []); renderMatches(data.confrontos || []);
            if (page.dataset.selectedPlayer && !state.atletaId) { state.atletaId = Number(page.dataset.selectedPlayer); select.value = String(state.atletaId); }
        } catch (error) { setAlert(error.message, true); select.innerHTML = '<option>Não foi possível carregar</option>'; }
    }

    function scoutSummary(scouts) {
        const parts = Object.entries(scouts || {}).filter(([, value]) => Number(value) !== 0).map(([code, value]) => `${shortScouts[code] || code} ${integer(value)}`);
        return parts.length ? parts.join(' · ') : 'sem scouts';
    }

    function renderSummary(summary) {
        $('scoutCrossingSummary').innerHTML = [['Média', number(summary.media), true], ['Jogos', integer(summary.jogos)], ['Maior', number(summary.maior_pontuacao)], ['Menor', number(summary.menor_pontuacao)]].map(([label, value, accent]) => `<div class="scx-summary-item${accent ? ' accent' : ''}"><span>${label}</span><strong>${value}</strong></div>`).join('');
    }

    function renderRecent(matches) {
        const target = $('scoutCrossingRecent');
        if (!matches.length) { target.innerHTML = '<div class="scx-muted">Nenhuma pontuação encontrada.</div>'; return; }
        target.innerHTML = matches.map((match) => `<button type="button" class="scx-recent-row" data-round="${match.rodada}"><span class="scx-round">R${match.rodada}</span><span class="scx-match-copy"><strong>${escapeHtml(match.adversario_nome)}</strong><small>${escapeHtml(match.mando_label)} · ${escapeHtml(match.casa_nome)} x ${escapeHtml(match.visitante_nome)}</small></span><span class="scx-points">${number(match.pontuacao)} <em>(${escapeHtml(scoutSummary(match.scouts))})</em></span><i class="fas fa-chevron-right"></i></button>`).join('');
        target.querySelectorAll('[data-round]').forEach((button) => button.addEventListener('click', () => openDetail(Number(button.dataset.round))));
    }

    function renderPositionScouts(scouts) {
        const target = $('scoutCrossingPositionScouts');
        target.innerHTML = scouts?.length ? scouts.map((scout) => `<div class="scx-scout-row"><span><b>${escapeHtml(scout.codigo.toUpperCase())}</b> · ${escapeHtml(scout.nome)}</span><strong>${number(scout.media)}</strong></div>`).join('') : '<div class="scx-muted">Sem referência disponível.</div>';
    }

    function renderOpponents(opponents) {
        const target = $('scoutCrossingOpponents');
        target.innerHTML = opponents?.length ? opponents.map((opponent) => `<div class="scx-opponent-row"><div><strong>${escapeHtml(opponent.nome)}</strong><small>${integer(opponent.jogos)} jogo(s)</small></div><strong>${number(opponent.media)} pts</strong></div>`).join('') : '<div class="scx-muted">Nenhum adversário identificado.</div>';
    }

    function renderHomeAway(items) {
        $('scoutCrossingHomeAway').innerHTML = (items || []).map((item) => `<div class="scx-home-row"><div><strong>${item.label}</strong><small>${integer(item.jogos)} jogo(s) com pontuação</small></div><strong>${number(item.media)}</strong></div>`).join('');
    }

    function renderConfrontation(data) {
        const target = $('scoutCrossingConfrontation'); const match = data.confronto; const ceded = data.cedidos_adversario || {};
        if (!match) { target.hidden = true; target.innerHTML = ''; return; }
        target.hidden = false;
        const opponent = match.adversario || {};
        const scouts = ceded.scouts || {};
        target.innerHTML = `<div class="scx-confrontation-head"><div class="scx-confrontation-title"><img src="${escapeHtml(opponent.escudo || '')}" alt="${escapeHtml(opponent.nome || '')}"><div><strong>O que ${escapeHtml(opponent.nome || 'o adversário')} cedeu</strong><small>${escapeHtml(match.casa_nome)} x ${escapeHtml(match.visitante_nome)} · ${match.mando_label}</small></div></div><strong class="scx-confrontation-score">${number(match.pontuacao)}</strong></div><div class="scx-conceded">${Object.entries(scouts).map(([code, value]) => `<div class="scx-conceded-item"><span>${escapeHtml(shortScouts[code] || code)} · ${escapeHtml(scoutLabels[code] || code)}</span><strong>${number(value)}</strong></div>`).join('') || '<span class="scx-muted">Sem scouts cedidos registrados.</span>'}</div>`;
    }

    function renderResult(data) {
        $('scoutCrossingEmpty').hidden = true; $('scoutCrossingResults').hidden = false;
        $('scoutCrossingPlayerName').textContent = data.jogador.nome;
        $('scoutCrossingPlayerMeta').textContent = `${data.jogador.posicao} · ${data.jogador.clube_nome} · R${data.filtros.rodada}`;
        const avatar = $('scoutCrossingPlayerAvatar'); const photo = normalizedPhoto(data.jogador.foto, data.jogador.id);
        avatar.innerHTML = photo ? `<img src="${escapeHtml(photo)}" alt="${escapeHtml(data.jogador.nome)}">` : '<i class="fas fa-user"></i>';
        const image = avatar.querySelector('img'); if (image) image.onerror = () => { const fallback = typeof getPlayerImage === 'function' ? getPlayerImage(data.jogador.id) : ''; if (fallback && image.src !== fallback) image.src = fallback; else { image.remove(); avatar.innerHTML = '<i class="fas fa-user"></i>'; } };
        renderSummary(data.resumo); renderConfrontation(data); renderRecent(data.ultimas_pontuacoes || []); renderPositionScouts(data.scouts_da_posicao || []); renderOpponents(data.resumo.adversarios || []); renderHomeAway(data.resumo.mando || []);
    }

    async function runCrossing() {
        if (!state.atletaId || !state.posicaoId || !state.adversarioId) { setAlert('Selecione o jogador e o confronto da rodada.', true); return; }
        const params = new URLSearchParams({ atleta_id: state.atletaId, posicao_id: state.posicaoId, adversario_id: state.adversarioId });
        setAlert('Calculando o cruzamento...');
        try { const response = await fetch(`${page.dataset.crossingUrl}?${params}`); const data = await response.json(); if (!response.ok) throw new Error(data.error || 'Não foi possível executar o cruzamento.'); state.temporada = Number(data.filtros.temporada); state.rodada = Number(data.filtros.rodada); renderResult(data); setAlert(''); } catch (error) { setAlert(error.message, true); }
    }

    function detailUrl(atletaId, rodada) { return `/cruzamento-scouts/api/detalhe/${atletaId}/${rodada}`; }
    async function openDetail(rodada, atletaId = state.atletaId) {
        const modal = $('modalScoutCrossingDetail'); if (!modal || !atletaId) return;
        try { const response = await fetch(`${detailUrl(atletaId, rodada)}`); const data = await response.json(); if (!response.ok) throw new Error(data.error || 'Detalhe indisponível.');
            $('scoutCrossingModalTitle').textContent = `Rodada ${data.rodada}`; $('scoutCrossingModalMatch').textContent = `${data.casa_nome} x ${data.visitante_nome}`; $('scoutCrossingModalScore').textContent = number(data.pontuacao);
            $('scoutCrossingModalMeta').innerHTML = [data.mando_label, data.local || 'Local não informado', `Scouts: ${scoutSummary(data.scouts)}`].map((item) => `<span>${escapeHtml(item)}</span>`).join('');
            $('scoutCrossingModalScouts').innerHTML = Object.entries(data.scouts || {}).map(([code, value]) => `<div class="scout-crossing-modal-scout"><span>${escapeHtml(scoutLabels[code] || code)}</span><strong>${integer(value)}</strong></div>`).join(''); modal.hidden = false; modal.setAttribute('aria-hidden', 'false'); document.body.style.overflow = 'hidden';
        } catch (error) { setAlert(error.message, true); }
    }

    function closeModal() { const modal = $('modalScoutCrossingDetail'); if (!modal) return; modal.hidden = true; modal.setAttribute('aria-hidden', 'true'); document.body.style.overflow = ''; }
    window.openScoutCrossingModal = (athleteId, options = {}) => {
        const requestedRound = Number(options.rodada || state.rodada);
        if (requestedRound) return openDetail(requestedRound, Number(athleteId));
        fetch('/cruzamento-scouts/api/contexto')
            .then((response) => response.json().then((data) => ({ response, data })))
            .then(({ response, data }) => { if (!response.ok) throw new Error(data.error || 'Contexto da rodada indisponível.'); state.temporada = Number(data.temporada); state.rodada = Number(data.rodada); return openDetail(state.rodada, Number(athleteId)); })
            .catch((error) => setAlert(error.message, true));
    };
    window.closeScoutCrossingModal = closeModal;

    if (!page) return;
    $('scoutCrossingPlayer')?.addEventListener('change', (event) => { state.atletaId = Number(event.target.value) || null; state.adversarioId = null; renderMatches(state.matches); $('scoutCrossingResults').hidden = true; });
    document.querySelectorAll('.scx-position').forEach((button) => button.addEventListener('click', () => { document.querySelectorAll('.scx-position').forEach((item) => { item.classList.remove('is-selected'); item.setAttribute('aria-selected', 'false'); }); button.classList.add('is-selected'); button.setAttribute('aria-selected', 'true'); state.posicaoId = Number(button.dataset.position); state.atletaId = null; state.adversarioId = null; loadOptions(); }));
    document.querySelectorAll('[data-scout-crossing-close]').forEach((element) => element.addEventListener('click', closeModal));
    document.addEventListener('keydown', (event) => { if (event.key === 'Escape') closeModal(); });
    state.posicaoId = Number(document.querySelector('.scx-position.is-selected')?.dataset.position || 5);
    fetch(`${page.dataset.optionsUrl}?posicao_id=${state.posicaoId}`).then((response) => response.json()).then((data) => { renderTeams(data.times || []); const first = data.times?.[0]; if (first) { state.teamId = first.id; renderTeams(data.times); loadOptions(); } }).catch((error) => setAlert(error.message, true));
}());
