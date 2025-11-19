"""
Script de teste para enviar email via Brevo
"""
import os
import sys
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

# Importar a função de envio de email
from utils.email_service import send_verification_email

def test_send_email():
    """Testa o envio de email"""
    print("=" * 60)
    print("TESTE DE ENVIO DE EMAIL - BREVO")
    print("=" * 60)
    print()
    
    # Verificar variáveis de ambiente
    api_key = os.getenv('BREVO_API_KEY', '')
    sender_email = os.getenv('BREVO_SENDER_EMAIL', '9bd33c001@smtp-brevo.com')
    
    print(f"[INFO] BREVO_API_KEY: {'✅ Presente' if api_key else '❌ Não encontrada'}")
    if api_key:
        print(f"       Valor completo: {repr(api_key)}")
        print(f"       Tamanho: {len(api_key)} caracteres")
        print(f"       Tem espaços? {bool(' ' in api_key)}")
        # Remover espaços se houver
        api_key_clean = api_key.strip()
        if api_key_clean != api_key:
            print(f"       ⚠️  Removendo espaços: {repr(api_key_clean)}")
            api_key = api_key_clean
    print(f"[INFO] BREVO_SENDER_EMAIL: {sender_email}")
    print()
    
    # Email de teste
    test_email = "renan_vianna7@icloud.com"
    test_username = "Renan (Teste)"
    test_token = "test-token-12345"
    
    print(f"[INFO] Enviando email de teste para: {test_email}")
    print()
    
    # Tentar enviar email
    try:
        result = send_verification_email(
            email=test_email,
            username=test_username,
            verification_token=test_token
        )
        
        print()
        print("=" * 60)
        if result['success']:
            print("✅ SUCESSO! Email enviado com sucesso!")
            print(f"   Mensagem: {result.get('message', 'N/A')}")
        else:
            print("❌ ERRO ao enviar email!")
            print(f"   Erro: {result.get('error', 'Erro desconhecido')}")
        print("=" * 60)
        
        return result['success']
        
    except Exception as e:
        print()
        print("=" * 60)
        print(f"❌ EXCEÇÃO ao tentar enviar email: {str(e)}")
        import traceback
        print(traceback.format_exc())
        print("=" * 60)
        return False

if __name__ == "__main__":
    success = test_send_email()
    sys.exit(0 if success else 1)

