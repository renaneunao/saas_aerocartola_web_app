# Configuração do Brevo para Envio de Emails

## ⚠️ IMPORTANTE: API Key vs Senha SMTP

**A senha SMTP NÃO é a mesma coisa que a API Key!**

- **Senha SMTP**: `rS0MHk1zptXEOVvC` (usada apenas para conexão SMTP)
- **API Key**: Começa com `xkeysib-` e deve ser gerada no painel do Brevo

## Como Obter a API Key

1. Acesse: https://app.brevo.com/settings/keys/api
2. Clique em "Generate a new API key"
3. Escolha "v3" e dê um nome (ex: "Cartola Manager")
4. Copie a chave gerada (ela começa com `xkeysib-`)
5. **IMPORTANTE**: Você só verá a chave uma vez! Salve-a imediatamente.

## Variáveis de Ambiente Necessárias

Adicione as seguintes variáveis ao seu arquivo `.env`:

```env
# ========================================
# CONFIGURAÇÕES DO BREVO (EMAIL)
# ========================================
# API Key do Brevo v3 (gerada no painel, começa com "xkeysib-")
# NÃO use a senha SMTP aqui!
BREVO_API_KEY=xkeysib-sua-api-key-aqui

# Email do remetente - deve ser um email VERIFICADO no Brevo
# IMPORTANTE: O login SMTP (9bd33c001@smtp-brevo.com) é usado apenas para autenticação
# O sender email deve ser um email verificado no painel do Brevo
# Exemplo: renan_vianna7@icloud.com (verificado no Brevo)
BREVO_SENDER_EMAIL=renan_vianna7@icloud.com
BREVO_SENDER_NAME=Aero Cartola

# Configurações SMTP (para referência, mas estamos usando API REST)
BREVO_SMTP_SERVER=smtp-relay.brevo.com
BREVO_SMTP_PORT=587
BREVO_SMTP_LOGIN=9bd33c001@smtp-brevo.com
BREVO_SMTP_PASSWORD=rS0MHk1zptXEOVvC

# URL base da aplicação (para links de verificação de email)
BASE_URL=http://localhost:5000
```

## Observações Importantes

1. **Email do Remetente**: O `BREVO_SENDER_EMAIL` deve ser um email **VERIFICADO** no painel do Brevo. O `BREVO_SMTP_LOGIN` (9bd33c001@smtp-brevo.com) é usado apenas para autenticação SMTP, mas o sender email deve ser um email verificado (ex: renan_vianna7@icloud.com). Verifique no painel do Brevo quais emails estão verificados.

2. **API Key**: Deve ser gerada no painel do Brevo e começa com `xkeysib-`. A senha SMTP (`rS0MHk1zptXEOVvC`) NÃO funciona como API Key.

3. **BASE_URL**: Configure com a URL da sua aplicação em produção (ex: `https://seu-dominio.com`).

## Documentação

- [Brevo Python SDK](https://github.com/getbrevo/brevo-python)
- [Brevo API Documentation](https://developers.brevo.com/docs/send-a-transactional-email)

