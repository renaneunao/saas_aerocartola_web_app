(function () {
    'use strict';

    const labels = {
        a: 'A', ca: 'CA', cv: 'CV', de: 'DE', ds: 'DS', fc: 'FC', fd: 'FD',
        ff: 'FF', fs: 'FS', g: 'G', gs: 'GS', i: 'I', sg: 'SG'
    };

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
        const entries = Object.entries(scouts || {}).filter(([, value]) => Number(value) > 0);
        if (!entries.length) return '';
        return entries.map(([code, value]) =>
            `<span><b>${escapeHtml(labels[code] || code.toUpperCase())}</b> ${escapeHtml(number(value))}</span>`
        ).join('');
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
            </div>
            <div class="modal-scout-history-inline-scouts">${scouts || '<span class="is-muted">Sem scouts positivos</span>'}</div>
        </article>`;
    }

    function render(prefix, data, fallbackPhoto) {
        const root = document.getElementById(`modal${prefix}ScoutHistory`);
        if (!root) return;
        const status = root.querySelector(`#modal${prefix}ScoutHistoryStatus`);
        const summary = root.querySelector(`#modal${prefix}ScoutHistorySummary`);
        const list = root.querySelector(`#modal${prefix}ScoutHistoryList`);
        const crossingLink = root.querySelector(`#modal${prefix}ScoutCrossingLink`);
        // Uma linha sem entrada em campo não é uma pontuação do jogador;
        // ela deve aparecer como rodada sem dados no calendário de 1 a 38.
        const matches = (data.ultimas_pontuacoes || []).filter((match) => match.entrou_em_campo === true);
        const photo = imageUrl(data.jogador?.foto) || imageUrl(fallbackPhoto);

        if (status) status.textContent = photo ? 'Dados atuais' : 'Dados atuais · foto indisponível';
        if (summary) {
            summary.innerHTML = [
                ['Média', number(data.resumo?.media)],
                ['Jogos', String(data.resumo?.jogos || 0)],
                ['Maior nota', number(data.resumo?.maior_pontuacao)]
            ].map(([label, value]) => `<div class="modal-scout-history-summary-card"><span>${label}</span><strong>${value}</strong></div>`).join('');
        }

        const currentRound = Math.max(1, Number(data.filtros?.rodada || 38));
        const byRound = new Map(matches
            .filter((match) => Number(match.rodada) <= currentRound)
            .map((match) => [Number(match.rodada), match]));
        // A coluna mais à esquerda sempre começa pela rodada mais recente.
        // Rodadas futuras não ocupam espaço no histórico, mas lacunas passadas
        // continuam opacas para preservar a leitura da temporada.
        const ranges = [[27, 38], [14, 26], [1, 13]]
            .map(([start, end]) => [start, Math.min(end, currentRound)])
            .filter(([start, end]) => start <= end);
        list.innerHTML = ranges.map(([start, end]) => {
            const cards = Array.from({ length: end - start + 1 }, (_, index) => {
                const round = end - index;
                return roundCard(round, byRound.get(round));
            }).join('');
            return `<section class="modal-scout-history-column" aria-label="Rodadas ${start} a ${end}">
                <p class="modal-scout-history-range">Rodada ${start}–${end}</p>${cards}
            </section>`;
        }).join('');
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
