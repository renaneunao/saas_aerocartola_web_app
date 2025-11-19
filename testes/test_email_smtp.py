"""
Script de teste para enviar email via SMTP do Brevo
"""
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

def test_send_email_smtp():
    """Testa o envio de email via SMTP"""
    print("=" * 60)
    print("TESTE DE ENVIO DE EMAIL - BREVO SMTP")
    print("=" * 60)
    print()
    
    # Configurações SMTP
    smtp_server = os.getenv('BREVO_SMTP_SERVER', 'smtp-relay.brevo.com')
    smtp_port = int(os.getenv('BREVO_SMTP_PORT', '587'))
    smtp_login = os.getenv('BREVO_SMTP_LOGIN', '9bd33c001@smtp-brevo.com')
    smtp_password = os.getenv('BREVO_SMTP_PASSWORD', 'rS0MHk1zptXEOVvC')
    sender_email = os.getenv('BREVO_SENDER_EMAIL', '9bd33c001@smtp-brevo.com')
    sender_name = os.getenv('BREVO_SENDER_NAME', 'Aero Cartola')
    
    print(f"[INFO] SMTP Server: {smtp_server}")
    print(f"[INFO] SMTP Port: {smtp_port}")
    print(f"[INFO] SMTP Login: {smtp_login}")
    print(f"[INFO] SMTP Password: {'✅ Presente' if smtp_password else '❌ Não encontrada'}")
    print(f"[INFO] Sender Email: {sender_email}")
    print()
    
    # Email de teste
    to_email = "renan_vianna7@icloud.com"
    subject = "Teste de Email - Aero Cartola"
    
    # Criar mensagem HTML
    html_body = """
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
                <h2>✅ Teste de Email Funcionando!</h2>
                <p>Olá, Renan!</p>
                <p>Este é um email de teste enviado via SMTP do Brevo.</p>
                <p>Se você recebeu este email, significa que a configuração SMTP está funcionando corretamente!</p>
                <p>Agora podemos usar este método para enviar os emails de verificação.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    text_body = """
    Teste de Email Funcionando!
    
    Olá, Renan!
    
    Este é um email de teste enviado via SMTP do Brevo.
    Se você recebeu este email, significa que a configuração SMTP está funcionando corretamente!
    Agora podemos usar este método para enviar os emails de verificação.
    """
    
    try:
        print(f"[INFO] Criando mensagem...")
        msg = MIMEMultipart('alternative')
        msg['From'] = f"{sender_name} <{sender_email}>"
        msg['To'] = to_email
        msg['Subject'] = subject
        
        # Adicionar versões texto e HTML
        part1 = MIMEText(text_body, 'plain', 'utf-8')
        part2 = MIMEText(html_body, 'html', 'utf-8')
        
        msg.attach(part1)
        msg.attach(part2)
        
        print(f"[INFO] Conectando ao servidor SMTP...")
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.set_debuglevel(1)  # Ativar debug
        
        print(f"[INFO] Iniciando TLS...")
        server.starttls()
        
        print(f"[INFO] Fazendo login...")
        server.login(smtp_login, smtp_password)
        
        print(f"[INFO] Enviando email para {to_email}...")
        server.sendmail(sender_email, to_email, msg.as_string())
        
        print(f"[INFO] Fechando conexão...")
        server.quit()
        
        print()
        print("=" * 60)
        print("✅ SUCESSO! Email enviado via SMTP!")
        print("=" * 60)
        return True
        
    except smtplib.SMTPAuthenticationError as e:
        print()
        print("=" * 60)
        print(f"❌ ERRO de autenticação SMTP: {str(e)}")
        print("=" * 60)
        return False
    except Exception as e:
        print()
        print("=" * 60)
        print(f"❌ ERRO ao enviar email: {str(e)}")
        import traceback
        print(traceback.format_exc())
        print("=" * 60)
        return False

if __name__ == "__main__":
    success = test_send_email_smtp()
    exit(0 if success else 1)

