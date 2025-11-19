"""
Script de teste FINAL para enviar email usando o sender verificado
Força o uso do email verificado
"""
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

def test_send_email_final():
    """Testa o envio de email com sender verificado"""
    print("=" * 60)
    print("TESTE FINAL - SENDER VERIFICADO")
    print("=" * 60)
    print()
    
    # Configurações SMTP
    smtp_server = os.getenv('BREVO_SMTP_SERVER', 'smtp-relay.brevo.com')
    smtp_port = int(os.getenv('BREVO_SMTP_PORT', '587'))
    smtp_login = os.getenv('BREVO_SMTP_LOGIN', '9bd33c001@smtp-brevo.com')
    smtp_password = os.getenv('BREVO_SMTP_PASSWORD', 'rS0MHk1zptXEOVvC')
    
    # FORÇAR o uso do sender verificado
    sender_email = 'renan_vianna7@icloud.com'  # Email verificado no Brevo
    sender_name = 'Aero Cartola'
    
    print(f"[INFO] SMTP Login (autenticação): {smtp_login}")
    print(f"[INFO] Sender Email (remetente verificado): {sender_email}")
    print(f"[INFO] Sender Name: {sender_name}")
    print()
    
    # Email de teste
    to_email = "renan_vianna7@icloud.com"
    subject = "✅ Teste Final - Sender Verificado"
    
    html_body = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background: linear-gradient(135deg, #0c4a6e 0%, #075985 100%); border-radius: 10px; padding: 30px; color: white;">
            <div style="background: white; color: #333; padding: 30px; border-radius: 8px; margin: 20px 0;">
                <h2 style="color: #0c4a6e;">✅ Teste Final com Sender Verificado!</h2>
                <p>Olá, Renan!</p>
                <p><strong>Este email foi enviado usando o sender verificado: renan_vianna7@icloud.com</strong></p>
                <p>Se você recebeu este email, significa que o sistema está funcionando corretamente!</p>
                <p>Agora podemos usar este método para enviar os emails de verificação de conta.</p>
                <hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">
                <p style="font-size: 12px; color: #666;">
                    <strong>Configuração:</strong><br>
                    SMTP Login: 9bd33c001@smtp-brevo.com (autenticação)<br>
                    Sender Email: renan_vianna7@icloud.com (verificado no Brevo)<br>
                    Servidor: smtp-relay.brevo.com:587
                </p>
            </div>
        </div>
    </body>
    </html>
    """
    
    text_body = """
    Teste Final com Sender Verificado!
    
    Olá, Renan!
    
    Este email foi enviado usando o sender verificado: renan_vianna7@icloud.com
    
    Se você recebeu este email, significa que o sistema está funcionando corretamente!
    Agora podemos usar este método para enviar os emails de verificação de conta.
    
    Configuração:
    - SMTP Login: 9bd33c001@smtp-brevo.com (autenticação)
    - Sender Email: renan_vianna7@icloud.com (verificado no Brevo)
    - Servidor: smtp-relay.brevo.com:587
    """
    
    try:
        print(f"[INFO] Criando mensagem...")
        msg = MIMEMultipart('alternative')
        msg['From'] = formataddr((sender_name, sender_email))
        msg['To'] = to_email
        msg['Subject'] = subject
        msg['Reply-To'] = sender_email
        
        part1 = MIMEText(text_body, 'plain', 'utf-8')
        part2 = MIMEText(html_body, 'html', 'utf-8')
        
        msg.attach(part1)
        msg.attach(part2)
        
        print(f"[INFO] Conectando ao servidor SMTP...")
        server = smtplib.SMTP(smtp_server, smtp_port, timeout=30)
        server.set_debuglevel(1)
        
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
            return False
        
        print()
        print("=" * 60)
        print("✅ SUCESSO! Email enviado com sender verificado!")
        print(f"   De: {sender_email}")
        print(f"   Para: {to_email}")
        print()
        print("⚠️  Verifique:")
        print("   1. Sua caixa de entrada")
        print("   2. A pasta de SPAM")
        print("   3. Os logs do Brevo para confirmar entrega")
        print("=" * 60)
        return True
        
    except Exception as e:
        print()
        print("=" * 60)
        print(f"❌ ERRO: {str(e)}")
        import traceback
        print(traceback.format_exc())
        print("=" * 60)
        return False

if __name__ == "__main__":
    success = test_send_email_final()
    exit(0 if success else 1)

