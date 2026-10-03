# 🚀 Instruções para Testar o Sistema de Planos

> Documento histórico. A matriz atual está em [docs/PLANOS_E_PERMISSOES.md](docs/PLANOS_E_PERMISSOES.md).
> Os contratos da API são verificados com `python -m unittest discover -s tests -v`.

## 📋 Passos para Executar

### 1. Inicializar o Sistema de Planos

Execute o script de inicialização:

```bash
python init_plans.py
```

Isso irá:
- ✅ Verificar/criar tabela de usuários
- ✅ Adicionar coluna `plano` na tabela `acw_users`
- ✅ Criar tabela de histórico de planos

### 2. Aplicar Planos aos Usuários Existentes

Execute o script para aplicar planos:

```bash
python aplicar_planos_usuarios.py
```

Isso irá:
- ✅ Aplicar plano 'pro' para usuários administradores (para testes)
- ✅ Manter plano 'free' para usuários normais
- ✅ Mostrar resumo de todos os usuários e seus planos

### 3. Iniciar a Aplicação

```bash
python app.py
```

### 4. Acessar a Página de Teste de Planos

1. Faça login como administrador
2. No menu lateral, clique em **"Testar Planos (Admin)"**
3. Você verá:
   - Seu plano atual
   - Cards dos 3 planos disponíveis (Free, Avançado, Pro)
   - Permissões detalhadas do seu plano atual
4. Clique em qualquer botão "Selecionar" para alterar seu plano
5. As permissões serão atualizadas automaticamente

## 🎯 Funcionalidades Implementadas

### Backend
- ✅ Sistema de planos (Free, Avançado, Pro)
- ✅ Coluna `plano` na tabela `acw_users`
- ✅ API `/api/user/permissions` para retornar permissões
- ✅ API `/api/admin/alterar-plano` para alterar plano (apenas admins)
- ✅ Função `get_current_user()` atualizada para incluir plano

### Frontend
- ✅ Página `/admin/planos` para admins testarem planos
- ✅ Interface visual com cards dos 3 planos
- ✅ Exibição de permissões detalhadas
- ✅ Botões para alterar plano instantaneamente
- ✅ Link no menu lateral para admins

### Scripts
- ✅ `init_plans.py` - Inicializa o sistema
- ✅ `aplicar_planos_usuarios.py` - Aplica planos aos usuários existentes

## 📊 Estrutura dos Planos

### Free
- 2 perfis de jogo
- 2 perfis de SG
- 1 time
- Ranking limitado (apenas 2 jogadores visíveis)
- Sem escalação

### Avançado
- 5 perfis de jogo
- 6 perfis de SG
- 2 times
- Ranking completo
- Escalar 1 time
- Estatísticas avançadas
- Fechar defesa

### Pro
- 15 perfis de jogo
- 10 perfis de SG
- Times ilimitados
- Editar pesos dos módulos
- Multi-escalação
- Hack do goleiro
- Tudo liberado

## 🔍 Verificações

### Verificar se o sistema está funcionando:

1. **Verificar coluna no banco:**
```sql
SELECT id, username, plano FROM acw_users;
```

2. **Verificar permissões via API:**
```bash
# Faça login primeiro, depois:
curl http://localhost:5000/api/user/permissions
```

3. **Testar alteração de plano:**
- Acesse `/admin/planos` como admin
- Clique em qualquer plano
- Verifique se as permissões mudam

## 🐛 Troubleshooting

### Erro: "Coluna 'plano' não existe"
Execute: `python init_plans.py`

### Erro: "Usuário não tem plano"
Execute: `python aplicar_planos_usuarios.py`

### Permissões não atualizam
- Recarregue a página
- Verifique se o JavaScript está carregando (`plan-permissions.js`)
- Verifique o console do navegador para erros

## ✅ Próximos Passos

Após testar os planos, você pode:
1. Aplicar bloqueios visuais nas páginas de módulos
2. Aplicar bloqueios na página de escalação
3. Limitar perfis de jogo/SG baseado no plano
4. Implementar verificação de limite de times

