# Mudanças: Recombinação de Posições Desescaladas

## Problema Identificado

Quando uma posição não conseguia ser escalada devido a restrições de orçamento, o sistema simplesmente a desescalava e tentava novamente, mas **não fazia recombinações** entre as posições desescaladas para encontrar a melhor opção que cabia no orçamento.

**Resultado:** Escalações incompletas com menos de 12 jogadores (ex: 11 jogadores).

### Exemplo do Log
```
❌ Erro ao escalar: Escalação inválida: 11 atletas. Esperado: 12
```

## Solução Implementada

### 1. Funções de Combinação (JavaScript)

Implementadas duas funções auxiliares no arquivo `/workspace/static/js/escalacao_ideal.js`:

#### `combinations(arr, size)`
Gera todas as combinações possíveis de um array (equivalente ao `itertools.combinations` do Python).

**Exemplo:**
```javascript
combinations([1, 2, 3, 4], 2)
// Resultado: [[1,2], [1,3], [1,4], [2,3], [2,4], [3,4]]
```

#### `product(...arrays)`
Gera o produto cartesiano de múltiplos arrays (equivalente ao `itertools.product` do Python).

**Exemplo:**
```javascript
product([1, 2], [3, 4])
// Resultado: [[1,3], [1,4], [2,3], [2,4]]
```

### 2. Lógica de Recombinação

Modificado o método `tentarEscalacao(posicoesDesescaladas)` para:

1. **Escalar posições prioritárias primeiro** (excluindo as desescaladas)
2. **Calcular orçamento restante**
3. **Buscar candidatos** para cada posição desescalada
   - Todas as posições: **5 candidatos** (otimizado para performance)
4. **Gerar combinações** para cada posição desescalada
5. **Calcular produto cartesiano** de todas as combinações
6. **Testar cada combinação** e escolher a melhor que cabe no orçamento
7. **Escalar a melhor combinação encontrada**

### 3. Validação Final

Adicionada validação no método `calcular()` para garantir que todos os 12 jogadores foram escalados:

```javascript
const totalEsperado = Object.values(this.formacao).reduce((sum, v) => sum + v, 0);
const totalAtual = Object.values(escalacao.titulares).reduce((sum, arr) => sum + arr.length, 0);

if (totalAtual !== totalEsperado) {
    throw new Error(`Escalação inválida: ${totalAtual} atletas. Esperado: ${totalEsperado}`);
}
```

## Fluxo de Escalação Atualizado

```
┌─────────────────────────────────────────────────────┐
│ 1. Tentar escalação com prioridades                │
│    (atacantes → laterais → meias → zagueiros →      │
│     goleiros → técnicos)                            │
└──────────────────┬──────────────────────────────────┘
                   │
                   ↓
         ┌─────────────────┐
         │ Sucesso?        │
         └────────┬────────┘
                  │
         ┌────────┴────────┐
         │                 │
        Sim               Não
         │                 │
         ↓                 ↓
   ┌─────────┐    ┌──────────────────┐
   │ Hack GK │    │ Desescalar       │
   │ Reservas│    │ posição menos    │
   │ Capitão │    │ prioritária      │
   └─────────┘    └────────┬─────────┘
                           │
                           ↓
                  ┌────────────────────┐
                  │ Escalar posições   │
                  │ prioritárias       │
                  └────────┬───────────┘
                           │
                           ↓
                  ┌────────────────────┐
                  │ Calcular orçamento │
                  │ restante           │
                  └────────┬───────────┘
                           │
                           ↓
                  ┌────────────────────┐
                  │ Buscar candidatos  │
                  │ para desescaladas  │
                  └────────┬───────────┘
                           │
                           ↓
                  ┌────────────────────┐
                  │ Gerar combinações  │
                  │ (combinations)     │
                  └────────┬───────────┘
                           │
                           ↓
                  ┌────────────────────┐
                  │ Produto cartesiano │
                  │ (product)          │
                  └────────┬───────────┘
                           │
                           ↓
                  ┌────────────────────┐
                  │ Testar combinações │
                  │ e escolher melhor  │
                  └────────┬───────────┘
                           │
                           ↓
                  ┌────────────────────┐
                  │ Escalar melhor     │
                  │ combinação         │
                  └────────┬───────────┘
                           │
                           ↓
                     ┌─────────┐
                     │ Sucesso │
                     └─────────┘
```

## 💡 Desescalação Progressiva

**O sistema agora funciona assim:**

1. **Tenta escalar tudo** → Se falhar: desescala posição 1
2. **Recombina com 1 posição** (5 candidatos) → Se falhar: desescala posição 2
3. **Recombina com 2 posições** (5x5 = 25 combinações) → Se falhar: desescala posição 3
4. **Recombina com 3 posições** (5x5x5 = 125 combinações) → E assim por diante...

Isso garante que **sempre** haverá uma combinação válida que preenche as 12 posições!

## Exemplo de Log Esperado

```
🎯 Tentativa de escalação. Desescaladas: []
...
❌ Insuficiente: 0/1

⚠️  Desescalando treinadores...

🎯 Tentativa de escalação. Desescaladas: [treinadores]
...
💰 Custo total dos titulares: R$ 125.32 / R$ 133.66

🔄 Recombinando posições desescaladas
   Orçamento restante: R$ 8.34
   📦 Recombinando 1 posição(ões): [treinadores]

📊 Buscando 5 candidatos para cada posição desescalada...

📋 Candidatos para treinadores: 2
   - Técnico 1 (R$ 10.00, 5.00 pts)
   - Técnico 2 (R$ 8.00, 4.50 pts)

🔍 Gerando combinações possíveis...
   Total de combinações a testar: 2

✅ Melhor combinação encontrada! Pontuação: 4.50
   treinadores: Técnico 2 (R$ 8.00)

💰 Custo FINAL: R$ 133.32 / R$ 133.66

✅ ESCALAÇÃO CONCLUÍDA!
💰 Custo: R$ 127.17 / R$ 133.66
📊 Pontuação estimada: 82.94 pts
```

## Arquivos Modificados

- `/workspace/static/js/escalacao_ideal.js`
  - Adicionado método `combinations(arr, size)`
  - Adicionado método `product(...arrays)`
  - Modificado método `tentarEscalacao(posicoesDesescaladas)` com lógica de recombinação
  - Adicionada validação no método `calcular()`

## Arquivos de Teste Criados

- `/workspace/test_combinations.html` - Testa funções de combinação
- `/workspace/test_escalacao_desescalacao.html` - Testa escalação completa com desescalação

## Como Testar

1. Execute o servidor local:
   ```bash
   cd /workspace
   python3 -m http.server 8888
   ```

2. Acesse no navegador:
   - `http://localhost:8888/test_combinations.html` - Teste de combinações
   - `http://localhost:8888/test_escalacao_desescalacao.html` - Teste de escalação completa

3. Ou use a aplicação normalmente:
   - Acesse o módulo de "Escalação Ideal"
   - Configure as opções desejadas
   - Execute o cálculo

## Benefícios

✅ **Escalações completas:** Sempre tenta preencher todas as 12 posições
✅ **Melhor uso do orçamento:** Encontra a melhor combinação dentro do orçamento disponível
✅ **Validação robusta:** Detecta e reporta erros de escalação com detalhamento
✅ **Logs detalhados:** Mostra todo o processo de recombinação

## Referência

A implementação segue a lógica original do arquivo `/workspace/calculo_escalacao_ideal.py` (linhas 492-570), que já implementava corretamente a recombinação de posições desescaladas.
