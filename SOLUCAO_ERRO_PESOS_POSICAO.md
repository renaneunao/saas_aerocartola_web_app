# 🔧 Solução: Erro ao Salvar Pesos (Coluna pesos_posicao)

## 📋 Problema Identificado

Ao tentar salvar os pesos, você está encontrando um erro relacionado à coluna `pesos_posicao` que não existe mais (ou não deveria existir) na tabela `acw_weight_configurations`.

### Causa Raiz

A coluna `pesos_posicao` foi **removida do código** mas ainda **existe no banco de dados**. Isso causa conflitos quando o código tenta fazer INSERT ou UPDATE na tabela, pois:

1. O código Python não envia dados para esta coluna (porque ela não é mais usada)
2. Mas o banco de dados ainda espera esta coluna (se ela existir com NOT NULL ou sem DEFAULT)
3. Isso gera erro na hora de salvar

## ✅ Solução Implementada

Foram feitas **2 correções**:

### 1. Migration Automática (Permanente) ✅

Adicionei lógica no arquivo `init_database.py` para **remover automaticamente** a coluna `pesos_posicao` quando o banco de dados for inicializado.

**Localização da correção:**
- Arquivo: `/workspace/init_database.py`
- Linhas: 122-137

**O que foi adicionado:**
```python
# Verificar e remover coluna pesos_posicao se existir (não é mais utilizada)
if table_exists:
    cursor.execute('''
        SELECT EXISTS (
            SELECT FROM information_schema.columns 
            WHERE table_schema = 'public' 
            AND table_name = 'acw_weight_configurations'
            AND column_name = 'pesos_posicao'
        )
    ''')
    if cursor.fetchone()[0]:
        print("   Removendo coluna obsoleta pesos_posicao...")
        cursor.execute('ALTER TABLE acw_weight_configurations DROP COLUMN IF EXISTS pesos_posicao')
        conn.commit()
        print("   ✅ Coluna pesos_posicao removida")
```

### 2. Script de Correção Imediata ✅

Criei um script que você pode executar **AGORA** para remover a coluna sem precisar reiniciar a aplicação.

**Arquivo:** `/workspace/fix_pesos_posicao_column.py`

## 🚀 Como Executar a Correção

### Opção 1: Script Imediato (Recomendado)

Execute este comando no terminal:

```bash
python3 fix_pesos_posicao_column.py
```

**Ou dentro do container Docker:**

```bash
docker exec -it <nome-do-container> python3 fix_pesos_posicao_column.py
```

**Exemplo de saída esperada:**
```
🔧 CORRIGINDO ERRO: Removendo coluna obsoleta pesos_posicao
======================================================================

1️⃣  Verificando se a coluna pesos_posicao existe...
   ✅ Coluna pesos_posicao encontrada

2️⃣  Removendo coluna pesos_posicao...
   ✅ Coluna removida com sucesso!

3️⃣  Verificando estrutura final da tabela...
   Colunas atuais:
      - id (integer)
      - user_id (integer)
      - name (character varying)
      - perfil_peso_jogo (integer)
      - perfil_peso_sg (integer)
      - is_default (boolean)
      - created_at (timestamp without time zone)
      - updated_at (timestamp without time zone)
      - team_id (integer)

======================================================================
✅ CORREÇÃO CONCLUÍDA COM SUCESSO!
Agora você pode salvar os pesos sem problemas.
======================================================================
```

### Opção 2: Migration SQL Manual

Se preferir executar SQL diretamente:

```sql
-- Verificar se a coluna existe
SELECT column_name 
FROM information_schema.columns 
WHERE table_name = 'acw_weight_configurations' 
AND column_name = 'pesos_posicao';

-- Remover a coluna se existir
ALTER TABLE acw_weight_configurations DROP COLUMN IF EXISTS pesos_posicao;

-- Verificar resultado
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'acw_weight_configurations'
ORDER BY ordinal_position;
```

### Opção 3: Reiniciar Aplicação

A correção será aplicada automaticamente quando você reiniciar a aplicação, pois o `init_database.py` foi atualizado.

## 📝 O Que Foi Corrigido

### Arquivos Modificados

1. **`/workspace/init_database.py`**
   - ✅ Adicionada verificação automática para remover coluna `pesos_posicao`
   - ✅ A migração será executada toda vez que o banco for inicializado
   - ✅ Não quebra se a coluna já foi removida (usa IF EXISTS)

2. **`/workspace/fix_pesos_posicao_column.py`** (NOVO)
   - ✅ Script de correção imediata
   - ✅ Verifica existência da coluna
   - ✅ Remove a coluna com segurança
   - ✅ Mostra estrutura final da tabela

## ✅ Verificação Final

Após executar a correção, você pode testar:

1. **Acesse a aplicação**
2. **Vá para os módulos** (goleiro, lateral, zagueiro, etc.)
3. **Ajuste os pesos** conforme necessário
4. **Clique em "Salvar Pesos"**
5. **Verifique se não há mais erro** ✅

## 📚 Contexto Adicional

A coluna `pesos_posicao` foi originalmente criada para armazenar pesos das posições na tabela `acw_weight_configurations`, mas **nunca foi efetivamente utilizada**. Os pesos das posições sempre foram (e continuam sendo) armazenados corretamente na tabela `acw_posicao_weights`.

### Documentação Relacionada

- `ANALISE_REMOCAO_PESOS_POSICAO.md` - Análise detalhada
- `RESUMO_REMOCAO_PESOS_POSICAO.md` - Resumo das alterações
- `README_EXECUCAO_REMOCAO.md` - Instruções anteriores
- `migration_remover_pesos_posicao.sql` - Script SQL original

## 🎯 Resultado Esperado

Após aplicar esta correção:

✅ A coluna `pesos_posicao` será removida do banco de dados  
✅ O salvamento de pesos funcionará corretamente  
✅ Nenhum erro será exibido ao salvar configurações  
✅ Todos os pesos serão salvos na tabela correta (`acw_posicao_weights`)  

## ❓ Em Caso de Dúvidas

Se o erro persistir após executar o script, verifique:

1. **Logs do erro**: Capture a mensagem de erro completa
2. **Colunas da tabela**: Execute o SELECT acima para ver a estrutura atual
3. **Permissões**: Certifique-se de ter permissões para ALTER TABLE
4. **Connection**: Verifique se a variável DATABASE_URL está configurada corretamente

---

**Data da correção:** 2025-11-07  
**Branch:** cursor/fix-non-existent-column-error-on-save-ffd0
