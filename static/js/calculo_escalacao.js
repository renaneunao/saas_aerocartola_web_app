/**
 * Módulo de Rankings e Pesos
 * Exibe os melhores jogadores por posição e pesos de clubes
 */

// Carregar cards ao inicializar
document.addEventListener('DOMContentLoaded', async function() {
    showLoader('Carregando informações e rankings do time...');
    try {
        await carregarCardsTop5();
    } finally {
        hideLoader();
    }
});

/**
 * Carrega os dados dos rankings e pesos
 */
async function carregarCardsTop5() {
    try {
        const response = await fetch('/api/escalacao-ideal/dados');
        const data = await response.json();
        
        if (data.error) {
            throw new Error(data.error);
        }
        
        exibirInfoInicial(data);
        exibirCardsTop5(data);
    } catch (error) {
        console.error('Erro ao carregar dados:', error);
        showToast('Erro ao carregar dados do time', 'error');
        document.getElementById('infoInicialContent').innerHTML = `
            <div class="text-center text-red-400 py-8">
                <i class="fas fa-exclamation-triangle text-2xl mb-2"></i>
                <p>Erro ao carregar informações: ${error.message}</p>
            </div>
        `;
        document.getElementById('top5CardsContent').innerHTML = `
            <div class="text-center text-red-400 py-8">
                <i class="fas fa-exclamation-triangle text-2xl mb-2"></i>
                <p>Erro ao carregar rankings: ${error.message}</p>
            </div>
        `;
    }
}

/**
 * Exibe as informações do time (patrimônio, rodada, team ID)
 */
function exibirInfoInicial(data) {
    const container = document.getElementById('infoInicialContent');
    
    container.innerHTML = `
        <div class="flex items-center gap-3 bg-dark-blue-800/30 rounded-lg px-4 py-3 border border-dark-blue-700">
            <i class="fas fa-wallet text-yellow-400 text-xl"></i>
            <div>
                <span class="text-gray-300 text-sm">Patrimônio</span>
                <p class="text-yellow-300 font-bold text-lg">R$ ${parseFloat(data.patrimonio || 0).toFixed(2)}</p>
                ${data.patrimonio_error ? `<span class="text-red-400 text-xs">⚠️ ${data.patrimonio_error}</span>` : ''}
            </div>
        </div>
        <div class="flex items-center gap-3 bg-dark-blue-800/30 rounded-lg px-4 py-3 border border-dark-blue-700">
            <i class="fas fa-calendar-alt text-blue-400 text-xl"></i>
            <div>
                <span class="text-gray-300 text-sm">Rodada</span>
                <p class="text-white font-semibold text-lg">${data.rodada_atual || 'N/A'}</p>
            </div>
        </div>
        <div class="flex items-center gap-3 bg-dark-blue-800/30 rounded-lg px-4 py-3 border border-dark-blue-700">
            <i class="fas fa-shield-alt text-green-400 text-xl"></i>
            <div>
                <span class="text-gray-300 text-sm">Time ID</span>
                <p class="text-white font-semibold text-lg">${data.team_id || 'N/A'}</p>
            </div>
        </div>
    `;
}

/**
 * Exibe os cards com top 5 de cada posição e pesos
 */
function exibirCardsTop5(data) {
    const container = document.getElementById('top5CardsContent');
    let html = '';
    
    const posicoes = [
        { key: 'goleiro', nome: 'Goleiros', icon: 'fas fa-hands' },
        { key: 'zagueiro', nome: 'Zagueiros', icon: 'fas fa-shield-alt' },
        { key: 'lateral', nome: 'Laterais', icon: 'fas fa-arrows-alt-h' },
        { key: 'meia', nome: 'Meias', icon: 'fas fa-running' },
        { key: 'atacante', nome: 'Atacantes', icon: 'fas fa-futbol' },
        { key: 'treinador', nome: 'Treinadores', icon: 'fas fa-clipboard-list' }
    ];
    
    // Layout: Rankings de posições (6 colunas) e Pesos (2 colunas) na mesma linha
    html += '<div class="grid grid-cols-1 lg:grid-cols-8 gap-4">';
    
    // Rankings de Posições (6 colunas)
    for (const pos of posicoes) {
        const ranking = data.rankings_por_posicao[pos.key] || [];
        const top5 = ranking.slice(0, 5);
        
        html += `
            <div class="bg-dark-blue-800/30 rounded-lg border border-dark-blue-500/30 p-3">
                <div class="flex items-center gap-2 mb-3 pb-2 border-b border-dark-blue-600">
                    <i class="${pos.icon} text-yellow-400 text-sm"></i>
                    <h4 class="text-yellow-300 font-bold text-sm">${pos.nome}</h4>
                </div>
                <div class="space-y-2">
        `;
        
        if (top5.length === 0) {
            html += '<p class="text-gray-500 text-xs text-center py-2">Nenhum jogador</p>';
        } else {
            for (let i = 0; i < top5.length; i++) {
                const jogador = top5[i];
                const clube = data.clubes_dict[jogador.clube_id] || {};
                const escudo = clube.escudo_url || 'https://s.glbimg.com/es/sde/f/organizacoes/2018/03/10/flamengo_60x60.png';
                const preco = parseFloat(jogador.preco_num || jogador.preco || 0).toFixed(2);
                const pontos = parseFloat(jogador.pontuacao_total || 0).toFixed(1);
                
                html += `
                    <div class="bg-dark-blue-900/50 rounded p-3 border border-dark-blue-700 hover:border-yellow-500/50 transition-all">
                        <div class="flex items-start gap-2 mb-2">
                            <img src="${escudo}" alt="${clube.nome || 'Clube'}" class="w-6 h-6 rounded flex-shrink-0" onerror="this.src='https://s.glbimg.com/es/sde/f/organizacoes/2018/03/10/flamengo_60x60.png'">
                            <span class="text-white text-sm font-semibold flex-1">${jogador.apelido || 'N/A'}</span>
                        </div>
                        <div class="flex justify-between text-xs">
                            <span class="text-yellow-400 font-medium">R$ ${preco}</span>
                            <span class="text-green-400 font-medium">${pontos} pts</span>
                        </div>
                    </div>
                `;
            }
        }
        
        html += '</div></div>';
    }
    
    // Peso de Jogo (1 coluna)
    html += `
        <div class="bg-dark-blue-800/30 rounded-lg border border-dark-blue-500/30 p-3">
            <div class="flex items-center gap-2 mb-3 pb-2 border-b border-dark-blue-600">
                <i class="fas fa-fire text-orange-400 text-sm"></i>
                <h4 class="text-orange-300 font-bold text-sm">Peso de Jogo</h4>
            </div>
            <div class="space-y-2">
    `;
    
    if (data.top5_peso_jogo && data.top5_peso_jogo.length > 0) {
        for (const item of data.top5_peso_jogo) {
            const clube = data.clubes_dict[item.clube_id] || {};
            const escudo = clube.escudo_url || 'https://s.glbimg.com/es/sde/f/organizacoes/2018/03/10/flamengo_60x60.png';
            const peso = parseFloat(item.peso_jogo || 0).toFixed(2);
            
            html += `
                <div class="bg-dark-blue-900/50 rounded p-3 border border-dark-blue-700 hover:border-orange-500/50 transition-all">
                    <div class="flex items-center gap-2">
                        <img src="${escudo}" alt="${clube.nome || 'Clube'}" class="w-6 h-6 rounded flex-shrink-0" onerror="this.src='https://s.glbimg.com/es/sde/f/organizacoes/2018/03/10/flamengo_60x60.png'">
                        <div class="flex-1">
                            <div class="text-white text-sm font-semibold">${clube.nome || 'N/A'}</div>
                            <div class="text-orange-400 text-xs font-medium">${peso}</div>
                        </div>
                    </div>
                </div>
            `;
        }
    } else {
        html += '<p class="text-gray-500 text-xs text-center py-2">Nenhum clube</p>';
    }
    
    html += '</div></div>';
    
    // Peso SG (1 coluna)
    html += `
        <div class="bg-dark-blue-800/30 rounded-lg border border-dark-blue-500/30 p-3">
            <div class="flex items-center gap-2 mb-3 pb-2 border-b border-dark-blue-600">
                <i class="fas fa-chart-line text-green-400 text-sm"></i>
                <h4 class="text-green-300 font-bold text-sm">Peso SG</h4>
            </div>
            <div class="space-y-2">
    `;
    
    if (data.top5_peso_sg && data.top5_peso_sg.length > 0) {
        for (const item of data.top5_peso_sg) {
            const clube = data.clubes_dict[item.clube_id] || {};
            const escudo = clube.escudo_url || 'https://s.glbimg.com/es/sde/f/organizacoes/2018/03/10/flamengo_60x60.png';
            const peso = parseFloat(item.peso_sg || 0).toFixed(2);
            
            html += `
                <div class="bg-dark-blue-900/50 rounded p-3 border border-dark-blue-700 hover:border-green-500/50 transition-all">
                    <div class="flex items-center gap-2">
                        <img src="${escudo}" alt="${clube.nome || 'Clube'}" class="w-6 h-6 rounded flex-shrink-0" onerror="this.src='https://s.glbimg.com/es/sde/f/organizacoes/2018/03/10/flamengo_60x60.png'">
                        <div class="flex-1">
                            <div class="text-white text-sm font-semibold">${clube.nome || 'N/A'}</div>
                            <div class="text-green-400 text-xs font-medium">${peso}</div>
                        </div>
                    </div>
                </div>
            `;
        }
    } else {
        html += '<p class="text-gray-500 text-xs text-center py-2">Nenhum clube</p>';
    }
    
    html += '</div></div>';
    html += '</div>'; // Fecha grid principal
    
    container.innerHTML = html;
}

