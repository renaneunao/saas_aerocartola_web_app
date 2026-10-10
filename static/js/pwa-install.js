(() => {
    'use strict';
    const banner = document.getElementById('aeroInstallBanner');
    if (!banner) return;
    const action = document.getElementById('aeroInstallAction');
    const help = document.getElementById('aeroInstallHelp');
    const dismissalKey = 'aero-cartola-install-dismissed-v1';
    const standalone = window.matchMedia('(display-mode: standalone)');
    const ios = /iPad|iPhone|iPod/.test(navigator.userAgent)
        || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
    const mobile = ios || /Android/.test(navigator.userAgent);
    let deferredPrompt = null;
    let dismissed = false;
    try { dismissed = localStorage.getItem(dismissalKey) === '1'; } catch (_) { /* Armazenamento indisponível. */ }
    const installed = () => standalone.matches || navigator.standalone === true;
    function render() {
        banner.hidden = installed() || dismissed || (!mobile && !deferredPrompt);
        action.textContent = deferredPrompt ? 'Instalar Aero Cartola' : 'Adicionar atalho';
        if (installed() && help.open) help.close();
    }
    function dismiss() {
        dismissed = true;
        try { localStorage.setItem(dismissalKey, '1'); } catch (_) { /* Dispensa apenas nesta visita. */ }
        render();
    }
    function showInstructions() {
        const otherIosBrowser = ios && /CriOS|FxiOS|EdgiOS|OPiOS/.test(navigator.userAgent);
        document.getElementById('aeroInstallHelpIntro').textContent = ios
            ? (otherIosBrowser ? 'Se a opção não aparecer neste navegador, abra aerocartola.com no Safari.' : 'No iPhone, adicione pelo menu de compartilhamento do Safari.')
            : 'Adicione o Aero Cartola pelo menu do seu navegador.';
        const steps = ios
            ? ['Toque em Compartilhar (quadrado com uma seta para cima). Se não estiver visível, procure no menu do navegador.', 'Escolha “Adicionar à Tela de Início”. Se necessário, role a lista de opções.', 'Confirme o nome “Aero Cartola” e toque em “Adicionar”. A logo aparecerá na sua tela inicial.']
            : ['Abra o menu do navegador (geralmente os três pontos).', 'Escolha “Instalar aplicativo” ou “Adicionar à tela inicial”.', 'Confirme para criar o atalho do Aero Cartola.'];
        document.getElementById('aeroInstallHelpSteps').replaceChildren(...steps.map(text => {
            const li = document.createElement('li'); li.textContent = text; return li;
        }));
        help.showModal();
    }
    window.addEventListener('beforeinstallprompt', event => {
        event.preventDefault(); deferredPrompt = event; render();
    });
    window.addEventListener('appinstalled', () => {
        deferredPrompt = null; dismiss(); if (help.open) help.close();
    });
    standalone.addEventListener('change', render);
    document.getElementById('aeroInstallDismiss').addEventListener('click', dismiss);
    document.getElementById('aeroInstallHelpClose').addEventListener('click', () => help.close());
    document.getElementById('aeroInstallHelpDone').addEventListener('click', () => { help.close(); dismiss(); });
    help.addEventListener('click', event => {
        if (event.target !== help) return;
        const r = help.getBoundingClientRect();
        if (event.clientX < r.left || event.clientX > r.right || event.clientY < r.top || event.clientY > r.bottom) help.close();
    });
    action.addEventListener('click', async () => {
        if (!deferredPrompt) { showInstructions(); return; }
        const prompt = deferredPrompt; deferredPrompt = null; action.disabled = true;
        try {
            await prompt.prompt();
            const result = await prompt.userChoice;
            if (result.outcome === 'accepted') dismiss();
        } catch (_) { showInstructions(); }
        finally { action.disabled = false; render(); }
    });
    render();
})();
