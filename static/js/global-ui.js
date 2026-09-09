/* Melhorias visuais globais, sem interferir em dados ou regras de negócio. */
(function () {
    'use strict';

    const BLUE_STYLE_PATTERN = /(^|\s)(bg-(blue|sky|cyan)-|from-(blue|sky|cyan)-|to-(blue|sky|cyan)-)/;
    const SEMANTIC_PATTERN = /excluir|remover|apagar|cancelar|sair|logout|salvar|confirmar|enviar|pagar|assinar|upgrade|reembolsar/;

    function normalizeButton(button) {
        if (!(button instanceof HTMLElement) || button.dataset.aeroButtonReady === 'true') return;
        button.dataset.aeroButtonReady = 'true';

        const label = (button.textContent || button.getAttribute('aria-label') || '')
            .replace(/\s+/g, ' ')
            .trim()
            .toLowerCase();
        const classes = button.getAttribute('class') || '';
        const isDanger = /(^|\s)(bg-red-|from-red-|to-red-|text-red-)/.test(classes);
        if (!isDanger && !SEMANTIC_PATTERN.test(label) && BLUE_STYLE_PATTERN.test(classes)) {
            button.classList.add('aero-button-neutral');
        }
        if (/detalhes|visualizar|ver detalhes/.test(label)) {
            button.classList.add('aero-button-details');
        }
    }

    function normalizeTable(table) {
        if (!(table instanceof HTMLTableElement) || table.classList.contains('position-table')) return;
        table.classList.add('aero-responsive-table');
        const parent = table.parentElement;
        if (parent) parent.classList.add('aero-table-scroll');
    }

    function audit(root) {
        if (!(root instanceof Element || root instanceof Document)) return;
        if (root.matches?.('button, a[role="button"], a[class*="bg-"]')) normalizeButton(root);
        root.querySelectorAll?.('button, a[role="button"], a[class*="bg-"]').forEach(normalizeButton);
        if (root.matches?.('table')) normalizeTable(root);
        root.querySelectorAll?.('table').forEach(normalizeTable);
    }

    function initialize() {
        document.body.classList.add('aero-global-ui');
        audit(document);
        new MutationObserver((mutations) => {
            mutations.forEach((mutation) => mutation.addedNodes.forEach((node) => audit(node)));
        }).observe(document.body, { childList: true, subtree: true });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initialize, { once: true });
    } else {
        initialize();
    }
})();
