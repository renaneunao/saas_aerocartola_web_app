/**
 * Função para obter a URL da foto de um jogador pelo ID
 * Tenta carregar .jpg primeiro, depois .png
 * Se não encontrar, retorna null para mostrar fallback
 */
function getPlayerImage(atletaId) {
    if (!atletaId) return null;
    
    const basePath = '/static/cartola_imgs/foto_atletas/';
    const jpgUrl = `${basePath}${atletaId}.jpg`;
    const pngUrl = `${basePath}${atletaId}.png`;
    
    // Retornar a URL do jpg primeiro (mais comum)
    // O código que chama essa função deve tentar carregar e usar onerror para tentar png
    return jpgUrl;
}

/**
 * Função para carregar foto de um jogador em um elemento img
 * Tenta jpg primeiro, depois png, e se falhar mostra um "X"
 */
function loadPlayerImage(imgElement, atletaId) {
    if (!imgElement || !atletaId) {
        mostrarFallback(imgElement);
        return;
    }
    
    const basePath = '/static/cartola_imgs/foto_atletas/';
    let tentouJpg = false;
    let tentouPng = false;
    
    // Função para tentar carregar uma extensão
    const tentarCarregar = (extensao) => {
        const url = `${basePath}${atletaId}.${extensao}`;
        
        // Configurar handlers antes de definir src
        imgElement.onload = function() {
            this.style.display = 'block';
            // Esconder fallback se existir
            const fallback = this.nextElementSibling;
            if (fallback && fallback.classList.contains('player-fallback')) {
                fallback.style.display = 'none';
            }
            // Limpar handlers
            this.onload = null;
            this.onerror = null;
        };
        
        imgElement.onerror = function() {
            if (extensao === 'jpg' && !tentouPng) {
                // Tentar png
                tentouJpg = true;
                tentarCarregar('png');
            } else {
                // Ambas falharam, mostrar X
                mostrarFallback(this);
                // Limpar handlers
                this.onload = null;
                this.onerror = null;
            }
        };
        
        // Definir src para iniciar o carregamento
        imgElement.src = url;
        
        if (extensao === 'jpg') {
            tentouJpg = true;
        } else {
            tentouPng = true;
        }
    };
    
    // Começar tentando jpg
    tentarCarregar('jpg');
}

/**
 * Mostra fallback com "X" quando foto não é encontrada
 */
function mostrarFallback(imgElement) {
    imgElement.style.display = 'none';
    
    // Criar ou mostrar elemento fallback
    let fallback = imgElement.nextElementSibling;
    if (!fallback || !fallback.classList.contains('player-fallback')) {
        fallback = document.createElement('div');
        fallback.className = 'player-fallback w-full h-full bg-red-600 rounded-full flex items-center justify-center';
        fallback.style.display = 'flex';
        fallback.innerHTML = '<span class="text-white font-bold text-xs">X</span>';
        imgElement.parentNode.insertBefore(fallback, imgElement.nextSibling);
    } else {
        fallback.style.display = 'flex';
    }
}

/**
 * Carrega fotos de todos os jogadores na página
 * Procura por elementos com id="player-img-{atletaId}"
 */
function loadAllPlayerImages() {
    const playerImages = document.querySelectorAll('[id^="player-img-"]');
    
    playerImages.forEach(function(img) {
        const atletaId = img.id.replace('player-img-', '');
        if (atletaId) {
            loadPlayerImage(img, parseInt(atletaId));
        }
    });
}

// Auto-carregar quando o DOM estiver pronto
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', loadAllPlayerImages);
} else {
    // DOM já está pronto
    loadAllPlayerImages();
}

// Exportar funções globalmente
window.getPlayerImage = getPlayerImage;
window.loadPlayerImage = loadPlayerImage;
window.loadAllPlayerImages = loadAllPlayerImages;
window.mostrarFallback = mostrarFallback;

