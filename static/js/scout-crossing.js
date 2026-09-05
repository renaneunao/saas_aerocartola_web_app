(function () {
    'use strict';

    const page = document.getElementById('scoutCrossingPage');
    const modal = document.getElementById('modalScoutCrossingDetail');
    const state = { temporada: null, rodada: null, atletaId: null, posicaoId: null };
    const scoutLabels = {
        a: 'Assistências', ca: 'Cartões amarelos', cv: 'Cartões vermelhos', de: 'Defesas', ds: 'Desarmes',
        fc: 'Faltas cometidas', fd: 'Finalizações defendidas', ff: 'Finalizações para fora', fs: 'Faltas sofridas',
        g: 'Gols', gs: 'Gols sofridos', i: 'Impedimentos', sg: 'Saldo de gols'
    };

    function escapeHtml(value) {
        return String(value ?? '').replace(/[&<>'"]/g, (char) => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#039;', '"': '&quot;'
        }[char]));
    }

    function number(value, digits = 2) {
        const parsed = Number(value);
        return Number.isFinite(parsed) ? parsed.toLocaleString('pt-BR', {
            minimumFractionDigits: digits, maximumFractionDigits: digits
        }) : '0,00';
    }

    function integer(value) {
        const parsed = Number(value);
        return Number.isFinite(parsed) ? Math.round(parsed).toLocaleString('pt-BR') : '0';
    }

    function formatDate(value) {
        if (!value) return 'Data não informada';
        const date = new Date(value);
        return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleDateString('pt-BR');
    }

    function setAlert(message, isError = false) {
        const alert = document.getElementById('scoutCrossingAlert');
        if (!alert) return;
        alert.hidden = !message;
        alert.textContent = message || '';
        alert.classList.toggle('scout-crossing-alert-error', isError);
    }

    function selectValue(id) {
        return document.getElementById(id)?.value || '';
    }

    function renderOptions(selectId, items, placeholder, valueKey, labelFn) {
        const select = document.getElementById(selectId);
        if (!select) return;
        select.innerHTML = `<option value="">${escapeHtml(placeholder)}</option>` + items.map((item) => {
            const value = item[valueKey];
            return `<option value="${escapeHtml(value)}">${escapeHtml(labelFn(item))}</option>`;
        }).join('');
    }

    function setRoundOptions(rounds, selectedRound) {
        const select = document.getElementById('scoutCrossingRound');
        if (!select) return;
        select.innerHTML = rounds.map((round) => `<option value="${round}">Rodada ${round}</option>`).join('');
        if (rounds.length) select.value = String(rounds.includes(Number(selectedRound)) ? selectedRound : rounds[0]);
        state.rodada = select.value || null;
    }

    async function loadOptions({ clearPlayer = false, preserveRound = true } = {}) {
        if (!page) return;
        const position = selectValue('scoutCrossingPosition');
        const season = selectValue('scoutCrossingSeason');
        if (!position || !season) return;
        const playerSelect = document.getElementById('scoutCrossingPlayer');
        if (clearPlayer) {
            playerSelect.value = '';
            state.atletaId = null;
        }
        playerSelect.disabled = true;
        playerSelect.innerHTML = '<option value="">Carregando jogadores...</option>';
        const params = new URLSearchParams({ temporada: season, posicao_id: position });
        const currentRound = selectValue('scoutCrossingRound');
        if (preserveRound && currentRound) params.set('rodada', currentRound);
        if (playerSelect.value) params.set('atleta_id', playerSelect.value);

        try {
            const response = await fetch(`${page.dataset.optionsUrl}?${params}`);
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Erro ao carregar opções.');
            setRoundOptions(data.rodadas || [], currentRound);
            renderOptions('scoutCrossingPlayer', data.jogadores || [], 'Selecione o jogador', 'id', (item) => `${item.nome} · ${item.clube_nome}`);
            playerSelect.disabled = !(data.jogadores || []).length;
            const initialPlayer = clearPlayer ? '' : (state.atletaId || page.dataset.selectedPlayer || '');
            if (initialPlayer && [...playerSelect.options].some((option) => option.value === String(initialPlayer))) {
                playerSelect.value = String(initialPlayer);
                state.atletaId = Number(initialPlayer);
            }
            await loadOpponentOptions(data.adversarios || []);
            document.getElementById('scoutCrossingFilterHelp').textContent = data.jogadores?.length
                ? 'O cruzamento considera partidas até a rodada selecionada.'
                : 'Nenhum jogador encontrado para estes filtros.';
        } catch (error) {
            playerSelect.innerHTML = '<option value="">Não foi possível carregar</option>';
            setAlert(error.message, true);
        }
    }

    async function loadOpponentOptions(prefetched = null) {
        const playerId = selectValue('scoutCrossingPlayer');
        const opponentSelect = document.getElementById('scoutCrossingOpponent');
        if (!opponentSelect) return;
        if (!playerId) {
            renderOptions('scoutCrossingOpponent', [], 'Todos os adversários', 'id', () => '');
            opponentSelect.disabled = true;
            return;
        }
        let opponents = prefetched;
        if (opponents === null) {
            const params = new URLSearchParams({
                temporada: selectValue('scoutCrossingSeason'),
                posicao_id: selectValue('scoutCrossingPosition'),
                rodada: selectValue('scoutCrossingRound'),
                atleta_id: playerId
            });
            const response = await fetch(`${page.dataset.optionsUrl}?${params}`);
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Erro ao carregar adversários.');
            opponents = data.adversarios || [];
        }
        renderOptions('scoutCrossingOpponent', opponents || [], 'Todos os adversários', 'id', (item) => item.nome);
        opponentSelect.disabled = !(opponents || []).length;
        const selectedOpponent = page.dataset.selectedOpponent;
        if (selectedOpponent && [...opponentSelect.options].some((option) => option.value === String(selectedOpponent))) {
            opponentSelect.value = selectedOpponent;
        }
    }

    function renderSummary(summary) {
        const target = document.getElementById('scoutCrossingSummary');
        const cards = [
            ['Média no recorte', number(summary.media), true],
            ['Jogos analisados', integer(summary.jogos), false],
            ['Maior pontuação', number(summary.maior_pontuacao), false],
            ['Menor pontuação', number(summary.menor_pontuacao), false]
        ];
        target.innerHTML = cards.map(([label, value, accent]) => `<div class="scout-crossing-summary-item${accent ? ' accent' : ''}"><span>${label}</span><strong>${value}</strong></div>`).join('');
    }

    function renderRecent(matches) {
        const target = document.getElementById('scoutCrossingRecent');
        if (!matches.length) {
            target.innerHTML = '<div class="scout-crossing-muted">Nenhuma pontuação encontrada no recorte.</div>';
            return;
        }
        target.innerHTML = matches.map((match) => `<button type="button" class="scout-crossing-recent-row" data-round="${match.rodada}">
            <span class="scout-crossing-round">R${match.rodada}</span>
            <span class="scout-crossing-match"><strong>${escapeHtml(match.adversario_nome)}</strong><span>${escapeHtml(match.mando_label)} · ${escapeHtml(match.casa_nome)} x ${escapeHtml(match.visitante_nome)}</span></span>
            <span class="scout-crossing-points">${number(match.pontuacao)}</span><i class="fas fa-chevron-right text-slate-600 text-xs"></i>
        </button>`).join('');
        target.querySelectorAll('[data-round]').forEach((button) => button.addEventListener('click', () => openDetail(Number(button.dataset.round))));
    }

    function renderPositionScouts(scouts) {
        const target = document.getElementById('scoutCrossingPositionScouts');
        if (!scouts.length) {
            target.innerHTML = '<div class="scout-crossing-muted">Não há scouts de posição disponíveis.</div>';
            return;
        }
        const max = Math.max(...scouts.map((scout) => Number(scout.media) || 0), 1);
        target.innerHTML = scouts.map((scout) => `<div class="scout-crossing-scout-row">
            <span class="scout-crossing-scout-label"><b class="scout-crossing-scout-code">${escapeHtml(scout.codigo)}</b>${escapeHtml(scout.nome)}</span>
            <span class="scout-crossing-scout-value">${number(scout.media)}</span>
            <span class="scout-crossing-scout-track"><span class="scout-crossing-scout-fill" style="width:${Math.max(3, (Number(scout.media) / max) * 100)}%"></span></span>
        </div>`).join('');
    }

    function renderOpponents(opponents) {
        const target = document.getElementById('scoutCrossingOpponents');
        if (!opponents.length) {
            target.innerHTML = '<div class="scout-crossing-muted">Nenhum adversário identificado.</div>';
            return;
        }
        target.innerHTML = opponents.map((opponent) => `<div class="scout-crossing-opponent-row">
            <span class="scout-crossing-opponent-main"><strong>${escapeHtml(opponent.nome)}</strong><span>${integer(opponent.jogos)} jogo(s)</span></span>
            <span class="scout-crossing-opponent-media">${number(opponent.media)} pts</span>
        </div>`).join('');
    }

    function renderHomeAway(items) {
        const target = document.getElementById('scoutCrossingHomeAway');
        target.innerHTML = items.map((item) => `<div class="scout-crossing-home-row">
            <div class="scout-crossing-home-row-header"><span>${item.label}</span><strong>${number(item.media)}</strong></div>
            <div class="scout-crossing-home-track"><div class="scout-crossing-home-fill" style="width:${item.jogos ? Math.min(100, Math.max(7, item.media * 10)) : 0}%"></div></div>
            <span class="text-slate-500 text-[11px]">${integer(item.jogos)} jogo(s) com pontuação</span>
        </div>`).join('');
    }

    function renderResult(data) {
        document.getElementById('scoutCrossingEmpty').hidden = true;
        document.getElementById('scoutCrossingResults').hidden = false;
        document.getElementById('scoutCrossingPlayerName').textContent = data.jogador.nome;
        document.getElementById('scoutCrossingPlayerMeta').textContent = `${data.jogador.posicao} · ${data.jogador.clube_nome} · Temporada ${data.filtros.temporada}`;
        const avatar = document.getElementById('scoutCrossingPlayerAvatar');
        const photo = data.jogador.foto;
        avatar.innerHTML = photo ? `<img src="${escapeHtml(photo)}" alt="${escapeHtml(data.jogador.nome)}">` : '<i class="fas fa-user"></i>';
        renderSummary(data.resumo);
        renderRecent(data.ultimas_pontuacoes || []);
        renderPositionScouts(data.scouts_da_posicao || []);
        renderOpponents(data.resumo.adversarios || []);
        renderHomeAway(data.resumo.mando || []);
    }

    async function runCrossing(event) {
        event.preventDefault();
        const submit = document.getElementById('scoutCrossingSubmit');
        const params = new URLSearchParams({
            atleta_id: selectValue('scoutCrossingPlayer'), posicao_id: selectValue('scoutCrossingPosition'),
            temporada: selectValue('scoutCrossingSeason'), rodada: selectValue('scoutCrossingRound')
        });
        const opponent = selectValue('scoutCrossingOpponent');
        if (opponent) params.set('adversario_id', opponent);
        if (!params.get('atleta_id')) { setAlert('Selecione um jogador para cruzar os scouts.', true); return; }
        submit.disabled = true;
        submit.querySelector('span').textContent = 'Cruzando...';
        setAlert('');
        try {
            const response = await fetch(`${page.dataset.crossingUrl}?${params}`);
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Não foi possível executar o cruzamento.');
            state.temporada = Number(data.filtros.temporada);
            state.rodada = Number(data.filtros.rodada);
            state.atletaId = Number(data.filtros.atleta_id);
            state.posicaoId = Number(data.filtros.posicao_id);
            renderResult(data);
        } catch (error) {
            setAlert(error.message, true);
        } finally {
            submit.disabled = false;
            submit.querySelector('span').textContent = 'Cruzar scouts';
        }
    }

    function detailUrl(atletaId, rodada, temporada) {
        const template = page?.dataset.detailUrlTemplate || '/cruzamento-scouts/api/detalhe/0/0';
        return template.replace('/0/0', `/${atletaId}/${rodada}`) + `?temporada=${encodeURIComponent(temporada)}`;
    }

    function renderModal(match) {
        document.getElementById('scoutCrossingModalTitle').textContent = `Rodada ${match.rodada}`;
        document.getElementById('scoutCrossingModalMatch').textContent = `${match.casa_nome} x ${match.visitante_nome}`;
        document.getElementById('scoutCrossingModalScore').textContent = number(match.pontuacao);
        document.getElementById('scoutCrossingModalMeta').innerHTML = [
            `${match.mando_label}`, `${formatDate(match.partida_data)}`, match.local || 'Local não informado',
            match.placar_casa !== null && match.placar_casa !== undefined ? `Placar ${match.placar_casa} x ${match.placar_fora}` : 'Placar não informado'
        ].map((item) => `<span>${escapeHtml(item)}</span>`).join('');
        document.getElementById('scoutCrossingModalScouts').innerHTML = Object.entries(match.scouts || {}).map(([code, value]) => `<div class="scout-crossing-modal-scout"><span>${escapeHtml(scoutLabels[code] || code)}</span><strong>${integer(value)}</strong></div>`).join('');
        modal.hidden = false;
        modal.setAttribute('aria-hidden', 'false');
        document.body.style.overflow = 'hidden';
    }

    async function openDetail(rodada, atletaId = state.atletaId, temporada = state.temporada || Number(selectValue('scoutCrossingSeason'))) {
        if (!atletaId || !rodada || !temporada || !modal) return;
        try {
            const response = await fetch(detailUrl(atletaId, rodada, temporada));
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Detalhe indisponível.');
            renderModal(data);
        } catch (error) {
            setAlert(error.message, true);
        }
    }

    function closeModal() {
        if (!modal) return;
        modal.hidden = true;
        modal.setAttribute('aria-hidden', 'true');
        document.body.style.overflow = '';
    }

    // API pública para ser chamada por qualquer modal de detalhe existente.
    window.openScoutCrossingModal = function (atletaId, options = {}) {
        const rodada = Number(options.rodada || state.rodada || selectValue('scoutCrossingRound'));
        const temporada = Number(options.temporada || state.temporada || selectValue('scoutCrossingSeason'));
        if (rodada && temporada) {
            openDetail(rodada, Number(atletaId), temporada);
            return;
        }
        fetch('/cruzamento-scouts/api/contexto')
            .then((response) => response.json().then((data) => ({ response, data })))
            .then(({ response, data }) => {
                if (!response.ok) throw new Error(data.error || 'Contexto da rodada indisponível.');
                state.temporada = Number(data.temporada);
                state.rodada = Number(data.rodada);
                openDetail(state.rodada, Number(atletaId), state.temporada);
            })
            .catch((error) => setAlert(error.message, true));
    };
    window.closeScoutCrossingModal = closeModal;

    document.querySelectorAll('[data-scout-crossing-close]').forEach((element) => element.addEventListener('click', closeModal));
    document.addEventListener('keydown', (event) => { if (event.key === 'Escape' && modal && !modal.hidden) closeModal(); });

    if (!page) return;
    document.getElementById('scoutCrossingForm')?.addEventListener('submit', runCrossing);
    document.getElementById('scoutCrossingPosition')?.addEventListener('change', () => loadOptions({ clearPlayer: true, preserveRound: true }));
    document.getElementById('scoutCrossingSeason')?.addEventListener('change', () => loadOptions({ clearPlayer: true, preserveRound: false }));
    document.getElementById('scoutCrossingRound')?.addEventListener('change', () => loadOptions({ preserveRound: true }));
    document.getElementById('scoutCrossingPlayer')?.addEventListener('change', async () => {
        state.atletaId = Number(selectValue('scoutCrossingPlayer')) || null;
        try { await loadOpponentOptions(null); } catch (error) { setAlert(error.message, true); }
    });
    loadOptions();
}());
