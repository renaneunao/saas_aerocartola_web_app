"""
Script de teste detalhado para enviar email via SMTP do Brevo
Com logs detalhados e verificação de entrega
"""
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

def test_send_email_smtp_detailed():
    """Testa o envio de email via SMTP com logs detalhados"""
    print("=" * 60)
    print("TESTE DETALHADO DE ENVIO DE EMAIL - BREVO SMTP")
    print("=" * 60)
    print()
    
    # Configurações SMTP
    smtp_server = os.getenv('BREVO_SMTP_SERVER', 'smtp-relay.brevo.com')
    smtp_port = int(os.getenv('BREVO_SMTP_PORT', '587'))
    smtp_login = os.getenv('BREVO_SMTP_LOGIN', '9bd33c001@smtp-brevo.com')
    smtp_password = os.getenv('BREVO_SMTP_PASSWORD', 'rS0MHk1zptXEOVvC')
    sender_email = os.getenv('BREVO_SENDER_EMAIL', '9bd33c001@smtp-brevo.com')
    sender_name = os.getenv('BREVO_SENDER_NAME', 'Cartola Manager')
    
    print(f"[INFO] SMTP Server: {smtp_server}")
    print(f"[INFO] SMTP Port: {smtp_port}")
    print(f"[INFO] SMTP Login: {smtp_login}")
    print(f"[INFO] SMTP Password: {'✅ Presente' if smtp_password else '❌ Não encontrada'}")
    print(f"[INFO] Sender Email: {sender_email}")
    print()
    
    # Email de teste
    to_email = "renan_vianna7@icloud.com"
    subject = "Teste Detalhado - Cartola Manager"
    
    # Criar mensagem HTML
    html_body = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Teste de Email</title>
    </head>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background: linear-gradient(135deg, #0c4a6e 0%, #075985 100%); border-radius: 10px; padding: 30px; color: white;">
            <div style="background: white; color: #333; padding: 30px; border-radius: 8px; margin: 20px 0;">
                <h2 style="color: #0c4a6e;">✅ Teste de Email Detalhado!</h2>
                <p>Olá, Renan!</p>
                <p>Este é um email de teste enviado via SMTP do Brevo com logs detalhados.</p>
                <p><strong>Se você recebeu este email, significa que o sistema está funcionando!</strong></p>
                <p>Verifique também a caixa de spam caso não tenha recebido.</p>
                <hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">
                <p style="font-size: 12px; color: #666;">
                    Enviado de: {sender_email}<br>
                    Para: {to_email}<br>
                    Servidor: {smtp_server}:{smtp_port}
                </p>
            </div>
        </div>
    </body>
    </html>
    """.format(sender_email=sender_email, to_email=to_email, smtp_server=smtp_server, smtp_port=smtp_port)
    
    text_body = f"""
    Teste de Email Detalhado!
    
    Olá, Renan!
    
    Este é um email de teste enviado via SMTP do Brevo com logs detalhados.
    Se você recebeu este email, significa que o sistema está funcionando!
    
    Verifique também a caixa de spam caso não tenha recebido.
    
    Enviado de: {sender_email}
    Para: {to_email}
    Servidor: {smtp_server}:{smtp_port}
    """
    
    try:
        print(f"[INFO] Criando mensagem...")
        msg = MIMEMultipart('alternative')
        msg['From'] = formataddr((sender_name, sender_email))
        msg['To'] = to_email
        msg['Subject'] = subject
        msg['Reply-To'] = sender_email
        
        # Adicionar versões texto e HTML
        part1 = MIMEText(text_body, 'plain', 'utf-8')
        part2 = MIMEText(html_body, 'html', 'utf-8')
        
        msg.attach(part1)
        msg.attach(part2)
        
        print(f"[INFO] Conectando ao servidor SMTP {smtp_server}:{smtp_port}...")
        server = smtplib.SMTP(smtp_server, smtp_port, timeout=30)
        server.set_debuglevel(2)  # Debug nível 2 para ver tudo
        
        print(f"[INFO] Iniciando TLS...")
        server.starttls()
        
        print(f"[INFO] Fazendo login com {smtp_login}...")
        server.login(smtp_login, smtp_password)
        print(f"[INFO] ✅ Login bem-sucedido!")
        
        print(f"[INFO] Enviando email de {sender_email} para {to_email}...")
        result = server.sendmail(sender_email, [to_email], msg.as_string())
        
        print(f"[INFO] Fechando conexão...")
        server.quit()
        
        if result:
            print(f"[WARNING] Alguns emails falharam: {result}")
        else:
            print(f"[INFO] ✅ Email aceito pelo servidor!")
        
        print()
        print("=" * 60)
        print("✅ SUCESSO! Email enviado via SMTP!")
        print(f"   De: {sender_email}")
        print(f"   Para: {to_email}")
        print(f"   Assunto: {subject}")
        print()
        print("⚠️  IMPORTANTE:")
        print("   1. Verifique sua caixa de entrada")
        print("   2. Verifique a pasta de SPAM/Lixo Eletrônico")
        print("   3. O email pode levar alguns minutos para chegar")
        print("   4. Se não receber, verifique se o email está correto")
        print("=" * 60)
        return True
        
    except smtplib.SMTPAuthenticationError as e:
        print()
        print("=" * 60)
        print(f"❌ ERRO de autenticação SMTP: {str(e)}")
        print("=" * 60)
        return False
    except smtplib.SMTPRecipientsRefused as e:
        print()
        print("=" * 60)
        print(f"❌ ERRO: Destinatário recusado: {str(e)}")
        print("   Verifique se o email está correto")
        print("=" * 60)
        return False
    except smtplib.SMTPSenderRefused as e:
        print()
        print("=" * 60)
        print(f"❌ ERRO: Remetente recusado: {str(e)}")
        print("   Verifique se o email do remetente está verificado no Brevo")
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
    success = test_send_email_smtp_detailed()
    exit(0 if success else 1)

