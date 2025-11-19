"""
Script de teste para enviar email usando o SDK oficial do Brevo
"""
import os
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

try:
    import sib_api_v3_sdk
    from sib_api_v3_sdk.rest import ApiException
    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False
    print("❌ SDK não instalado. Execute: pip install sib-api-v3-sdk")

def test_send_email_sdk():
    """Testa o envio de email usando o SDK oficial"""
    if not SDK_AVAILABLE:
        return False
        
    print("=" * 60)
    print("TESTE DE ENVIO DE EMAIL - BREVO SDK OFICIAL")
    print("=" * 60)
    print()
    
    # Configurações
    api_key = os.getenv('BREVO_API_KEY', 'rS0MHk1zptXEOVvC')
    sender_email = os.getenv('BREVO_SENDER_EMAIL', '9bd33c001@smtp-brevo.com')
    sender_name = os.getenv('BREVO_SENDER_NAME', 'Aero Cartola')
    
    print(f"[INFO] API Key: {'✅ Presente' if api_key else '❌ Não encontrada'}")
    if api_key:
        print(f"       Valor: {api_key[:10]}...")
    print(f"[INFO] Sender Email: {sender_email}")
    print()
    
    # Configurar SDK
    configuration = sib_api_v3_sdk.Configuration()
    configuration.api_key['api-key'] = api_key
    
    # Criar instância da API
    api_instance = sib_api_v3_sdk.TransactionalEmailsApi(sib_api_v3_sdk.ApiClient(configuration))
    
    # Email de teste
    to_email = "renan_vianna7@icloud.com"
    subject = "Teste de Email - Aero Cartola (SDK)"
    
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
            }
            .container {
                background: linear-gradient(135deg, #0c4a6e 0%, #075985 100%);
                border-radius: 10px;
                padding: 30px;
                color: white;
            }
            .content {
                background: white;
                color: #333;
                padding: 30px;
                border-radius: 8px;
                margin: 20px 0;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="content">
                <h2>✅ Teste de Email com SDK Oficial!</h2>
                <p>Olá, Renan!</p>
                <p>Este é um email de teste enviado usando o SDK oficial do Brevo.</p>
                <p>Se você recebeu este email, significa que o SDK está funcionando corretamente!</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    text_content = """
    Teste de Email com SDK Oficial!
    
    Olá, Renan!
    
    Este é um email de teste enviado usando o SDK oficial do Brevo.
    Se você recebeu este email, significa que o SDK está funcionando corretamente!
    """
    
    # Preparar email
    send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
        to=[{"email": to_email, "name": "Renan"}],
        sender={"name": sender_name, "email": sender_email},
        subject=subject,
        html_content=html_content,
        text_content=text_content
    )
    
    try:
        print(f"[INFO] Enviando email para {to_email}...")
        api_response = api_instance.send_transac_email(send_smtp_email)
        
        print()
        print("=" * 60)
        print("✅ SUCESSO! Email enviado usando SDK!")
        print(f"   Message ID: {api_response.message_id}")
        print("=" * 60)
        return True
        
    except ApiException as e:
        print()
        print("=" * 60)
        print(f"❌ ERRO ao enviar email via SDK:")
        print(f"   Status: {e.status}")
        print(f"   Reason: {e.reason}")
        print(f"   Body: {e.body}")
        print("=" * 60)
        return False
    except Exception as e:
        print()
        print("=" * 60)
        print(f"❌ ERRO: {str(e)}")
        import traceback
        print(traceback.format_exc())
        print("=" * 60)
        return False

if __name__ == "__main__":
    success = test_send_email_sdk()
    exit(0 if success else 1)

