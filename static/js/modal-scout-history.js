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

    window.renderModalFavoritism = function (data) {
        const side = ['casa', 'visitante'].includes(data?.favoritismo_lado)
            ? data.favoritismo_lado : 'equilibrado';
        const width = Math.max(0, Math.min(50, Number(data?.favoritismo_bar_percent) || 0));
        const favorite = side === 'casa' ? 'mandante' : side === 'visitante' ? 'visitante' : '';
        const title = `Favoritismo do confronto · escala comum da rodada · ${favorite ? `${favorite} favorito` : 'confronto equilibrado'}`;
        const homeName = escapeHtml(data?.favoritismo_clube_casa_nome || 'Mandante');
        const awayName = escapeHtml(data?.favoritismo_clube_visitante_nome || 'Visitante');
        const teamLine = (kind, label, name, value, isFavorite) =>
            `<div class="modal-detail-favoritism-team is-${kind}${isFavorite ? ' is-favorite' : ''}"><span class="modal-detail-favoritism-team-name"><b>${label}</b><strong>${name}</strong>${isFavorite ? '<em>FAVORITO</em>' : ''}</span><b class="modal-detail-favoritism-team-value">${number(value)}</b></div>`;
        return `<div class="modal-detail-favoritism-heading"><span>MANDANTE</span><span>VISITANTE</span></div><div class="modal-detail-favoritism-teams">${teamLine('casa', 'CASA', homeName, data?.favoritismo_casa, side === 'casa')}${teamLine('visitante', 'FORA', awayName, data?.favoritismo_visitante, side === 'visitante')}</div><div class="modal-detail-favoritism-meter is-${side}" role="img" aria-label="${escapeHtml(title)}"><i style="--favoritismo-width:${width}%"></i></div><div class="modal-detail-favoritism-caption">${favorite ? `${favorite === 'mandante' ? homeName : awayName} é o favorito deste confronto` : 'Sem favoritismo definido entre os times'}</div>`;
    };

    window.renderModalSG = function (data) {
        const percent = Math.max(0, Math.min(100, Number(data?.peso_sg_percentual) || 0));
        const rounded = Math.round(percent);
        return `<div class="modal-detail-sg-meter" role="img" aria-label="Indicador relativo de SG: ${rounded}%"><i style="width:${percent}%"></i></div><div class="modal-detail-sg-caption"><b>${rounded}%</b><span>do maior índice de SG da rodada</span></div>`;
    };

    function imageUrl(value) {
        let candidate = String(value || '').trim();
        if (!candidate || candidate.includes('placeholder_')) return '';
        if (candidate.startsWith('//')) return `https:${candidate}`;
        if (!/\/silhuetas\/[^/]+\/FORMATO\.png(?:\?|$)/i.test(candidate)) {
            candidate = candidate.replace(/FORMATO/gi, '220x220');
        }
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

    function fixtureScoreValue(value) {
        const parsed = Number(value);
        return value !== null && value !== undefined && value !== '' && Number.isFinite(parsed)
            ? String(Math.round(parsed))
            : '—';
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
            const content = image ? `<img src="${escapeHtml(image)}" alt="" data-history-shield>` : `<span class="modal-scout-history-shield-fallback">${initials}</span>`;
            return side === 'home'
                ? `<span class="modal-scout-history-fixture-team ${side} ${active ? 'active' : 'dim'}">${content}<b>${escapeHtml(label)}</b></span>`
                : `<span class="modal-scout-history-fixture-team ${side} ${active ? 'active' : 'dim'}"><b>${escapeHtml(label)}</b>${content}</span>`;
        };
        return `<div class="modal-scout-history-fixture">${team(home, 'home')}<b class="modal-scout-history-score-value">${fixtureScoreValue(match?.placar_casa)}</b><span class="modal-scout-history-fixture-vs" aria-hidden="true">×</span><b class="modal-scout-history-score-value">${fixtureScoreValue(match?.placar_fora)}</b>${team(away, 'away')}</div>`;
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
            </div>
             <div class="modal-scout-history-inline-scouts">${scouts || '<span class="is-muted">Sem scouts</span>'}</div>
         </article>`;
    }

    function cededSummary(profile, mando, limit) {
        const summary = profile?.por_mando?.[mando];
        if (!summary || !Number(summary.jogos_com_dados)) {
            return '<div class="modal-scout-history-ceded-empty">Sem partidas suficientes neste mando.</div>';
        }
        const allGames = summary.historico_completo || summary.historico || [];
        const games = limit === 'all' ? allGames : allGames.slice(0, Math.max(1, Number(limit) || 5));
        const gamesWithPlayers = games.filter((game) => (game.jogadores || []).length);
        const denominator = Math.max(1, gamesWithPlayers.length);
        const totals = {};
        gamesWithPlayers.forEach((game) => Object.entries(game.scouts || {}).forEach(([code, raw]) => {
            const value = Number(raw) || 0;
            totals[code] = (totals[code] || 0) + value;
        }));
        const recommended = profile?.mando_relevante === mando;
        const scoutRows = Object.entries(totals)
            .filter(([, total]) => Number(total) !== 0)
            .sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]))
            .map(([code, total]) => `<div class="modal-scout-history-ceded-row ${negativeScouts.has(code) ? 'is-negative' : 'is-positive'}"><span><b>${escapeHtml(labels[code] || code.toUpperCase())}</b> ${escapeHtml(labels[code] ? '' : code)}</span><strong><span>${Number(total).toLocaleString('pt-BR')}</span><small>${(Number(total) / denominator).toLocaleString('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1 })} méd.</small></strong></div>`)
            .join('');
        const recent = games.map((match) => {
            const players = (match.jogadores || []).map((player) => {
                const photo = window.resolvePlayerPhoto(player.foto, player.id);
                const avatar = photo ? `<img src="${escapeHtml(photo)}" alt="" loading="lazy">` : '<i class="fas fa-user"></i>';
                return `<div class="modal-scout-history-ceded-player"><span class="modal-scout-history-ceded-player-avatar">${avatar}</span><strong>${escapeHtml(player.nome || 'Atleta')}</strong><span class="modal-scout-history-ceded-player-scouts">${scoutSummary(player.scouts)}</span><b>${number(player.pontuacao)} pts</b></div>`;
            }).join('') || '<span class="modal-scout-history-ceded-empty">Sem atleta da posição com dados.</span>';
            return `<details class="modal-scout-history-ceded-match" open><summary><span>Rodada ${match.rodada}</span><span class="modal-scout-history-ceded-fixture">${fixtureMarkup(match)}</span><span class="modal-scout-history-ceded-scouts-inline">${scoutSummary(match.scouts)}</span><strong>${number(match.pontuacao)} pts</strong><i class="fas fa-chevron-down" aria-hidden="true"></i></summary><div class="modal-scout-history-ceded-players">${players}</div></details>`;
        }).join('');
        const points = gamesWithPlayers.flatMap((game) => (game.jogadores || []).map((player) => Number(player.pontuacao) || 0));
        const averagePoints = points.length ? points.reduce((sum, value) => sum + value, 0) / points.length : 0;
        const peak = points.length ? Math.max(...points) : 0;
        const threshold = (value) => points.length ? Math.round(points.filter((point) => point >= value).length / points.length * 100) : 0;
        return `<div class="modal-scout-history-ceded-context ${recommended ? 'is-recommended' : ''}">${recommended ? '<i class="fas fa-crosshairs"></i><span>Recorte mais parecido com o confronto atual</span>' : '<span>Histórico geral deste mando</span>'}</div><div class="modal-scout-history-ceded-metrics"><span><small>Jogos no recorte</small><b>${gamesWithPlayers.length}</b></span><span><small>Pts/atleta</small><b>${number(averagePoints)}</b></span><span><small>Pico</small><b>${number(peak)}</b></span><span><small>Atletas</small><b>${points.length}</b></span></div><div class="modal-scout-history-ceded-thresholds"><span>≥5 pts <b>${threshold(5)}%</b></span><span>≥8 pts <b>${threshold(8)}%</b></span><span>≥12 pts <b>${threshold(12)}%</b></span></div><div class="modal-scout-history-ceded-scouts"><div class="modal-scout-history-ceded-row is-heading"><span>Scout</span><strong><span>Soma</span><small>Média/jogo</small></strong></div>${scoutRows || '<span class="modal-scout-history-ceded-empty">Nenhum scout registrado neste recorte.</span>'}</div><div class="modal-scout-history-ceded-matches">${recent || '<span class="modal-scout-history-ceded-empty">Sem partidas neste recorte.</span>'}</div>`;
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
            const profile = data.cedidos_adversario || {};
            const limitControl = root.querySelector('[data-ceded-history-limit]');
            const paintCeded = () => {
                const limit = limitControl?.value || '5';
                cededHome.innerHTML = cededSummary(profile, 'casa', limit);
                cededAway.innerHTML = cededSummary(profile, 'fora', limit);
            };
            if (limitControl && !limitControl.dataset.bound) {
                limitControl.dataset.bound = '1';
                limitControl.addEventListener('change', paintCeded);
            }
            paintCeded();
            ceded.hidden = !Object.values(profile.por_mando || {}).some((summary) => Number(summary?.jogos_com_dados) > 0);
        }
    }

    async function openAvailabilityModal() {
        document.getElementById('quickAvailabilityModal')?.remove();
        const overlay = document.createElement('div');
        overlay.id = 'quickAvailabilityModal';
        overlay.className = 'quick-availability-overlay';
        overlay.innerHTML = `<section class="quick-availability-dialog" role="dialog" aria-modal="true" aria-labelledby="quickAvailabilityTitle">
            <header><div><span>Controle da rodada</span><h2 id="quickAvailabilityTitle">Disponibilidade dos jogadores</h2><p data-availability-context>Carregando jogadores…</p></div><button type="button" data-close aria-label="Fechar"><i class="fas fa-xmark"></i></button></header>
            <div class="quick-availability-filters">
                <label>Posição<select data-filter-position><option value="">Todas as posições</option><option value="1">Goleiros</option><option value="2">Laterais</option><option value="3">Zagueiros</option><option value="4">Meias</option><option value="5">Atacantes</option><option value="6">Técnicos</option></select></label>
                <label>Time do jogador<select data-filter-club><option value="">Todos os times</option></select></label>
                <label class="quick-availability-search">Buscar jogador<input type="search" data-filter-search placeholder="Nome ou clube"></label>
                <label>Ordenar por<select data-filter-sort><option value="expected">Expectativa</option><option value="average">Média</option><option value="price_asc">Preço crescente</option><option value="price_desc">Preço decrescente</option><option value="games">Jogos</option><option value="scout">Scout selecionado</option><option value="name">Nome</option></select></label>
                <label>Scout para ordenar<select data-filter-scout><option value="ds">DS · Desarmes</option><option value="fs">FS · Faltas sofridas</option><option value="ff">FF · Finalizações para fora</option><option value="fd">FD · Finalizações defendidas</option><option value="de">DEF · Defesas</option><option value="fc">FC · Faltas cometidas</option><option value="g">G · Gols</option><option value="a">A · Assistências</option><option value="sg">SG · Saldo de gols</option><option value="gs">GS · Gols sofridos</option><option value="i">IMP · Impedimentos</option><option value="ca">CA · Cartões amarelos</option><option value="cv">CV · Cartões vermelhos</option></select></label>
            </div>
            <nav class="quick-availability-tabs" aria-label="Filtrar disponibilidade"><button class="active" data-status-filter="provaveis">Prováveis</button><button data-status-filter="all">Todos</button><button data-status-filter="poupar">Poupados</button><button data-status-filter="cravado">Cravados</button><button class="quick-availability-reload" type="button" data-reload><i class="fas fa-rotate"></i> Atualizar</button><span data-count></span></nav>
            <div class="quick-availability-feedback" role="status"></div>
            <div class="quick-availability-table-wrap"><table><thead><tr><th>Jogador</th><th>Posição</th><th>Clube</th><th>Média</th><th>Expectativa</th><th>Preço</th><th>Status</th><th>Decisão</th></tr></thead><tbody data-rows><tr><td colspan="8">Carregando…</td></tr></tbody></table></div>
            <footer><span>Nulos não podem ser cravados como prováveis.</span><button type="button" data-close>Fechar</button></footer>
        </section>`;
        document.body.append(overlay);
        const $ = (selector) => overlay.querySelector(selector);
        const close = () => overlay.remove();
        overlay.querySelectorAll('[data-close]').forEach((button) => button.addEventListener('click', close));
        overlay.addEventListener('click', (event) => { if (event.target === overlay) close(); });
        overlay.querySelector('[data-close]')?.focus();
        overlay.addEventListener('keydown', (event) => { if (event.key === 'Escape') close(); });
        const state = { items: [], teamId: null, season: null, round: null, tab: 'provaveis', pending: new Set() };
        const positionNames = { 1: 'Goleiro', 2: 'Lateral', 3: 'Zagueiro', 4: 'Meia', 5: 'Atacante', 6: 'Técnico' };
        const statusName = (item) => Number(item.source_status_id ?? item.status_id);
        const feedback = (message, error = false) => { const el = $('.quick-availability-feedback'); el.textContent = message; el.classList.toggle('is-error', error); };
        const renderRows = () => {
            const search = $('[data-filter-search]').value.trim().toLocaleLowerCase();
            const position = $('[data-filter-position]').value;
            const club = $('[data-filter-club]').value;
            const sort = $('[data-filter-sort]').value;
            const scout = $('[data-filter-scout]').value;
            const rows = state.items.filter((item) => {
                const status = statusName(item);
                if (position && String(item.posicao_id) !== position) return false;
                if (club && String(item.clube_id) !== club) return false;
                if (search && !`${item.apelido || ''} ${item.nome || ''} ${item.clube_nome || ''}`.toLocaleLowerCase().includes(search)) return false;
                if (state.tab === 'poupar') return item.rule === 'poupar';
                if (state.tab === 'cravado') return item.rule === 'cravado';
                if (state.tab === 'provaveis') return item.rule !== 'poupar' && (status === 7 || item.rule === 'cravado') && status !== 6;
                return true;
            }).sort((a, b) => {
                if (sort === 'average') return Number(b.media_num || 0) - Number(a.media_num || 0);
                if (sort === 'price_asc') return Number(a.preco_num || 0) - Number(b.preco_num || 0);
                if (sort === 'price_desc') return Number(b.preco_num || 0) - Number(a.preco_num || 0);
                if (sort === 'games') return Number(b.jogos_num || 0) - Number(a.jogos_num || 0);
                if (sort === 'scout') return Number(b.scouts?.[scout] || 0) - Number(a.scouts?.[scout] || 0);
                if (sort === 'name') return String(a.apelido || a.nome || '').localeCompare(String(b.apelido || b.nome || ''), 'pt-BR');
                return Number(b.pontos_num || 0) - Number(a.pontos_num || 0);
            });
            $('[data-count]').textContent = `${rows.length} jogador(es)`;
            $('[data-rows]').innerHTML = rows.length ? rows.map((item) => {
                const nullStatus = statusName(item) === 6;
                const pending = state.pending.has(String(item.atleta_id));
                const photo = window.resolvePlayerPhoto(item.foto, item.atleta_id);
                const decision = (rule, text, icon, allowed = true) => `<button type="button" data-rule="${rule}" data-id="${item.atleta_id}" ${pending || !allowed ? 'disabled' : ''} class="${item.rule === rule ? 'is-active' : ''}"><i class="fas ${pending ? 'fa-spinner fa-spin' : icon}"></i>${pending ? 'Salvando' : item.rule === rule ? (rule === 'poupar' ? 'Poupado' : 'Cravado') : text}</button>`;
                return `<tr><td><div class="quick-availability-player">${photo ? `<img src="${escapeHtml(photo)}" alt="">` : '<i class="fas fa-user"></i>'}<strong>${escapeHtml(item.apelido || item.nome || 'Atleta')}</strong></div></td><td>${escapeHtml(positionNames[item.posicao_id] || '—')}</td><td>${escapeHtml(item.clube_abrev || item.clube_nome || '—')}</td><td>${Number(item.media_num || 0).toFixed(2)}</td><td>${Number(item.pontos_num || 0).toFixed(2)}</td><td>C$ ${Number(item.preco_num || 0).toFixed(2)}</td><td>${escapeHtml(item.status_nome || 'Desconhecido')}</td><td class="quick-availability-actions">${decision('poupar', 'Poupar', 'fa-ban')}${decision('cravado', 'Cravar', 'fa-check', !nullStatus)}${item.rule ? decision('clear', 'Limpar', 'fa-xmark') : ''}</td></tr>`;
            }).join('') : '<tr><td colspan="8">Nenhum jogador encontrado para este filtro.</td></tr>';
        };
        const reload = async () => {
            const params = new URLSearchParams();
            if ($('[data-filter-position]').value) params.set('position_id', $('[data-filter-position]').value);
            const response = await fetch(`/api/player-availability/candidates?${params}`);
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Não foi possível carregar a disponibilidade.');
            state.items = data.items || []; state.teamId = data.team_id; state.season = data.season; state.round = data.round_number;
            $('[data-availability-context]').textContent = `Temporada ${state.season} · Rodada ${state.round} · Time selecionado`;
            const clubSelect = $('[data-filter-club]');
            const previous = clubSelect.value;
            const clubs = [...new Map(state.items.map((item) => [String(item.clube_id), item.clube_abrev || item.clube_nome || 'Clube'])).entries()].sort((a, b) => a[1].localeCompare(b[1], 'pt-BR'));
            clubSelect.innerHTML = '<option value="">Todos os times</option>' + clubs.map(([id, name]) => `<option value="${escapeHtml(id)}">${escapeHtml(name)}</option>`).join('');
            if (clubs.some(([id]) => id === previous)) clubSelect.value = previous;
            renderRows();
        };
        overlay.querySelectorAll('[data-filter-position],[data-filter-club],[data-filter-search],[data-filter-sort],[data-filter-scout]').forEach((control) => control.addEventListener(control.type === 'search' ? 'input' : 'change', () => {
            if (control.matches('[data-filter-position]')) reload().catch((error) => feedback(error.message, true));
            else renderRows();
        }));
        $('[data-reload]').addEventListener('click', () => reload().catch((error) => feedback(error.message, true)));
        overlay.querySelectorAll('[data-status-filter]').forEach((button) => button.addEventListener('click', () => {
            overlay.querySelectorAll('[data-status-filter]').forEach((tab) => tab.classList.toggle('active', tab === button));
            state.tab = button.dataset.statusFilter; renderRows();
        }));
        $('[data-rows]').addEventListener('click', async (event) => {
            const button = event.target.closest('button[data-rule]');
            if (!button || button.disabled) return;
            const athleteId = button.dataset.id;
            const rule = button.dataset.rule;
            const item = state.items.find((candidate) => String(candidate.atleta_id) === athleteId);
            const previousRule = item?.rule;
            state.pending.add(athleteId); if (item) item.rule = rule === 'clear' ? null : rule; renderRows();
            try {
                const endpoint = rule === 'clear'
                    ? `/api/player-availability/${athleteId}?${new URLSearchParams({ team_id: state.teamId, temporada: state.season, rodada: state.round })}`
                    : '/api/player-availability';
                const response = await fetch(endpoint, rule === 'clear' ? { method: 'DELETE' } : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ team_id: state.teamId, athlete_id: athleteId, rule, temporada: state.season, rodada: state.round }) });
                const data = await response.json();
                if (!response.ok) throw new Error(data.error || 'Não foi possível atualizar a disponibilidade.');
                feedback(rule === 'clear' ? 'Regra removida.' : 'Disponibilidade atualizada.');
            } catch (error) { if (item) item.rule = previousRule; feedback(error.message, true); }
            finally { state.pending.delete(athleteId); renderRows(); }
        });
        await reload().catch((error) => feedback(error.message, true));
    }

    async function load(prefix, atletaId, positionId, fallbackPhoto) {
        const root = document.getElementById(`modal${prefix}ScoutHistory`);
        if (!root || !atletaId) return;
        const modal = root.closest('.aero-player-detail-modal');
        if (modal) {
            modal.dataset.athleteId = atletaId;
            let actions = modal.querySelector('.module-player-availability-actions');
            if (!actions) {
                actions = document.createElement('div');
                actions.className = 'module-player-availability-actions';
                actions.innerHTML = '<button type="button" class="availability-mark-out">Cravar que não joga</button><button type="button" class="dashboard-availability-link availability-open-modal">Rever disponibilidade de jogadores</button><span role="status"></span>';
                root.before(actions);
                actions.querySelector('.availability-mark-out').addEventListener('click', async () => {
                    const button = actions.querySelector('.availability-mark-out');
                    const message = actions.querySelector('[role=status]');
                    const playerName = escapeHtml(modal.querySelector('h3')?.textContent?.trim() || 'este jogador');
                    const confirmed = typeof window.showConfirm === 'function'
                        ? await window.showConfirm(`Marcar ${playerName} como alguém que não joga nesta rodada? Ele sairá dos rankings e da escalação desta rodada. Você pode desfazer essa decisão na página “Disponibilidade dos jogadores”.`, 'Confirmar disponibilidade', { confirmText: 'Sim, não joga', cancelText: 'Cancelar' })
                        : window.confirm(`Marcar ${playerName} como não joga nesta rodada? Você pode desfazer em Disponibilidade dos jogadores.`);
                    if (!confirmed) return;
                    button.disabled = true;
                    try {
                        const contextRes = await fetch('/api/player-availability/candidates?context_only=1');
                        const context = await contextRes.json();
                        if (!contextRes.ok) throw new Error(context.error || 'Selecione um time primeiro.');
                        const res = await fetch('/api/player-availability', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({team_id:context.team_id, temporada:context.season, rodada:context.round_number, athlete_id:modal.dataset.athleteId, rule:'poupar'})});
                        const result = await res.json();
                        if (!res.ok) throw new Error(result.error || 'Não foi possível salvar.');
                        message.textContent = 'Marcado como não joga. Você pode desfazer em Disponibilidade dos jogadores.';
                        document.querySelectorAll('table button[data-atleta-id]').forEach(details => {
                            if (details.dataset.atletaId === modal.dataset.athleteId) details.closest('tr')?.remove();
                        });
                        modal.classList.add('hidden');
                        window.setTimeout(() => window.location.reload(), 450);
                    } catch (error) { message.textContent = error.message; }
                    finally { button.disabled = false; }
                });
                actions.querySelector('.availability-open-modal').addEventListener('click', openAvailabilityModal);
            }
            actions.querySelector('[role=status]').textContent = '';
        }
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
