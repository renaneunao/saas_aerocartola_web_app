"""
Script de teste para enviar email usando o sender verificado
"""
import os
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

from utils.email_service import send_verification_email

def test_send_email_verified_sender():
    """Testa o envio de email com sender verificado"""
    print("=" * 60)
    print("TESTE DE ENVIO COM SENDER VERIFICADO")
    print("=" * 60)
    print()
    
    # Verificar configurações
    sender_email = os.getenv('BREVO_SENDER_EMAIL', 'renan_vianna7@icloud.com')
    smtp_login = os.getenv('BREVO_SMTP_LOGIN', '9bd33c001@smtp-brevo.com')
    
    print(f"[INFO] SMTP Login (autenticação): {smtp_login}")
    print(f"[INFO] Sender Email (remetente verificado): {sender_email}")
    print()
    
    # Email de teste
    to_email = "renan_vianna7@icloud.com"
    test_username = "Renan"
    test_token = "test-token-verified-sender"
    
    print(f"[INFO] Enviando email de teste para: {to_email}")
    print()
    
    try:
        result = send_verification_email(
            email=to_email,
            username=test_username,
            verification_token=test_token
        )
        
        print()
        print("=" * 60)
        if result['success']:
            print("✅ SUCESSO! Email enviado com sender verificado!")
            print(f"   Mensagem: {result.get('message', 'N/A')}")
        else:
            print("❌ ERRO ao enviar email!")
            print(f"   Erro: {result.get('error', 'Erro desconhecido')}")
        print("=" * 60)
        
        return result['success']
        
    except Exception as e:
        print()
        print("=" * 60)
        print(f"❌ EXCEÇÃO: {str(e)}")
        import traceback
        print(traceback.format_exc())
        print("=" * 60)
        return False

if __name__ == "__main__":
    success = test_send_email_verified_sender()
    exit(0 if success else 1)

