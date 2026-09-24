(function () {
    'use strict';

    const labels = {
        a: 'A', ca: 'CA', cv: 'CV', de: 'DE', ds: 'DS', fc: 'FC', fd: 'FD',
        ff: 'FF', fs: 'FS', g: 'G', gs: 'GS', i: 'I', sg: 'SG'
    };
    const negativeScouts = new Set(['ca', 'cv', 'fc', 'gs', 'i']);

    function escapeHtml(value) {
        return String(value ?? '').replace(/[&<>'"]/g, (char) => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#039;', '"': '&quot;'
        }[char]));
    }

    function number(value) {
        const parsed = Number(value);
        return Number.isFinite(parsed) ? parsed.toLocaleString('pt-BR', {
            minimumFractionDigits: 2, maximumFractionDigits: 2
        }) : '0,00';
    }

    function imageUrl(value) {
        const candidate = String(value || '').trim();
        if (!candidate || candidate.includes('placeholder_')) return '';
        if (candidate.startsWith('//')) return `https:${candidate}`;
        return candidate;
    }

    window.resolvePlayerPhoto = function (primary, atletaId) {
        const mapped = typeof window.getPlayerImage === 'function' ? window.getPlayerImage(atletaId) : '';
        return imageUrl(primary) || imageUrl(mapped) || '';
    };

    function scoutSummary(scouts) {
        const entries = Object.entries(scouts || {})
            .filter(([, value]) => Number.isFinite(Number(value)) && Number(value) !== 0)
            .map(([code, value]) => {
                const raw = Number(value) || 0;
                const negative = negativeScouts.has(code) || raw < 0;
                return {
                    code,
                    negative,
                    label: labels[code] || code.toUpperCase(),
                    value: `${negative ? '-' : ''}${Math.round(Math.abs(raw)).toLocaleString('pt-BR')}`
                };
            });
        if (!entries.length) return '';
        const markup = (negative) => entries.filter((entry) => entry.negative === negative)
            .map((entry) => `<span title="${escapeHtml(entry.code)}"><b>${escapeHtml(entry.label)}</b> ${entry.value}</span>`)
            .join('');
        return `<span class="modal-scout-history-scouts-positive">${markup(false)}</span><span class="modal-scout-history-scouts-negative">${markup(true)}</span>`;
    }

    function fixtureMarkup(match) {
        const home = match?.casa || {
            nome: match?.casa_nome || 'Casa',
            abreviacao: match?.casa_abreviacao || match?.casa_nome || 'CASA',
            escudo: ''
        };
        const away = match?.fora || {
            nome: match?.visitante_nome || 'Fora',
            abreviacao: match?.visitante_abreviacao || match?.visitante_nome || 'FORA',
            escudo: ''
        };
        const playerId = Number(match?.clube_id);
        const team = (club, side) => {
            const id = Number(club?.id);
            const active = Number.isFinite(playerId) && playerId > 0 && id === playerId;
            const label = club?.abreviacao || club?.nome || '—';
            const initials = escapeHtml(String(label).replace(/[^A-Za-zÀ-ÿ0-9]/g, '').slice(0, 4).toUpperCase() || '—');
            const image = imageUrl(club?.escudo);
            return `<span class="modal-scout-history-fixture-team ${side} ${active ? 'active' : 'dim'}">${image ? `<img src="${escapeHtml(image)}" alt="" data-history-shield>` : ''}<span class="modal-scout-history-shield-fallback" ${image ? 'hidden' : ''}>${initials}</span><b>${escapeHtml(label)}</b></span>`;
        };
        return `<div class="modal-scout-history-fixture">${team(home, 'home')}<span class="modal-scout-history-fixture-vs" aria-hidden="true">×</span>${team(away, 'away')}</div>`;
    }

    function scoreLabel(match) {
        const rawHome = match?.placar_casa;
        const rawAway = match?.placar_fora;
        const home = Number(rawHome);
        const away = Number(rawAway);
        const validHome = rawHome !== null && rawHome !== undefined && rawHome !== '' && Number.isFinite(home);
        const validAway = rawAway !== null && rawAway !== undefined && rawAway !== '' && Number.isFinite(away);
        if (!validHome && !validAway) return 'Placar não informado';
        return `Placar ${validHome ? Math.round(home) : '—'} × ${validAway ? Math.round(away) : '—'}`;
    }

    function roundCard(round, match) {
        if (!match) {
            return `<article class="modal-scout-history-item is-empty" aria-label="Rodada ${round}, sem dados">
                <span class="modal-scout-history-round">Rodada ${round}</span>
                <span class="modal-scout-history-no-data">Sem dados</span>
            </article>`;
        }
        const scouts = scoutSummary(match.scouts);
        return `<article class="modal-scout-history-item" aria-label="Rodada ${round}, ${number(match.pontuacao)} pontos">
            <div class="modal-scout-history-card-head">
                <span class="modal-scout-history-round">Rodada ${round}</span>
                <strong class="modal-scout-history-point">${number(match.pontuacao)}</strong>
            </div>
            <div class="modal-scout-history-game">
                ${fixtureMarkup(match)}
                <small>${escapeHtml(match.mando_label || 'Sem mando')} · adversário ${escapeHtml(match.adversario_nome || 'não informado')}</small>
                <span class="modal-scout-history-score">${escapeHtml(scoreLabel(match))}</span>
            </div>
             <div class="modal-scout-history-inline-scouts">${scouts || '<span class="is-muted">Sem scouts</span>'}</div>
         </article>`;
    }

    function cededSummary(matches, mando) {
        const relevant = matches.filter((match) => match.mando === mando && match.cedidos_adversario?.scouts);
        if (!relevant.length) {
            return '<div class="modal-scout-history-ceded-empty">Sem cedidos registrados.</div>';
        }
        const totals = {};
        const counts = {};
        relevant.forEach((match) => {
            Object.entries(match.cedidos_adversario.scouts || {}).forEach(([code, value]) => {
                const numeric = Number(value);
                if (!Number.isFinite(numeric) || numeric === 0) return;
                totals[code] = (totals[code] || 0) + numeric;
                counts[code] = (counts[code] || 0) + 1;
            });
        });
        const rows = Object.entries(totals)
            .map(([code, value]) => {
                const average = value / Math.max(1, counts[code] || relevant.length);
                const negative = negativeScouts.has(code) || average < 0;
                return { code, average, negative };
            })
            .filter((item) => Math.round(Math.abs(item.average)) > 0)
            .sort((a, b) => Math.abs(b.average) - Math.abs(a.average));
        if (!rows.length) return '<div class="modal-scout-history-ceded-empty">Sem scouts cedidos acima de zero.</div>';
        const scores = relevant
            .sort((a, b) => Number(b.rodada) - Number(a.rodada))
            .map((match) => `Rodada ${match.rodada}: ${scoreLabel(match).replace(/^Placar\s*/, '')}`)
            .join(' · ');
        return `<div class="modal-scout-history-ceded-games">${relevant.length} jogo(s) com dados</div><div class="modal-scout-history-ceded-scores">${escapeHtml(scores)}</div>${rows.map((item) => `<div class="modal-scout-history-ceded-row ${item.negative ? 'is-negative' : 'is-positive'}"><span>${escapeHtml(labels[item.code] || item.code.toUpperCase())}</span><strong>${item.negative ? '-' : ''}${Math.round(Math.abs(item.average)).toLocaleString('pt-BR')}</strong></div>`).join('')}`;
    }

    function render(prefix, data, fallbackPhoto) {
        const root = document.getElementById(`modal${prefix}ScoutHistory`);
        if (!root) return;
        const status = root.querySelector(`#modal${prefix}ScoutHistoryStatus`);
        const summary = root.querySelector(`#modal${prefix}ScoutHistorySummary`);
        const list = root.querySelector(`#modal${prefix}ScoutHistoryList`);
        const ceded = root.querySelector(`#modal${prefix}ScoutHistoryCeded`);
        const cededHome = root.querySelector(`#modal${prefix}ScoutHistoryCededHome`);
        const cededAway = root.querySelector(`#modal${prefix}ScoutHistoryCededAway`);
        const crossingLink = root.querySelector(`#modal${prefix}ScoutCrossingLink`);
        // Mantemos também as linhas sem entrada em campo para que a rodada
        // apareça opaca, sem transformar ausência de pontuação em zero.
        const matches = data.ultimas_pontuacoes || [];
        const photo = imageUrl(data.jogador?.foto) || imageUrl(fallbackPhoto);

        if (status) status.textContent = photo ? 'Dados atuais' : 'Dados atuais · foto indisponível';
        if (summary) {
            summary.innerHTML = [
                ['Média', number(data.resumo?.media)],
                ['Jogos', String(data.resumo?.jogos || 0)],
                ['Maior nota', number(data.resumo?.maior_pontuacao)]
            ].map(([label, value]) => `<div class="modal-scout-history-summary-card"><span>${label}</span><strong>${value}</strong></div>`).join('');
        }

        // A rodada atual ainda não aconteceu; o histórico termina na rodada
        // anterior e nunca cria cards para rodadas futuras.
        const currentRound = Math.max(0, Number(data.filtros?.rodada || 38) - 1);
        const homeMatches = matches.filter((match) => Number(match.rodada) <= currentRound && match.mando === 'casa');
        const awayMatches = matches.filter((match) => Number(match.rodada) <= currentRound && match.mando === 'fora');
        const historyColumn = (title, items) => {
            const cards = items.length
                ? items.sort((a, b) => Number(b.rodada) - Number(a.rodada)).map((match) => roundCard(match.rodada, match.entrou_em_campo === true ? match : null)).join('')
                : '<div class="modal-scout-history-empty">Nenhum jogo deste tipo no histórico.</div>';
            return `<section class="modal-scout-history-column" aria-label="Rodadas ${title.toLocaleLowerCase()}">
                <p class="modal-scout-history-range">${title}</p>${cards}
            </section>`;
        };
        list.innerHTML = `${historyColumn('Em casa', homeMatches)}${historyColumn('Fora', awayMatches)}`;
        list.querySelectorAll('img[data-history-shield]').forEach((image) => {
            image.addEventListener('error', () => {
                image.hidden = true;
                if (image.nextElementSibling?.classList.contains('modal-scout-history-shield-fallback')) {
                    image.nextElementSibling.hidden = false;
                }
            }, { once: true });
        });
        if (crossingLink && data.jogador?.id) {
            crossingLink.href = `/cruzamento-scouts/?posicao_id=${encodeURIComponent(root.dataset.positionId || data.filtros?.posicao_id || '')}&atleta_id=${encodeURIComponent(data.jogador.id)}`;
        }
        if (ceded && cededHome && cededAway) {
            const historical = matches.filter((match) => Number(match.rodada) <= currentRound && match.entrou_em_campo === true);
            cededHome.innerHTML = cededSummary(historical, 'casa');
            cededAway.innerHTML = cededSummary(historical, 'fora');
            ceded.hidden = !historical.some((match) => match.cedidos_adversario?.scouts);
        }
    }

    async function load(prefix, atletaId, positionId, fallbackPhoto) {
        const root = document.getElementById(`modal${prefix}ScoutHistory`);
        if (!root || !atletaId) return;
        const status = root.querySelector(`#modal${prefix}ScoutHistoryStatus`);
        const list = root.querySelector(`#modal${prefix}ScoutHistoryList`);
        if (status) status.textContent = 'Carregando…';
        if (list) list.innerHTML = '<div class="modal-scout-history-empty">Buscando últimas rodadas…</div>';
        try {
            const contextResponse = await fetch('/cruzamento-scouts/api/contexto');
            const context = await contextResponse.json();
            if (!contextResponse.ok) throw new Error(context.error || 'Contexto indisponível.');
            const params = new URLSearchParams({
                atleta_id: atletaId,
                posicao_id: positionId,
                temporada: context.temporada,
                rodada: context.rodada
            });
            const response = await fetch(`/cruzamento-scouts/api/cruzar?${params}`);
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Histórico indisponível.');
            render(prefix, data, fallbackPhoto);
        } catch (error) {
            if (status) status.textContent = 'Não disponível';
            if (list) list.innerHTML = `<div class="modal-scout-history-empty">${escapeHtml(error.message)}</div>`;
        }
    }

    window.loadModalScoutHistory = load;
}());
