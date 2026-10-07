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

    function cededSummary(profile, mando) {
        const summary = profile?.por_mando?.[mando];
        if (!summary || !Number(summary.jogos_com_dados)) {
            return '<div class="modal-scout-history-ceded-empty">Sem partidas suficientes neste mando.</div>';
        }
        const recommended = profile?.mando_relevante === mando;
        const scoutRows = (summary.scouts_detalhados || [])
            .filter((item) => Math.round(Math.abs(Number(item.media_por_jogo) || 0)) > 0)
            .map((item) => `<div class="modal-scout-history-ceded-row ${negativeScouts.has(item.codigo) ? 'is-negative' : 'is-positive'}"><span><b>${escapeHtml(labels[item.codigo] || item.codigo.toUpperCase())}</b> ${escapeHtml(item.nome || '')}</span><strong>${Math.round(Math.abs(Number(item.media_por_jogo) || 0)).toLocaleString('pt-BR')} <small>${Number(item.recorrencia || 0)}%</small></strong></div>`)
            .join('');
        const recent = (summary.historico || []).slice(0, 8).map((match) => {
            const players = (match.jogadores || []).map((player) => {
                const photo = window.resolvePlayerPhoto(player.foto, player.id);
                const avatar = photo ? `<img src="${escapeHtml(photo)}" alt="" loading="lazy">` : '<i class="fas fa-user"></i>';
                return `<div class="modal-scout-history-ceded-player"><span class="modal-scout-history-ceded-player-avatar">${avatar}</span><strong>${escapeHtml(player.nome || 'Atleta')}</strong><span class="modal-scout-history-ceded-player-scouts">${scoutSummary(player.scouts)}</span><b>${number(player.pontuacao)} pts</b></div>`;
            }).join('') || '<span class="modal-scout-history-ceded-empty">Sem atleta da posição com dados.</span>';
            return `<details class="modal-scout-history-ceded-match"><summary><span>Rodada ${match.rodada}</span><span class="modal-scout-history-ceded-fixture">${fixtureMarkup(match)}</span><span class="modal-scout-history-ceded-scouts-inline">${scoutSummary(match.scouts)}</span><strong>${number(match.pontuacao)} pts</strong><i class="fas fa-chevron-down" aria-hidden="true"></i></summary><div class="modal-scout-history-ceded-players">${players}</div></details>`;
        }).join('');
        return `<div class="modal-scout-history-ceded-context ${recommended ? 'is-recommended' : ''}">${recommended ? '<i class="fas fa-crosshairs"></i><span>Recorte mais parecido com o confronto atual</span>' : '<span>Histórico geral deste mando</span>'}</div><div class="modal-scout-history-ceded-metrics"><span><small>Jogos</small><b>${summary.jogos_com_dados}</b></span><span><small>Pts/jogo</small><b>${number(summary.pontuacao_por_jogo)}</b></span><span><small>Pts/atleta</small><b>${number(summary.pontuacao_por_atleta)}</b></span><span><small>Pico</small><b>${number(summary.pico)}</b></span></div><div class="modal-scout-history-ceded-thresholds"><span>≥5 pts <b>${summary.recorrencia?.['5'] || 0}%</b></span><span>≥8 pts <b>${summary.recorrencia?.['8'] || 0}%</b></span><span>≥12 pts <b>${summary.recorrencia?.['12'] || 0}%</b></span></div><div class="modal-scout-history-ceded-scouts">${scoutRows || '<span class="modal-scout-history-ceded-empty">Nenhum scout positivo no recorte.</span>'}</div><div class="modal-scout-history-ceded-matches">${recent || '<span class="modal-scout-history-ceded-empty">Sem partidas recentes.</span>'}</div>`;
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
            cededHome.innerHTML = cededSummary(profile, 'casa');
            cededAway.innerHTML = cededSummary(profile, 'fora');
            ceded.hidden = !Object.values(profile.por_mando || {}).some((summary) => Number(summary?.jogos_com_dados) > 0);
        }
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
                actions.innerHTML = '<button type="button" class="ideal-panel-expand">Cravar que não joga</button><a class="dashboard-availability-link" href="/api/player-availability/page">Rever disponibilidade</a><span role="status"></span>';
                root.before(actions);
                actions.querySelector('button').addEventListener('click', async () => {
                    const button = actions.querySelector('button');
                    const message = actions.querySelector('[role=status]');
                    button.disabled = true;
                    try {
                        const contextRes = await fetch('/api/player-availability/candidates?context_only=1');
                        const context = await contextRes.json();
                        if (!contextRes.ok) throw new Error(context.error || 'Selecione um time primeiro.');
                        const res = await fetch('/api/player-availability', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({team_id:context.team_id, temporada:context.season, rodada:context.round_number, athlete_id:modal.dataset.athleteId, rule:'poupar'})});
                        const result = await res.json();
                        if (!res.ok) throw new Error(result.error || 'Não foi possível salvar.');
                        message.textContent = 'Marcado como não joga. Removido do ranking desta rodada.';
                        document.querySelectorAll('table button[data-atleta-id]').forEach(details => {
                            if (details.dataset.atletaId === modal.dataset.athleteId) details.closest('tr')?.remove();
                        });
                        modal.classList.add('hidden');
                    } catch (error) { message.textContent = error.message; }
                    finally { button.disabled = false; }
                });
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
