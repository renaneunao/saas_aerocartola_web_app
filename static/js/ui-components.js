/**
 * UI Components - Sistema centralizado de feedback visual
 * Glass Neon Dark Theme
 */

// =============================================================================
// LOADER / SPINNER
// =============================================================================

let loaderElement = null;
let loaderCount = 0;

function showLoader(message = 'Carregando...') {
    loaderCount++;
    
    if (!loaderElement) {
        loaderElement = document.getElementById('globalLoader');
    }
    
    if (!loaderElement) return;
    
    loaderElement.style.opacity = '1';
    loaderElement.style.pointerEvents = 'auto';
    
    const msg = document.getElementById('loaderMessage');
    if (msg) msg.textContent = message;
}

function hideLoader() {
    loaderCount = Math.max(0, loaderCount - 1);
    if (loaderCount === 0 && loaderElement) {
        loaderElement.style.opacity = '0';
        loaderElement.style.pointerEvents = 'none';
    }
}

function updateLoaderMessage(message) {
    const messageEl = document.getElementById('loaderMessage');
    if (messageEl) messageEl.textContent = message;
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

function showToast(message, type = 'info', duration = 4000) {
    const toast = document.createElement('div');
    
    const config = {
        success: { bg: 'rgba(0,255,136,0.1)', border: 'rgba(0,255,136,0.3)', text: '#00FF88', icon: 'fa-check-circle' },
        error:   { bg: 'rgba(239,68,68,0.1)', border: 'rgba(239,68,68,0.3)', text: '#EF4444', icon: 'fa-exclamation-circle' },
        warning: { bg: 'rgba(245,158,11,0.1)', border: 'rgba(245,158,11,0.3)', text: '#F59E0B', icon: 'fa-exclamation-triangle' },
        info:    { bg: 'rgba(0,229,255,0.1)', border: 'rgba(0,229,255,0.3)', text: '#00E5FF', icon: 'fa-info-circle' }
    };
    
    const c = config[type] || config.info;
    
    Object.assign(toast.style, {
        background: c.bg,
        backdropFilter: 'blur(12px)',
        WebkitBackdropFilter: 'blur(12px)',
        border: `1px solid ${c.border}`,
        color: c.text,
        padding: '10px 16px',
        borderRadius: '12px',
        display: 'flex',
        alignItems: 'center',
        gap: '10px',
        minWidth: '280px',
        maxWidth: '400px',
        transform: 'translateX(400px)',
        opacity: '0',
        transition: 'all 0.3s ease',
        cursor: 'pointer',
        boxShadow: `0 0 20px ${c.border.replace('0.3)', '0.08)')}`,
        fontSize: '13px',
        fontWeight: '500'
    });
    
    toast.innerHTML = `
        <i class="fas ${c.icon}" style="font-size:16px;flex-shrink:0"></i>
        <span style="flex:1">${message}</span>
        <button style="color:${c.text};opacity:0.6;background:none;border:none;cursor:pointer;padding:2px;font-size:12px" onclick="this.closest('[style*=translateX]').remove()">
            <i class="fas fa-times"></i>
        </button>
    `;
    
    toastContainer.appendChild(toast);
    
    setTimeout(() => {
        toast.style.transform = 'translateX(0)';
        toast.style.opacity = '1';
    }, 10);
    
    if (duration > 0) {
        setTimeout(() => removeToast(toast), duration);
    }
    
    toast.addEventListener('click', (e) => {
        if (!e.target.closest('button')) removeToast(toast);
    });
    
    return toast;
}

function removeToast(toast) {
    toast.style.transform = 'translateX(400px)';
    toast.style.opacity = '0';
    setTimeout(() => {
        if (toast.parentNode) toast.parentNode.removeChild(toast);
    }, 300);
}

// =============================================================================
// ALERT DIALOG
// =============================================================================

function showAlert(message, title = '', type = 'info') {
    return new Promise((resolve) => {
        const overlay = document.createElement('div');
        overlay.className = 'fixed inset-0 flex items-center justify-center z-[9999] transition-opacity duration-300';
        overlay.style.opacity = '0';
        overlay.style.backgroundColor = 'rgba(6,11,20,0.7)';
        overlay.style.backdropFilter = 'blur(8px)';
        overlay.style.webkitBackdropFilter = 'blur(8px)';
        
        const config = {
            success: { color: '#00FF88', bg: 'rgba(0,255,136,0.08)', border: 'rgba(0,255,136,0.2)', icon: 'fa-check-circle' },
            error:   { color: '#EF4444', bg: 'rgba(239,68,68,0.08)', border: 'rgba(239,68,68,0.2)', icon: 'fa-exclamation-circle' },
            warning: { color: '#F59E0B', bg: 'rgba(245,158,11,0.08)', border: 'rgba(245,158,11,0.2)', icon: 'fa-exclamation-triangle' },
            info:    { color: '#00E5FF', bg: 'rgba(0,229,255,0.08)', border: 'rgba(0,229,255,0.2)', icon: 'fa-info-circle' }
        };
        
        const c = config[type] || config.info;
        
        overlay.innerHTML = `
            <div id="alertContent" style="background:rgba(11,17,32,0.9);backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);border:1px solid ${c.border};border-radius:20px;padding:24px;max-width:420px;width:90%;transform:scale(0.95);transition:transform 0.3s ease;box-shadow:0 0 40px ${c.border.replace('0.2)', '0.08)')},0 20px 60px rgba(0,0,0,0.5)">
                <div style="display:flex;align-items:flex-start;gap:14px;margin-bottom:20px">
                    <i class="fas ${c.icon}" style="font-size:28px;color:${c.color};flex-shrink:0;margin-top:2px"></i>
                    <div style="flex:1">
                        ${title ? `<h3 style="color:#EDF2FA;font-size:17px;font-weight:600;margin-bottom:6px">${title}</h3>` : ''}
                        <p style="color:#94A3B8;font-size:14px;line-height:1.5">${message}</p>
                    </div>
                </div>
                <div style="display:flex;justify-content:flex-end">
                    <button id="alertOkBtn" style="background:${c.bg};color:${c.color};border:1px solid ${c.border};padding:8px 24px;border-radius:10px;font-size:13px;font-weight:600;cursor:pointer;transition:all 0.2s">
                        OK
                    </button>
                </div>
            </div>
        `;
        
        document.body.appendChild(overlay);
        
        setTimeout(() => {
            overlay.style.opacity = '1';
            document.getElementById('alertContent').style.transform = 'scale(1)';
        }, 10);
        
        const closeAlert = () => {
            overlay.style.opacity = '0';
            document.getElementById('alertContent').style.transform = 'scale(0.95)';
            setTimeout(() => {
                if (overlay.parentNode) overlay.parentNode.removeChild(overlay);
                resolve(true);
            }, 300);
        };
        
        const okBtn = document.getElementById('alertOkBtn');
        okBtn.addEventListener('mouseenter', () => { okBtn.style.background = c.bg.replace('0.08)', '0.16)'); });
        okBtn.addEventListener('mouseleave', () => { okBtn.style.background = c.bg; });
        okBtn.addEventListener('click', closeAlert);
        overlay.addEventListener('click', (e) => { if (e.target === overlay) closeAlert(); });
    });
}

// =============================================================================
// CONFIRM DIALOG
// =============================================================================

function showConfirm(message, title = 'Confirmar', options = {}) {
    const { confirmText = 'Confirmar', cancelText = 'Cancelar' } = options;
    
    return new Promise((resolve) => {
        const overlay = document.createElement('div');
        overlay.className = 'fixed inset-0 flex items-center justify-center z-[9999] transition-opacity duration-300';
        overlay.style.opacity = '0';
        overlay.style.backgroundColor = 'rgba(6,11,20,0.7)';
        overlay.style.backdropFilter = 'blur(8px)';
        overlay.style.webkitBackdropFilter = 'blur(8px)';
        
        overlay.innerHTML = `
            <div id="confirmContent" style="background:rgba(11,17,32,0.9);backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);border:1px solid rgba(0,229,255,0.15);border-radius:20px;padding:24px;max-width:420px;width:90%;transform:scale(0.95);transition:transform 0.3s ease;box-shadow:0 0 40px rgba(0,229,255,0.06),0 20px 60px rgba(0,0,0,0.5)">
                <div style="margin-bottom:20px">
                    <h3 style="color:#EDF2FA;font-size:17px;font-weight:600;margin-bottom:8px">${title}</h3>
                    <p style="color:#94A3B8;font-size:14px;line-height:1.5">${message}</p>
                </div>
                <div style="display:flex;justify-content:flex-end;gap:10px">
                    <button id="confirmCancelBtn" style="background:rgba(255,255,255,0.04);color:#94A3B8;border:1px solid rgba(255,255,255,0.08);padding:8px 20px;border-radius:10px;font-size:13px;font-weight:500;cursor:pointer;transition:all 0.2s">
                        ${cancelText}
                    </button>
                    <button id="confirmOkBtn" style="background:rgba(0,229,255,0.08);color:#00E5FF;border:1px solid rgba(0,229,255,0.2);padding:8px 20px;border-radius:10px;font-size:13px;font-weight:600;cursor:pointer;transition:all 0.2s">
                        ${confirmText}
                    </button>
                </div>
            </div>
        `;
        
        document.body.appendChild(overlay);
        
        setTimeout(() => {
            overlay.style.opacity = '1';
            document.getElementById('confirmContent').style.transform = 'scale(1)';
        }, 10);
        
        const closeConfirm = (result) => {
            overlay.style.opacity = '0';
            document.getElementById('confirmContent').style.transform = 'scale(0.95)';
            setTimeout(() => {
                if (overlay.parentNode) overlay.parentNode.removeChild(overlay);
                resolve(result);
            }, 300);
        };
        
        const okBtn = document.getElementById('confirmOkBtn');
        const cancelBtn = document.getElementById('confirmCancelBtn');
        okBtn.addEventListener('mouseenter', () => { okBtn.style.background = 'rgba(0,229,255,0.16)'; });
        okBtn.addEventListener('mouseleave', () => { okBtn.style.background = 'rgba(0,229,255,0.08)'; });
        cancelBtn.addEventListener('mouseenter', () => { cancelBtn.style.background = 'rgba(255,255,255,0.08)'; });
        cancelBtn.addEventListener('mouseleave', () => { cancelBtn.style.background = 'rgba(255,255,255,0.04)'; });
        okBtn.addEventListener('click', () => closeConfirm(true));
        cancelBtn.addEventListener('click', () => closeConfirm(false));
        overlay.addEventListener('click', (e) => { if (e.target === overlay) closeConfirm(false); });
    });
}

// =============================================================================
// EXPORT
// =============================================================================

window.showLoader = showLoader;
window.hideLoader = hideLoader;
window.updateLoaderMessage = updateLoaderMessage;
window.showToast = showToast;
window.showAlert = showAlert;
window.showConfirm = showConfirm;
