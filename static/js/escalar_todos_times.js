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
    
    // Função para verificar e adicionar botão na sidebar
    function verificarEAdicionarBotaoSidebar() {
        const timesListEl = document.getElementById('timesList');
        if (!timesListEl) return;
        
        // Verificar se já existe o botão
        if (document.getElementById('escalarTodosTimesBtnSidebar')) return;
        
        // Verificar se há mais de um time (verificar elementos com data-team-id ou itens clicáveis)
        const times = timesListEl.querySelectorAll('div[class*="cursor-pointer"]');
        if (times.length <= 1) return;
        
        // Criar botão como se fosse o primeiro item da lista
        const botaoItem = document.createElement('div');
        botaoItem.className = 'px-3 py-2 text-sm rounded-l-lg cursor-pointer transition-all duration-200 text-green-300 hover:bg-green-600/20 hover:text-white';
        botaoItem.innerHTML = `
            <div class="flex items-center">
                <div class="w-8 h-8 rounded mr-2 flex items-center justify-center bg-green-500/20">
                    <i class="fas fa-bolt text-sm text-green-400"></i>
                </div>
                <span class="flex-1 truncate">Escalar Todos os Times</span>
            </div>
        `;
        botaoItem.id = 'escalarTodosTimesBtnSidebar';
        
        // Adicionar como primeiro item da lista
        timesListEl.insertBefore(botaoItem, timesListEl.firstChild);
        
        // Adicionar event listener
        botaoItem.addEventListener('click', async function() {
            await executarEscalarTodosTimes();
        });
    }
    
    // Observar mudanças na lista de times
    const timesListEl = document.getElementById('timesList');
    if (timesListEl) {
        const observer = new MutationObserver(() => {
            setTimeout(verificarEAdicionarBotaoSidebar, 500);
        });
        observer.observe(timesListEl, { childList: true, subtree: true });
        // Tentar adicionar imediatamente também
        setTimeout(verificarEAdicionarBotaoSidebar, 1000);
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
        modal.className = 'fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4';
        modal.innerHTML = `
            <div class="bg-dark-blue-900 rounded-2xl border border-dark-blue-700 shadow-2xl max-w-2xl w-full p-6">
                <div class="flex items-center justify-between mb-4">
                    <h3 class="text-xl font-bold text-white flex items-center gap-2">
                        <i class="fas fa-bolt text-yellow-400"></i>
                        Escalar Todos os Times
                    </h3>
                    <button id="fecharModalEscalarTodos" class="text-dark-blue-300 hover:text-white">
                        <i class="fas fa-times text-xl"></i>
                    </button>
                </div>
                
                <!-- Barra de progresso -->
                <div class="mb-4">
                    <div class="flex justify-between text-sm text-dark-blue-300 mb-2">
                        <span id="progressTextTodos">Iniciando...</span>
                        <span id="progressPercentTodos">0%</span>
                    </div>
                    <div class="w-full bg-dark-blue-800 rounded-full h-3 overflow-hidden">
                        <div id="progressBarTodos" class="bg-gradient-to-r from-green-500 to-emerald-500 h-full transition-all duration-300" style="width: 0%"></div>
                    </div>
                </div>
                
                <!-- Logs -->
                <div id="logsContainerTodos" class="bg-dark-blue-950 rounded-lg p-4 max-h-96 overflow-y-auto font-mono text-sm">
                </div>
                
                <!-- Botão de fechar (só aparece quando concluído) -->
                <div id="btnFecharContainerTodos" class="mt-4 hidden">
                    <button id="btnFecharEscalarTodos" class="w-full bg-green-600 hover:bg-green-700 text-white font-bold py-2 px-4 rounded-lg transition-colors">
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
                'text-dark-blue-300'
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
        document.getElementById('btnFecharEscalarTodos').addEventListener('click', fecharModal);
        
        // Executar escalação de todos os times
        const escalarTodos = new EscalarTodosTimes();
        escalarTodos.setProgressCallback(updateProgress);
        escalarTodos.setLogCallback(addLog);
        
        try {
            const resultado = await escalarTodos.executar();
            
            // Mostrar botão de fechar
            document.getElementById('btnFecharContainerTodos').classList.remove('hidden');
            
            // Mostrar toast de sucesso
            const mensagem = resultado.falhas === 0 
                ? `🎉 Todos os ${resultado.sucessos} times foram escalados com sucesso!`
                : `⚠️ ${resultado.sucessos} times escalados, ${resultado.falhas} com erro`;
            showToast(mensagem, resultado.falhas === 0 ? 'success' : 'warning', 5000);
            
        } catch (error) {
            addLog(`❌ ERRO: ${error.message}`, 'error');
            updateProgress(0, 'Erro ao executar escalação de todos os times');
            
            // Mostrar botão de fechar mesmo em caso de erro
            document.getElementById('btnFecharContainerTodos').classList.remove('hidden');
            
            // Mostrar alerta
            showAlert('Erro ao Escalar Todos os Times', error.message, 'error');
        }
    }
});

