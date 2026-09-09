(function () {
    'use strict';

    function pad(value) {
        return String(Math.max(0, Math.floor(value))).padStart(2, '0');
    }

    function updateCountdown(element) {
        const deadline = Date.parse(element.dataset.marketDeadline || '');
        if (!Number.isFinite(deadline)) return;
        const totalSeconds = Math.max(0, Math.floor((deadline - Date.now()) / 1000));
        const days = Math.floor(totalSeconds / 86400);
        const hours = Math.floor((totalSeconds % 86400) / 3600);
        const minutes = Math.floor((totalSeconds % 3600) / 60);
        const seconds = totalSeconds % 60;
        element.querySelector('[data-countdown-days]')?.replaceChildren(document.createTextNode(days));
        element.querySelector('[data-countdown-hours]')?.replaceChildren(document.createTextNode(pad(hours)));
        element.querySelector('[data-countdown-minutes]')?.replaceChildren(document.createTextNode(pad(minutes)));
        element.querySelector('[data-countdown-seconds]')?.replaceChildren(document.createTextNode(pad(seconds)));
        element.classList.toggle('is-closed', totalSeconds === 0);
    }

    function init() {
        const countdown = document.querySelector('[data-market-deadline]');
        if (!countdown) return;
        updateCountdown(countdown);
        window.setInterval(() => updateCountdown(countdown), 1000);
    }

    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, { once: true });
    else init();
}());
