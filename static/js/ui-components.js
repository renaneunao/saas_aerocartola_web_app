/**
 * UI Components - Sistema centralizado de feedback visual
 * Spinner, Toasts, Confirmações e Alerts personalizados
 */

// =============================================================================
// LOADER / SPINNER
// =============================================================================

let loaderElement = null;
let loaderCount = 0; // Para gerenciar múltiplas chamadas simultâneas

/**
 * Mostra um spinner de carregamento global
 * @param {string} message - Mensagem a ser exibida (opcional)
 */
function showLoader(message = 'Carregando...') {
    loaderCount++;
    
    if (!loaderElement) {
        // Criar elemento do loader
        loaderElement = document.createElement('div');
        loaderElement.id = 'globalLoader';
        loaderElement.className = 'fixed inset-0 flex items-center justify-center z-[9999] transition-opacity duration-300';
        loaderElement.style.opacity = '0';
        loaderElement.style.backdropFilter = 'blur(8px)';
        loaderElement.style.backgroundColor = 'rgba(0, 0, 0, 0.7)';
        
        loaderElement.innerHTML = `
            <style>
                @keyframes neonPulse {
                    0%, 100% {
                        box-shadow: 0 0 20px rgba(59, 130, 246, 0.8),
                                    0 0 40px rgba(59, 130, 246, 0.6),
                                    0 0 60px rgba(59, 130, 246, 0.4),
                                    inset 0 0 20px rgba(59, 130, 246, 0.3);
                    }
                    50% {
                        box-shadow: 0 0 30px rgba(59, 130, 246, 1),
                                    0 0 60px rgba(59, 130, 246, 0.8),
                                    0 0 90px rgba(59, 130, 246, 0.6),
                                    inset 0 0 30px rgba(59, 130, 246, 0.5);
                    }
                }
                
                @keyframes spinNeon {
                    0% {
                        transform: rotate(0deg);
                    }
                    100% {
                        transform: rotate(360deg);
                    }
                }
                
                .neon-spinner {
                    animation: spinNeon 1s linear infinite;
                }
                
                .neon-ring {
                    animation: neonPulse 2s ease-in-out infinite;
                }
            </style>
            
            <div class="bg-gradient-to-br from-gray-900/90 to-gray-800/90 backdrop-blur-sm rounded-2xl shadow-2xl p-10 max-w-md w-full mx-4 transform transition-all duration-300 scale-95 border border-blue-500/30" id="loaderContent">
                <div class="flex flex-col items-center">
                    <!-- Spinner Neon -->
                    <div class="relative w-24 h-24 mb-6">
                        <!-- Anel externo com glow -->
                        <div class="absolute inset-0 rounded-full border-4 border-blue-500/20"></div>
                        
                        <!-- Anel animado com efeito neon -->
                        <div class="neon-spinner absolute inset-0">
                            <div class="w-full h-full rounded-full border-4 border-transparent border-t-blue-500 border-r-blue-400 neon-ring"></div>
                        </div>
                        
                        <!-- Centro com glow -->
                        <div class="absolute inset-0 flex items-center justify-center">
                            <div class="w-12 h-12 rounded-full bg-gradient-to-br from-blue-500 to-blue-600 shadow-lg" style="box-shadow: 0 0 20px rgba(59, 130, 246, 0.6), inset 0 0 10px rgba(255, 255, 255, 0.3);"></div>
                        </div>
                    </div>
                    
                    <!-- Mensagem -->
                    <p class="text-white text-lg font-semibold text-center mb-2" id="loaderMessage">${message}</p>
                    <p class="text-blue-300 text-sm text-center opacity-75">Aguarde...</p>
                </div>
            </div>
        `;
        
        document.body.appendChild(loaderElement);
        
        // Animação de entrada
        setTimeout(() => {
            loaderElement.style.opacity = '1';
            document.getElementById('loaderContent').style.transform = 'scale(1)';
        }, 10);
    } else {
        // Atualizar mensagem se já existir
        const messageEl = document.getElementById('loaderMessage');
        if (messageEl) {
            messageEl.textContent = message;
        }
    }
}

/**
 * Esconde o spinner de carregamento
 */
function hideLoader() {
    loaderCount = Math.max(0, loaderCount - 1);
    
    if (loaderCount === 0 && loaderElement) {
        loaderElement.style.opacity = '0';
        const content = document.getElementById('loaderContent');
        if (content) {
            content.style.transform = 'scale(0.95)';
        }
        
        setTimeout(() => {
            if (loaderElement && loaderElement.parentNode) {
                loaderElement.parentNode.removeChild(loaderElement);
            }
            loaderElement = null;
        }, 300);
    }
}

/**
 * Atualiza a mensagem do loader sem escondê-lo
 * @param {string} message - Nova mensagem
 */
function updateLoaderMessage(message) {
    const messageEl = document.getElementById('loaderMessage');
    if (messageEl) {
        messageEl.textContent = message;
    }
}

// =============================================================================
// TOAST NOTIFICATIONS
// =============================================================================

const toastContainer = createToastContainer();

function createToastContainer() {
    const container = document.createElement('div');
    container.id = 'toastContainer';
    container.className = 'fixed top-4 right-4 z-[9998] flex flex-col gap-2';
    document.body.appendChild(container);
    return container;
}

/**
 * Mostra uma notificação toast
 * @param {string} message - Mensagem a ser exibida
 * @param {string} type - Tipo: 'success', 'error', 'warning', 'info'
 * @param {number} duration - Duração em ms (0 = infinito)
 */
function showToast(message, type = 'info', duration = 4000) {
    const toast = document.createElement('div');
    
    const colors = {
        success: 'bg-green-600',
        error: 'bg-red-600',
        warning: 'bg-yellow-600',
        info: 'bg-blue-600'
    };
    
    const icons = {
        success: 'fa-check-circle',
        error: 'fa-exclamation-circle',
        warning: 'fa-exclamation-triangle',
        info: 'fa-info-circle'
    };
    
    toast.className = `${colors[type] || colors.info} text-white px-6 py-4 rounded-lg shadow-lg flex items-center gap-3 min-w-[300px] max-w-md transform transition-all duration-300 cursor-pointer hover:shadow-xl`;
    toast.style.transform = 'translateX(400px)';
    toast.style.opacity = '0';
    
    toast.innerHTML = `
        <i class="fas ${icons[type] || icons.info} text-xl flex-shrink-0"></i>
        <span class="flex-1 font-medium">${message}</span>
        <button class="ml-2 text-white hover:text-gray-200 transition-colors" onclick="this.parentElement.remove()">
            <i class="fas fa-times"></i>
        </button>
    `;
    
    toastContainer.appendChild(toast);
    
    // Animação de entrada
    setTimeout(() => {
        toast.style.transform = 'translateX(0)';
        toast.style.opacity = '1';
    }, 10);
    
    // Auto remover
    if (duration > 0) {
        setTimeout(() => {
            removeToast(toast);
        }, duration);
    }
    
    // Remover ao clicar
    toast.addEventListener('click', () => removeToast(toast));
    
    return toast;
}

function removeToast(toast) {
    toast.style.transform = 'translateX(400px)';
    toast.style.opacity = '0';
    setTimeout(() => {
        if (toast.parentNode) {
            toast.parentNode.removeChild(toast);
        }
    }, 300);
}

// =============================================================================
// ALERT PERSONALIZADO
// =============================================================================

/**
 * Mostra um alert customizado
 * @param {string} message - Mensagem
 * @param {string} title - Título (opcional)
 * @param {string} type - Tipo: 'success', 'error', 'warning', 'info'
 */
function showAlert(message, title = '', type = 'info') {
    return new Promise((resolve) => {
        const overlay = document.createElement('div');
        overlay.className = 'fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-[9999] transition-opacity duration-300';
        overlay.style.opacity = '0';
        
        const colors = {
            success: 'text-green-600',
            error: 'text-red-600',
            warning: 'text-yellow-600',
            info: 'text-blue-600'
        };
        
        const icons = {
            success: 'fa-check-circle',
            error: 'fa-exclamation-circle',
            warning: 'fa-exclamation-triangle',
            info: 'fa-info-circle'
        };
        
        overlay.innerHTML = `
            <div class="bg-gradient-to-br from-gray-900/95 to-gray-800/95 backdrop-blur-sm border-2 border-blue-500/30 rounded-2xl shadow-2xl p-6 max-w-md w-full mx-4 transform transition-all duration-300 scale-95" id="alertContent">
                <div class="flex items-start gap-4 mb-4">
                    <i class="fas ${icons[type] || icons.info} text-3xl ${colors[type] || colors.info} flex-shrink-0 mt-1"></i>
                    <div class="flex-1">
                        ${title ? `<h3 class="text-xl font-bold text-white mb-2">${title}</h3>` : ''}
                        <p class="text-gray-300">${message}</p>
                    </div>
                </div>
                <div class="flex justify-end">
                    <button class="px-6 py-2 bg-gradient-to-r from-blue-500 to-blue-600 hover:from-blue-600 hover:to-blue-700 text-white rounded-lg transition-all duration-200 font-medium shadow-lg" id="alertOkBtn" style="box-shadow: 0 0 20px rgba(59, 130, 246, 0.3);">
                        OK
                    </button>
                </div>
            </div>
        `;
        
        document.body.appendChild(overlay);
        
        // Animação de entrada
        setTimeout(() => {
            overlay.style.opacity = '1';
            document.getElementById('alertContent').style.transform = 'scale(1)';
        }, 10);
        
        // Função para fechar
        const closeAlert = () => {
            overlay.style.opacity = '0';
            document.getElementById('alertContent').style.transform = 'scale(0.95)';
            setTimeout(() => {
                if (overlay.parentNode) {
                    overlay.parentNode.removeChild(overlay);
                }
                resolve(true);
            }, 300);
        };
        
        // Event listeners
        document.getElementById('alertOkBtn').addEventListener('click', closeAlert);
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) closeAlert();
        });
    });
}

// =============================================================================
// CONFIRM PERSONALIZADO
// =============================================================================

/**
 * Mostra um dialog de confirmação customizado
 * @param {string} message - Mensagem
 * @param {string} title - Título (opcional)
 * @param {object} options - Opções (confirmText, cancelText)
 */
function showConfirm(message, title = 'Confirmar', options = {}) {
    const {
        confirmText = 'Confirmar',
        cancelText = 'Cancelar',
        confirmClass = 'bg-blue-600 hover:bg-blue-700',
        cancelClass = 'bg-gray-300 hover:bg-gray-400 text-gray-800'
    } = options;
    
    return new Promise((resolve) => {
        const overlay = document.createElement('div');
        overlay.className = 'fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-[9999] transition-opacity duration-300';
        overlay.style.opacity = '0';
        
        overlay.innerHTML = `
            <div class="bg-gradient-to-br from-gray-900/95 to-gray-800/95 backdrop-blur-sm border-2 border-blue-500/30 rounded-2xl shadow-2xl p-6 max-w-md w-full mx-4 transform transition-all duration-300 scale-95" id="confirmContent">
                <div class="mb-6">
                    <h3 class="text-xl font-bold text-white mb-3">${title}</h3>
                    <p class="text-gray-300">${message}</p>
                </div>
                <div class="flex justify-end gap-3">
                    <button class="px-6 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition-all duration-200 font-medium" id="confirmCancelBtn">
                        ${cancelText}
                    </button>
                    <button class="px-6 py-2 bg-gradient-to-r from-blue-500 to-blue-600 hover:from-blue-600 hover:to-blue-700 text-white rounded-lg transition-all duration-200 font-medium shadow-lg" id="confirmOkBtn" style="box-shadow: 0 0 20px rgba(59, 130, 246, 0.3);">
                        ${confirmText}
                    </button>
                </div>
            </div>
        `;
        
        document.body.appendChild(overlay);
        
        // Animação de entrada
        setTimeout(() => {
            overlay.style.opacity = '1';
            document.getElementById('confirmContent').style.transform = 'scale(1)';
        }, 10);
        
        // Função para fechar
        const closeConfirm = (result) => {
            overlay.style.opacity = '0';
            document.getElementById('confirmContent').style.transform = 'scale(0.95)';
            setTimeout(() => {
                if (overlay.parentNode) {
                    overlay.parentNode.removeChild(overlay);
                }
                resolve(result);
            }, 300);
        };
        
        // Event listeners
        document.getElementById('confirmOkBtn').addEventListener('click', () => closeConfirm(true));
        document.getElementById('confirmCancelBtn').addEventListener('click', () => closeConfirm(false));
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) closeConfirm(false);
        });
    });
}

// =============================================================================
// EXPORTAR (se usar módulos)
// =============================================================================

// Para uso global
window.showLoader = showLoader;
window.hideLoader = hideLoader;
window.updateLoaderMessage = updateLoaderMessage;
window.showToast = showToast;
window.showAlert = showAlert;
window.showConfirm = showConfirm;

