# Salvamento Automático de Pesos Padrão

## Objetivo

Garantir que **todos os cálculos e exibições de tabelas sempre usem pesos salvos no banco de dados**, nunca pesos temporários ou hardcoded no JavaScript.

## Implementação

### Fluxo Anterior:
1. Usuário abre um módulo pela primeira vez
2. Sistema exibe tabela com pesos padrão do JS (não salvos)
3. Usuário precisa clicar em "Salvar Pesos" manualmente
4. ❌ Problema: Tabela aparecia com pesos não salvos

### Fluxo Novo:
1. Usuário abre um módulo pela primeira vez
2. ✅ Sistema verifica se há pesos salvos
3. ✅ Se NÃO houver pesos salvos → **Salva automaticamente os pesos padrão**
4. ✅ Só depois exibe a tabela
5. ✅ Garantia: **Tabela SEMPRE aparece com pesos salvos**

## Alterações Implementadas

### 1. Backend (app.py)

#### API `/api/modulos/<modulo>/verificar-ranking`
**Linha**: 1174-1284

**Mudanças**:
- Adicionada verificação de pesos salvos na tabela `acw_posicao_weights`
- Retorna `has_weights: true/false` além de `has_ranking`
- Permite que o frontend saiba se precisa salvar pesos

**Código adicionado**:
```python
# Verificar se há pesos salvos para este time e módulo
cursor.execute('''
    SELECT weights_json FROM acw_posicao_weights
    WHERE user_id = %s AND team_id = %s AND posicao = %s
''', (user['id'], team_id, modulo))
peso_row = cursor.fetchone()
has_weights = peso_row is not None and peso_row[0] is not None
```

**Retornos atualizados**:
```python
return jsonify({
    'has_ranking': True/False,
    'has_weights': True/False,  # NOVO!
    'rodada_atual': ...,
    'ranking_count': ...
})
```

### 2. Frontend - Templates HTML

#### Botão "Salvar Pesos" → "Salvar e Recalcular"

Atualizado em todos os módulos para deixar claro que salvar vai recalcular:

**Módulos atualizados**:
- ✅ `templates/modulo_goleiro.html` (linha 140-147)
- ✅ `templates/modulo_lateral.html` (linha 184-191)
- ✅ `templates/modulo_zagueiro.html` (linha 129-136)
- ✅ `templates/modulo_meia.html` (linha 173-180)
- ✅ `templates/modulo_atacante.html` (linha 173-180)

**Antes**:
```html
<i class="fas fa-info-circle mr-2"></i>
Alterações serão aplicadas ao recalcular
...
<i class="fas fa-save mr-2"></i>
Salvar Pesos
```

**Depois**:
```html
<i class="fas fa-info-circle mr-2"></i>
Clique para salvar e recalcular com os novos pesos
...
<i class="fas fa-save mr-2"></i>
Salvar e Recalcular
```

#### Lógica JavaScript de Salvamento Automático

Adicionado em todos os módulos na função `carregarDados()`:

**Módulos atualizados**:
- ✅ `templates/modulo_goleiro.html` (linhas 413-470)
- ✅ `templates/modulo_lateral.html` (linhas 456-503)
- ✅ `templates/modulo_zagueiro.html` (linhas 404-450)
- ✅ `templates/modulo_meia.html` (linhas 453-500)
- ✅ `templates/modulo_atacante.html` (linhas 453-500)

**Código adicionado**:
```javascript
try {
    const checkResponse = await fetch('/api/modulos/<posicao>/verificar-ranking');
    const checkData = await checkResponse.json();
    
    // Se não tem pesos salvos, salvar os pesos padrão ANTES de continuar
    if (!checkData.has_weights) {
        updateProgress(15, 'Salvando pesos padrão...');
        addProgressLog('💾 Primeira vez! Salvando pesos padrão...', 'info');
        
        // Pegar pesos do formulário (que já vêm do servidor com valores padrão)
        const form = document.getElementById('pesosForm');
        const formData = new FormData(form);
        const pesos = {};
        for (const [key, value] of formData.entries()) {
            pesos[key] = parseFloat(value);
        }
        
        // Salvar pesos padrão
        const saveResponse = await fetch('/api/modulos/<posicao>/pesos', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(pesos)
        });
        
        if (!saveResponse.ok) {
            throw new Error('Erro ao salvar pesos padrão');
        }
        
        addProgressLog('✅ Pesos padrão salvos com sucesso!', 'success');
    }
}
```

## Benefícios

### 1. Consistência Total
- ✅ **100% dos cálculos usam pesos salvos no banco**
- ✅ Nunca há discrepância entre formulário e tabela
- ✅ Rastreabilidade completa de quais pesos foram usados

### 2. Auditoria e Histórico
- ✅ Todos os pesos ficam registrados em `acw_posicao_weights`
- ✅ Possibilidade futura de histórico de alterações
- ✅ Facilita debugging e suporte

### 3. Experiência do Usuário
- ✅ Usuário não precisa saber que deve "salvar" na primeira vez
- ✅ Sistema "just works" - salva automaticamente
- ✅ Botão deixa claro: "Salvar e Recalcular"

### 4. Integridade de Dados
- ✅ Garante que rankings salvos sempre têm pesos correspondentes
- ✅ Evita situações onde há ranking mas não há pesos
- ✅ Banco de dados sempre consistente

## Fluxograma

```
┌─────────────────────────────────────┐
│ Usuário abre módulo (ex: /goleiro) │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│ JavaScript: Verificar pesos salvos  │
│ GET /api/modulos/goleiro/verificar  │
└──────────────┬──────────────────────┘
               │
      ┌────────┴────────┐
      │                 │
      ▼                 ▼
┌─────────────┐   ┌──────────────┐
│ has_weights │   │ has_weights  │
│   = false   │   │   = true     │
└─────┬───────┘   └──────┬───────┘
      │                   │
      ▼                   │
┌─────────────────────┐   │
│ 💾 Salvar pesos     │   │
│ padrão (POST)       │   │
└─────┬───────────────┘   │
      │                   │
      └────────┬──────────┘
               │
               ▼
┌─────────────────────────────────────┐
│ Verificar se há ranking salvo       │
└──────────────┬──────────────────────┘
               │
      ┌────────┴────────┐
      │                 │
      ▼                 ▼
┌─────────────┐   ┌──────────────┐
│ has_ranking │   │ has_ranking  │
│   = false   │   │   = true     │
└─────┬───────┘   └──────┬───────┘
      │                   │
      ▼                   ▼
┌─────────────┐   ┌──────────────┐
│ Calcular    │   │ Exibir       │
│ ranking     │   │ ranking      │
│ (com pesos  │   │ salvo        │
│  salvos)    │   │              │
└─────┬───────┘   └──────┬───────┘
      │                   │
      └────────┬──────────┘
               │
               ▼
┌─────────────────────────────────────┐
│ ✅ Exibir tabela                    │
│ (sempre com pesos salvos!)          │
└─────────────────────────────────────┘
```

## Testando

### Cenário 1: Primeira Vez (Sem Pesos Salvos)
1. Criar um novo time/credencial
2. Abrir qualquer módulo (ex: Goleiros)
3. ✅ Deve aparecer mensagem: "💾 Primeira vez! Salvando pesos padrão..."
4. ✅ Tabela deve aparecer com os pesos salvos
5. ✅ Verificar no banco: `SELECT * FROM acw_posicao_weights WHERE posicao = 'goleiro'`

### Cenário 2: Com Pesos Salvos
1. Time já tem pesos salvos
2. Abrir o módulo
3. ✅ NÃO deve aparecer mensagem de salvamento
4. ✅ Deve usar pesos existentes

### Cenário 3: Alterar Pesos
1. Modificar algum peso no formulário
2. Clicar em "Salvar e Recalcular"
3. ✅ Deve salvar os novos pesos
4. ✅ Deve recalcular a tabela automaticamente

### Cenário 4: Múltiplos Times
1. Criar 2 times diferentes
2. Cada um deve ter seus próprios pesos salvos
3. ✅ Alteração em um não afeta o outro

## Tabelas do Banco Afetadas

### `acw_posicao_weights`
```sql
CREATE TABLE IF NOT EXISTS acw_posicao_weights (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    team_id INTEGER NOT NULL,
    posicao VARCHAR(20) NOT NULL,  -- 'goleiro', 'lateral', etc
    weights_json JSONB NOT NULL,    -- Pesos salvos
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES acf_users(id),
    UNIQUE(user_id, team_id, posicao)
);
```

## Arquivos Modificados

### Backend:
- ✅ `/workspace/app.py` (linhas 1174-1284)

### Frontend - Templates:
- ✅ `/workspace/templates/modulo_goleiro.html`
- ✅ `/workspace/templates/modulo_lateral.html`
- ✅ `/workspace/templates/modulo_zagueiro.html`
- ✅ `/workspace/templates/modulo_meia.html`
- ✅ `/workspace/templates/modulo_atacante.html`

### Documentação:
- ✅ `/workspace/SINCRONIZACAO_PESOS.md` (criado anteriormente)
- ✅ `/workspace/SALVAMENTO_AUTOMATICO_PESOS.md` (este arquivo)

---

**Data**: 2025-11-05  
**Status**: ✅ Implementado e Testado  
**Impacto**: Alto - Melhora significativa na consistência e UX
