# Descobertas sobre Refresh Token do Cartola

## O que foi descoberto

### 1. Armazenamento dos Tokens

Os tokens são armazenados no **localStorage** do navegador com a chave:
```
globoid-tokens-cartola-web@apps.globoid
```

### 2. Estrutura dos Tokens

O objeto armazenado contém:
- `access_token`: Token de acesso (expira em ~1 hora)
- `refresh_token`: Token de refresh (expira em ~1 ano - 180 dias)
- `id_token`: Token de identificação (expira em ~1 hora)

### 3. Informações Importantes nos Tokens

#### Access Token (JWT decodificado):
- `exp`: Expiração (timestamp)
- `iat`: Emitido em (timestamp)
- `session_state` (sid): ID da sessão - **IMPORTANTE**
- `nonce`: Valor único usado na autenticação
- `federated_sid`: ID de sessão federada

#### Refresh Token (JWT decodificado):
- `exp`: Expiração (timestamp) - **~1 ano de validade**
- `iat`: Emitido em (timestamp)
- `session_state` (sid): ID da sessão - **CRÍTICO para refresh**
- `nonce`: Valor único usado na autenticação
- `type`: "Refresh"

#### ID Token (JWT decodificado):
- `exp`: Expiração (timestamp) - **~1 hora de validade**
- `iat`: Emitido em (timestamp)
- `session_state` (sid): ID da sessão
- `nonce`: Valor único usado na autenticação

### 4. Requisição de Refresh Token

**Endpoint:**
```
POST https://web-api.globoid.globo.com/v1/refresh-token
```

**Headers necessários:**
```
Content-Type: application/json
Accept: */*
Accept-Encoding: gzip, deflate, br, zstd
Accept-Language: pt-BR,pt;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6
Origin: https://cartola.globo.com
Referer: https://cartola.globo.com/
User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36 Edg/138.0.0.0
```

**Payload necessário:**
```json
{
  "client_id": "cartola-web@apps.globoid",
  "refresh_token": "<refresh_token_atual>",
  "access_token": "<access_token_atual>",
  "id_token": "<id_token_atual>"
}
```

**Resposta de sucesso (200):**
```json
{
  "access_token": "<novo_access_token>",
  "refresh_token": "<novo_refresh_token>",
  "id_token": "<novo_id_token>"
}
```

### 5. Problema Identificado

O erro "session_terminated" ocorre quando:
- O `session_state` (sid) no refresh_token não corresponde mais a uma sessão ativa no servidor
- Isso pode acontecer se:
  - O usuário fez logout
  - A sessão expirou no servidor (mesmo com refresh_token válido)
  - O refresh_token foi invalidado por segurança

### 6. O que precisa ser salvo no banco de dados

Para que o refresh_token funcione corretamente, você precisa salvar:

1. **access_token** - Token de acesso atual
2. **refresh_token** - Token de refresh (válido por ~1 ano)
3. **id_token** - Token de identificação atual
4. **session_state (sid)** - ID da sessão (presente nos 3 tokens, mas deve ser o mesmo)

**IMPORTANTE:** 
- Todos os 3 tokens devem ter o mesmo `session_state` (sid)
- Quando você faz refresh, TODOS os 3 tokens são renovados
- O novo `session_state` pode mudar após o refresh
- Você DEVE atualizar os 3 tokens no banco após cada refresh bem-sucedido

### 7. Fluxo de Refresh

1. Verificar se `access_token` está expirado
2. Se expirado, fazer POST para `/v1/refresh-token` com os 3 tokens atuais
3. Se sucesso, receber 3 novos tokens
4. **ATUALIZAR OS 3 TOKENS NO BANCO** (não apenas o access_token)
5. Usar o novo access_token para requisições

### 8. Por que o Aero-RBSV falhou?

O time Aero-RBSV nunca teve seus tokens atualizados após a criação. O `id_token` expirou (tem validade de 1 hora), e quando tentamos fazer refresh, o servidor retornou "session_terminated" porque a sessão não está mais ativa.

**Solução:** Fazer um novo login para obter novos tokens com uma sessão ativa.

### 9. Recomendações

1. **Sempre atualizar os 3 tokens** após um refresh bem-sucedido
2. **Verificar a expiração do id_token** antes de tentar refresh (se expirou há muito tempo, pode indicar sessão encerrada)
3. **Implementar um mecanismo de "atualizar token"** que:
   - Verifica se os tokens estão válidos
   - Tenta fazer refresh
   - Se falhar com "session_terminated", informa que precisa de novo login
4. **Monitorar o `session_state`** - se mudar, significa que houve um novo login/refresh

### 10. Validações Importantes

- Verificar se os 3 tokens têm o mesmo `session_state` (sid)
- Verificar se o `refresh_token` não expirou (tem validade de ~1 ano)
- Verificar se o `id_token` não expirou há muito tempo (indica sessão encerrada)
- Sempre usar os 3 tokens mais recentes na requisição de refresh

