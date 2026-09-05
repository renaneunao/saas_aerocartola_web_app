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

    function scoutMarkup(scouts) {
        const entries = Object.entries(scouts || {});
        if (!entries.length) return '<span class="modal-scout-history-empty">Sem scouts registrados</span>';
        return entries.map(([code, value]) =>
            `<span class="modal-scout-history-scout">${escapeHtml(labels[code] || code.toUpperCase())}<strong>${escapeHtml(number(value))}</strong></span>`
        ).join('');
    }

    function scoutSummary(scouts) {
        const entries = Object.entries(scouts || {});
        if (!entries.length) return '';
        return `(${entries.map(([code, value]) => `${labels[code] || code.toUpperCase()} ${Number(value) || 0}`).join(' · ')})`;
    }

    function render(prefix, data, fallbackPhoto) {
        const root = document.getElementById(`modal${prefix}ScoutHistory`);
        if (!root) return;
        const status = root.querySelector(`#modal${prefix}ScoutHistoryStatus`);
        const summary = root.querySelector(`#modal${prefix}ScoutHistorySummary`);
        const list = root.querySelector(`#modal${prefix}ScoutHistoryList`);
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

        if (!matches.length) {
            list.innerHTML = '<div class="modal-scout-history-empty">Nenhuma pontuação encontrada até a rodada atual.</div>';
            return;
        }

        list.innerHTML = matches.map((match) => {
            const conceded = match.cedidos_adversario || {};
            const concededScouts = conceded.scouts || {};
            const concededText = Object.keys(concededScouts).length
                ? Object.entries(concededScouts).map(([code, value]) => `${labels[code] || code.toUpperCase()} ${number(value)}`).join(' · ')
                : 'Sem referência de cedidos';
            return `<article class="modal-scout-history-item">
                <button type="button" class="modal-scout-history-row" aria-expanded="false">
                    <span class="modal-scout-history-round">R${escapeHtml(match.rodada)}</span>
                    <span class="modal-scout-history-game"><strong>${escapeHtml(match.adversario_nome || 'Adversário não informado')}</strong><small>${escapeHtml(match.mando_label || 'Mando indisponível')} · ${escapeHtml(match.casa_nome || 'Casa')} x ${escapeHtml(match.visitante_nome || 'Fora')}</small></span>
                    <span class="modal-scout-history-point-wrap"><small class="modal-scout-history-inline-scouts">${escapeHtml(scoutSummary(match.scouts))}</small><strong class="modal-scout-history-point">${number(match.pontuacao)}</strong></span>
                </button>
                <div class="modal-scout-history-detail">
                    <div><p class="modal-scout-history-detail-title">Scouts do jogador</p><div class="modal-scout-history-scouts">${scoutMarkup(match.scouts)}</div></div>
                    <div><p class="modal-scout-history-detail-title">Cedidos pelo adversário · ${escapeHtml(concededText)}</p><div class="modal-scout-history-scouts">${scoutMarkup(concededScouts)}</div></div>
                </div>
            </article>`;
        }).join('');

        list.querySelectorAll('.modal-scout-history-row').forEach((button) => {
            button.addEventListener('click', () => {
                const item = button.closest('.modal-scout-history-item');
                const expanded = item.classList.toggle('is-open');
                button.setAttribute('aria-expanded', String(expanded));
            });
        });
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
