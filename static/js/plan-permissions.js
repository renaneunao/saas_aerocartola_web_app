/**
 * Sistema de Permissões e Planos - Frontend
 * Gerencia verificações de permissões, bloqueios visuais e tooltips
 */

class PlanPermissions {
    constructor() {
        this.permissions = null;
        this.planKey = 'free';
        this.planName = 'Free';
        this.loaded = false;
    }

    /**
     * Carrega as permissões do usuário do backend
     */
    async loadPermissions() {
        try {
            const response = await fetch('/api/user/permissions');
            if (!response.ok) {
                console.error('Erro ao carregar permissões:', response.status);
                return false;
            }
            
            const data = await response.json();
            this.permissions = data.permissions;
            this.planKey = data.planKey;
            this.planName = data.plan;
            this.loaded = true;
            
            // Disparar evento customizado
            document.dispatchEvent(new CustomEvent('permissionsLoaded', { 
                detail: { permissions: this.permissions, plan: this.planName } 
            }));
            
            return true;
        } catch (error) {
            console.error('Erro ao carregar permissões:', error);
            return false;
        }
    }

    /**
     * Verifica se o usuário tem permissão para uma funcionalidade
     */
    hasPermission(feature) {
        if (!this.loaded || !this.permissions) {
            console.warn('Permissões não carregadas ainda');
            return false;
        }
        return this.permissions[feature] || false;
    }

    /**
     * Retorna o número máximo de perfis de jogo permitidos
     */
    getMaxPerfisJogo() {
        return this.permissions?.pesosJogo || 2;
    }

    /**
     * Retorna o número máximo de perfis de SG permitidos
     */
    getMaxPerfisSG() {
        return this.permissions?.pesosSG || 2;
    }

    /**
     * Retorna o número máximo de times permitidos
     */
    getMaxTimes() {
        const max = this.permissions?.timesMaximos || 1;
        return max === 'infinite' ? 999999 : max;
    }

    /**
     * Retorna o nível de risco permitido
     */
    getNivelRisco() {
        return this.permissions?.nivelRisco || 1;
    }

    /**
     * Aplica blur em elementos bloqueados
     */
    applyBlur(element, enabled = true) {
        if (enabled) {
            element.style.filter = 'blur(6px)';
            element.style.pointerEvents = 'none';
            element.style.userSelect = 'none';
            element.classList.add('plan-blocked');
        } else {
            element.style.filter = '';
            element.style.pointerEvents = '';
            element.style.userSelect = '';
            element.classList.remove('plan-blocked');
        }
    }

    /**
     * Adiciona overlay de bloqueio com tooltip
     */
    addBlockOverlay(element, message, requiredPlan = null) {
        // Remover overlay existente se houver
        const existing = element.querySelector('.plan-block-overlay');
        if (existing) {
            existing.remove();
        }

        const overlay = document.createElement('div');
        overlay.className = 'plan-block-overlay';
        overlay.style.cssText = `
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.8);
            backdrop-filter: blur(6px);
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            z-index: 10;
            border-radius: inherit;
            cursor: not-allowed;
        `;

        const icon = document.createElement('i');
        icon.className = 'fas fa-lock';
        icon.style.cssText = 'font-size: 2rem; color: #fbbf24; margin-bottom: 0.5rem;';

        const text = document.createElement('p');
        text.textContent = message;
        text.style.cssText = 'color: white; font-weight: bold; text-align: center; padding: 0 1rem;';

        if (requiredPlan) {
            const planText = document.createElement('p');
            planText.textContent = `Disponível no plano ${requiredPlan}`;
            planText.style.cssText = 'color: #94a3b8; font-size: 0.875rem; margin-top: 0.5rem;';
            overlay.appendChild(planText);
        }

        overlay.appendChild(icon);
        overlay.appendChild(text);

        // Garantir que o elemento pai tenha position relative
        const parent = element;
        if (getComputedStyle(parent).position === 'static') {
            parent.style.position = 'relative';
        }

        parent.appendChild(overlay);
    }

    /**
     * Remove overlay de bloqueio
     */
    removeBlockOverlay(element) {
        const overlay = element.querySelector('.plan-block-overlay');
        if (overlay) {
            overlay.remove();
        }
    }

    /**
     * Desabilita botão e adiciona tooltip
     */
    disableButton(button, message, requiredPlan = null) {
        button.disabled = true;
        button.classList.add('plan-disabled');
        
        // Adicionar tooltip
        button.setAttribute('title', requiredPlan ? `${message} (Disponível no plano ${requiredPlan})` : message);
        button.setAttribute('data-toggle', 'tooltip');
        button.setAttribute('data-placement', 'top');
        
        // Adicionar ícone de bloqueio se não tiver
        if (!button.querySelector('.fa-lock')) {
            const icon = document.createElement('i');
            icon.className = 'fas fa-lock';
            icon.style.marginLeft = '0.5rem';
            button.appendChild(icon);
        }
    }

    /**
     * Habilita botão e remove tooltip
     */
    enableButton(button) {
        button.disabled = false;
        button.classList.remove('plan-disabled');
        button.removeAttribute('title');
        button.removeAttribute('data-toggle');
        button.removeAttribute('data-placement');
        
        const icon = button.querySelector('.fa-lock');
        if (icon) {
            icon.remove();
        }
    }

    /**
     * Limita lista de elementos (para rankings Free)
     */
    limitList(container, maxItems, applyBlur = true) {
        const items = Array.from(container.children);
        
        items.forEach((item, index) => {
            if (index < maxItems) {
                // Item visível
                if (applyBlur) {
                    this.applyBlur(item, false);
                }
                this.removeBlockOverlay(item);
            } else {
                // Item bloqueado
                if (applyBlur) {
                    this.applyBlur(item, true);
                }
                this.addBlockOverlay(item, 'Conteúdo bloqueado', 'Avançado ou Pro');
            }
        });
    }

    /**
     * Verifica se um perfil de jogo pode ser usado
     */
    canUsePerfilJogo(perfilId) {
        return perfilId <= this.getMaxPerfisJogo();
    }

    /**
     * Verifica se um perfil de SG pode ser usado
     */
    canUsePerfilSG(perfilId) {
        return perfilId <= this.getMaxPerfisSG();
    }

    /**
     * Retorna mensagem de erro para funcionalidade bloqueada
     */
    getBlockedMessage(feature) {
        const messages = {
            'podeEscalar': 'Escalar time está disponível no plano Avançado ou Pro.',
            'editarPesosModulos': 'Edição de pesos está disponível apenas no plano Pro.',
            'hackGoleiro': 'Hack do Goleiro está disponível apenas no plano Pro.',
            'multiEscalacao': 'Multi-escalação está disponível apenas no plano Pro.',
            'fecharDefesa': 'Fechar Defesa está disponível no plano Avançado ou Pro.',
            'estatisticasAvancadas': 'Estatísticas Avançadas estão disponíveis no plano Avançado ou Pro.',
            'rankingCompleto': 'Ranking completo está disponível no plano Avançado ou Pro.',
        };
        
        return messages[feature] || `Esta funcionalidade não está disponível no plano ${this.planName}.`;
    }

    /**
     * Retorna o plano necessário para uma funcionalidade
     */
    getRequiredPlan(feature) {
        const planMap = {
            'podeEscalar': 'Avançado',
            'editarPesosModulos': 'Pro',
            'hackGoleiro': 'Pro',
            'multiEscalacao': 'Pro',
            'fecharDefesa': 'Avançado',
            'estatisticasAvancadas': 'Avançado',
            'rankingCompleto': 'Avançado',
        };
        
        return planMap[feature] || 'Avançado';
    }
}

// Instância global
const planPermissions = new PlanPermissions();

// Carregar permissões ao carregar a página
document.addEventListener('DOMContentLoaded', async () => {
    await planPermissions.loadPermissions();
});

// Exportar para uso global
window.planPermissions = planPermissions;

