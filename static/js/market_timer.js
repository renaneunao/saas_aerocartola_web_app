/**
 * Market Countdown Timer for Aero Cartola
 * Handles the countdown until market closing based on timestamp
 */
function initMarketTimer() {
    const timerEl = document.getElementById('mercado-timer');
    if (!timerEl) return;

    const timestamp = parseInt(timerEl.getAttribute('data-timestamp'));
    if (!timestamp) return;

    const closingTime = timestamp * 1000;

    function updateTimer() {
        const now = new Date().getTime();
        const diff = closingTime - now;

        if (diff <= 0) {
            timerEl.innerHTML = "Mercado Fechado";
            return;
        }

        const days = Math.floor(diff / (1000 * 60 * 60 * 24));
        const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
        const mins = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
        const secs = Math.floor((diff % (1000 * 60)) / 1000);

        let timeStr = '<span class="hidden sm:inline">Fecha em: </span>';
        if (days > 0) timeStr += days + "d ";

        timeStr += hours.toString().padStart(2, '0') + ":" +
            mins.toString().padStart(2, '0') + ":" +
            secs.toString().padStart(2, '0');

        timerEl.innerHTML = timeStr;
    }

    // Update every second
    const interval = setInterval(updateTimer, 1000);
    updateTimer();

    // Clean up interval if element is removed from DOM (not strictly necessary but good practice)
    // In a SPA this would be more important.
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initMarketTimer);
} else {
    initMarketTimer();
}
