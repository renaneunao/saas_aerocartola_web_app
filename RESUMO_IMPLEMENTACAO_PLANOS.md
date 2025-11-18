# 📘 Resumo da Implementação - Sistema de Planos

## ✅ O que foi implementado

Sistema de planos simplificado, sem dependências do Stripe, focado nos 3 planos: **Free**, **Avançado** e **Pro**.

## 🗄️ Estrutura do Banco de Dados

### Modificação na Tabela `acw_users`

Adicionada coluna `plano` diretamente na tabela de usuários:

```sql
ALTER TABLE acw_users 
ADD COLUMN plano VARCHAR(50) NOT NULL DEFAULT 'free';

ALTER TABLE acw_users 
ADD CONSTRAINT check_plano_valido 
CHECK (plano IN ('free', 'avancado', 'pro'));
```

### Nova Tabela: `acw_plan_history` (Opcional)

Tabela de histórico para auditoria de mudanças de planos:

```sql
CREATE TABLE acw_plan_history (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES acw_users(id) ON DELETE CASCADE,
    plano_anterior VARCHAR(50),
    plano_novo VARCHAR(50) NOT NULL,
    motivo VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## 📋 JSON Oficial dos Planos

### Free
```json
{
  "name": "Free",
  "rankingCompleto": false,
  "pesosJogo": 2,
  "pesosSG": 2,
  "editarPesosModulos": false,
  "verEscalacaoIdealCompleta": false,
  "podeEscalar": false,
  "timesMaximos": 1,
  "estatisticasAvancadas": false,
  "fecharDefesa": false,
  "hackGoleiro": false,
  "multiEscalacao": false,
  "nivelRisco": 1
}
```

### Avançado
```json
{
  "name": "Avançado",
  "rankingCompleto": true,
  "pesosJogo": 5,
  "pesosSG": 6,
  "editarPesosModulos": false,
  "verEscalacaoIdealCompleta": true,
  "podeEscalar": true,
  "timesMaximos": 2,
  "estatisticasAvancadas": true,
  "fecharDefesa": true,
  "hackGoleiro": false,
  "multiEscalacao": false,
  "nivelRisco": 3
}
```

### Pro
```json
{
  "name": "Pro",
  "rankingCompleto": true,
  "pesosJogo": 15,
  "pesosSG": 10,
  "editarPesosModulos": true,
  "verEscalacaoIdealCompleta": true,
  "podeEscalar": true,
  "timesMaximos": "infinite",
  "estatisticasAvancadas": true,
  "fecharDefesa": true,
  "hackGoleiro": true,
  "multiEscalacao": true,
  "nivelRisco": 10
}
```

## 🔧 Como Inicializar

Execute o script de inicialização:

```bash
python init_plans.py
```

Isso irá:
1. Verificar conexão com o banco
2. Verificar/criar tabela de usuários
3. Adicionar coluna `plano` na tabela `acw_users`
4. Criar tabela de histórico (opcional)

## 📁 Arquivos Criados/Modificados

### Novos Arquivos
- `models/plans.py` - Modelo de planos e permissões
- `utils/permissions.py` - Decorators e helpers de permissões
- `static/js/plan-permissions.js` - JavaScript para frontend
- `init_plans.py` - Script de inicialização
- `verificar_banco.py` - Script de verificação do banco

### Arquivos Modificados
- `app.py` - Adicionada rota `/api/user/permissions`
- `templates/base.html` - Adicionado script `plan-permissions.js`

## 🚀 Como Usar

### Backend

```python
from models.plans import get_user_plan, set_user_plan, get_user_plan_config
from utils.permissions import check_permission, get_user_permissions

# Obter plano do usuário
plano = get_user_plan(user_id)  # Retorna: 'free', 'avancado' ou 'pro'

# Definir plano do usuário
set_user_plan(user_id, 'avancado', motivo='Upgrade manual')

# Obter configuração completa do plano
config = get_user_plan_config(user_id)

# Verificar permissão específica
if check_permission(user_id, 'podeEscalar'):
    # Usuário pode escalar
    pass

# Obter todas as permissões (para API)
permissions = get_user_permissions(user_id)
```

### Frontend

```javascript
// Aguardar carregamento das permissões
document.addEventListener('permissionsLoaded', () => {
    // Verificar permissão
    if (planPermissions.hasPermission('podeEscalar')) {
        // Habilitar funcionalidade
    } else {
        // Bloquear e mostrar mensagem
        planPermissions.disableButton(btn, 'Mensagem', 'Avançado');
    }
    
    // Limitar lista de rankings (Free: apenas 2)
    if (!planPermissions.hasPermission('rankingCompleto')) {
        planPermissions.limitList(container, 2, true);
    }
});
```

## 📊 API Endpoints

### GET `/api/user/permissions`

Retorna todas as permissões do usuário logado:

```json
{
  "plan": "Free",
  "planKey": "free",
  "permissions": {
    "rankingCompleto": false,
    "pesosJogo": 2,
    "pesosSG": 2,
    "editarPesosModulos": false,
    "verEscalacaoIdealCompleta": false,
    "podeEscalar": false,
    "timesMaximos": 1,
    "estatisticasAvancadas": false,
    "fecharDefesa": false,
    "hackGoleiro": false,
    "multiEscalacao": false,
    "nivelRisco": 1
  }
}
```

## 🎨 Próximos Passos (Frontend)

Aplicar bloqueios visuais nas páginas:

1. **Páginas de Módulos** - Limitar rankings e bloquear edição de pesos
2. **Página de Escalação** - Bloquear botão de escalar e aplicar blur
3. **Seleção de Perfis** - Bloquear perfis não permitidos
4. **Multi-times** - Verificar limite de times ao criar

## 📝 Notas Importantes

- ✅ Sistema simplificado: plano armazenado diretamente na tabela `acw_users`
- ✅ Sem dependências do Stripe (será integrado depois)
- ✅ Todos os usuários novos recebem plano 'free' por padrão
- ✅ Sistema de histórico opcional para auditoria
- ✅ Validação de planos via constraint no banco

## 🔍 Verificação

Para verificar a estrutura do banco:

```bash
python verificar_banco.py
```

