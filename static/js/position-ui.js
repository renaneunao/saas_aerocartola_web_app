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
        const panel = form.closest('.relative');
        if (!panel || panel.dataset.positionConfigReady === 'true') return;

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

    function teamShieldFromPlayerCell(playerCell, clubName) {
        if (!playerCell) return '';
        const images = Array.from(playerCell.querySelectorAll('img'));
        const matchingImage = images.find((image) => image.alt === clubName);
        return matchingImage || images[1] || null;
    }

    function renderGameCell(clubCell, opponentCell, playerCell) {
        const clubName = textOf(clubCell) || 'Clube';
        const opponentName = textOf(opponentCell) || 'Adversário';
        const shield = teamShieldFromPlayerCell(playerCell, clubName);
        const opponentShield = opponentCell?.querySelector('img');
        const shieldMarkup = shield && shield.src
            ? `<img src="${escapeHtml(shield.src)}" alt="${escapeHtml(clubName)}" class="position-game-shield">`
            : '<i class="fas fa-shield-halved position-game-shield-icon" aria-hidden="true"></i>';
        const opponentShieldMarkup = opponentShield && opponentShield.src
            ? `<img src="${escapeHtml(opponentShield.src)}" alt="${escapeHtml(opponentName)}" class="position-game-shield">`
            : '<i class="fas fa-shield-halved" aria-hidden="true"></i>';

        clubCell.innerHTML = `
            <div class="position-game" title="${escapeHtml(clubName)} contra ${escapeHtml(opponentName)}">
                <span class="position-game-team position-game-team--player">
                    ${shieldMarkup}
                    <span class="position-game-team-name">${escapeHtml(clubName)}</span>
                </span>
                <span class="position-game-vs" aria-hidden="true">VS</span>
                <span class="position-game-team position-game-team--opponent" aria-label="Adversário: ${escapeHtml(opponentName)}" title="Adversário oculto">
                    ${opponentShieldMarkup}
                </span>
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

    function initialize() {
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
