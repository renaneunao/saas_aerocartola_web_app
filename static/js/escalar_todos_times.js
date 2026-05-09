/**
 * Escalar Todos os Times - Cartola FC
 * Escala todos os times do usuário de uma vez, respeitando as configurações individuais de cada time
 */

class EscalarTodosTimes {
    constructor() {
        this.timesProcessados = 0;
        this.timesTotal = 0;
        this.timeOriginal = null;
        this.resultados = [];
        this.progressCallback = null;
        this.logCallback = null;
    }

    /**
     * Define callback para atualização de progresso
     */
    setProgressCallback(callback) {
        this.progressCallback = callback;
    }

    /**
     * Define callback para logs
     */
    setLogCallback(callback) {
        this.logCallback = callback;
    }

    /**
     * Log interno
     */
    log(mensagem, tipo = 'info') {
        if (this.logCallback && typeof this.logCallback === 'function') {
            this.logCallback(mensagem, tipo);
        }
        console.log(`[ESCALAR TODOS OS TIMES] ${mensagem}`);
    }

    /**
     * Atualiza progresso
     */
    updateProgress(percent, mensagem) {
        if (this.progressCallback && typeof this.progressCallback === 'function') {
            this.progressCallback(percent, mensagem);
        }
    }

    /**
     * Carrega scripts de cálculo necessários
     */
    async carregarScriptsCalculo() {
        // Verificar se já estão carregados
        if (window.EscalacaoRapida && window.EscalacaoIdeal && 
            window.CalculoGoleiro && window.CalculoLateral && 
            window.CalculoZagueiro && window.CalculoMeia && 
            window.CalculoAtacante && window.CalculoTreinador) {
            return;
        }
        
        // Verificar se os scripts já estão no DOM (carregados pelo dashboard ou módulos)
        const scriptsNoDOM = document.querySelectorAll('script[src*="calculo_"], script[src*="escalacao"]');
        if (scriptsNoDOM.length > 0) {
            // Aguardar um pouco para que os scripts sejam processados
            for (let i = 0; i < 20; i++) {
                await new Promise(resolve => setTimeout(resolve, 200));
                
                if (window.EscalacaoRapida && window.EscalacaoIdeal && 
                    window.CalculoGoleiro && window.CalculoLateral && 
                    window.CalculoZagueiro && window.CalculoMeia && 
                    window.CalculoAtacante && window.CalculoTreinador) {
                    return;
                }
            }
        }
        
        // Se ainda não estiverem carregados, carregar dinamicamente
        const scripts = [
            'calculo_goleiro.js',
            'calculo_lateral.js',
            'calculo_zagueiro.js',
            'calculo_meia.js',
            'calculo_atacante.js',
            'calculo_treinador.js',
            'escalacao_ideal.js',
            'escalacao_rapida.js'
        ];
        
        for (const scriptName of scripts) {
            // Verificar se a classe já existe antes de tentar carregar
            if (scriptName.includes('calculo_goleiro') && window.CalculoGoleiro) continue;
            if (scriptName.includes('calculo_lateral') && window.CalculoLateral) continue;
            if (scriptName.includes('calculo_zagueiro') && window.CalculoZagueiro) continue;
            if (scriptName.includes('calculo_meia') && window.CalculoMeia) continue;
            if (scriptName.includes('calculo_atacante') && window.CalculoAtacante) continue;
            if (scriptName.includes('calculo_treinador') && window.CalculoTreinador) continue;
            if (scriptName.includes('escalacao_ideal') && window.EscalacaoIdeal) continue;
            if (scriptName.includes('escalacao_rapida') && window.EscalacaoRapida) continue;
            
            // Verificar se o script já foi carregado no DOM
            const existingScript = document.querySelector(`script[src*="${scriptName}"]`);
            if (existingScript) {
                // Aguardar mais tempo para que seja processado
                for (let i = 0; i < 10; i++) {
                    await new Promise(resolve => setTimeout(resolve, 200));
                    // Verificar se a classe foi carregada
                    if (scriptName.includes('calculo_goleiro') && window.CalculoGoleiro) break;
                    if (scriptName.includes('calculo_lateral') && window.CalculoLateral) break;
                    if (scriptName.includes('calculo_zagueiro') && window.CalculoZagueiro) break;
                    if (scriptName.includes('calculo_meia') && window.CalculoMeia) break;
                    if (scriptName.includes('calculo_atacante') && window.CalculoAtacante) break;
                    if (scriptName.includes('calculo_treinador') && window.CalculoTreinador) break;
                    if (scriptName.includes('escalacao_ideal') && window.EscalacaoIdeal) break;
                    if (scriptName.includes('escalacao_rapida') && window.EscalacaoRapida) break;
                }
                continue;
            }
            
            // Tentar diferentes caminhos
            const caminhos = [
                `/static/js/${scriptName}`,
                `${window.location.origin}/static/js/${scriptName}`,
                `static/js/${scriptName}`
            ];
            
            let carregado = false;
            for (const src of caminhos) {
                try {
                    await new Promise((resolve, reject) => {
                        const script = document.createElement('script');
                        script.src = src;
                        script.async = false;
                        script.onload = () => {
                            carregado = true;
                            resolve();
                        };
                        script.onerror = () => {
                            reject(new Error(`Erro ao carregar ${src}`));
                        };
                        document.head.appendChild(script);
                    });
                    break; // Se carregou com sucesso, sair do loop
                } catch (error) {
                    // Tentar próximo caminho
                    continue;
                }
            }
            
            // Pequena pausa entre scripts
            await new Promise(resolve => setTimeout(resolve, 200));
        }
        
        // Aguardar um pouco mais para garantir que tudo foi processado
        await new Promise(resolve => setTimeout(resolve, 1000));
    }
    
    /**
     * Carrega um script dinamicamente
     */
    async carregarScript(src) {
        return new Promise((resolve, reject) => {
            // Verificar se o script já foi carregado
            const existingScript = document.querySelector(`script[src="${src}"]`);
            if (existingScript) {
                resolve();
                return;
            }
            
            const script = document.createElement('script');
            script.src = src;
            script.onload = resolve;
            script.onerror = () => reject(new Error(`Erro ao carregar script: ${src}`));
            document.head.appendChild(script);
        });
    }

    /**
     * Busca todos os times do usuário
     */
    async buscarTodosTimes() {
        const response = await fetch('/api/credenciais/lista');
        if (!response.ok) {
            throw new Error('Erro ao buscar lista de times');
        }
        
        const data = await response.json();
        const times = data.times || [];
        
        if (times.length === 0) {
            throw new Error('Nenhum time cadastrado');
        }
        
        if (times.length === 1) {
            throw new Error('Você precisa ter mais de um time cadastrado para usar esta funcionalidade');
        }
        
        this.log(`📋 ${times.length} times encontrados`, 'info');
        return times;
    }

    /**
     * Salva o time original selecionado
     */
    async salvarTimeOriginal() {
        // Buscar time atual da sessão
        const response = await fetch('/api/credenciais/lista');
        if (response.ok) {
            const data = await response.json();
            const timeSelecionado = data.times.find(t => t.selected);
            if (timeSelecionado) {
                this.timeOriginal = timeSelecionado.id;
            }
        }
    }

    /**
     * Seleciona um time
     */
    async selecionarTime(teamId) {
        const response = await fetch('/api/time/selecionar', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ team_id: teamId })
        });
        
        if (!response.ok) {
            throw new Error(`Erro ao selecionar time ${teamId}`);
        }
        
        // Aguardar um pouco para garantir que a sessão foi atualizada
        await new Promise(resolve => setTimeout(resolve, 500));
    }

    /**
     * Volta para o time original
     */
    async voltarTimeOriginal() {
        if (this.timeOriginal) {
            await this.selecionarTime(this.timeOriginal);
        }
    }

    /**
     * Escala um time específico
     */
    async escalarTime(time) {
        this.log(`🚀 Processando time: ${time.team_name}`, 'info');
        
        try {
            // 1. Selecionar o time
            await this.selecionarTime(time.id);
            
            // 2. Verificar se EscalacaoRapida está disponível (já deveria estar carregado)
            if (!window.EscalacaoRapida) {
                throw new Error('Classe EscalacaoRapida não encontrada. Os scripts devem ser carregados antes de processar os times.');
            }
            
            const escalacaoRapida = new window.EscalacaoRapida();
            
            // Configurar callbacks
            escalacaoRapida.setProgressCallback((percent, mensagem) => {
                // Ajustar progresso para o time atual
                const progressBase = (this.timesProcessados / this.timesTotal) * 100;
                const progressTime = (percent / this.timesTotal);
                const progressTotal = progressBase + progressTime;
                this.updateProgress(
                    Math.min(progressTotal, 100),
                    `${time.team_name}: ${mensagem}`
                );
            });
            
            escalacaoRapida.setLogCallback((mensagem, tipo) => {
                this.log(`[${time.team_name}] ${mensagem}`, tipo);
            });
            
            // 3. Executar escalação rápida
            const resultado = await escalacaoRapida.executar();
            
            this.log(`✅ Time ${time.team_name} escalado com sucesso!`, 'success');
            
            return {
                success: true,
                time: time,
                resultado: resultado
            };
            
        } catch (error) {
            this.log(`❌ Erro ao escalar time ${time.team_name}: ${error.message}`, 'error');
            return {
                success: false,
                time: time,
                erro: error.message
            };
        }
    }

    /**
     * Executa escalação de todos os times
     */
    async executar() {
        try {
            this.updateProgress(0, 'Iniciando...');
            
            // 1. Carregar scripts de cálculo ANTES de tudo
            await this.carregarScriptsCalculo();
            
            // Verificar se os scripts foram carregados
            if (!window.EscalacaoRapida) {
                throw new Error('Não foi possível carregar os scripts necessários. Os scripts podem não estar disponíveis nesta página. Tente usar a funcionalidade na página de módulos ou recarregue a página.');
            }
            
            // 2. Salvar time original
            await this.salvarTimeOriginal();
            
            // 3. Buscar todos os times
            const times = await this.buscarTodosTimes();
            this.timesTotal = times.length;
            this.timesProcessados = 0;
            
            // 4. Processar cada time
            for (const time of times) {
                this.timesProcessados++;
                
                const resultado = await this.escalarTime(time);
                this.resultados.push(resultado);
                
                // Pequena pausa entre times para não sobrecarregar
                if (this.timesProcessados < this.timesTotal) {
                    await new Promise(resolve => setTimeout(resolve, 1000));
                }
            }
            
            // 4. Voltar para o time original
            await this.voltarTimeOriginal();
            
            // 5. Resumo final
            const sucessos = this.resultados.filter(r => r.success).length;
            const falhas = this.resultados.filter(r => !r.success).length;
            
            this.log(`📊 Resumo: ${sucessos}/${this.timesTotal} times escalados com sucesso`, sucessos === this.timesTotal ? 'success' : 'info');
            
            if (falhas > 0) {
                this.log(`❌ ${falhas} time(s) com erro:`, 'error');
                this.resultados.filter(r => !r.success).forEach(r => {
                    this.log(`  • ${r.time.team_name}: ${r.erro}`, 'error');
                });
            }
            
            this.updateProgress(100, 'Concluído!');
            
            return {
                success: true,
                total: this.timesTotal,
                sucessos: sucessos,
                falhas: falhas,
                resultados: this.resultados
            };
            
        } catch (error) {
            this.log(`❌ ERRO GERAL: ${error.message}`, 'error');
            
            // Tentar voltar para o time original mesmo em caso de erro
            try {
                await this.voltarTimeOriginal();
            } catch (e) {
                this.log(`⚠️ Aviso: Não foi possível restaurar o time original`, 'warning');
            }
            
            throw error;
        }
    }
}

// Inicializar quando o DOM estiver pronto
document.addEventListener('DOMContentLoaded', function() {
    // Botão no dashboard
    const btnDashboard = document.getElementById('escalarTodosTimesBtn');
    if (btnDashboard) {
        btnDashboard.addEventListener('click', async function() {
            await executarEscalarTodosTimes();
        });
    }
    
    // Função para verificar e adicionar botão na sidebar (exposta globalmente)
    window.verificarEAdicionarBotaoSidebar = async function verificarEAdicionarBotaoSidebar() {
        console.log('[DEBUG] verificarEAdicionarBotaoSidebar chamada');
        const timesListEl = document.getElementById('timesList');
        if (!timesListEl) {
            console.log('[DEBUG] timesListEl não encontrado, retornando');
            return;
        }
        
        // Verificar se já existe o botão (verificação mais robusta)
        const botaoExistente = document.getElementById('escalarTodosTimesBtnSidebar');
        console.log('[DEBUG] Botão existente encontrado?', !!botaoExistente);
        
        if (botaoExistente && timesListEl.contains(botaoExistente)) {
            console.log('[DEBUG] Botão já existe e está na lista correta, retornando');
            return; // Botão já existe e está na lista correta
        }
        
        // Se o botão existe mas não está na lista, removê-lo (caso de elemento órfão)
        if (botaoExistente) {
            console.log('[DEBUG] Botão existe mas não está na lista, removendo elemento órfão');
            botaoExistente.remove();
        }
        
        // Verificar permissão multiEscalacao
        let temPermissao = false;
        try {
            console.log('[DEBUG] Verificando permissões...');
            const permsResponse = await fetch('/api/user/permissions');
            if (permsResponse.ok) {
                const permsData = await permsResponse.json();
                temPermissao = permsData.permissions.multiEscalacao === true;
                console.log('[DEBUG] Permissão multiEscalacao:', temPermissao);
            }
        } catch (error) {
            console.error('[DEBUG] Erro ao verificar permissões:', error);
            return; // Se não conseguir verificar, não mostrar o botão
        }
        
        // Se não tiver permissão, não mostrar o botão
        if (!temPermissao) {
            console.log('[DEBUG] Sem permissão, retornando');
            return;
        }
        
        // Verificar se há mais de um time
        // Buscar por elementos com data-team-id (tanto no layout vertical quanto no grid)
        const times = timesListEl.querySelectorAll('[data-team-id]');
        console.log('[DEBUG] Times encontrados:', times.length);
        
        // Excluir o próprio botão se tiver data-team-id (não deve ter, mas por segurança)
        const timesFiltrados = Array.from(times).filter(el => el.id !== 'escalarTodosTimesBtnSidebar');
        console.log('[DEBUG] Times filtrados (excluindo botão):', timesFiltrados.length);
        
        if (timesFiltrados.length <= 1) {
            console.log('[DEBUG] Menos de 2 times, retornando');
            return;
        }
        
        // Verificar novamente se o botão já existe (double-check)
        const botaoExistenteNovamente = document.getElementById('escalarTodosTimesBtnSidebar');
        if (botaoExistenteNovamente) {
            console.log('[DEBUG] ⚠️ Botão já existe no double-check! Não adicionando novamente.');
            return;
        }
        
        console.log('[DEBUG] ✅ Criando e adicionando botão...');
        
        // Criar botão
        const botaoItem = document.createElement('div');
        botaoItem.className = 'px-3 py-2 text-sm rounded-l-lg cursor-pointer transition-all duration-200 text-green-300 hover:bg-green-600/20 hover:text-white mb-2';
        botaoItem.innerHTML = `
            <div class="flex items-center">
                <div class="w-8 h-8 rounded mr-2 flex items-center justify-center bg-green-500/20">
                    <i class="fas fa-bolt text-sm text-green-400"></i>
                </div>
                <span class="flex-1 truncate">Escalar Todos os Times</span>
            </div>
        `;
        botaoItem.id = 'escalarTodosTimesBtnSidebar';
        
        // Adicionar como primeiro item da lista (antes de qualquer time)
        timesListEl.insertBefore(botaoItem, timesListEl.firstChild);
        console.log('[DEBUG] ✅ Botão adicionado com sucesso!');
        
        // Verificar quantos botões existem agora
        const todosBotoes = document.querySelectorAll('#escalarTodosTimesBtnSidebar');
        console.log('[DEBUG] ⚠️ Total de botões encontrados após adicionar:', todosBotoes.length);
        if (todosBotoes.length > 1) {
            console.error('[DEBUG] ❌ ERRO: Múltiplos botões detectados!', todosBotoes);
        }
        
        // Adicionar event listener
        botaoItem.addEventListener('click', async function() {
            await executarEscalarTodosTimes();
        });
    }
    
    // Observar mudanças na lista de times (com debounce para evitar múltiplas execuções)
    let timeoutId = null;
    const timesListEl = document.getElementById('timesList');
    if (timesListEl) {
        const observer = new MutationObserver((mutations) => {
            console.log('[DEBUG] MutationObserver: Mudanças detectadas', mutations.length);
            
            // Ignorar se a mudança foi causada pela adição do próprio botão
            const foiAdicaoBotao = mutations.some(mutation => 
                Array.from(mutation.addedNodes).some(node => 
                    node.id === 'escalarTodosTimesBtnSidebar' || 
                    (node.querySelector && node.querySelector('#escalarTodosTimesBtnSidebar'))
                )
            );
            
            if (foiAdicaoBotao) {
                console.log('[DEBUG] MutationObserver: Mudança foi adição do botão, ignorando');
                return;
            }
            
            // Ignorar se estamos renderizando (evitar múltiplas chamadas durante o forEach)
            // Verificar se há múltiplos itens sendo adicionados de uma vez (renderização em lote)
            const totalNodesAdded = mutations.reduce((sum, mutation) => sum + mutation.addedNodes.length, 0);
            console.log('[DEBUG] MutationObserver: Total de nós adicionados:', totalNodesAdded);
            
            if (totalNodesAdded > 1) {
                // Múltiplos itens sendo adicionados = renderização em lote, ignorar
                console.log('[DEBUG] MutationObserver: Renderização em lote detectada, ignorando');
                return;
            }
            
            // Debounce: cancelar timeout anterior e criar novo
            if (timeoutId) {
                console.log('[DEBUG] MutationObserver: Cancelando timeout anterior');
                clearTimeout(timeoutId);
            }
            console.log('[DEBUG] MutationObserver: Agendando verificarEAdicionarBotaoSidebar em 500ms');
            timeoutId = setTimeout(() => {
                console.log('[DEBUG] MutationObserver: Executando verificarEAdicionarBotaoSidebar agora');
                verificarEAdicionarBotaoSidebar();
                timeoutId = null;
            }, 500);
        });
        
        // Salvar observer globalmente para poder desabilitá-lo durante renderização
        window.escalarTodosTimesObserver = observer;
        observer.observe(timesListEl, { childList: true, subtree: false });
        
        // Não chamar imediatamente - deixar que a função renderizarTimesSidebar chame após renderizar
    }
    
    // Função principal
    async function executarEscalarTodosTimes() {
        // Confirmar ação
        const confirmado = await showConfirm(
            'Deseja escalar TODOS os seus times?\n\n' +
            'Esta ação irá:\n' +
            '1. Calcular rankings de todas as posições para cada time\n' +
            '2. Calcular a escalação ideal de cada time\n' +
            '3. Escalar todos os times no Cartola FC\n\n' +
            '⚠️ Cada time usará suas próprias configurações (pesos, perfis, preferências).\n' +
            '⚠️ Esta ação não pode ser desfeita!',
            '⚡ Escalar Todos os Times',
            { confirmText: 'Sim, escalar todos!', cancelText: 'Cancelar' }
        );
        
        if (!confirmado) return;
        
        // Desabilitar botões
        const btnSidebar = document.getElementById('escalarTodosTimesBtnSidebar');
        const btnDashboard = document.getElementById('escalarTodosTimesBtn');
        let btnSidebarText = null;
        let btnDashboardText = null;
        
        if (btnSidebar) {
            btnSidebar.disabled = true;
            btnSidebarText = btnSidebar.innerHTML;
            btnSidebar.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Processando...';
        }
        if (btnDashboard) {
            btnDashboard.disabled = true;
            btnDashboardText = btnDashboard.innerHTML;
            btnDashboard.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Processando...';
        }
        
        // Criar modal de progresso
        const modal = document.createElement('div');
        Object.assign(modal.style, {
            position: 'fixed', inset: '0', zIndex: '50',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            padding: '16px', backgroundColor: 'rgba(6,11,20,0.75)',
            backdropFilter: 'blur(10px)', webkitBackdropFilter: 'blur(10px)'
        });
        modal.innerHTML = `
            <div style="background:rgba(11,17,32,0.9);backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);border:1px solid rgba(0,229,255,0.12);border-radius:20px;box-shadow:0 0 40px rgba(0,229,255,0.06),0 20px 60px rgba(0,0,0,0.5);max-width:640px;width:100%;padding:24px;max-height:90vh;overflow-y:auto">
                <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:16px">
                    <h3 style="color:#EDF2FA;font-size:18px;font-weight:700;display:flex;align-items:center;gap:8px">
                        <i class="fas fa-layer-group" style="color:#F59E0B"></i>
                        Escalar Todos os Times
                    </h3>
                    <button id="fecharModalEscalarTodos" style="background:none;border:none;color:#64748B;cursor:pointer;font-size:18px;padding:4px">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
                
                <div style="margin-bottom:16px">
                    <div style="display:flex;justify-content:space-between;font-size:13px;color:#94A3B8;margin-bottom:6px">
                        <span id="progressTextTodos">Iniciando...</span>
                        <span id="progressPercentTodos" style="font-family:'JetBrains Mono',monospace">0%</span>
                    </div>
                    <div style="width:100%;background:rgba(17,27,46,0.6);border-radius:999px;height:8px;overflow:hidden">
                        <div id="progressBarTodos" style="background:linear-gradient(90deg,#F59E0B,#00FF88);height:100%;width:0%;transition:width 0.3s ease;border-radius:999px;box-shadow:0 0 8px rgba(245,158,11,0.3)"></div>
                    </div>
                </div>
                
                <div id="logsContainerTodos" style="background:rgba(6,11,20,0.4);border:1px solid rgba(255,255,255,0.04);border-radius:12px;padding:12px;max-height:320px;overflow-y:auto;font-family:'JetBrains Mono',monospace;font-size:12px;line-height:1.6">
                </div>
                
                <div id="btnFecharContainerTodos" style="margin-top:16px;display:none">
                    <button id="btnFecharEscalarTodos" style="width:100%;background:rgba(0,255,136,0.08);color:#00FF88;border:1px solid rgba(0,255,136,0.2);padding:10px;border-radius:10px;font-size:14px;font-weight:600;cursor:pointer;transition:all 0.2s">
                        Fechar
                    </button>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
        
        // Funções auxiliares
        const updateProgress = (percent, mensagem) => {
            const progressBar = document.getElementById('progressBarTodos');
            const progressText = document.getElementById('progressTextTodos');
            const progressPercent = document.getElementById('progressPercentTodos');
            
            if (progressBar) progressBar.style.width = `${percent}%`;
            if (progressText) progressText.textContent = mensagem || 'Processando...';
            if (progressPercent) progressPercent.textContent = `${Math.round(percent)}%`;
        };
        
        const addLog = (mensagem, tipo = 'info') => {
            const logsContainer = document.getElementById('logsContainerTodos');
            if (!logsContainer) return;
            
            const logEntry = document.createElement('div');
            logEntry.className = `mb-1 ${
                tipo === 'success' ? 'text-green-400' :
                tipo === 'error' ? 'text-red-400' :
                tipo === 'warning' ? 'text-yellow-400' :
                'text-slate-300'
            }`;
            logEntry.textContent = mensagem;
            logsContainer.appendChild(logEntry);
            logsContainer.scrollTop = logsContainer.scrollHeight;
        };
        
        const fecharModal = () => {
            modal.remove();
            if (btnSidebar && btnSidebarText) {
                btnSidebar.disabled = false;
                btnSidebar.innerHTML = btnSidebarText;
            }
            if (btnDashboard && btnDashboardText) {
                btnDashboard.disabled = false;
                btnDashboard.innerHTML = btnDashboardText;
            }
        };
        
        // Event listeners
        document.getElementById('fecharModalEscalarTodos').addEventListener('click', fecharModal);
        const btnFecharTodos = document.getElementById('btnFecharEscalarTodos');
        btnFecharTodos.addEventListener('click', fecharModal);
        btnFecharTodos.addEventListener('mouseenter', () => { btnFecharTodos.style.background = 'rgba(0,255,136,0.16)'; });
        btnFecharTodos.addEventListener('mouseleave', () => { btnFecharTodos.style.background = 'rgba(0,255,136,0.08)'; });
        
        // Executar escalação de todos os times
        const escalarTodos = new EscalarTodosTimes();
        escalarTodos.setProgressCallback(updateProgress);
        escalarTodos.setLogCallback(addLog);
        
        try {
            const resultado = await escalarTodos.executar();
            
            // Mostrar botão de fechar
            document.getElementById('btnFecharContainerTodos').style.display = 'block';
            
            // Mostrar toast de sucesso
            const mensagem = resultado.falhas === 0 
                ? `🎉 Todos os ${resultado.sucessos} times foram escalados com sucesso!`
                : `⚠️ ${resultado.sucessos} times escalados, ${resultado.falhas} com erro`;
            showToast(mensagem, resultado.falhas === 0 ? 'success' : 'warning', 5000);
            
        } catch (error) {
            addLog(`❌ ERRO: ${error.message}`, 'error');
            updateProgress(0, 'Erro ao executar escalação de todos os times');
            
            // Mostrar botão de fechar mesmo em caso de erro
            document.getElementById('btnFecharContainerTodos').style.display = 'block';
            
            // Mostrar alerta
            showAlert('Erro ao Escalar Todos os Times', error.message, 'error');
        }
    }
});

