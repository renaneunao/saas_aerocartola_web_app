(function () {
    'use strict';

    const page = document.getElementById('scoutCrossingPage');
    if (!page) return;
    const state = {
        temporada: Number(page.dataset.currentSeason || 0), rodada: Number(page.dataset.currentRound || 0),
        teamId: null, posicaoId: null, atletaId: null, players: [], filteredPlayers: [],
        statusFilter: 'provaveis', sortBy: 'expected', historyExpanded: false, selectedData: null, predictionContext: null,
        predictionById: {}
    };
    const positionSlug = { 1: 'goleiro', 2: 'lateral', 3: 'zagueiro', 4: 'meia', 5: 'atacante', 6: 'treinador' };
    const calculatorByPosition = { 1: 'CalculoGoleiro', 2: 'CalculoLateral', 3: 'CalculoZagueiro', 4: 'CalculoMeia', 5: 'CalculoAtacante', 6: 'CalculoTreinador' };
    function calculatorClass(positionId) {
        // Classes declaradas em scripts clássicos podem ficar no escopo global
        // sem virar propriedades de window. O fallback em window mantém
        // compatibilidade com versões antigas dos calculadores.
        switch (Number(positionId)) {
        case 1: return typeof CalculoGoleiro !== 'undefined' ? CalculoGoleiro : window.CalculoGoleiro;
        case 2: return typeof CalculoLateral !== 'undefined' ? CalculoLateral : window.CalculoLateral;
        case 3: return typeof CalculoZagueiro !== 'undefined' ? CalculoZagueiro : window.CalculoZagueiro;
        case 4: return typeof CalculoMeia !== 'undefined' ? CalculoMeia : window.CalculoMeia;
        case 5: return typeof CalculoAtacante !== 'undefined' ? CalculoAtacante : window.CalculoAtacante;
        case 6: return typeof CalculoTreinador !== 'undefined' ? CalculoTreinador : window.CalculoTreinador;
        default: return null;
        }
    }
    const shortScouts = { a: 'A', ca: 'CA', cv: 'CV', de: 'DEF', ds: 'DS', fc: 'FC', fd: 'FD', ff: 'FF', fs: 'FS', g: 'G', gs: 'GS', i: 'IMP', sg: 'SG' };
    const scoutLabels = { a: 'Assistências', ca: 'Cartões amarelos', cv: 'Cartões vermelhos', de: 'Defesas', ds: 'Desarmes', fc: 'Faltas cometidas', fd: 'Finalizações defendidas', ff: 'Finalizações para fora', fs: 'Faltas sofridas', g: 'Gols', gs: 'Gols sofridos', i: 'Impedimentos', sg: 'Saldo de gols' };
    const escapeHtml = (value) => String(value ?? '').replace(/[&<>'"]/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#039;', '"': '&quot;' }[char]));
    const number = (value, digits = 2) => Number.isFinite(Number(value)) ? Number(value).toLocaleString('pt-BR', { minimumFractionDigits: digits, maximumFractionDigits: digits }) : '0,00';
    const integer = (value) => Number.isFinite(Number(value)) ? Math.round(Number(value)).toLocaleString('pt-BR') : '0';
    const $ = (id) => document.getElementById(id);
    const selectedPosition = () => Number(document.querySelector('.scx-position.is-selected')?.dataset.position || state.posicaoId || 5);
    const predictionValue = (player) => Number(state.predictionById[player.id] ?? player.previsao ?? player.pontos_num ?? player.media_num ?? 0);
    const normalizedPhoto = (value, athleteId) => {
        let photo = value || (typeof window.getPlayerImage === 'function' ? window.getPlayerImage(Number(athleteId)) : '') || '';
        if (photo.startsWith('//')) photo = `https:${photo}`;
        photo = photo.replace(/FORMATO/gi, '220x220');
        return photo.startsWith('http://') ? `https://${photo.slice(7)}` : photo;
    };
    function setAlert(message, error = false) { const alert = $('scoutCrossingAlert'); if (!alert) return; alert.hidden = !message; alert.textContent = message || ''; alert.classList.toggle('scx-alert-error', error); }
    function currentClub(id) { const teams = state.lastTeams || []; return teams.find((team) => Number(team.id) === Number(id)) || {}; }

    function teamButton(team) {
        const selected = Number(state.teamId) === Number(team.id);
        const valid = team.valido !== false;
        const image = team.escudo ? `<img src="${escapeHtml(team.escudo)}" alt="" loading="lazy">` : '<span class="scx-team-fallback"><i class="fas fa-shield-halved"></i></span>';
        return `<button type="button" class="scx-team${selected ? ' is-selected' : ''}${valid ? '' : ' is-invalid'}" data-team="${team.id}" role="option" aria-selected="${selected}" aria-disabled="${!valid}" title="${escapeHtml(valid ? team.nome : `${team.nome} · sem confronto válido`)}"${valid ? '' : ' disabled'}>${image}<b>${escapeHtml(team.abreviacao || team.nome)}</b>${valid ? '' : '<small>sem jogo</small>'}</button>`;
    }
    function renderTeams(teams) {
        const target = $('scoutCrossingTeams'); if (!target) return;
        state.lastTeams = teams || [];
        target.innerHTML = teams?.length ? teams.map(teamButton).join('') : '<span class="scx-muted">Nenhum time encontrado na rodada atual.</span>';
        target.querySelectorAll('[data-team]').forEach((button) => button.addEventListener('click', () => {
            const clicked = Number(button.dataset.team);
            state.teamId = Number(state.teamId) === clicked ? null : clicked;
            state.atletaId = null; state.historyExpanded = false; loadOptions();
        }));
    }
    function statusClass(player) {
        if (player.availability_rule === 'cravado') return 'scx-status-lock';
        if (Number(player.status_id) === 7) return 'scx-status-probable';
        if ([2, 3, 5].includes(Number(player.status_id))) return 'scx-status-doubt';
        return 'scx-status-out';
    }
    function statusText(player) { return player.availability_rule === 'cravado' ? 'Cravado' : player.status_nome || 'Status'; }
    function playerOption(player) {
        const photo = normalizedPhoto(player.foto, player.id);
        const initials = escapeHtml((player.nome || '?').slice(0, 2).toUpperCase());
        const avatar = photo ? `<img src="${escapeHtml(photo)}" alt="" loading="lazy" data-fallback="${initials}">` : `<span class="scx-player-option-avatar">${initials}</span>`;
        const selected = Number(state.atletaId) === Number(player.id);
        return `<button type="button" class="scx-player-option${selected ? ' is-selected' : ''}" data-player="${player.id}">${avatar}<span class="scx-player-option-identity"><strong>${escapeHtml(player.nome)}</strong><small>${escapeHtml(player.clube_abrev || player.clube_nome || 'Clube')} · <span class="${statusClass(player)} scx-status">${escapeHtml(statusText(player))}</span></small></span><span class="scx-player-option-stat scx-player-option-expected"><small>Previsão</small><b>${number(predictionValue(player))}</b></span><span class="scx-player-option-stat"><small>Média</small><b>${number(player.media_num)}</b></span><span class="scx-player-option-stat scx-player-option-price"><small>Preço</small><b>C$ ${number(player.preco_num)}</b></span><span class="scx-player-option-stat scx-player-option-games"><small>Jogos</small><b>${integer(player.jogos_num)}</b></span></button>`;
    }
    function filterPlayers() {
        const text = ($('scoutCrossingSearch')?.value || '').trim().toLocaleLowerCase();
        const scout = $('scoutCrossingScout')?.value || '';
        const filtered = (state.players || []).filter((player) => {
            if (state.teamId && Number(player.clube_id) !== Number(state.teamId)) return false;
            // Nulos nunca jogam e não entram na análise. Atletas poupados
            // permanecem visíveis em “Todos” para que a regra possa ser
            // conferida, mas nunca aparecem no filtro inicial de prováveis.
            if (Number(player.status_id) === 6) return false;
            if (state.statusFilter === 'provaveis' && (player.availability_rule === 'poupar' || (Number(player.status_id) !== 7 && player.availability_rule !== 'cravado'))) return false;
            if (state.statusFilter === 'cravados' && player.availability_rule !== 'cravado') return false;
            if (state.statusFilter === 'duvidas' && ![2, 3, 5].includes(Number(player.status_id))) return false;
            if (text && !`${player.nome || ''} ${player.clube_nome || ''}`.toLocaleLowerCase().includes(text)) return false;
            return true;
        });
        const sortBy = $('scoutCrossingSort')?.value || state.sortBy || 'expected';
        state.sortBy = sortBy;
        state.filteredPlayers = filtered.sort((a, b) => {
            if (sortBy === 'average') return Number(b.media_num || 0) - Number(a.media_num || 0);
            if (sortBy === 'price_asc') return Number(a.preco_num || 0) - Number(b.preco_num || 0);
            if (sortBy === 'price_desc') return Number(b.preco_num || 0) - Number(a.preco_num || 0);
            if (sortBy === 'games') return Number(b.jogos_num || 0) - Number(a.jogos_num || 0);
            if (sortBy === 'scout') return Number(b.scouts?.[scout] || 0) - Number(a.scouts?.[scout] || 0);
            if (sortBy === 'name') return String(a.nome || '').localeCompare(String(b.nome || ''), 'pt-BR');
            return predictionValue(b) - predictionValue(a);
        });
    }
    function renderPlayers() {
        filterPlayers();
        const target = $('scoutCrossingPlayers'); if (!target) return;
        target.innerHTML = state.filteredPlayers.length ? state.filteredPlayers.map(playerOption).join('') : '<div class="scx-muted">Nenhum atleta atende aos filtros atuais.</div>';
        target.querySelectorAll('img[data-fallback]').forEach((image) => image.addEventListener('error', () => {
            const fallback = document.createElement('span'); fallback.className = 'scx-player-option-avatar'; fallback.textContent = image.dataset.fallback; image.replaceWith(fallback);
        }, { once: true }));
        target.querySelectorAll('[data-player]').forEach((button) => button.addEventListener('click', () => { state.atletaId = Number(button.dataset.player); const select = $('scoutCrossingPlayer'); if (select) select.value = String(state.atletaId); state.historyExpanded = false; renderPlayers(); runCrossing(); }));
        $('scoutCrossingSelectionHint').textContent = `${state.filteredPlayers.length} atleta(s) no filtro · clique em um card para abrir o detalhamento.`;
    }
    function renderScoutFilter() {
        const select = $('scoutCrossingScout'); if (!select) return;
        const keys = new Set(); (state.players || []).forEach((player) => Object.keys(player.scouts || {}).forEach((key) => keys.add(key)));
        select.innerHTML = '<option value="">Escolha o scout</option>' + [...keys].map((key) => `<option value="${escapeHtml(key)}">${escapeHtml(shortScouts[key] || key.toUpperCase())} · ${escapeHtml(scoutLabels[key] || key)}</option>`).join('');
    }
    function renderHiddenPlayerSelect() {
        const select = $('scoutCrossingPlayer'); if (!select) return;
        select.innerHTML = '<option value="">Selecione o jogador</option>' + (state.players || []).map((player) => `<option value="${player.id}">${escapeHtml(player.nome)} · ${escapeHtml(player.clube_nome)}</option>`).join('');
        select.value = state.atletaId ? String(state.atletaId) : '';
    }

    async function loadPredictionContext() {
        const slug = positionSlug[state.posicaoId]; if (!slug) return;
        try {
            const response = await fetch(`/api/modulos/${slug}/dados`); const data = await response.json();
            if (!response.ok || data.error) throw new Error(data.error || 'Calculador indisponível');
            state.predictionContext = data;
            const modulePlayers = new Map((data.atletas || []).map((player) => [Number(player.atleta_id), player]));
            const Calculator = calculatorClass(state.posicaoId);
            const total = Calculator && data.escalacoes_data ? Object.values(data.escalacoes_data).reduce((sum, value) => sum + Number(value || 0), 0) || 1 : 1;
            if (Calculator) (state.players || []).forEach((player) => {
                const source = modulePlayers.get(Number(player.id));
                if (!source) return;
                try {
                    const calculator = new Calculator({ ...data, atletas: [source] });
                    const result = calculator.calcularPontuacao({ ...source, atleta_id: player.id }, total);
                    if (result && Number.isFinite(Number(result.pontuacao_total)) && Number(result.pontuacao_total) > -900) state.predictionById[player.id] = Number(result.pontuacao_total);
                } catch (error) { console.debug('[SCOUT CROSSING] previsão indisponível', player.id, error); }
            });
            renderPlayers();
        } catch (error) {
            console.debug('[SCOUT CROSSING] calculador não carregado:', error.message);
            renderPlayers();
        }
    }
    async function loadOptions() {
        state.posicaoId = selectedPosition();
        const params = new URLSearchParams({ posicao_id: state.posicaoId });
        if (state.teamId) params.set('clube_id', state.teamId);
        if (page.dataset.selectedPlayer && !state.atletaId) params.set('atleta_id', page.dataset.selectedPlayer);
        setAlert('Carregando atletas da rodada...');
        try {
            const response = await fetch(`${page.dataset.optionsUrl}?${params}`); const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Não foi possível carregar as opções.');
            state.temporada = Number(data.temporada); state.rodada = Number(data.rodada); state.lastTeams = data.times || [];
            if (page.dataset.selectedPlayer && !state.atletaId && data.jogadores?.some((player) => Number(player.id) === Number(page.dataset.selectedPlayer))) state.atletaId = Number(page.dataset.selectedPlayer);
            renderTeams(data.times || []); state.players = data.jogadores || []; state.predictionById = {};
            renderScoutFilter(); renderHiddenPlayerSelect(); renderPlayers(); setAlert('');
            await loadPredictionContext();
            if (state.atletaId && state.players.some((player) => Number(player.id) === Number(state.atletaId))) runCrossing();
        } catch (error) { setAlert(error.message, true); $('scoutCrossingSelectionHint').textContent = 'Não foi possível carregar os jogadores.'; }
    }

    function scoutSummary(scouts) { const parts = Object.entries(scouts || {}).filter(([, value]) => Number(value) > 0).map(([code, value]) => `${shortScouts[code] || code} ${integer(value)}`); return parts.length ? parts.join(' · ') : 'sem scouts'; }
    function renderSummary(summary) { $('scoutCrossingSummary').innerHTML = [['Média', number(summary.media), true], ['Jogos', integer(summary.jogos)], ['Última', number(summary.ultima_pontuacao)], ['Maior', number(summary.maior_pontuacao)], ['Menor', number(summary.menor_pontuacao)]].map(([label, value, accent]) => `<div class="scx-summary-item${accent ? ' accent' : ''}"><span>${label}</span><strong>${value}</strong></div>`).join(''); }
    function fixtureMarkup(home, away, activeId) {
        const active = Number(activeId); const homeActive = Number(home?.id) === active; const awayActive = Number(away?.id) === active;
        const team = (item, side, isActive) => {
            const label = item?.abreviacao || item?.nome || '—';
            const initials = escapeHtml(String(label).slice(0, 3).toUpperCase());
            const image = item?.escudo
                ? `<img src="${escapeHtml(item.escudo)}" alt="" onerror="this.outerHTML='<span class=\"scx-fixture-fallback\">${initials}</span>'">`
                : `<span class="scx-fixture-fallback">${initials}</span>`;
            return `<span class="scx-fixture-team ${side} ${isActive ? 'active' : 'dim'}">${image}<b>${escapeHtml(label)}</b></span>`;
        };
        return `<span class="scx-fixture-pair">${team(home || {}, 'home', homeActive)}<b class="scx-fixture-vs">×</b>${team(away || {}, 'away', awayActive)}</span>`;
    }
    function renderRecent(matches) {
        const target = $('scoutCrossingRecent'); const played = (matches || []).filter((match) => match.entrou_em_campo === true); if (!played.length) { target.innerHTML = '<div class="scx-muted">Nenhuma pontuação encontrada.</div>'; return; }
        const visible = state.historyExpanded ? played : played.slice(0, 5);
        target.innerHTML = visible.map((match) => `<article class="scx-recent-row"><span class="scx-round">Rodada ${match.rodada}</span><span class="scx-match-copy"><strong>${escapeHtml(match.adversario_nome)}</strong><small>${escapeHtml(match.mando_label)} · ${fixtureMarkup(match.casa, match.fora, match.clube_id)}</small></span><span class="scx-points">${number(match.pontuacao)} <em>(${escapeHtml(scoutSummary(match.scouts))})</em></span></article>`).join('');
        if (played.length > 5) target.innerHTML += `<button type="button" class="scx-history-more" id="scoutCrossingHistoryMore">${state.historyExpanded ? 'Mostrar somente as 5 últimas' : `Mostrar histórico completo (${played.length})`}</button>`;
        $('scoutCrossingHistoryMore')?.addEventListener('click', () => { state.historyExpanded = !state.historyExpanded; renderRecent(played); });
    }
    function renderPositionScouts(scouts) { const target = $('scoutCrossingPositionScouts'); target.innerHTML = scouts?.length ? scouts.map((scout) => `<div class="scx-scout-row"><span><b>${escapeHtml(scout.codigo.toUpperCase())}</b> · ${escapeHtml(scout.nome)}</span><strong>${number(scout.media)}</strong></div>`).join('') : '<div class="scx-muted">Sem referência disponível.</div>'; }
    function renderOpponents(opponents) { const target = $('scoutCrossingOpponents'); target.innerHTML = opponents?.length ? opponents.map((opponent) => `<div class="scx-opponent-row"><div><strong>${escapeHtml(opponent.nome)}</strong><small>${integer(opponent.jogos)} jogo(s)</small></div><strong>${number(opponent.media)} pts</strong></div>`).join('') : '<div class="scx-muted">Nenhum adversário identificado.</div>'; }
    function renderHomeAway(items) { $('scoutCrossingHomeAway').innerHTML = (items || []).map((item) => `<div class="scx-home-row"><div><strong>${item.label}</strong><small>${integer(item.jogos)} jogo(s) com pontuação</small></div><strong>${number(item.media)}</strong></div>`).join(''); }
    function renderConfrontation(data) {
        const target = $('scoutCrossingConfrontation'); const match = data.confronto; const ceded = data.cedidos_adversario || {};
        if (!match) { target.hidden = true; target.innerHTML = ''; return; }
        target.hidden = false; const scouts = Object.entries(ceded.scouts || {}).filter(([, value]) => Number(value) > 0);
        target.innerHTML = `<div class="scx-confrontation-head"><div class="scx-confrontation-title">${fixtureMarkup(match.casa, match.fora, data.jogador.clube_id)}<div><strong>Cedidos do adversário no confronto</strong><small>${escapeHtml(match.mando_label)} · ${integer(ceded.jogos)} jogo(s) anteriores</small></div></div><strong class="scx-confrontation-score">${number(ceded.pontuacao)} pts</strong></div><div class="scx-conceded">${scouts.map(([code, value]) => `<div class="scx-conceded-item"><span>${escapeHtml(shortScouts[code] || code)} · ${escapeHtml(scoutLabels[code] || code)}</span><strong>${number(value)}</strong></div>`).join('') || '<span class="scx-muted">Sem scouts cedidos registrados.</span>'}</div>`;
    }
    function renderPrediction(player) {
        const value = predictionValue(player); $('scoutCrossingPrediction').textContent = `Previsão calculada: ${number(value)} pts`;
        $('scoutCrossingPredictionNote').textContent = `${positionSlug[state.posicaoId] || 'posição'} · calculador específico da posição · rodada atual`;
    }
    function renderCompareOptions() {
        const select = $('scoutCrossingComparePlayer'); if (!select) return;
        select.innerHTML = '<option value="">Escolha outro atleta</option>' + state.players.filter((player) => Number(player.id) !== Number(state.atletaId) && Number(player.posicao_id || state.posicaoId) === Number(state.posicaoId) && player.availability_rule !== 'poupar' && Number(player.status_id) !== 6).sort((a, b) => predictionValue(b) - predictionValue(a)).map((player) => `<option value="${player.id}">${escapeHtml(player.nome)} · ${number(predictionValue(player))} pts</option>`).join('');
    }
    function renderResult(data) {
        state.selectedData = data; $('scoutCrossingEmpty').hidden = true; $('scoutCrossingResults').hidden = false;
        const player = data.jogador; $('scoutCrossingPlayerName').textContent = player.nome || 'Jogador';
        const stats = [`média ${number(player.media_num)}`, `${integer(player.jogos_num)} jogos`, `${number(player.pontos_num)} pts`];
        $('scoutCrossingPlayerMeta').textContent = `${player.posicao || 'Posição'} · ${player.clube_nome || 'Clube'} · Rodada ${data.filtros.rodada} · ${stats.join(' · ')}`;
        const avatar = $('scoutCrossingPlayerAvatar'); const photo = normalizedPhoto(player.foto, player.id); avatar.innerHTML = photo ? `<img src="${escapeHtml(photo)}" alt="${escapeHtml(player.nome)}">` : '<i class="fas fa-user"></i>';
        const image = avatar.querySelector('img'); if (image) image.onerror = () => { image.remove(); avatar.innerHTML = '<i class="fas fa-user"></i>'; };
        renderSummary(data.resumo); renderPrediction(state.players.find((item) => Number(item.id) === Number(player.id)) || player); renderCompareOptions(); renderConfrontation(data); renderRecent(data.ultimas_pontuacoes || []); renderPositionScouts(data.scouts_da_posicao || []); renderOpponents(data.resumo.adversarios || []); renderHomeAway(data.resumo.mando || []);
        document.getElementById('scoutCrossingResults').scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
    async function runCrossing() {
        if (!state.atletaId || !state.posicaoId) return;
        const params = new URLSearchParams({ atleta_id: state.atletaId, posicao_id: state.posicaoId }); setAlert('Calculando o cruzamento...');
        try { const response = await fetch(`${page.dataset.crossingUrl}?${params}`); const data = await response.json(); if (!response.ok) throw new Error(data.error || 'Não foi possível executar o cruzamento.'); state.temporada = Number(data.filtros.temporada); state.rodada = Number(data.filtros.rodada); renderResult(data); setAlert(''); } catch (error) { setAlert(error.message, true); }
    }
    async function comparePlayers() {
        const otherId = Number($('scoutCrossingComparePlayer')?.value || 0); if (!otherId || !state.selectedData) return;
        try { const response = await fetch(`${page.dataset.crossingUrl}?atleta_id=${otherId}&posicao_id=${state.posicaoId}`); const other = await response.json(); if (!response.ok) throw new Error(other.error || 'Comparação indisponível.');
            const first = state.selectedData.jogador; const second = other.jogador; const firstExpected = predictionValue(state.players.find((p) => Number(p.id) === Number(first.id)) || first); const secondExpected = predictionValue(state.players.find((p) => Number(p.id) === Number(second.id)) || second);
            const metrics = [['Previsão', firstExpected, secondExpected], ['Média', first.media_num, second.media_num], ['Pontos', first.pontos_num, second.pontos_num], ['Jogos', first.jogos_num, second.jogos_num], ['Maior nota', state.selectedData.resumo.maior_pontuacao, other.resumo.maior_pontuacao]];
            $('scoutCrossingComparison').hidden = false; $('scoutCrossingComparison').innerHTML = `<div class="scx-comparison-head"><strong>${escapeHtml(first.nome)} × ${escapeHtml(second.nome)}</strong><span class="scx-muted">verde = melhor · vermelho = menor</span></div><div class="scx-comparison-grid">${metrics.map(([label, a, b]) => `<span class="scx-compare-value ${Number(a) >= Number(b) ? 'better' : 'worse'}">${number(a)}</span><span class="scx-compare-label">${label}</span><span class="scx-compare-value ${Number(b) >= Number(a) ? 'better' : 'worse'}">${number(b)}</span>`).join('')}</div>`;
        } catch (error) { setAlert(error.message, true); }
    }
    document.querySelectorAll('.scx-position').forEach((button) => button.addEventListener('click', () => { document.querySelectorAll('.scx-position').forEach((item) => { item.classList.remove('is-selected'); item.setAttribute('aria-selected', 'false'); }); button.classList.add('is-selected'); button.setAttribute('aria-selected', 'true'); state.posicaoId = Number(button.dataset.position); state.atletaId = null; state.historyExpanded = false; loadOptions(); }));
    document.querySelectorAll('[data-status-filter]').forEach((button) => button.addEventListener('click', () => { document.querySelectorAll('[data-status-filter]').forEach((item) => item.classList.remove('is-selected')); button.classList.add('is-selected'); state.statusFilter = button.dataset.statusFilter; renderPlayers(); }));
    ['scoutCrossingSearch'].forEach((id) => $(id)?.addEventListener('input', renderPlayers));
    ['scoutCrossingSort', 'scoutCrossingScout'].forEach((id) => $(id)?.addEventListener('change', renderPlayers)); $('scoutCrossingCompareButton')?.addEventListener('click', comparePlayers);
    $('scoutCrossingPlayer')?.addEventListener('change', (event) => { state.atletaId = Number(event.target.value) || null; renderPlayers(); runCrossing(); });
    state.posicaoId = selectedPosition();
    if (page.dataset.selectedPlayer) state.atletaId = Number(page.dataset.selectedPlayer);
    loadOptions();
}());
