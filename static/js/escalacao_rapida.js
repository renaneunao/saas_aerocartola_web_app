/**
 * Escalação Rápida - Cartola FC
 * Calcula todos os rankings, escalação ideal e escala o time automaticamente
 */

// Mapeamento de módulos
const MODULOS = ['goleiro', 'lateral', 'zagueiro', 'meia', 'atacante', 'treinador'];
const MODULO_TO_CLASS = {
    'goleiro': 'CalculoGoleiro',
    'lateral': 'CalculoLateral',
    'zagueiro': 'CalculoZagueiro',
    'meia': 'CalculoMeia',
    'atacante': 'CalculoAtacante',
    'treinador': 'CalculoTreinador'
};

class EscalacaoRapida {
    constructor() {
        this.rankingsCalculados = {};
        this.rodadaAtual = null;
        this.configurationId = null;
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
        console.log(`[ESCALAÇÃO RÁPIDA] ${mensagem}`);
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
     * Carrega dados de um módulo específico
     */
    async carregarDadosModulo(modulo) {
        this.log(`📡 Carregando dados do módulo: ${modulo}...`, 'info');
        
        const response = await fetch(`/api/modulos/${modulo}/dados`);
        if (!response.ok) {
            const error = await response.json();
            throw new Error(`Erro ao carregar dados de ${modulo}: ${error.error || 'Erro desconhecido'}`);
        }
        
        const data = await response.json();
        
        // Salvar rodada e configuration_id na primeira chamada
        if (!this.rodadaAtual) {
            this.rodadaAtual = data.rodada_atual;
            this.configurationId = data.configuration_id;
        }
        
        return data;
    }

    /**
     * Salva pesos padrão se não existirem
     */
    async verificarESalvarPesos(modulo, dados) {
        try {
            const checkResponse = await fetch(`/api/modulos/${modulo}/verificar-ranking`);
            const checkData = await checkResponse.json();
            
            if (!checkData.has_weights) {
                this.log(`💾 Salvando pesos padrão para ${modulo}...`, 'info');
                
                // Salvar pesos padrão
                const saveResponse = await fetch(`/api/modulos/${modulo}/pesos`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(dados.pesos)
                });
                
                if (!saveResponse.ok) {
                    throw new Error(`Erro ao salvar pesos de ${modulo}`);
                }
                
                this.log(`✅ Pesos salvos para ${modulo}`, 'success');
            }
        } catch (error) {
            this.log(`⚠️ Aviso ao verificar pesos de ${modulo}: ${error.message}`, 'warning');
        }
    }

    /**
     * Calcula ranking de um módulo específico
     */
    async calcularRankingModulo(modulo, dados) {
        this.log(`⚙️ Calculando ranking de ${modulo}...`, 'info');
        
        // Desativar bloqueadores de cálculo (queremos sempre recalcular na escalação rápida)
        const bloqueadorMap = {
            'goleiro': 'BLOQUEAR_CALCULO_GOLEIRO',
            'lateral': 'BLOQUEAR_CALCULO_LATERAL',
            'zagueiro': 'BLOQUEAR_CALCULO_ZAGUEIRO',
            'meia': 'BLOQUEAR_CALCULO_MEIA',
            'atacante': 'BLOQUEAR_CALCULO_ATACANTE',
            'treinador': 'BLOQUEAR_CALCULO_TREINADOR'
        };
        
        const bloqueadorNome = bloqueadorMap[modulo];
        if (bloqueadorNome && window[bloqueadorNome]) {
            window[bloqueadorNome] = false;
        }
        
        // Verificar se as classes de cálculo estão disponíveis
        const className = MODULO_TO_CLASS[modulo];
        if (!window[className]) {
            throw new Error(`Classe de cálculo ${className} não encontrada. Certifique-se de que os scripts de cálculo estão carregados.`);
        }
        
        // Criar instância do calculador
        const Calculador = window[className];
        const calculo = new Calculador(dados);
        
        // Mapear método de cálculo por módulo
        const metodoMap = {
            'goleiro': 'calcularMelhoresGoleiros',
            'lateral': 'calcularMelhoresLaterais',
            'zagueiro': 'calcularMelhoresZagueiros',
            'meia': 'calcularMelhoresMeias',
            'atacante': 'calcularMelhoresAtacantes',
            'treinador': 'calcularMelhoresTreinadores'
        };
        
        const metodoNome = metodoMap[modulo];
        if (!metodoNome || typeof calculo[metodoNome] !== 'function') {
            throw new Error(`Método de cálculo ${metodoNome} não encontrado para ${modulo}`);
        }
        
        // Calcular ranking (top 20)
        const resultados = calculo[metodoNome](20);
        
        // Adicionar rank
        resultados.forEach((resultado, index) => {
            resultado.rank = index + 1;
        });
        
        this.log(`✅ Ranking de ${modulo} calculado: ${resultados.length} jogadores`, 'success');
        
        return resultados;
    }

    /**
     * Salva ranking de um módulo
     */
    async salvarRankingModulo(modulo, ranking) {
        this.log(`💾 Salvando ranking de ${modulo}...`, 'info');
        
        const response = await fetch(`/api/modulos/${modulo}/salvar-ranking`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                ranking_data: ranking,
                rodada_atual: this.rodadaAtual,
                configuration_id: this.configurationId
            })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(`Erro ao salvar ranking de ${modulo}: ${error.error || 'Erro desconhecido'}`);
        }
        
        this.log(`✅ Ranking de ${modulo} salvo com sucesso`, 'success');
    }

    /**
     * Calcula todos os rankings
     */
    async calcularTodosRankings() {
        this.log('═'.repeat(60), 'info');
        this.log('🚀 INICIANDO CÁLCULO DE TODOS OS RANKINGS', 'info');
        this.log('═'.repeat(60), 'info');
        
        const totalModulos = MODULOS.length;
        let modulosProcessados = 0;
        
        for (const modulo of MODULOS) {
            try {
                // Atualizar progresso
                const progressPercent = Math.floor((modulosProcessados / totalModulos) * 60);
                this.updateProgress(progressPercent, `Processando ${modulo}...`);
                
                // 1. Carregar dados
                const dados = await this.carregarDadosModulo(modulo);
                
                // 2. Verificar e salvar pesos se necessário
                await this.verificarESalvarPesos(modulo, dados);
                
                // 3. Calcular ranking
                const ranking = await this.calcularRankingModulo(modulo, dados);
                
                // 4. Salvar ranking
                await this.salvarRankingModulo(modulo, ranking);
                
                // Armazenar ranking
                this.rankingsCalculados[modulo] = ranking;
                
                modulosProcessados++;
                this.log(`✅ Módulo ${modulo} concluído (${modulosProcessados}/${totalModulos})`, 'success');
                
            } catch (error) {
                this.log(`❌ Erro ao processar ${modulo}: ${error.message}`, 'error');
                throw error;
            }
        }
        
        this.log('═'.repeat(60), 'info');
        this.log('✅ TODOS OS RANKINGS CALCULADOS COM SUCESSO!', 'success');
        this.log('═'.repeat(60), 'info');
        
        this.updateProgress(60, 'Todos os rankings calculados!');
    }

    /**
     * Calcula escalação ideal
     */
    async calcularEscalacaoIdeal() {
        this.log('═'.repeat(60), 'info');
        this.log('🎯 CALCULANDO ESCALAÇÃO IDEAL', 'info');
        this.log('═'.repeat(60), 'info');
        
        this.updateProgress(65, 'Buscando dados para escalação ideal...');
        
        // Buscar dados da escalação ideal
        const response = await fetch('/api/escalacao-ideal/dados');
        if (!response.ok) {
            const error = await response.json();
            throw new Error(`Erro ao buscar dados de escalação: ${error.error || 'Erro desconhecido'}`);
        }
        
        const dados = await response.json();
        
        // Verificar se EscalacaoIdeal está disponível
        if (!window.EscalacaoIdeal) {
            throw new Error('Classe EscalacaoIdeal não encontrada. Certifique-se de que o script está carregado.');
        }
        
        this.updateProgress(70, 'Configurando escalação ideal...');
        
        // Buscar configurações padrão (ou usar valores padrão)
        let configResponse;
        try {
            configResponse = await fetch('/api/escalacao-ideal/config');
        } catch (e) {
            configResponse = null;
        }
        
        let config = {
            formacao: '4-3-3',
            posicao_capitao: 'atacantes',
            posicao_reserva_luxo: 'atacantes',
            prioridades: ['atacantes', 'laterais', 'meias', 'zagueiros', 'goleiros', 'treinadores'],
            fechar_defesa: false,
            hack_goleiro: false
        };
        
        if (configResponse && configResponse.ok) {
            const configData = await configResponse.json();
            if (configData.formacao) config.formacao = configData.formacao;
            if (configData.posicao_capitao) config.posicao_capitao = configData.posicao_capitao;
            if (configData.posicao_reserva_luxo) config.posicao_reserva_luxo = configData.posicao_reserva_luxo;
            
            // Converter prioridades para array se for string
            if (configData.prioridades) {
                if (Array.isArray(configData.prioridades)) {
                    config.prioridades = configData.prioridades;
                } else if (typeof configData.prioridades === 'string') {
                    // Converter string separada por vírgula em array
                    config.prioridades = configData.prioridades.split(',').map(p => {
                        const posicao = p.trim();
                        // Normalizar "tecnicos" para "treinadores"
                        return posicao === 'tecnicos' ? 'treinadores' : posicao;
                    });
                } else {
                    // Se não for array nem string, usar padrão
                    config.prioridades = ['atacantes', 'laterais', 'meias', 'zagueiros', 'goleiros', 'treinadores'];
                }
            }
            
            if (configData.fechar_defesa !== undefined) config.fechar_defesa = configData.fechar_defesa;
            if (configData.hack_goleiro !== undefined) config.hack_goleiro = configData.hack_goleiro;
        }
        
        // Garantir que prioridades seja sempre um array válido
        if (!Array.isArray(config.prioridades) || config.prioridades.length === 0) {
            config.prioridades = ['atacantes', 'laterais', 'meias', 'zagueiros', 'goleiros', 'treinadores'];
        }
        
        this.updateProgress(75, 'Criando instância do escalador...');
        
        // Criar instância do escalador
        const escalador = new window.EscalacaoIdeal({
            rodada_atual: dados.rodada_atual,
            patrimonio: dados.patrimonio,
            rankings_por_posicao: dados.rankings_por_posicao,
            todos_goleiros: dados.todos_goleiros || [],
            clubes_sg: dados.clubes_sg || [],
            adversarios_dict: dados.adversarios_dict || {},
            formacao: config.formacao,
            posicao_capitao: config.posicao_capitao,
            posicao_reserva_luxo: config.posicao_reserva_luxo,
            prioridades: config.prioridades,
            fechar_defesa: config.fechar_defesa,
            hack_goleiro: config.hack_goleiro
        });
        
        // Configurar callback de logs
        escalador.setLogCallback((msg) => this.log(msg, 'log'));
        
        this.updateProgress(80, 'Calculando escalação ideal...');
        
        // Calcular escalação
        const escalacao = await escalador.calcular();
        
        this.log('═'.repeat(60), 'info');
        this.log('✅ ESCALAÇÃO IDEAL CALCULADA COM SUCESSO!', 'success');
        this.log('═'.repeat(60), 'info');
        
        this.updateProgress(90, 'Escalação ideal calculada!');
        
        return escalacao;
    }

    /**
     * Escala o time no Cartola
     */
    async escalarTime(escalacao) {
        this.log('═'.repeat(60), 'info');
        this.log('🚀 ESCALANDO TIME NO CARTOLA FC', 'info');
        this.log('═'.repeat(60), 'info');
        
        this.updateProgress(92, 'Preparando escalação...');
        
        // Buscar formação atual (padrão 4-3-3)
        let formacao = '4-3-3';
        try {
            const configResponse = await fetch('/api/escalacao-ideal/config');
            if (configResponse && configResponse.ok) {
                const configData = await configResponse.json();
                if (configData.formacao) {
                    formacao = configData.formacao;
                }
            }
        } catch (e) {
            // Usar padrão
        }
        
        this.updateProgress(95, 'Enviando escalação para o Cartola...');
        
        const payload = {
            escalacao: escalacao,
            formacao: formacao
        };
        
        this.log(`\n📤 PAYLOAD ENVIADO PARA O BACKEND:`);
        this.log(`   Formação: ${payload.formacao}`);

        // Logar titulares por posição com nomes
        this.log(`\n👕 TITULARES SELECIONADOS:`);
        const posicaoEmoji = { goleiros: '🧤', zagueiros: '🛡️', laterais: '↔️', meias: '🎯', atacantes: '⚽', treinadores: '📋' };
        for (const [pos, jogadores] of Object.entries(escalacao.titulares)) {
            if (jogadores && jogadores.length > 0) {
                jogadores.forEach(j => {
                    const cap = j.eh_capitao ? ' 👑 CAPITÃO' : '';
                    this.log(`   ${posicaoEmoji[pos] || '•'} [${pos.toUpperCase()}] ${j.apelido} (R$ ${parseFloat(j.preco_num || j.preco || 0).toFixed(2)})${cap}`);
                });
            }
        }

        // Logar reservas com nomes
        this.log(`\n🪑 RESERVAS:`);
        for (const [pos, jogadores] of Object.entries(escalacao.reservas || {})) {
            if (jogadores && jogadores.length > 0) {
                jogadores.forEach(j => {
                    const luxo = j.eh_reserva_luxo ? ' 💎 LUXO' : '';
                    this.log(`   ${posicaoEmoji[pos] || '•'} [${pos.toUpperCase()}] ${j.apelido} (R$ ${parseFloat(j.preco_num || j.preco || 0).toFixed(2)})${luxo}`);
                });
            }
        }

        const response = await fetch('/api/escalacao-ideal/escalar', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        
        const data = await response.json();

        // Sempre exibir atletas_debug do backend (disponível em sucesso e erro)
        if (data.atletas_debug && data.atletas_debug.length > 0) {
            this.log(`\n📋 ATLETAS CONFIRMADOS PELO BACKEND (${data.atletas_debug.length} total):`);
            const titulares = data.atletas_debug.filter(a => a.tipo === 'titular');
            const reservaLuxo = data.atletas_debug.filter(a => a.tipo === 'reserva_luxo');
            const reservas = data.atletas_debug.filter(a => a.tipo === 'reserva');
            titulares.forEach(a => {
                const cap = a.capitao ? ' 👑' : '';
                this.log(`   ✅ [TITULAR] ${a.apelido} | ${a.posicao} | R$ ${parseFloat(a.preco || 0).toFixed(2)}${cap}`);
            });
            reservaLuxo.forEach(a => {
                this.log(`   💎 [RES.LUXO] ${a.apelido} | ${a.posicao} | R$ ${parseFloat(a.preco || 0).toFixed(2)}`);
            });
            reservas.forEach(a => {
                this.log(`   🪑 [RESERVA] ${a.apelido} | ${a.posicao} | R$ ${parseFloat(a.preco || 0).toFixed(2)}`);
            });
            if (data.payload_enviado) {
                this.log(`\n📦 PAYLOAD CARTOLA: atletas=[${(data.payload_enviado.atletas || []).join(', ')}] | capitao=${data.payload_enviado.capitao} | reserva_luxo=${data.payload_enviado.reserva_luxo_id}`);
            }
        }
        
        if (!response.ok || !data.success) {
            const errorMsg = data.error || 'Erro desconhecido';
            this.log(`❌ Erro ao escalar: ${errorMsg}`, 'error');
            throw new Error(errorMsg);
        }
        
        this.log('═'.repeat(60), 'info');
        this.log('✅ TIME ESCALADO COM SUCESSO NO CARTOLA FC!', 'success');
        this.log(`📝 ${data.mensagem || 'Escalação realizada com sucesso!'}`, 'success');
        this.log('═'.repeat(60), 'info');
        
        this.updateProgress(100, 'Time escalado com sucesso!');
        
        return data;
    }

    /**
     * Executa todo o processo de escalação rápida
     */
    async executar() {
        try {
            this.updateProgress(0, 'Iniciando escalação rápida...');
            this.log('🚀 INICIANDO ESCALAÇÃO RÁPIDA', 'info');
            
            // 1. Calcular todos os rankings
            await this.calcularTodosRankings();
            
            // 2. Calcular escalação ideal
            const escalacao = await this.calcularEscalacaoIdeal();
            
            // 3. Escalar time
            await this.escalarTime(escalacao);
            
            this.log('🎉 ESCALAÇÃO RÁPIDA CONCLUÍDA COM SUCESSO!', 'success');
            
            return {
                success: true,
                escalacao: escalacao,
                rankings: this.rankingsCalculados
            };
            
        } catch (error) {
            this.log(`❌ ERRO NA ESCALAÇÃO RÁPIDA: ${error.message}`, 'error');
            throw error;
        }
    }
}

// Exportar para uso global
if (typeof window !== 'undefined') {
    window.EscalacaoRapida = EscalacaoRapida;
}

// Inicializar quando o DOM estiver pronto
document.addEventListener('DOMContentLoaded', function() {
    const btn = document.getElementById('escalacaoRapidaBtn');
    if (!btn) return;
    
    // Verificar se o botão está desabilitado (sem permissão)
    if (btn.disabled) {
        return; // Não adicionar event listener se estiver desabilitado
    }
    
    btn.addEventListener('click', async function() {
        // Verificação de segurança adicional
        if (btn.disabled) {
            return;
        }
        
        // Confirmar ação
        const confirmado = await showConfirm(
            'Deseja executar a Escalação Rápida?\n\n' +
            'Este processo irá:\n' +
            '1. Calcular rankings de todas as posições\n' +
            '2. Calcular a escalação ideal\n' +
            '3. Escalar o time automaticamente no Cartola FC\n\n' +
            '⚠️ Esta ação não pode ser desfeita!',
            '⚡ Escalação Rápida',
            { confirmText: 'Sim, executar!', cancelText: 'Cancelar' }
        );
        
        if (!confirmado) return;
        
        // Desabilitar botão
        btn.disabled = true;
        const btnText = btn.innerHTML;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Processando...';
        
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
                        <i class="fas fa-bolt" style="color:#00FF88"></i>
                        Escalação Rápida
                    </h3>
                    <button id="fecharModalEscalacaoRapida" style="background:none;border:none;color:#64748B;cursor:pointer;font-size:18px;padding:4px">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
                
                <div style="margin-bottom:16px">
                    <div style="display:flex;justify-content:space-between;font-size:13px;color:#94A3B8;margin-bottom:6px">
                        <span id="progressText">Iniciando...</span>
                        <span id="progressPercent" style="font-family:'JetBrains Mono',monospace">0%</span>
                    </div>
                    <div style="width:100%;background:rgba(17,27,46,0.6);border-radius:999px;height:8px;overflow:hidden">
                        <div id="progressBar" style="background:linear-gradient(90deg,#00FF88,#00E5FF);height:100%;width:0%;transition:width 0.3s ease;border-radius:999px;box-shadow:0 0 8px rgba(0,255,136,0.3)"></div>
                    </div>
                </div>
                
                <div id="logsContainer" style="background:rgba(6,11,20,0.4);border:1px solid rgba(255,255,255,0.04);border-radius:12px;padding:12px;max-height:320px;overflow-y:auto;font-family:'JetBrains Mono',monospace;font-size:12px;line-height:1.6">
                    <div style="color:#64748B">Aguardando início...</div>
                </div>
                
                <div id="btnFecharContainer" style="margin-top:16px;display:none">
                    <button id="btnFecharEscalacaoRapida" style="width:100%;background:rgba(0,255,136,0.08);color:#00FF88;border:1px solid rgba(0,255,136,0.2);padding:10px;border-radius:10px;font-size:14px;font-weight:600;cursor:pointer;transition:all 0.2s">
                        Fechar
                    </button>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
        
        // Funções auxiliares
        const updateProgress = (percent, mensagem) => {
            const progressBar = document.getElementById('progressBar');
            const progressText = document.getElementById('progressText');
            const progressPercent = document.getElementById('progressPercent');
            
            if (progressBar) progressBar.style.width = `${percent}%`;
            if (progressText) progressText.textContent = mensagem || 'Processando...';
            if (progressPercent) progressPercent.textContent = `${Math.round(percent)}%`;
        };
        
        const addLog = (mensagem, tipo = 'info') => {
            const logsContainer = document.getElementById('logsContainer');
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
            btn.disabled = false;
            btn.innerHTML = btnText;
        };
        
        // Event listeners
        document.getElementById('fecharModalEscalacaoRapida').addEventListener('click', fecharModal);
        const btnFechar = document.getElementById('btnFecharEscalacaoRapida');
        btnFechar.addEventListener('click', fecharModal);
        btnFechar.addEventListener('mouseenter', () => { btnFechar.style.background = 'rgba(0,255,136,0.16)'; });
        btnFechar.addEventListener('mouseleave', () => { btnFechar.style.background = 'rgba(0,255,136,0.08)'; });
        
        // Executar escalação rápida
        const escalacaoRapida = new EscalacaoRapida();
        escalacaoRapida.setProgressCallback(updateProgress);
        escalacaoRapida.setLogCallback(addLog);
        
        try {
            const resultado = await escalacaoRapida.executar();
            
            // Mostrar botão de fechar
            document.getElementById('btnFecharContainer').style.display = 'block';
            
            // Mostrar toast de sucesso
            showToast('🎉 Escalação rápida concluída com sucesso!', 'success', 5000);
            
        } catch (error) {
            addLog(`❌ ERRO: ${error.message}`, 'error');
            updateProgress(0, 'Erro ao executar escalação rápida');
            
            // Mostrar botão de fechar mesmo em caso de erro
            document.getElementById('btnFecharContainer').style.display = 'block';
            
            // Mostrar alerta
            showAlert('Erro na Escalação Rápida', error.message, 'error');
        }
    });
});

