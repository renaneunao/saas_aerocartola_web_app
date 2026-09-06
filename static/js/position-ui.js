/*
 * Ajustes visuais compartilhados pelas páginas de posições.
 * Este arquivo não altera os dados recebidos nem participa dos cálculos.
 */
(function () {
    'use strict';

    const POSITION_TABLE_PATTERN = /^tabela(Goleiros|Zagueiros|Laterais|Meias|Atacantes|Treinadores)$/i;

    function escapeHtml(value) {
        return String(value || '')
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

        // O próprio formulário também possui a classe `relative`. O painel
        // real é o contêiner pai, que contém cabeçalho, overlay e formulário.
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
        return image && image.getAttribute('src') && image.getAttribute('src') !== ''
            ? image.getAttribute('src')
            : '';
    }

    function fallbackShield(cell, alt) {
        if (!cell) return '';
        const image = Array.from(cell.querySelectorAll('img')).find((candidate) =>
            (candidate.getAttribute('alt') || '').trim() === alt
        ) || cell.querySelector('img');
        return imageSource(image);
    }

    function shieldMarkup(url, name, abbreviation) {
        if (url) {
            return `<img src="${escapeHtml(url)}" alt="${escapeHtml(name)}" class="position-game-shield">`;
        }
        // Nunca substitua um escudo por um escudo genérico. Se a origem não
        // tiver URL, mantenha uma identificação textual curta do clube.
        return `<span class="position-game-shield-fallback" aria-hidden="true">${escapeHtml((abbreviation || name || '?').slice(0, 3).toUpperCase())}</span>`;
    }

    function renderGameCell(clubCell, opponentCell, playerCell) {
        const playerClubName = textOf(clubCell) || 'Clube';
        const opponentName = textOf(opponentCell) || 'Adversário';
        const playerIsHome = clubCell.dataset.positionPlayerHome === 'true';
        const playerIsAway = clubCell.dataset.positionPlayerHome === 'false';
        const knownMando = playerIsHome || playerIsAway;

        // A ordem visual segue a partida real: mandante à esquerda e
        // visitante à direita. O destaque acompanha o clube do atleta.
        const homeName = knownMando
            ? (playerIsHome ? playerClubName : opponentName)
            : playerClubName;
        const awayName = knownMando
            ? (playerIsAway ? playerClubName : opponentName)
            : opponentName;
        const homeIsPlayer = knownMando ? playerIsHome : true;
        const awayIsPlayer = knownMando ? playerIsAway : false;
        const homeUrl = clubCell.dataset.positionHomeShield ||
            (homeIsPlayer ? fallbackShield(playerCell, playerClubName) : fallbackShield(opponentCell, opponentName));
        const awayUrl = clubCell.dataset.positionAwayShield ||
            (awayIsPlayer ? fallbackShield(playerCell, playerClubName) : fallbackShield(opponentCell, opponentName));
        const teamMarkup = (name, url, isPlayer, sideLabel, sideClass) => `
            <span class="position-game-team position-game-team--${sideClass} ${isPlayer ? 'position-game-team--player' : 'position-game-team--opponent'}"
                  aria-label="${escapeHtml(sideLabel)}: ${escapeHtml(name)}"
                  title="${escapeHtml(name)}">
                ${shieldMarkup(url, name, name)}
                <span class="position-game-team-name">${escapeHtml(name)}</span>
            </span>`;

        clubCell.innerHTML = `
            <div class="position-game" title="${escapeHtml(homeName)} contra ${escapeHtml(awayName)}">
                ${teamMarkup(homeName, homeUrl, homeIsPlayer, 'Casa', 'home')}
                <span class="position-game-vs" aria-hidden="true">VS</span>
                ${teamMarkup(awayName, awayUrl, awayIsPlayer, 'Fora', 'away')}
            </div>`;
        clubCell.classList.add('position-game-cell');
    }

    function prepareTable(table) {
        if (!table || !POSITION_TABLE_PATTERN.test(table.id || '')) return;

        table.classList.add('position-table');
        table.closest('.overflow-x-auto')?.classList.add('position-table-scroll');

        const headerRow = table.querySelector('thead tr');
        if (!headerRow) return;

        const headers = Array.from(headerRow.children);
        const playerIndex = headers.findIndex((cell) => textOf(cell).toLowerCase() === 'jogador');
        const originalClubIndex = headers.findIndex((cell) => {
            const label = textOf(cell).toLowerCase();
            return label === 'clube' || label === 'casa';
        });
        const gameIndex = originalClubIndex >= 0
            ? originalClubIndex
            : headers.findIndex((cell) => textOf(cell).toLowerCase() === 'jogo');
        const opponentIndex = headers.findIndex((cell) => {
            const label = textOf(cell).toLowerCase();
            return label === 'adversário' || label === 'adversario' || label === 'visitante';
        });
        const hasOpponentColumn = opponentIndex >= 0 || table.dataset.positionHasOpponent === 'true';
        if (opponentIndex >= 0) table.dataset.positionHasOpponent = 'true';

        if (playerIndex < 0 || gameIndex < 0) return;

        headerRow.children[playerIndex].classList.add('position-player-sticky');
        const clubHeader = headerRow.children[gameIndex];
        if (textOf(clubHeader).toLowerCase() !== 'jogo') clubHeader.textContent = 'Jogo';
        clubHeader.classList.add('position-game-header');
        if (clubHeader.getAttribute('title') !== 'Clube do atleta e adversário') {
            clubHeader.setAttribute('title', 'Clube do atleta e adversário');
        }

        if (opponentIndex >= 0 && opponentIndex !== gameIndex) {
            headerRow.children[opponentIndex].remove();
        }

        table.querySelectorAll('tbody tr').forEach((row) => {
            const cells = Array.from(row.children);
            if (cells.length <= Math.max(playerIndex, gameIndex)) return;

            const playerCell = cells[playerIndex];
            const clubCell = cells[gameIndex];
            const gameAlreadyReady = clubCell.dataset.positionGameReady === 'true';
            // Após a primeira passagem, o cabeçalho já se chama "Jogo", mas
            // novas linhas ainda podem vir com as duas células originais.
            const opponentCell = hasOpponentColumn
                ? (opponentIndex >= 0
                    ? cells[opponentIndex]
                    : (!gameAlreadyReady && cells.length > headerRow.children.length ? cells[gameIndex + 1] : null))
                : null;

            playerCell.classList.add('position-player-sticky');
            if (!gameAlreadyReady) {
                renderGameCell(clubCell, opponentCell, playerCell);
                clubCell.dataset.positionGameReady = 'true';
            }
            if (opponentCell && opponentCell !== clubCell) opponentCell.remove();
        });
    }

    function setupPositionTables() {
        document.querySelectorAll('table').forEach(prepareTable);
    }

    function isPositionPage() {
        return Boolean(
            document.querySelector('form#pesosForm') ||
            document.querySelector('table[id^="tabela"]')
        );
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
