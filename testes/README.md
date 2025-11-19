# Diretório de Testes

Este diretório contém todos os scripts de teste da aplicação.

## Testes Disponíveis

### test_refresh_token.py
Script para testar a funcionalidade de refresh_token dos tokens de autenticação do Cartola.

**Uso:**
```bash
python testes/test_refresh_token.py
```

**Funcionalidades:**
- Verifica o time "Aero-RBSV" do usuário "renaneunao"
- Verifica se os tokens (access, refresh, id) são diferentes
- Verifica a expiração dos tokens
- Testa se o access_token atual está funcionando
- Tenta fazer refresh do token
- Testa se o novo token funciona após o refresh
- Mostra informações detalhadas sobre erros

### test_email*.py
Scripts de teste para funcionalidades de email (movidos da raiz do projeto).

