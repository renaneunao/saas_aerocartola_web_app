# 🎨 UI Components - Guia de Uso

Sistema centralizado de feedback visual para toda a aplicação.

## 📦 Componentes Disponíveis

### 1. 🔄 Loader (Spinner de Carregamento)

**Mostrar loader:**
```javascript
showLoader('Carregando dados...');
```

**Esconder loader:**
```javascript
hideLoader();
```

**Atualizar mensagem (sem esconder):**
```javascript
updateLoaderMessage('Processando...');
```

**Exemplo completo:**
```javascript
async function minhaFuncao() {
    showLoader('Buscando dados...');
    
    try {
        const response = await fetch('/api/dados');
        updateLoaderMessage('Processando dados...');
        const data = await response.json();
        
        // ... processar dados ...
        
    } finally {
        hideLoader(); // SEMPRE esconder no finally!
    }
}
```

---

### 2. 🔔 Toast Notifications

**Sintaxe:**
```javascript
showToast(mensagem, tipo, duracao);
```

**Tipos disponíveis:**
- `'success'` - Verde (✅ sucesso)
- `'error'` - Vermelho (❌ erro)
- `'warning'` - Amarelo (⚠️ aviso)
- `'info'` - Azul (ℹ️ informação)

**Exemplos:**
```javascript
// Toast de sucesso (4 segundos)
showToast('Dados salvos com sucesso!', 'success');

// Toast de erro (5 segundos)
showToast('Erro ao processar requisição', 'error', 5000);

// Toast de aviso
showToast('Atenção: Dados não sincronizados', 'warning');

// Toast permanente (não some automaticamente)
showToast('Processamento em andamento...', 'info', 0);
```

---

### 3. ⚠️ Alert Personalizado

**Sintaxe:**
```javascript
await showAlert(mensagem, titulo, tipo);
```

**Tipos:** `'success'`, `'error'`, `'warning'`, `'info'`

**Exemplos:**
```javascript
// Alert simples
await showAlert('Operação concluída!', 'Sucesso', 'success');

// Alert de erro
await showAlert('Não foi possível conectar ao servidor', 'Erro', 'error');

// Alert de aviso
await showAlert('Você tem alterações não salvas', 'Atenção', 'warning');

// Alert informativo
await showAlert('Esta ação não pode ser desfeita', 'Informação', 'info');
```

---

### 4. ❓ Confirm Personalizado

**Sintaxe:**
```javascript
const confirmado = await showConfirm(mensagem, titulo, opcoes);
```

**Opções disponíveis:**
```javascript
{
    confirmText: 'Texto do botão confirmar',
    cancelText: 'Texto do botão cancelar',
    confirmClass: 'Classes CSS do botão confirmar',
    cancelClass: 'Classes CSS do botão cancelar'
}
```

**Exemplos:**
```javascript
// Confirm simples
const confirmar = await showConfirm(
    'Deseja realmente deletar este item?',
    'Confirmar Exclusão'
);

if (confirmar) {
    // Usuário clicou em "Confirmar"
    deletarItem();
}

// Confirm customizado
const confirmar = await showConfirm(
    'Esta ação é irreversível. Continuar?',
    'Atenção',
    {
        confirmText: 'Sim, continuar',
        cancelText: 'Não, voltar',
        confirmClass: 'bg-red-600 hover:bg-red-700' // Botão vermelho
    }
);
```

---

## 🎯 Exemplos Práticos

### Exemplo 1: Salvar Dados
```javascript
async function salvarDados() {
    showLoader('Salvando dados...');
    
    try {
        const response = await fetch('/api/salvar', {
            method: 'POST',
            body: JSON.stringify(dados)
        });
        
        if (response.ok) {
            showToast('Dados salvos com sucesso!', 'success');
        } else {
            throw new Error('Erro ao salvar');
        }
    } catch (error) {
        showAlert(error.message, 'Erro ao Salvar', 'error');
    } finally {
        hideLoader();
    }
}
```

### Exemplo 2: Deletar com Confirmação
```javascript
async function deletarTime(timeId) {
    const confirmar = await showConfirm(
        'Tem certeza que deseja deletar este time? Esta ação não pode ser desfeita.',
        '🗑️ Deletar Time',
        {
            confirmText: 'Sim, deletar',
            cancelText: 'Cancelar',
            confirmClass: 'bg-red-600 hover:bg-red-700'
        }
    );
    
    if (!confirmar) return;
    
    showLoader('Deletando time...');
    
    try {
        await fetch(`/api/times/${timeId}`, { method: 'DELETE' });
        showToast('Time deletado com sucesso!', 'success');
        recarregarLista();
    } catch (error) {
        showAlert('Erro ao deletar time', 'Erro', 'error');
    } finally {
        hideLoader();
    }
}
```

### Exemplo 3: Múltiplas Etapas
```javascript
async function processarComplexo() {
    showLoader('Iniciando processamento...');
    
    try {
        // Etapa 1
        updateLoaderMessage('Buscando dados (1/3)...');
        const dados = await buscarDados();
        
        // Etapa 2
        updateLoaderMessage('Processando (2/3)...');
        const resultado = await processar(dados);
        
        // Etapa 3
        updateLoaderMessage('Salvando (3/3)...');
        await salvar(resultado);
        
        showToast('Processamento concluído!', 'success');
        
    } catch (error) {
        showAlert(error.message, 'Erro no Processamento', 'error');
    } finally {
        hideLoader();
    }
}
```

---

## ⚡ Boas Práticas

1. **SEMPRE use `hideLoader()` no `finally`**
   ```javascript
   try {
       showLoader('...');
       // código
   } finally {
       hideLoader(); // ✅ SEMPRE!
   }
   ```

2. **Use Toast para feedback rápido**
   - Toast: Informações rápidas, não bloqueantes
   - Alert: Informações importantes que exigem atenção

3. **Use Confirm para ações destrutivas**
   - Sempre peça confirmação antes de deletar/modificar dados importantes

4. **Mensagens claras e objetivas**
   ```javascript
   // ❌ Ruim
   showLoader('Aguarde...');
   
   // ✅ Bom
   showLoader('Calculando escalação ideal...');
   ```

5. **Evite loaders para operações instantâneas**
   - Se a operação leva < 500ms, considere não usar loader

---

## 🎨 Customização

Para customizar os estilos, edite o arquivo `static/js/ui-components.js`.

As cores seguem o padrão Tailwind CSS:
- Success: `bg-green-600`
- Error: `bg-red-600`
- Warning: `bg-yellow-600`
- Info: `bg-blue-600`

---

## 📍 Onde Usar

### ✅ Use Loader em:
- Requisições HTTP (fetch, POST, GET)
- Cálculos demorados no cliente
- Carregamento de dados
- Processos com múltiplas etapas

### ✅ Use Toast em:
- Confirmações de sucesso
- Erros não-críticos
- Avisos informativos
- Feedback de ações do usuário

### ✅ Use Alert em:
- Erros críticos
- Informações importantes
- Mensagens que exigem leitura

### ✅ Use Confirm em:
- Exclusões
- Ações irreversíveis
- Mudanças importantes
- Saída de páginas com dados não salvos

---

## 🔗 Importação

O arquivo já está importado globalmente no `base.html`:
```html
<script src="{{ url_for('static', filename='js/ui-components.js') }}"></script>
```

Todas as funções estão disponíveis globalmente em qualquer página! 🎉

