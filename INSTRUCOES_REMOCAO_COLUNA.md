# 🔧 Instruções para Remover a Coluna pesos_posicao

## Opções de Execução

### Opção 1: Executar dentro do Container Docker (RECOMENDADO)

Se você estiver usando Docker, execute o script dentro do container onde o app roda:

```bash
docker exec -it cartola-aero-web-app-container python3 executar_remocao_coluna.py
```

### Opção 2: Executar diretamente no servidor

Se você tiver acesso SSH ao servidor:

1. Configure as variáveis de ambiente:
```bash
export POSTGRES_HOST="seu-host"
export POSTGRES_PORT="5432"
export POSTGRES_USER="seu-usuario"
export POSTGRES_PASSWORD="sua-senha"
export POSTGRES_DB="seu-banco"
```

2. Execute o script:
```bash
python3 executar_remocao_coluna.py
```

### Opção 3: Executar SQL manualmente

Se preferir executar diretamente no banco:

```bash
psql -h seu-host -U seu-usuario -d seu-banco -f migration_remover_pesos_posicao.sql
```

Ou conecte-se ao banco e execute:

```sql
ALTER TABLE acw_weight_configurations DROP COLUMN IF EXISTS pesos_posicao;
```

### Opção 4: Usar ferramenta GUI de banco de dados

Se você usa uma ferramenta como pgAdmin, DBeaver, ou similar:

1. Conecte-se ao banco de dados
2. Execute a query:
```sql
ALTER TABLE acw_weight_configurations DROP COLUMN IF EXISTS pesos_posicao;
```

## Verificar se a remoção foi bem-sucedida

Execute esta query para verificar as colunas da tabela:

```sql
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'acw_weight_configurations'
ORDER BY ordinal_position;
```

A coluna `pesos_posicao` NÃO deve aparecer na lista.

## O que foi preparado

✅ **Código atualizado** - Todos os arquivos Python foram modificados para não usar mais `pesos_posicao`
✅ **Documentação atualizada** - ARQUITETURA.MD e SINCRONIZACAO_PESOS.md foram atualizados
✅ **Scripts prontos** - Script Python e SQL prontos para executar
✅ **Sem risco** - A coluna não é usada, só tem dicionários vazios

## Após a execução

Quando a coluna for removida, o sistema continuará funcionando normalmente porque:
- Os pesos reais estão em `acw_posicao_weights`
- O código já não usa mais `pesos_posicao`
- Nenhuma funcionalidade depende dessa coluna

## Problemas?

Se houver algum erro, consulte:
- `ANALISE_REMOCAO_PESOS_POSICAO.md` - Análise completa
- `RESUMO_REMOCAO_PESOS_POSICAO.md` - Resumo das alterações
