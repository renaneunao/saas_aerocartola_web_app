(function () {
    'use strict';

    const page = document.getElementById('scoutCrossingPage');
    if (!page) return;
    const state = {
        temporada: Number(page.dataset.currentSeason || 0), rodada: Number(page.dataset.currentRound || 0),
        teamIds: [], posicaoId: null, atletaId: null, selectedPlayerIds: [], players: [], filteredPlayers: [],
        statusFilter: 'provaveis', sortBy: 'expected', historyExpanded: false, selectedData: null, predictionContext: null,
        predictionById: {}, filtersTouched: false, crossingVersion: 0
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
    const negativeScouts = new Set(['ca', 'cv', 'fc', 'gs', 'i']);
    const statusOf = (player) => Number(player.source_status_id ?? player.status_id);
    const escapeHtml = (value) => String(value ?? '').replace(/[&<>'"]/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#039;', '"': '&quot;' }[char]));
    const number = (value, digits = 2) => Number.isFinite(Number(value)) ? Number(value).toLocaleString('pt-BR', { minimumFractionDigits: digits, maximumFractionDigits: digits }) : '0,00';
    const integer = (value) => Number.isFinite(Number(value)) ? Math.round(Number(value)).toLocaleString('pt-BR') : '0';
    const $ = (id) => document.getElementById(id);
    const selectedPosition = () => Number(document.querySelector('.scx-position.is-selected')?.dataset.position || state.posicaoId || 5);
    const predictionValue = (player) => Number(state.predictionById[player.id] ?? player.previsao ?? player.pontos_num ?? player.media_num ?? 0);
    const normalizedPhoto = (value, athleteId) => {
        let photo = value || (typeof window.getPlayerImage === 'function' ? window.getPlayerImage(Number(athleteId)) : '') || '';
        if (photo.startsWith('//')) photo = `https:${photo}`;
        // FORMATO.png é uma silhueta válida do Cartola. Só converta o
        // marcador em URLs de foto que realmente usam o padrão de tamanho;
        // transformar a silhueta em 220x220 gera um endereço inexistente.
        if (!/\/silhuetas\/[^/]+\/FORMATO\.png(?:\?|$)/i.test(photo)) {
            photo = photo.replace(/FORMATO/gi, '220x220');
        }
        return photo.startsWith('http://') ? `https://${photo.slice(7)}` : photo;
    };
    function setAlert(message, error = false) { const alert = $('scoutCrossingAlert'); if (!alert) return; alert.hidden = !message; alert.textContent = message || ''; alert.classList.toggle('scx-alert-error', error); }
    function currentClub(id) { const teams = state.lastTeams || []; return teams.find((team) => Number(team.id) === Number(id)) || {}; }

    function teamButton(team, side, fixture) {
        const selected = state.teamIds.includes(Number(team.id));
        const valid = fixture.valido !== false;
        const image = team.escudo ? `<img src="${escapeHtml(team.escudo)}" alt="Escudo de ${escapeHtml(team.nome || team.abreviacao || '')}" loading="lazy">` : '<span class="scx-team-fallback"><i class="fas fa-shield-halved"></i></span>';
        const score = side === 'casa' ? fixture.placar_casa : fixture.placar_fora;
        const scoreMarkup = fixtureScore(score);
        return `<button type="button" class="scx-match-team${selected ? ' is-selected' : ''}" data-team="${team.id}" role="option" aria-selected="${selected}" aria-disabled="${!valid}" title="${escapeHtml(valid ? `Selecionar ${team.nome || team.abreviacao || ''} · ${side === 'casa' ? 'casa' : 'fora'}` : `${team.nome || team.abreviacao || ''} · sem confronto válido`)}"${valid ? '' : ' disabled'}><span class="scx-match-team-side">${side === 'casa' ? 'C' : 'F'}</span>${image}<b>${escapeHtml(team.abreviacao || team.nome || '---')}</b><strong>${escapeHtml(scoreMarkup)}</strong></button>`;
    }
    function fixtureOption(fixture, index) {
        const invalid = fixture.valido === false;
        const status = invalid ? '<small class="scx-match-status">sem jogo válido</small>' : '';
        return `<article class="scx-match-option${invalid ? ' is-invalid' : ''}" data-fixture="${fixture.id}" aria-label="${escapeHtml(`${fixture.casa?.nome || ''} x ${fixture.fora?.nome || ''}`)}"><span class="scx-match-number">${String(index + 1).padStart(2, '0')}</span><div class="scx-match-option-teams">${teamButton(fixture.casa || {}, 'casa', fixture)}<span class="scx-match-option-vs">×</span>${teamButton(fixture.fora || {}, 'fora', fixture)}</div>${status}</article>`;
    }
    function renderTeams(fixtures) {
        const target = $('scoutCrossingTeams'); if (!target) return;
        const matches = fixtures || [];
        state.lastFixtures = matches;
        state.lastTeams = matches.flatMap((fixture) => [fixture.casa, fixture.fora]);
        target.innerHTML = matches.length ? matches.map(fixtureOption).join('') : '<span class="scx-muted">Nenhum confronto encontrado na rodada atual.</span>';
        target.querySelectorAll('[data-team]').forEach((button) => button.addEventListener('click', () => {
            const clicked = Number(button.dataset.team);
            state.teamIds = state.teamIds.includes(clicked)
                ? state.teamIds.filter((id) => id !== clicked)
                : [...state.teamIds, clicked];
            // Mantém o primeiro atleta como referência para que seja possível
            // selecionar o segundo depois de adicionar outro clube ao filtro.
            if (state.selectedPlayerIds.length > 1) {
                state.selectedPlayerIds = [state.selectedPlayerIds[0]];
                state.atletaId = state.selectedPlayerIds[0];
            }
            state.historyExpanded = false;
            state.filtersTouched = true;
            resetAnalysis();
            loadOptions();
        }));
    }
    function statusClass(player) {
        if (player.availability_rule === 'cravado') return 'scx-status-lock';
        if (statusOf(player) === 7) return 'scx-status-probable';
        if ([2, 3, 5].includes(statusOf(player))) return 'scx-status-doubt';
        return 'scx-status-out';
    }
    function statusText(player) { return player.availability_rule === 'cravado' ? 'Cravado' : player.status_nome || 'Status'; }
    function playerOption(player) {
        const photo = normalizedPhoto(player.foto, player.id);
        const initials = escapeHtml((player.nome || '?').slice(0, 2).toUpperCase());
        const avatar = photo ? `<img src="${escapeHtml(photo)}" alt="" loading="eager" decoding="async" data-fallback="${initials}">` : `<span class="scx-player-option-avatar">${initials}</span>`;
        const selectedIndex = state.selectedPlayerIds.indexOf(Number(player.id));
        const selected = selectedIndex >= 0;
        const selectionClass = selected ? (selectedIndex === 0 ? ' is-selected is-primary' : ' is-selected is-secondary') : '';
        const selectionLabel = selectedIndex === 0 ? '1º jogador selecionado' : selectedIndex === 1 ? '2º jogador selecionado' : '';
        return `<button type="button" class="scx-player-option${selectionClass}" data-player="${player.id}" title="${selectionLabel || 'Selecionar para o comparativo'}">${avatar}<span class="scx-player-option-identity"><strong>${escapeHtml(player.nome)}</strong><small>${escapeHtml(player.clube_abrev || player.clube_nome || 'Clube')} · <span class="${statusClass(player)} scx-status">${escapeHtml(statusText(player))}</span></small></span><span class="scx-player-option-stat scx-player-option-expected"><small>Previsão</small><b>${number(predictionValue(player))}</b></span><span class="scx-player-option-stat"><small>Média</small><b>${number(player.media_num)}</b></span><span class="scx-player-option-stat scx-player-option-price"><small>Preço</small><b>C$ ${number(player.preco_num)}</b></span><span class="scx-player-option-stat scx-player-option-games"><small>Jogos</small><b>${integer(player.jogos_num)}</b></span></button>`;
    }
    function filterPlayers() {
        const text = ($('scoutCrossingSearch')?.value || '').trim().toLocaleLowerCase();
        const scout = $('scoutCrossingScout')?.value || '';
        const filtered = (state.players || []).filter((player) => {
            if (state.teamIds.length && !state.teamIds.includes(Number(player.clube_id))) return false;
            // Nulos nunca jogam e não entram na análise. Atletas poupados
            // permanecem visíveis em “Todos” para que a regra possa ser
            // conferida, mas nunca aparecem no filtro inicial de prováveis.
            if (statusOf(player) === 6) return false;
            if (state.statusFilter === 'provaveis' && (player.availability_rule === 'poupar' || (statusOf(player) !== 7 && player.availability_rule !== 'cravado'))) return false;
            if (state.statusFilter === 'cravados' && player.availability_rule !== 'cravado') return false;
            if (state.statusFilter === 'duvidas' && ![2, 3, 5].includes(statusOf(player))) return false;
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

    function renderSelectionTray() {
        const target = $('scoutCrossingSelectionTray');
        if (!target) return;
        const selected = state.selectedPlayerIds
            .map((id) => state.players.find((player) => Number(player.id) === Number(id)))
            .filter(Boolean);
        if (!selected.length) {
            target.hidden = true;
            target.innerHTML = '';
            return;
        }
        target.hidden = false;
        target.innerHTML = `<div class="scx-selection-tray-copy"><strong>${selected.length}/2 jogadores selecionados</strong><small>${selected.length === 1 ? 'Escolha outro atleta, inclusive de outro time, para iniciar o comparativo.' : 'O comparativo é atualizado automaticamente.'}</small></div><div class="scx-selection-tray-players">${selected.map((player, index) => {
            const photo = normalizedPhoto(player.foto, player.id);
            const initials = escapeHtml((player.nome || '?').slice(0, 2).toUpperCase());
            const avatar = photo ? `<img src="${escapeHtml(photo)}" alt="" loading="eager">` : `<span>${initials}</span>`;
            return `<span class="scx-selection-tray-player"><span class="scx-selection-tray-number">${index + 1}</span><span class="scx-selection-tray-avatar">${avatar}</span><strong>${escapeHtml(player.nome)}</strong><small>${escapeHtml(player.clube_abrev || player.clube_nome || '')}</small></span>`;
        }).join('')}</div>`;
    }

    function selectPlayer(playerId) {
        const alreadySelected = state.selectedPlayerIds.includes(Number(playerId));
        if (alreadySelected) {
            // Ao tocar em um dos dois selecionados, ele vira o primeiro e o
            // usuário pode escolher imediatamente um novo adversário.
            state.selectedPlayerIds = [Number(playerId)];
        } else if (state.selectedPlayerIds.length === 0) {
            state.selectedPlayerIds = [Number(playerId)];
        } else if (state.selectedPlayerIds.length === 1) {
            state.selectedPlayerIds = [...state.selectedPlayerIds, Number(playerId)];
        } else {
            state.selectedPlayerIds = [state.selectedPlayerIds[0], Number(playerId)];
        }
        state.atletaId = state.selectedPlayerIds[0] || null;
        state.historyExpanded = false;
        resetAnalysis();
        renderPlayers();
        if (state.selectedPlayerIds.length === 2) runSelectedComparison();
    }

    function renderPlayers() {
        filterPlayers();
        const target = $('scoutCrossingPlayers'); if (!target) return;
        if (!state.filtersTouched && !state.selectedPlayerIds.length) {
            state.filteredPlayers = [];
            target.innerHTML = '<div class="scx-filter-prompt"><i class="fas fa-filter"></i><strong>Refine a busca para escolher um atleta</strong><span>Selecione um time, pesquise pelo nome ou escolha outro filtro acima.</span></div>';
            $('scoutCrossingSelectionHint').textContent = 'A lista aparece depois que você aplicar um filtro.';
            renderSelectionTray();
            return;
        }
        target.innerHTML = state.filteredPlayers.length ? state.filteredPlayers.map(playerOption).join('') : '<div class="scx-muted">Nenhum atleta atende aos filtros atuais.</div>';
        target.querySelectorAll('img[data-fallback]').forEach((image) => image.addEventListener('error', () => {
            const fallback = document.createElement('span'); fallback.className = 'scx-player-option-avatar'; fallback.textContent = image.dataset.fallback; image.replaceWith(fallback);
        }, { once: true }));
        target.querySelectorAll('[data-player]').forEach((button) => button.addEventListener('click', () => selectPlayer(Number(button.dataset.player))));
        $('scoutCrossingSelectionHint').textContent = state.selectedPlayerIds.length === 1
            ? `${state.filteredPlayers.length} atleta(s) no filtro · agora selecione o segundo jogador para comparar.`
            : state.selectedPlayerIds.length >= 2
                ? 'Dois atletas selecionados · comparativo atualizado automaticamente abaixo.'
                : `${state.filteredPlayers.length} atleta(s) no filtro · selecione dois jogadores para comparar.`;
        renderSelectionTray();
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
        setAlert('Carregando atletas da rodada...');
        try {
            const response = await fetch(`${page.dataset.optionsUrl}?${params}`); const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Não foi possível carregar as opções.');
            state.temporada = Number(data.temporada); state.rodada = Number(data.rodada); state.lastTeams = data.times || [];
            if (page.dataset.selectedPlayer && !state.selectedPlayerIds.length && data.jogadores?.some((player) => Number(player.id) === Number(page.dataset.selectedPlayer))) {
                state.selectedPlayerIds = [Number(page.dataset.selectedPlayer)];
                state.atletaId = Number(page.dataset.selectedPlayer);
            }
            renderTeams(data.confrontos || []); state.players = data.jogadores || []; state.predictionById = {};
            renderScoutFilter(); renderHiddenPlayerSelect(); renderPlayers(); setAlert('');
            await loadPredictionContext();
        } catch (error) { setAlert(error.message, true); $('scoutCrossingSelectionHint').textContent = 'Não foi possível carregar os jogadores.'; }
    }

    function scoutSummary(scouts) {
        const entries = Object.entries(scouts || {})
            .filter(([, value]) => Number.isFinite(Number(value)) && Number(value) !== 0)
            .map(([code, value]) => {
                const raw = Number(value) || 0;
                const negative = negativeScouts.has(code) || raw < 0;
                return {
                    code,
                    negative,
                    label: shortScouts[code] || code.toUpperCase(),
                    value: `${negative ? '-' : ''}${integer(Math.abs(raw))}`
                };
            });
        if (!entries.length) return '<span class="scx-scouts-empty">sem scouts</span>';
        const markup = (negative) => entries.filter((entry) => entry.negative === negative)
            .map((entry) => `<span title="${escapeHtml(scoutLabels[entry.code] || entry.code)}"><b>${escapeHtml(entry.label)}</b> ${entry.value}</span>`)
            .join('');
        return `<span class="scx-scouts-positive">${markup(false)}</span><span class="scx-scouts-negative">${markup(true)}</span>`;
    }
    function renderSummary(summary) { $('scoutCrossingSummary').innerHTML = [['Média', number(summary.media), true], ['Jogos', integer(summary.jogos)], ['Última', number(summary.ultima_pontuacao)], ['Maior', number(summary.maior_pontuacao)], ['Menor', number(summary.menor_pontuacao)]].map(([label, value, accent]) => `<div class="scx-summary-item${accent ? ' accent' : ''}"><span>${label}</span><strong>${value}</strong></div>`).join(''); }
    function fixtureScore(value) {
        const parsed = Number(value);
        return value !== null && value !== undefined && value !== '' && Number.isFinite(parsed) ? String(Math.round(parsed)) : '—';
    }
    function fixtureMarkup(home, away, activeId, scoreHome = null, scoreAway = null) {
        const active = Number(activeId); const homeActive = Number(home?.id) === active; const awayActive = Number(away?.id) === active;
        const team = (item, side, isActive) => {
            const label = item?.abreviacao || item?.nome || '—';
            const initials = escapeHtml(String(label).slice(0, 3).toUpperCase());
            const image = item?.escudo
                ? `<img src="${escapeHtml(item.escudo)}" alt="" data-scx-fixture-shield><span class="scx-fixture-fallback" hidden>${initials}</span>`
                : `<span class="scx-fixture-fallback">${initials}</span>`;
            return side === 'home'
                ? `<span class="scx-fixture-team ${side} ${isActive ? 'active' : 'dim'}"><b>${escapeHtml(label)}</b>${image}</span>`
                : `<span class="scx-fixture-team ${side} ${isActive ? 'active' : 'dim'}">${image}<b>${escapeHtml(label)}</b></span>`;
        };
        return `<span class="scx-fixture-pair">${team(home || {}, 'home', homeActive)}<b class="scx-fixture-score">${fixtureScore(scoreHome)}</b><b class="scx-fixture-vs">×</b><b class="scx-fixture-score">${fixtureScore(scoreAway)}</b>${team(away || {}, 'away', awayActive)}</span>`;
    }
    function bindFixtureFallbacks(root) {
        root?.querySelectorAll('img[data-scx-fixture-shield]').forEach((image) => {
            image.addEventListener('error', () => {
                image.hidden = true;
                if (image.nextElementSibling?.classList.contains('scx-fixture-fallback')) image.nextElementSibling.hidden = false;
            }, { once: true });
        });
    }
    function renderRecent(matches) {
        const target = $('scoutCrossingRecent');
        const currentRound = Number(state.rodada || 0);
        const played = (matches || []).filter((match) => match.entrou_em_campo === true && (!currentRound || Number(match.rodada) < currentRound));
        const renderColumn = (mando) => {
            const list = played.filter((match) => match.mando === mando).sort((a, b) => Number(b.rodada) - Number(a.rodada));
            const visible = state.historyExpanded ? list : list.slice(0, 5);
            return visible.length
                ? visible.map((match) => `<article class="scx-recent-row scx-recent-row-${mando}"><span class="scx-round">Rodada ${match.rodada}</span><span class="scx-match-copy"><strong>${escapeHtml(match.adversario_nome)}</strong><span class="scx-match-fixture">${fixtureMarkup(match.casa, match.fora, match.clube_id, match.placar_casa, match.placar_fora)}</span></span><span class="scx-points">${number(match.pontuacao)}<span class="scx-point-scouts">${scoutSummary(match.scouts)}</span></span></article>`).join('')
                : '<div class="scx-muted">Nenhuma pontuação encontrada.</div>';
        };
        const home = $('scoutCrossingRecentHome');
        const away = $('scoutCrossingRecentAway');
        if (home && away) {
            home.innerHTML = renderColumn('casa');
            away.innerHTML = renderColumn('fora');
            bindFixtureFallbacks(target);
        } else if (target) {
            target.innerHTML = played.length ? renderColumn('casa') + renderColumn('fora') : '<div class="scx-muted">Nenhuma pontuação encontrada.</div>';
        }
        if (target && played.length > 5) target.insertAdjacentHTML('beforeend', `<button type="button" class="scx-history-more" id="scoutCrossingHistoryMore">${state.historyExpanded ? 'Mostrar somente as 5 últimas' : `Mostrar histórico completo (${played.length})`}</button>`);
        bindFixtureFallbacks(target);
        $('scoutCrossingHistoryMore')?.addEventListener('click', () => { state.historyExpanded = !state.historyExpanded; renderRecent(played); });
    }
    function renderPositionScouts(scouts) { const target = $('scoutCrossingPositionScouts'); target.innerHTML = scouts?.length ? scouts.map((scout) => `<div class="scx-scout-row"><span><b>${escapeHtml(scout.codigo.toUpperCase())}</b> · ${escapeHtml(scout.nome)}</span><strong>${number(scout.media)}</strong></div>`).join('') : '<div class="scx-muted">Sem referência disponível.</div>'; }
    function renderOpponents(opponents) { const target = $('scoutCrossingOpponents'); target.innerHTML = opponents?.length ? opponents.map((opponent) => `<div class="scx-opponent-row"><div><strong>${escapeHtml(opponent.nome)}</strong><small>${integer(opponent.jogos)} jogo(s)</small></div><strong>${number(opponent.media)} pts</strong></div>`).join('') : '<div class="scx-muted">Nenhum adversário identificado.</div>'; }
    function renderHomeAway(items) { $('scoutCrossingHomeAway').innerHTML = (items || []).map((item) => `<div class="scx-home-row"><div><strong>${item.label}</strong><small>${integer(item.jogos)} jogo(s) com pontuação</small></div><strong>${number(item.media)}</strong></div>`).join(''); }
    function cededProfileMarkup(profile, compact = false) {
        const fallback = { jogos_com_dados: 0, pontuacao_por_jogo: 0, pontuacao_por_atleta: 0, pico: 0, scouts_detalhados: [], recorrencia: {} };
        const summary = profile?.por_mando?.[profile?.mando_relevante] || profile?.por_mando?.casa || profile?.por_mando?.fora || fallback;
        const metrics = `<div class="scx-ceded-metrics"><span><small>Jogos</small><b>${integer(summary.jogos_com_dados)}</b></span><span><small>Pts/jogo</small><b>${number(summary.pontuacao_por_jogo)}</b></span><span><small>Pts/atleta</small><b>${number(summary.pontuacao_por_atleta)}</b></span><span><small>Pico</small><b>${number(summary.pico)}</b></span></div>`;
        const thresholds = `<div class="scx-ceded-thresholds"><span>≥5 <b>${integer(summary.recorrencia?.['5'] || 0)}%</b></span><span>≥8 <b>${integer(summary.recorrencia?.['8'] || 0)}%</b></span><span>≥12 <b>${integer(summary.recorrencia?.['12'] || 0)}%</b></span></div>`;
        const scouts = (summary.scouts_detalhados || []).filter((item) => Math.round(Math.abs(Number(item.media_por_jogo) || 0)) > 0).map((item) => `<div class="scx-ceded-scout-row ${negativeScouts.has(item.codigo) ? 'is-negative' : 'is-positive'}"><span><b>${escapeHtml(shortScouts[item.codigo] || item.codigo.toUpperCase())}</b> ${escapeHtml(item.nome || '')}</span><strong>${integer(Math.abs(item.media_por_jogo || 0))}<small>${integer(item.recorrencia || 0)}% dos jogos</small></strong></div>`).join('') || '<span class="scx-muted">Nenhum scout positivo no recorte.</span>';
        if (compact) return `${metrics}${thresholds}<div class="scx-ceded-scouts">${scouts}</div>`;
        const games = (summary.historico || []).slice(0, 8).map((game) => {
            const players = (game.jogadores || []).map((player) => {
                const photo = normalizedPhoto(player.foto, player.id);
                const avatar = photo ? `<img src="${escapeHtml(photo)}" alt="" loading="lazy">` : '<i class="fas fa-user"></i>';
                return `<div class="scx-ceded-player"><span class="scx-ceded-player-avatar">${avatar}</span><strong>${escapeHtml(player.nome || 'Atleta')}</strong><span class="scx-ceded-player-scouts">${scoutSummary(player.scouts)}</span><b>${number(player.pontuacao)} pts</b></div>`;
            }).join('') || '<span class="scx-muted">Sem atleta da posição com dados.</span>';
            return `<details class="scx-ceded-game"><summary><span class="scx-ceded-game-round">Rodada ${integer(game.rodada)}</span><span class="scx-ceded-game-fixture">${fixtureMarkup(game.casa, game.fora, game.clube_id, game.placar_casa, game.placar_fora)}</span><span class="scx-ceded-game-scouts">${scoutSummary(game.scouts)}</span><strong>${number(game.pontuacao)} pts</strong><i class="fas fa-chevron-down" aria-hidden="true"></i></summary><div class="scx-ceded-player-list">${players}</div></details>`;
        }).join('');
        return `${metrics}${thresholds}<div class="scx-ceded-scouts">${scouts}</div><div class="scx-ceded-games">${games || '<span class="scx-muted">Sem partidas no recorte.</span>'}</div>`;
    }
    function renderConfrontation(data) {
        const target = $('scoutCrossingConfrontation'); const match = data.confronto; const ceded = data.cedidos_adversario || {};
        if (!match) { target.hidden = true; target.innerHTML = ''; return; }
        target.hidden = false;
        const relevant = ceded.mando_relevante ? `Adversário como ${ceded.mando_relevante === 'casa' ? 'mandante' : 'visitante'}` : 'Todos os mandos';
        target.innerHTML = `<div class="scx-confrontation-head"><div class="scx-confrontation-title">${fixtureMarkup(match.casa, match.fora, data.jogador.clube_id, match.placar_casa, match.placar_fora)}<div><strong>O que ${escapeHtml(match.adversario?.abreviacao || match.adversario?.nome || 'o adversário')} cede à posição</strong><small>${escapeHtml(match.mando_label)} para o jogador · ${escapeHtml(relevant)} · somente rodadas anteriores</small></div></div><strong class="scx-confrontation-score">${number(ceded.pontuacao)} pts/jogo</strong></div><div class="scx-conceded-profile">${cededProfileMarkup(ceded)}</div>`;
        bindFixtureFallbacks(target);
    }
    function renderPrediction(player) {
        const value = predictionValue(player); $('scoutCrossingPrediction').textContent = `Previsão calculada: ${number(value)} pts`;
        $('scoutCrossingPredictionNote').textContent = `${positionSlug[state.posicaoId] || 'posição'} · calculador específico da posição · rodada atual`;
    }
    function renderCompareOptions() {
        const select = $('scoutCrossingComparePlayer'); if (!select) return;
        select.innerHTML = '<option value="">Escolha outro atleta</option>' + state.players.filter((player) => Number(player.id) !== Number(state.atletaId) && Number(player.posicao_id || state.posicaoId) === Number(state.posicaoId) && player.availability_rule !== 'poupar' && statusOf(player) !== 6).sort((a, b) => predictionValue(b) - predictionValue(a)).map((player) => `<option value="${player.id}">${escapeHtml(player.nome)} · ${number(predictionValue(player))} pts</option>`).join('');
    }
    function resetAnalysis() {
        state.crossingVersion += 1;
        state.selectedData = null;
        $('scoutCrossingEmpty')?.setAttribute('hidden', '');
        $('scoutCrossingResults')?.setAttribute('hidden', '');
        const comparison = $('scoutCrossingComparison');
        if (comparison) { comparison.hidden = true; comparison.innerHTML = ''; }
        $('scoutCrossingSingleAnalysis')?.setAttribute('hidden', '');
    }

    function renderResult(data) {
        state.selectedData = data; $('scoutCrossingEmpty').hidden = true; $('scoutCrossingResults').hidden = false;
        const comparison = $('scoutCrossingComparison');
        if (comparison) { comparison.hidden = true; comparison.innerHTML = ''; }
        $('scoutCrossingSingleAnalysis')?.removeAttribute('hidden');
        const player = data.jogador; $('scoutCrossingPlayerName').textContent = player.nome || 'Jogador';
        const stats = [`média ${number(player.media_num)}`, `${integer(player.jogos_num)} jogos`, `${number(player.pontos_num)} pts`];
        $('scoutCrossingPlayerMeta').textContent = `${player.posicao || 'Posição'} · ${player.clube_nome || 'Clube'} · Rodada ${data.filtros.rodada} · ${stats.join(' · ')}`;
        const avatar = $('scoutCrossingPlayerAvatar'); const photo = normalizedPhoto(player.foto, player.id); avatar.innerHTML = photo ? `<img src="${escapeHtml(photo)}" alt="${escapeHtml(player.nome)}">` : '<i class="fas fa-user"></i>';
        const image = avatar.querySelector('img'); if (image) image.onerror = () => { image.remove(); avatar.innerHTML = '<i class="fas fa-user"></i>'; };
        renderSummary(data.resumo); renderPrediction(state.players.find((item) => Number(item.id) === Number(player.id)) || player); renderCompareOptions(); renderConfrontation(data); renderRecent(data.ultimas_pontuacoes || []); renderPositionScouts(data.scouts_da_posicao || []); renderOpponents(data.resumo.adversarios || []); renderHomeAway(data.resumo.mando || []);
        document.getElementById('scoutCrossingResults').scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
    function comparisonScoutRows(scouts) {
        return (scouts || []).map((scout) => `<div class="scx-side-scout"><span><b>${escapeHtml(scout.codigo?.toUpperCase() || '')}</b> · ${escapeHtml(scout.nome || '')}</span><strong>${number(scout.media)}</strong></div>`).join('') || '<div class="scx-muted">Sem referência disponível.</div>';
    }

    function comparisonHistory(data, mando) {
        const currentRound = Number(data.filtros?.rodada || state.rodada || 0);
        const matches = (data.ultimas_pontuacoes || []).filter((match) => match.entrou_em_campo === true && Number(match.rodada) < currentRound && match.mando === mando).slice(0, 5);
        if (!matches.length) return '<div class="scx-muted">Sem jogos registrados.</div>';
        return matches.map((match) => `<article class="scx-side-history-row"><span>Rodada ${match.rodada}</span><div><span class="scx-match-fixture">${fixtureMarkup(match.casa, match.fora, match.clube_id, match.placar_casa, match.placar_fora)}</span><small>${escapeHtml(match.adversario_nome || '')}</small></div><strong>${number(match.pontuacao)}<em>${scoutSummary(match.scouts)}</em></strong></article>`).join('');
    }

    function comparisonCeded(data) {
        const ceded = data.cedidos_adversario || {};
        return ceded.por_mando ? cededProfileMarkup(ceded) : '<span class="scx-muted">Sem scouts cedidos registrados.</span>';
    }

    function comparisonMatchup(data, player) {
        const match = data.confronto;
        if (!match) return '<div class="scx-side-matchup-empty">Sem confronto válido na rodada atual.</div>';
        const ownId = Number(player?.clube_id || data.jogador?.clube_id);
        const own = Number(match.casa?.id) === ownId ? match.casa : match.fora;
        const defense = [1, 2, 3].includes(Number(state.posicaoId));
        const favoritismo = Number(own?.favoritismo || 0);
        const favoritismoPercent = Math.max(0, Math.min(100, Number(own?.favoritismo_percent || 0)));
        const saldo = Number(own?.saldo || 0);
        const saldoPercent = Math.max(0, Math.min(100, Number(own?.saldo_percent || 0)));
        const signal = (label, value, percent, kind, title) => `<span class="scx-side-signal scx-side-signal-${kind}" title="${escapeHtml(title)}"><span><b>${label}</b> ${number(value)}</span><i><em style="width:${percent.toFixed(0)}%"></em></i></span>`;
        return `<div class="scx-side-matchup"><div class="scx-side-matchup-fixture">${fixtureMarkup(match.casa, match.fora, ownId, match.placar_casa, match.placar_fora)}</div><div class="scx-side-matchup-signals">${signal('F', favoritismo, favoritismoPercent, 'favorite', `Favoritismo do ${own?.nome || 'time'} pelo perfil de jogo`)}${defense ? signal('SG', saldoPercent, saldoPercent, 'sg', `Chance de saldo de gols do ${own?.nome || 'time'}`) : ''}</div></div>`;
    }

    function comparisonSide(data, prediction, comparisonMetrics = {}) {
        const player = data.jogador || {};
        const photo = normalizedPhoto(player.foto, player.id);
        const avatar = photo ? `<img src="${escapeHtml(photo)}" alt="${escapeHtml(player.nome || '')}" onerror="this.replaceWith(document.createTextNode(''))">` : '<i class="fas fa-user"></i>';
        const summary = data.resumo || {};
        const metric = (label, value, key, formatter = number) => {
            const other = Number(comparisonMetrics[key]);
            const current = Number(value);
            const tone = Number.isFinite(other) && current !== other ? (current > other ? 'better' : 'worse') : '';
            return `<div class="${tone}"><span>${label}</span><strong>${formatter(value)}</strong></div>`;
        };
        return `<article class="scx-comparison-side"><div class="scx-side-identity-row"><header class="scx-comparison-side-head"><div class="scx-avatar">${avatar}</div><div><p class="scx-overline">Jogador analisado</p><h3>${escapeHtml(player.nome || 'Jogador')}</h3><small>${escapeHtml(player.posicao || '')} · ${escapeHtml(player.clube_nome || '')}</small></div></header>${comparisonMatchup(data, player)}</div><div class="scx-side-metrics">${metric('Previsão', prediction, 'prediction')}${metric('Média', summary.media, 'average')}${metric('Jogos', summary.jogos, 'games', integer)}${metric('Maior', summary.maior_pontuacao, 'highest')}</div><div class="scx-side-section"><h4>Últimas pontuações</h4><div class="scx-side-history-columns"><div><span class="scx-side-column-label">Em casa</span>${comparisonHistory(data, 'casa')}</div><div><span class="scx-side-column-label">Fora</span>${comparisonHistory(data, 'fora')}</div></div></div><div class="scx-side-section"><h4>Cedidos no confronto atual</h4><div class="scx-side-ceded">${comparisonCeded(data)}</div></div><div class="scx-side-section"><h4>Principais scouts da posição</h4><div class="scx-side-scouts">${comparisonScoutRows(data.scouts_da_posicao)}</div></div></article>`;
    }

    function renderComparison(first, second) {
        const comparison = $('scoutCrossingComparison');
        if (!comparison) return;
        const firstPlayer = state.players.find((player) => Number(player.id) === Number(first.jogador?.id)) || first.jogador;
        const secondPlayer = state.players.find((player) => Number(player.id) === Number(second.jogador?.id)) || second.jogador;
        const firstMetrics = { prediction: predictionValue(firstPlayer), average: first.resumo?.media, games: first.resumo?.jogos, highest: first.resumo?.maior_pontuacao };
        const secondMetrics = { prediction: predictionValue(secondPlayer), average: second.resumo?.media, games: second.resumo?.jogos, highest: second.resumo?.maior_pontuacao };
        $('scoutCrossingEmpty')?.setAttribute('hidden', '');
        $('scoutCrossingResults')?.removeAttribute('hidden');
        $('scoutCrossingPrediction').textContent = 'Comparativo pronto';
        $('scoutCrossingPredictionNote').textContent = `${firstPlayer.nome || 'Jogador'} × ${secondPlayer.nome || 'Jogador'} · dados da rodada atual`;
        comparison.hidden = false;
        $('scoutCrossingSingleAnalysis')?.setAttribute('hidden', '');
        comparison.innerHTML = `<div class="scx-comparison-head"><div><p class="scx-overline">Comparativo da posição</p><h2>Leitura lado a lado</h2><span>Verde indica o melhor indicador entre os dois atletas.</span></div><button type="button" class="scx-button" data-clear-comparison><i class="fas fa-arrows-rotate"></i> Trocar seleção</button></div><div class="scx-comparison-grid scx-comparison-sides">${comparisonSide(first, firstMetrics.prediction, secondMetrics)}${comparisonSide(second, secondMetrics.prediction, firstMetrics)}</div>`;
        comparison.querySelector('[data-clear-comparison]')?.addEventListener('click', () => {
            state.selectedPlayerIds = state.selectedPlayerIds.length ? [state.selectedPlayerIds[0]] : [];
            state.atletaId = state.selectedPlayerIds[0] || null;
            state.historyExpanded = false;
            resetAnalysis();
            renderPlayers();
        });
        comparison.querySelectorAll('img').forEach((image) => image.addEventListener('error', () => image.remove(), { once: true }));
    }

    async function runCrossing() {
        if (!state.atletaId || !state.posicaoId) return;
        const version = ++state.crossingVersion;
        const params = new URLSearchParams({ atleta_id: state.atletaId, posicao_id: state.posicaoId }); setAlert('Calculando o cruzamento...');
        try { const response = await fetch(`${page.dataset.crossingUrl}?${params}`); const data = await response.json(); if (version !== state.crossingVersion) return; if (!response.ok) throw new Error(data.error || 'Não foi possível executar o cruzamento.'); state.temporada = Number(data.filtros.temporada); state.rodada = Number(data.filtros.rodada); renderResult(data); setAlert(''); } catch (error) { if (version === state.crossingVersion) setAlert(error.message, true); }
    }
    async function runSelectedComparison() {
        if (state.selectedPlayerIds.length !== 2 || !state.posicaoId) return;
        const version = ++state.crossingVersion;
        setAlert('Comparando os dois atletas...');
        try {
            const responses = await Promise.all(state.selectedPlayerIds.map(async (playerId) => {
                const params = new URLSearchParams({ atleta_id: playerId, posicao_id: state.posicaoId });
                const response = await fetch(`${page.dataset.crossingUrl}?${params}`);
                const data = await response.json();
                return { response, data };
            }));
            if (version !== state.crossingVersion) return;
            const failed = responses.find(({ response }) => !response.ok);
            if (failed) throw new Error(failed.data.error || 'Não foi possível executar o comparativo.');
            const [first, second] = responses.map(({ data }) => data);
            state.selectedData = first;
            state.temporada = Number(first.filtros?.temporada || state.temporada);
            state.rodada = Number(first.filtros?.rodada || state.rodada);
            renderComparison(first, second);
            setAlert('');
            $('scoutCrossingResults')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
        } catch (error) {
            if (version === state.crossingVersion) setAlert(error.message, true);
        }
    }
    async function comparePlayers() {
        const otherId = Number($('scoutCrossingComparePlayer')?.value || 0); if (!otherId || !state.selectedData) return;
        try { const response = await fetch(`${page.dataset.crossingUrl}?atleta_id=${otherId}&posicao_id=${state.posicaoId}`); const other = await response.json(); if (!response.ok) throw new Error(other.error || 'Comparação indisponível.');
            const first = state.selectedData.jogador; const second = other.jogador; const firstExpected = predictionValue(state.players.find((p) => Number(p.id) === Number(first.id)) || first); const secondExpected = predictionValue(state.players.find((p) => Number(p.id) === Number(second.id)) || second);
            const metrics = [['Previsão', firstExpected, secondExpected], ['Média', first.media_num, second.media_num], ['Pontos', first.pontos_num, second.pontos_num], ['Jogos', first.jogos_num, second.jogos_num], ['Maior nota', state.selectedData.resumo.maior_pontuacao, other.resumo.maior_pontuacao]];
            renderComparison(state.selectedData, other);
        } catch (error) { setAlert(error.message, true); }
    }
    document.querySelectorAll('.scx-position').forEach((button) => button.addEventListener('click', () => { document.querySelectorAll('.scx-position').forEach((item) => { item.classList.remove('is-selected'); item.setAttribute('aria-selected', 'false'); }); button.classList.add('is-selected'); button.setAttribute('aria-selected', 'true'); state.posicaoId = Number(button.dataset.position); state.atletaId = null; state.selectedPlayerIds = []; state.historyExpanded = false; state.filtersTouched = false; resetAnalysis(); loadOptions(); }));
    document.querySelectorAll('[data-status-filter]').forEach((button) => button.addEventListener('click', () => { document.querySelectorAll('[data-status-filter]').forEach((item) => item.classList.remove('is-selected')); button.classList.add('is-selected'); state.statusFilter = button.dataset.statusFilter; state.filtersTouched = true; renderPlayers(); }));
    ['scoutCrossingSearch'].forEach((id) => $(id)?.addEventListener('input', () => { state.filtersTouched = true; renderPlayers(); }));
    ['scoutCrossingSort', 'scoutCrossingScout'].forEach((id) => $(id)?.addEventListener('change', () => { state.filtersTouched = true; renderPlayers(); }));
    $('scoutCrossingPlayer')?.addEventListener('change', (event) => {
        const playerId = Number(event.target.value) || null;
        state.selectedPlayerIds = playerId ? [playerId] : [];
        state.atletaId = playerId;
        state.filtersTouched = true;
        resetAnalysis();
        renderPlayers();
    });
    state.posicaoId = selectedPosition();
    if (page.dataset.selectedPlayer) state.atletaId = Number(page.dataset.selectedPlayer);
    loadOptions();
}());
