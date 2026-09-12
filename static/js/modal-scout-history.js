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
                <strong>${escapeHtml(match.adversario_nome || 'Adversário não informado')}</strong>
                <small>${escapeHtml(match.mando_label || 'Sem mando')} · ${escapeHtml(match.casa_nome || 'Casa')} x ${escapeHtml(match.visitante_nome || 'Fora')}</small>
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

        const byRound = new Map(matches.map((match) => [Number(match.rodada), match]));
        const ranges = [[1, 13], [14, 26], [27, 38]];
        list.innerHTML = ranges.map(([start, end]) => {
            const cards = Array.from({ length: end - start + 1 }, (_, index) => {
                const round = start + index;
                return roundCard(round, byRound.get(round));
            }).join('');
            return `<section class="modal-scout-history-column" aria-label="Rodadas ${start} a ${end}">
                <p class="modal-scout-history-range">Rodada ${start}–${end}</p>${cards}
            </section>`;
        }).join('');
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
