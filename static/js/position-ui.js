/*
 * Comportamento compartilhado das tabelas de jogadores.
 * A camada visual não altera dados nem cálculos.
 */
(function () {
    'use strict';

    const POSITION_TABLE_PATTERN = /^tabela(Goleiros|Zagueiros|Laterais|Meias|Atacantes|Treinadores)$/i;

    function escapeHtml(value) {
        return String(value == null ? '' : value)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    function textOf(element) {
        return element ? element.textContent.replace(/\s+/g, ' ').trim() : '';
    }

    function setupWeightPanel(form) {
        if (!form) return;
        const panel = form.parentElement;
        if (!panel || panel === form || panel.dataset.positionConfigReady === 'true') return;
        const header = panel.firstElementChild;
        if (!header) return;

        panel.dataset.positionConfigReady = 'true';
        panel.classList.add('position-config-panel', 'position-config-collapsed');
        const lockLayer = Array.from(panel.children).find((child) =>
            child !== header && child.classList.contains('absolute') && child.classList.contains('inset-0')
        );
        if (lockLayer) lockLayer.classList.add('position-config-lock');

        header.classList.add('position-config-header');
        header.setAttribute('role', 'button');
        header.setAttribute('tabindex', '0');
        header.setAttribute('aria-expanded', 'false');
        header.setAttribute('aria-controls', form.id || 'pesosForm');
        header.setAttribute('title', 'Expandir configuração de pesos');

        const chevron = document.createElement('i');
        chevron.className = 'fas fa-chevron-down position-config-chevron';
        chevron.setAttribute('aria-hidden', 'true');
        header.querySelector('.flex.items-center')?.appendChild(chevron);

        const setExpanded = (expanded) => {
            panel.classList.toggle('position-config-collapsed', !expanded);
            header.setAttribute('aria-expanded', String(expanded));
            header.setAttribute('title', expanded ? 'Minimizar configuração de pesos' : 'Expandir configuração de pesos');
            chevron.classList.toggle('is-expanded', expanded);
        };
        const toggle = () => setExpanded(panel.classList.contains('position-config-collapsed'));
        header.addEventListener('click', toggle);
        header.addEventListener('keydown', (event) => {
            if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                toggle();
            }
        });
    }

    function setupWeightPanels() {
        document.querySelectorAll('form#pesosForm, form input[name^="f_"]')
            .forEach((element) => setupWeightPanel(element.tagName === 'FORM' ? element : element.form));
    }

    function imageSource(image) {
        return image && image.getAttribute('src') ? image.getAttribute('src') : '';
    }

    function abbreviation(name, explicit) {
        const value = String(explicit || '').trim();
        if (value) return value.slice(0, 4).toUpperCase();
        const normalized = String(name || '').trim().replace(/[^A-Za-zÀ-ÿ0-9 ]/g, ' ');
        const key = normalized.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/\s+/g, ' ');
        const known = {
            'athletico paranaense': 'CAP', 'athletico-pr': 'CAP', 'atletico pr': 'CAP',
            'atletico mineiro': 'CAM', 'atletico-mg': 'CAM', 'bahia': 'BAH',
            'botafogo': 'BOT', 'bragantino': 'RBB', 'red bull bragantino': 'RBB',
            'ceara': 'CEA', 'corinthians': 'COR', 'cruzeiro': 'CRU',
            'flamengo': 'FLA', 'fluminense': 'FLU', 'fortaleza': 'FOR',
            'gremio': 'GRE', 'internacional': 'INT', 'juventude': 'JUV',
            'mirassol': 'MIR', 'palmeiras': 'PAL', 'santos': 'SAN',
            'sao paulo': 'SAO', 'sport': 'SPO', 'vasco': 'VAS', 'vitoria': 'VIT'
        };
        if (known[key]) return known[key];
        const compact = key.replace(/\s+/g, '');
        if (compact.length <= 4) return compact.toUpperCase();
        return normalized ? normalized.split(/\s+/).map((part) => part[0]).join('').slice(0, 3).toUpperCase() : '---';
    }

    function shieldMarkup(url, name, abbr, extraClass) {
        if (url) {
            return `<img src="${escapeHtml(url)}" alt="${escapeHtml(name)}" class="position-game-shield ${extraClass || ''}">`;
        }
        return `<span class="position-game-shield-fallback ${extraClass || ''}" aria-hidden="true">${escapeHtml(abbreviation(name, abbr))}</span>`;
    }

    function boolFromAttribute(value) {
        if (value === 'true' || value === '1') return true;
        if (value === 'false' || value === '0') return false;
        return null;
    }

    function renderFixture(clubCell, opponentCell) {
        const clubName = clubCell.dataset.positionClubName || textOf(clubCell) || 'Clube';
        const opponentName = clubCell.dataset.positionOpponentName || textOf(opponentCell) || 'Adversário';
        const clubId = clubCell.dataset.positionClubId || '';
        const homeId = clubCell.dataset.positionHomeId || '';

        let playerIsHome = boolFromAttribute(clubCell.dataset.positionPlayerHome);
        if (playerIsHome === null && homeId && clubId) playerIsHome = String(homeId) === String(clubId);
        if (playerIsHome === null) playerIsHome = true;

        const homeName = playerIsHome ? clubName : opponentName;
        const awayName = playerIsHome ? opponentName : clubName;
        const homeIsPlayer = playerIsHome;
        const awayIsPlayer = !playerIsHome;
        const opponentImage = opponentCell ? opponentCell.querySelector('img') : null;
        const playerShieldUrl = clubCell.dataset.positionClubShield || '';
        const opponentShieldUrl = clubCell.dataset.positionOpponentShield || imageSource(opponentImage);
        const homeUrl = clubCell.dataset.positionHomeShield || (homeIsPlayer ? playerShieldUrl : opponentShieldUrl);
        const awayUrl = clubCell.dataset.positionAwayShield || (awayIsPlayer ? playerShieldUrl : opponentShieldUrl);
        const clubAbbr = clubCell.dataset.positionClubAbbr || '';
        const opponentAbbr = clubCell.dataset.positionOpponentAbbr || '';
        const homeAbbr = homeIsPlayer ? clubAbbr : opponentAbbr;
        const awayAbbr = awayIsPlayer ? clubAbbr : opponentAbbr;

        const fixture = document.createElement('div');
        fixture.className = 'position-game-inline';
        fixture.title = `${homeName} x ${awayName}`;
        fixture.setAttribute('aria-label', `${homeName} contra ${awayName}`);
        fixture.innerHTML = `
            <span class="position-game-label position-game-label--home ${homeIsPlayer ? 'position-game-team--player' : 'position-game-team--opponent'}">
                ${escapeHtml(abbreviation(homeName, homeAbbr))}
            </span>
            <span class="position-game-shields" aria-hidden="true">
                ${shieldMarkup(homeUrl, homeName, homeAbbr, homeIsPlayer ? 'position-game-shield--player' : 'position-game-shield--opponent')}
                <span class="position-game-inline-vs">×</span>
                ${shieldMarkup(awayUrl, awayName, awayAbbr, awayIsPlayer ? 'position-game-shield--player' : 'position-game-shield--opponent')}
            </span>
            <span class="position-game-label position-game-label--away ${awayIsPlayer ? 'position-game-team--player' : 'position-game-team--opponent'}">
                ${escapeHtml(abbreviation(awayName, awayAbbr))}
            </span>`;
        return fixture;
    }

    function markPlayerCell(playerCell) {
        playerCell.classList.add('position-player-sticky');
        // Só remova o marcador explícito do escudo do clube. A foto do
        // jogador nunca é inferida por tamanho ou removida por wrapper.
        playerCell.querySelectorAll('.position-team-shield').forEach((shield) => shield.closest('.position-team-shield-wrap')?.remove() || shield.remove());
    }

    function tableIsPositionTable(table) {
        if (table.classList.contains('position-player-table')) return true;
        if (POSITION_TABLE_PATTERN.test(table.id || '')) return true;
        const labels = Array.from(table.querySelectorAll('thead th')).map((cell) => textOf(cell).toLowerCase());
        return labels.includes('jogador') && labels.includes('pontuação');
    }

    function prepareTable(table) {
        if (!tableIsPositionTable(table)) return;
        table.classList.add('position-table');
        table.closest('.overflow-x-auto')?.classList.add('position-table-scroll');

        const headerRow = table.querySelector('thead tr');
        if (!headerRow) return;
        const headers = Array.from(headerRow.children);
        const visiblePlayerIndex = headers.findIndex((cell) => ['jogador', 'nome'].includes(textOf(cell).toLowerCase()));
        const visibleClubIndex = headers.findIndex((cell) => ['clube', 'casa'].includes(textOf(cell).toLowerCase()));
        const headerOpponentIndex = headers.findIndex((cell) => ['adversário', 'adversario', 'visitante'].includes(textOf(cell).toLowerCase()));
        const storedPlayerIndex = Number.parseInt(table.dataset.positionPlayerIndex || '', 10);
        const storedClubIndex = Number.parseInt(table.dataset.positionClubIndex || '', 10);
        const storedOpponentIndex = Number.parseInt(table.dataset.positionOpponentIndex || '', 10);
        const playerIndex = visiblePlayerIndex >= 0 ? visiblePlayerIndex : storedPlayerIndex;
        const clubIndex = visibleClubIndex >= 0 ? visibleClubIndex : storedClubIndex;
        const opponentIndex = headerOpponentIndex >= 0 ? headerOpponentIndex :
            (Number.isInteger(storedOpponentIndex) ? storedOpponentIndex : -1);

        // Treinadores e tabelas de outros módulos não têm adversário; nunca
        // tente fundir uma coluna inexistente por posição numérica.
        if (!Number.isInteger(playerIndex) || !Number.isInteger(clubIndex) || opponentIndex < 0) return;
        table.dataset.positionPlayerIndex = String(playerIndex);
        table.dataset.positionClubIndex = String(clubIndex);
        if (headerOpponentIndex >= 0) table.dataset.positionOpponentIndex = String(headerOpponentIndex);

        headerRow.children[playerIndex].classList.add('position-player-sticky');
        table.querySelectorAll('tbody tr').forEach((row) => {
            const playerCell = row.children[playerIndex];
            if (playerCell) markPlayerCell(playerCell);
        });

        let renderedRows = 0;
        const newlyRenderedRows = [];
        table.querySelectorAll('tbody tr').forEach((row) => {
            const clubCell = row.children[clubIndex];
            const playerCell = row.children[playerIndex];
            if (!clubCell || !playerCell) return;
            // Uma tabela pode ser recalculada sem que o elemento <table> seja
            // recriado. As linhas antigas já não possuem Clube/Adversário,
            // portanto não podem ser lidas novamente por índice.
            if (playerCell.dataset.positionGameReady === 'true') {
                renderedRows += 1;
                return;
            }
            // Após a primeira passagem o cabeçalho já não possui a coluna de
            // adversário. Linhas novas ainda chegam com a estrutura original;
            // só leia essa célula para linhas que ainda não foram renderizadas.
            const opponentCell = clubCell.dataset.positionFixtureReady === 'true'
                ? null
                : row.children[opponentIndex];
            if (!opponentCell && clubCell.dataset.positionFixtureReady !== 'true') return;
            if (clubCell.dataset.positionFixtureReady !== 'true') {
                const fixture = renderFixture(clubCell, opponentCell);
                const playerLine = playerCell.querySelector('.flex.items-center') || playerCell.firstElementChild;
                if (playerLine) {
                    playerLine.classList.add('position-player-line');
                    playerLine.insertBefore(fixture, playerLine.firstChild);
                } else {
                    playerCell.insertBefore(fixture, playerCell.firstChild);
                }
                clubCell.dataset.positionFixtureReady = 'true';
                playerCell.dataset.positionGameReady = 'true';
                newlyRenderedRows.push(row);
            }
            renderedRows += 1;
        });

        // Não remova cabeçalho/células enquanto o tbody ainda está vazio.
        // Os renderizadores assíncronos inserem as linhas depois do DOMReady.
        if (!renderedRows) return;

        if (headerOpponentIndex >= 0) {
            [headerOpponentIndex, clubIndex]
                .sort((a, b) => b - a)
                .forEach((index) => headerRow.children[index]?.remove());
        }
        newlyRenderedRows.forEach((row) => {
            [opponentIndex, clubIndex]
                .sort((a, b) => b - a)
                .forEach((index) => row.children[index]?.remove());
        });
    }

    function setupPositionTables() {
        document.querySelectorAll('table').forEach(prepareTable);
    }

    function isPositionPage() {
        return Boolean(document.querySelector('form#pesosForm, table[id^="tabela"], table.position-player-table'));
    }

    function initialize() {
        if (isPositionPage()) document.body.classList.add('position-page');
        setupWeightPanels();
        setupPositionTables();
        const observer = new MutationObserver(() => {
            setupWeightPanels();
            setupPositionTables();
        });
        observer.observe(document.body, { childList: true, subtree: true });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initialize, { once: true });
    } else {
        initialize();
    }
})();
