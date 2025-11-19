# Análise Completa: Como Manter Sessão Ativa e Refresh Token

## Resposta Direta à Pergunta

**Não há nada adicional que você possa salvar para manter a sessão ativa indefinidamente ou reativá-la quando encerrada.**

A sessão é gerenciada pelo servidor Keycloak/Globo, e quando ela é encerrada no servidor, não há como reativá-la apenas com tokens ou cookies salvos.

## Por que a Sessão é Encerrada?

A sessão pode ser encerrada no servidor por várias razões:
1. **Timeout de inatividade** - Se não houver atividade por um período
2. **Logout manual** - Se o usuário fizer logout em outro dispositivo
3. **Política de segurança** - Por segurança, o servidor pode encerrar sessões antigas
4. **Mudança de senha** - Se a senha for alterada
5. **Limpeza automática** - O servidor pode limpar sessões antigas periodicamente

## O que Você Pode Salvar

### 1. Tokens (OBRIGATÓRIO)
- `access_token` - Token de acesso (expira em ~1 hora)
- `refresh_token` - Token de refresh (expira em ~1 ano)
- `id_token` - Token de identificação (expira em ~1 hora)

**IMPORTANTE:** Todos os 3 tokens devem ser salvos e atualizados juntos após cada refresh.

### 2. Session State (sid) - Presente nos Tokens
O `session_state` (sid) está presente nos 3 tokens e deve ser o mesmo em todos. Este é o ID da sessão no servidor.

### 3. Cookies (NÃO são necessários para refresh)
Os cookies encontrados são:
- `hsid` - Session ID do Horizon (não relacionado à autenticação)
- `GLBID` - Globo ID (identificação do usuário)
- `GLOBO_ID` - JWT com informações do usuário
- `RESTART_URL` - URL de restart (não necessário para refresh)

**IMPORTANTE:** Os cookies NÃO são necessários para fazer refresh do token. O refresh funciona apenas com os 3 tokens.

### 4. Keycloak Callbacks (NÃO são necessários)
Os callbacks do Keycloak armazenados no localStorage (`kc-callback-*`) contêm:
- `state` - Estado da requisição OAuth
- `nonce` - Valor único da requisição
- `pkceCodeVerifier` - Verificador PKCE
- `expires` - Data de expiração

**IMPORTANTE:** Esses callbacks são usados apenas durante o fluxo de login inicial e não são necessários para refresh.

## Como Funciona o Refresh Token

### Requisição de Refresh
```
POST https://web-api.globoid.globo.com/v1/refresh-token
```

**Payload:**
```json
{
  "client_id": "cartola-web@apps.globoid",
  "refresh_token": "<refresh_token_atual>",
  "access_token": "<access_token_atual>",
  "id_token": "<id_token_atual>"
}
```

**Resposta de Sucesso:**
```json
{
  "access_token": "<novo_access_token>",
  "refresh_token": "<novo_refresh_token>",
  "id_token": "<novo_id_token>"
}
```

**IMPORTANTE:** Todos os 3 tokens são renovados juntos. Você DEVE atualizar os 3 no banco.

## Estratégia para Manter Tokens Válidos

### 1. Refresh Proativo
Fazer refresh dos tokens **antes** que o `access_token` expire:
- Verificar expiração do `access_token` periodicamente
- Fazer refresh quando faltar ~10 minutos para expirar
- Isso mantém a sessão ativa no servidor

### 2. Refresh Reativo
Quando uma requisição retornar 401 (Unauthorized):
- Tentar fazer refresh automaticamente
- Se sucesso, repetir a requisição original
- Se falhar, informar que precisa de novo login

### 3. Verificação de Sessão
Antes de tentar refresh, verificar:
- Se o `refresh_token` não expirou (tem validade de ~1 ano)
- Se o `id_token` não expirou há muito tempo (indica sessão encerrada)
- Se os 3 tokens têm o mesmo `session_state` (sid)

## Por que o Aero-RBSV Falhou?

1. O time foi criado em 2025-11-18
2. Os tokens nunca foram atualizados após a criação
3. O `id_token` expirou (tem validade de 1 hora)
4. Quando tentamos fazer refresh, o servidor retornou "session_terminated" porque:
   - A sessão foi encerrada no servidor (timeout ou limpeza)
   - O `session_state` (sid) nos tokens não corresponde mais a uma sessão ativa

## Solução: Botão "Atualizar Token"

Implementar um botão que:

1. **Verifica o estado atual:**
   - Verifica se o `access_token` está expirado
   - Verifica se o `refresh_token` está válido
   - Verifica se o `id_token` está válido

2. **Tenta fazer refresh:**
   - Se todos os tokens estão válidos, tenta refresh
   - Se sucesso, atualiza os 3 tokens no banco
   - Se falhar com "session_terminated", informa que precisa de novo login

3. **Feedback ao usuário:**
   - Se sucesso: "Tokens atualizados com sucesso!"
   - Se falhar: "Sessão expirada. Por favor, faça login novamente."

## Conclusão

**Não há como evitar que a sessão seja encerrada no servidor.** O que você pode fazer é:

1. ✅ Fazer refresh regularmente (antes que os tokens expirem)
2. ✅ Sempre atualizar os 3 tokens juntos após refresh
3. ✅ Implementar um botão "Atualizar Token" que tenta refresh
4. ✅ Se o refresh falhar, informar que precisa de novo login

**A sessão é gerenciada pelo servidor, e quando ela é encerrada, é necessário fazer um novo login para obter novos tokens com uma sessão ativa.**

