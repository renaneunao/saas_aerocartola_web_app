"""
Serviço de envio de emails usando Brevo (Sendinblue) via SMTP
Documentação: https://developers.brevo.com/docs/smtp-integration
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr
import os
from typing import Optional, Dict, Any

# Configurações do Brevo SMTP
BREVO_SMTP_SERVER = os.getenv('BREVO_SMTP_SERVER', 'smtp-relay.brevo.com')
BREVO_SMTP_PORT = int(os.getenv('BREVO_SMTP_PORT', '587'))
BREVO_SMTP_LOGIN = os.getenv('BREVO_SMTP_LOGIN', '9bd33c001@smtp-brevo.com')
BREVO_SMTP_PASSWORD = os.getenv('BREVO_SMTP_PASSWORD', 'rS0MHk1zptXEOVvC')
# IMPORTANTE: O sender email deve ser um email VERIFICADO no Brevo
# O login SMTP (9bd33c001@smtp-brevo.com) é usado apenas para autenticação
# O sender email deve ser o email verificado (ex: renan_vianna7@icloud.com)
BREVO_SENDER_EMAIL = os.getenv('BREVO_SENDER_EMAIL', 'renan_vianna7@icloud.com')
BREVO_SENDER_NAME = os.getenv('BREVO_SENDER_NAME', 'Aero Cartola')


def _send_email_smtp(to_email: str, to_name: str, subject: str, html_content: str, text_content: str) -> Dict[str, Any]:
    """
    Função auxiliar para enviar email via SMTP
    
    Args:
        to_email: Email do destinatário
        to_name: Nome do destinatário
        subject: Assunto do email
        html_content: Conteúdo HTML do email
        text_content: Conteúdo texto do email
        
    Returns:
        Dict com 'success' (bool) e 'message' ou 'error'
    """
    try:
        # Criar mensagem
        msg = MIMEMultipart('alternative')
        msg['From'] = formataddr((BREVO_SENDER_NAME, BREVO_SENDER_EMAIL))
        msg['To'] = to_email
        msg['Subject'] = subject
        msg['Reply-To'] = BREVO_SENDER_EMAIL
        
        # Adicionar versões texto e HTML
        part1 = MIMEText(text_content, 'plain', 'utf-8')
        part2 = MIMEText(html_content, 'html', 'utf-8')
        
        msg.attach(part1)
        msg.attach(part2)
        
        # Conectar e enviar
        server = smtplib.SMTP(BREVO_SMTP_SERVER, BREVO_SMTP_PORT, timeout=30)
        server.starttls()
        server.login(BREVO_SMTP_LOGIN, BREVO_SMTP_PASSWORD)
        result = server.sendmail(BREVO_SENDER_EMAIL, [to_email], msg.as_string())
        server.quit()
        
        # Verificar se houve algum erro
        if result:
            # Se result não estiver vazio, significa que alguns emails falharam
            failed_recipients = list(result.keys())
            return {
                'success': False,
                'error': f'Falha ao enviar para: {", ".join(failed_recipients)}'
            }
        
        return {
            'success': True,
            'message': 'Email enviado com sucesso!'
        }
        
    except smtplib.SMTPAuthenticationError as e:
        return {
            'success': False,
            'error': f'Erro de autenticação SMTP: {str(e)}'
        }
    except Exception as e:
        return {
            'success': False,
            'error': f'Erro ao enviar email: {str(e)}'
        }


def send_verification_email(email: str, username: str, verification_token: str) -> Dict[str, Any]:
    """
    Envia email de verificação para o usuário via SMTP
    
    Args:
        email: Email do destinatário
        username: Nome de usuário
        verification_token: Token de verificação
        
    Returns:
        Dict com 'success' (bool) e 'message' ou 'error'
    """
    try:
        # URL de verificação
        base_url = os.getenv('BASE_URL', 'http://localhost:5000')
        verification_url = f"{base_url}/verify-email?token={verification_token}"
        
        # Conteúdo HTML do email - cores ajustadas para melhor legibilidade
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    color: #1a1a1a;
                    background-color: #f5f5f5;
                    margin: 0;
                    padding: 20px;
                }}
                .email-wrapper {{
                    max-width: 600px;
                    margin: 0 auto;
                    background-color: #ffffff;
                }}
                .header {{
                    background: linear-gradient(135deg, #0c4a6e 0%, #075985 100%);
                    padding: 30px 20px;
                    text-align: center;
                    border-radius: 10px 10px 0 0;
                }}
                .header h1 {{
                    margin: 0;
                    font-size: 28px;
                    color: #ffffff;
                    font-weight: bold;
                }}
                .content {{
                    background: #ffffff;
                    color: #1a1a1a;
                    padding: 40px 30px;
                    border-radius: 0 0 10px 10px;
                }}
                .content h2 {{
                    color: #0c4a6e;
                    margin-top: 0;
                    font-size: 24px;
                }}
                .content p {{
                    color: #333333;
                    font-size: 16px;
                    margin: 15px 0;
                }}
                .button-container {{
                    text-align: center;
                    margin: 30px 0;
                }}
                .button {{
                    display: inline-block;
                    background: linear-gradient(135deg, #0ea5e9 0%, #0284c7 100%);
                    color: #ffffff !important;
                    padding: 15px 40px;
                    text-decoration: none;
                    border-radius: 5px;
                    font-weight: bold;
                    font-size: 16px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.2);
                }}
                .button:hover {{
                    background: linear-gradient(135deg, #0284c7 0%, #0369a1 100%);
                }}
                .link-box {{
                    background-color: #f0f9ff;
                    border-left: 4px solid #0ea5e9;
                    padding: 15px;
                    margin: 20px 0;
                    border-radius: 4px;
                    word-break: break-all;
                }}
                .link-box code {{
                    color: #0369a1;
                    font-size: 14px;
                    font-family: 'Courier New', monospace;
                }}
                .footer {{
                    background-color: #f9fafb;
                    padding: 20px;
                    text-align: center;
                    font-size: 12px;
                    color: #666666;
                    border-top: 1px solid #e5e7eb;
                    border-radius: 0 0 10px 10px;
                }}
                .warning {{
                    background-color: #fef3c7;
                    border-left: 4px solid #f59e0b;
                    padding: 15px;
                    margin: 20px 0;
                    border-radius: 4px;
                    font-size: 14px;
                    color: #92400e;
                }}
            </style>
        </head>
        <body>
            <div class="email-wrapper">
                <div class="header">
                    <h1>⚽ Aero Cartola</h1>
                </div>
                <div class="content">
                    <h2>Olá, {username}!</h2>
                    <p>Obrigado por se cadastrar no <strong>Aero Cartola</strong>!</p>
                    <p>Para ativar sua conta, clique no botão abaixo para verificar seu email:</p>
                    <div class="button-container">
                        <a href="{verification_url}" class="button">Verificar Email</a>
                    </div>
                    <p style="text-align: center; color: #666; font-size: 14px;">Ou copie e cole o link abaixo no seu navegador:</p>
                    <div class="link-box">
                        <code>{verification_url}</code>
                    </div>
                    <div class="warning">
                        <strong>⚠️ Importante:</strong> Se você não criou esta conta, pode ignorar este email com segurança.
                    </div>
                </div>
                <div class="footer">
                    <p>Este é um email automático, por favor não responda.</p>
                    <p>&copy; 2024 Aero Cartola. Todos os direitos reservados.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Conteúdo texto simples (fallback)
        text_content = f"""
        Olá, {username}!
        
        Obrigado por se cadastrar no Aero Cartola!
        
        Para ativar sua conta, acesse o link abaixo:
        {verification_url}
        
        Se você não criou esta conta, pode ignorar este email.
        
        Atenciosamente,
        Equipe Aero Cartola
        """
        
        return _send_email_smtp(
            to_email=email,
            to_name=username,
            subject="Verifique seu email - Aero Cartola",
            html_content=html_content,
            text_content=text_content
        )
            
    except Exception as e:
        import traceback
        print(f"[ERROR] Exceção ao enviar email de verificação: {str(e)}")
        print(f"[ERROR] Traceback: {traceback.format_exc()}")
        return {
            'success': False,
            'error': f'Erro ao enviar email: {str(e)}'
        }


def send_welcome_email(email: str, username: str) -> Dict[str, Any]:
    """
    Envia email de boas-vindas após verificação
    
    Args:
        email: Email do destinatário
        username: Nome de usuário
        
    Returns:
        Dict com 'success' (bool) e 'message' ou 'error'
    """
    try:
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    color: #1a1a1a;
                    background-color: #f5f5f5;
                    margin: 0;
                    padding: 20px;
                }}
                .email-wrapper {{
                    max-width: 600px;
                    margin: 0 auto;
                    background-color: #ffffff;
                }}
                .header {{
                    background: linear-gradient(135deg, #0c4a6e 0%, #075985 100%);
                    padding: 30px 20px;
                    text-align: center;
                    border-radius: 10px 10px 0 0;
                }}
                .header h1 {{
                    margin: 0;
                    font-size: 28px;
                    color: #ffffff;
                    font-weight: bold;
                }}
                .content {{
                    background: #ffffff;
                    color: #1a1a1a;
                    padding: 40px 30px;
                    border-radius: 0 0 10px 10px;
                }}
                .content h2 {{
                    color: #0c4a6e;
                    margin-top: 0;
                    font-size: 24px;
                }}
                .content p {{
                    color: #333333;
                    font-size: 16px;
                    margin: 15px 0;
                }}
                .features {{
                    background-color: #f0f9ff;
                    padding: 20px;
                    border-radius: 8px;
                    margin: 20px 0;
                }}
                .features ul {{
                    margin: 10px 0;
                    padding-left: 20px;
                }}
                .features li {{
                    color: #1a1a1a;
                    margin: 10px 0;
                    font-size: 16px;
                }}
                .footer {{
                    background-color: #f9fafb;
                    padding: 20px;
                    text-align: center;
                    font-size: 12px;
                    color: #666666;
                    border-top: 1px solid #e5e7eb;
                    border-radius: 0 0 10px 10px;
                }}
            </style>
        </head>
        <body>
            <div class="email-wrapper">
                <div class="header">
                    <h1>⚽ Aero Cartola</h1>
                </div>
                <div class="content">
                    <h2>Bem-vindo ao Aero Cartola, {username}!</h2>
                    <p><strong>Sua conta foi verificada com sucesso! 🎉</strong></p>
                    <p>Agora você pode aproveitar todos os recursos da plataforma:</p>
                    <div class="features">
                        <ul>
                            <li>📊 Rankings completos de jogadores</li>
                            <li>⚽ Escalação ideal automatizada</li>
                            <li>📈 Estatísticas avançadas</li>
                            <li>🎯 Múltiplos times (planos Avançado e Pro)</li>
                        </ul>
                    </div>
                    <p><strong>Acesse sua conta e comece a usar agora mesmo!</strong></p>
                </div>
                <div class="footer">
                    <p>Este é um email automático, por favor não responda.</p>
                    <p>&copy; 2024 Aero Cartola. Todos os direitos reservados.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        text_content = f"""
        Bem-vindo ao Aero Cartola, {username}!
        
        Sua conta foi verificada com sucesso!
        
        Agora você pode aproveitar todos os recursos da plataforma:
        - Rankings completos de jogadores
        - Escalação ideal automatizada
        - Estatísticas avançadas
        - Múltiplos times (planos Avançado e Pro)
        
        Acesse sua conta e comece a usar agora mesmo!
        """
        
        return _send_email_smtp(
            to_email=email,
            to_name=username,
            subject="Bem-vindo ao Aero Cartola!",
            html_content=html_content,
            text_content=text_content
        )
            
    except Exception as e:
        return {'success': False, 'error': str(e)}
