from flask import Flask, jsonify, render_template, Response, request, redirect, url_for, flash, session
import traceback
import json
from datetime import datetime, timezone, timedelta
import os
from dotenv import load_dotenv

# Carregar variáveis de ambiente do .env
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'change-me-to-a-secure-random-value')

# Configuração do Redis para sessões
# Detectar se está rodando dentro do Docker ou fora (para testes)
# Dentro do Docker: usar 'redis_cache' (nome do serviço na rede Docker)
# Fora do Docker: usar o IP do VPS
import socket
try:
    # Tentar resolver o hostname 'redis_cache' - se funcionar, estamos no Docker
    socket.gethostbyname('redis_cache')
    REDIS_HOST = 'redis_cache'
except socket.gaierror:
    # Se não conseguir resolver, estamos fora do Docker, usar IP do VPS
    REDIS_HOST = os.getenv('REDIS_HOST', '194.163.142.108')

REDIS_PORT = int(os.getenv('REDIS_PORT', '6379'))
REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', '')
REDIS_DB = int(os.getenv('REDIS_DB', '0'))

# Criar conexão Redis para Flask-Session
import redis
redis_available = False
redis_client = None

try:
    redis_client = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        password=REDIS_PASSWORD if REDIS_PASSWORD else None,
        db=REDIS_DB,
        decode_responses=False,  # Flask-Session precisa de bytes
        socket_connect_timeout=3,
        socket_timeout=3
    )
    # Testar conexão
    redis_client.ping()
    redis_available = True
    print(f"✅ Redis conectado com sucesso em {REDIS_HOST}:{REDIS_PORT}")
except Exception as e:
    print(f"⚠️  Redis não disponível ({e}). Usando sessões em memória (não persistem após reiniciar).")
    redis_available = False

# Configurar Flask-Session
if redis_available and redis_client:
    # Usar Redis para sessões persistentes
    app.config['SESSION_TYPE'] = 'redis'
    app.config['SESSION_REDIS'] = redis_client
    app.config['SESSION_PERMANENT'] = True
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=1)  # Padrão: 1 dia (será ajustado no login se "Lembrar de mim")
    app.config['SESSION_USE_SIGNER'] = True
    app.config['SESSION_KEY_PREFIX'] = 'session:'
else:
    # Fallback: usar sessões em memória (não persistem)
    app.config['SESSION_TYPE'] = 'filesystem'
    app.config['SESSION_PERMANENT'] = True
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=1)
    app.config['SESSION_USE_SIGNER'] = True
    print("⚠️  Usando sessões em memória. As sessões serão perdidas ao reiniciar a aplicação.")

# Inicializar Flask-Session
from flask_session import Session
Session(app)

from database import get_db_connection, close_db_connection
from models.users import (
    authenticate_user,
    get_all_users,
    create_user,
    update_user_password,
    verify_email_token
)
from utils.email_service import send_verification_email, send_welcome_email
from models.teams import get_all_user_teams, create_team, get_team, update_team

# Registrar Blueprints
from routes.pagamento import pagamento_bp
app.register_blueprint(pagamento_bp)

# Timezone: Brasília (America/Sao_Paulo)
try:
    from zoneinfo import ZoneInfo
    TZ_BR = ZoneInfo("America/Sao_Paulo")
except Exception:
    TZ_BR = None
    try:
        import pytz
        TZ_BR = pytz.timezone("America/Sao_Paulo")
    except Exception:
        pytz = None

def now_brasilia():
    """Return current datetime in Brasília timezone if possible, else local naive now."""
    try:
        if TZ_BR is not None:
            return datetime.now(TZ_BR)
    except Exception:
        pass
    return datetime.now()

# ========================================
# SISTEMA DE AUTENTICAÇÃO
# ========================================

def login_required(f):
    """Decorator para proteger rotas que requerem autenticação"""
    from functools import wraps
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_user_authenticated():
            flash('Você precisa fazer login para acessar esta página.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Decorator para proteger rotas que requerem privilégios de admin"""
    from functools import wraps
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_user_authenticated():
            flash('Você precisa fazer login para acessar esta página.', 'error')
            return redirect(url_for('login'))
        
        user = get_current_user()
        if not user or not user.get('is_admin', False):
            flash('Você precisa ser administrador para acessar esta página.', 'error')
            return redirect(url_for('index'))
        
        return f(*args, **kwargs)
    return decorated_function

def team_required(f):
    """Decorator para proteger rotas que requerem que o usuário tenha pelo menos um time cadastrado"""
    from functools import wraps
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_user_authenticated():
            flash('Você precisa fazer login para acessar esta página.', 'warning')
            return redirect(url_for('login'))
        
        user = get_current_user()
        if not user:
            flash('Erro ao verificar usuário.', 'error')
            return redirect(url_for('login'))
        
        # Verificar se o usuário tem times cadastrados
        from models.teams import get_all_user_teams, create_teams_table
        conn = get_db_connection()
        try:
            create_teams_table(conn)
            teams = get_all_user_teams(conn, user['id'])
            if not teams or len(teams) == 0:
                flash('Você precisa adicionar um time antes de acessar esta página.', 'warning')
                return redirect(url_for('associar_credenciais'))
        finally:
            close_db_connection(conn)
        
        return f(*args, **kwargs)
    return decorated_function

def is_user_authenticated():
    """Verifica se o usuário está autenticado"""
    return session.get('user_id') is not None

def get_current_user():
    """Retorna os dados do usuário atual ou None"""
    user_id = session.get('user_id')
    if not user_id:
        return None
    
    conn = get_db_connection()
    if not conn:
        return None
    
    try:
        cursor = conn.cursor()
        # Verificar se a coluna plano existe
        cursor.execute('''
            SELECT EXISTS (
                SELECT FROM information_schema.columns 
                WHERE table_schema = 'public' 
                AND table_name = 'acw_users'
                AND column_name = 'plano'
            )
        ''')
        tem_coluna_plano = cursor.fetchone()[0]
        
        if tem_coluna_plano:
            cursor.execute('''
                SELECT id, username, email, full_name, is_active, is_admin, plano
                FROM acw_users
                WHERE id = %s AND is_active = TRUE
            ''', (user_id,))
        else:
            cursor.execute('''
                SELECT id, username, email, full_name, is_active, is_admin
                FROM acw_users
                WHERE id = %s AND is_active = TRUE
            ''', (user_id,))
        
        row = cursor.fetchone()
        if not row:
            return None
        
        user_data = {
            'id': row[0],
            'username': row[1],
            'email': row[2],
            'full_name': row[3],
            'is_active': row[4],
            'is_admin': row[5]
        }
        
        # Adicionar plano se a coluna existir
        if tem_coluna_plano and len(row) > 6:
            user_data['plano'] = row[6] or 'free'
        else:
            user_data['plano'] = 'free'
        
        return user_data
    except Exception as e:
        print(f"Erro ao buscar usuário: {e}")
        return None
    finally:
        close_db_connection(conn)

def logout_user():
    """Faz logout do usuário atual - limpa sessão do Redis"""
    # Limpar todos os dados da sessão
    session.clear()
    # Garantir que a sessão seja marcada como não permanente
    session.permanent = False

@app.context_processor
def inject_user():
    """Injeta variáveis globais em todos os templates"""
    user = get_current_user()
    
    # Verificar se o usuário tem times cadastrados
    has_teams = False
    if user:
        from models.teams import get_all_user_teams, create_teams_table
        conn = get_db_connection()
        if conn:
            try:
                create_teams_table(conn)
                teams = get_all_user_teams(conn, user['id'])
                has_teams = len(teams) > 0
            except Exception as e:
                print(f"Erro ao verificar times do usuário: {e}")
            finally:
                close_db_connection(conn)
    
    # Buscar permissões do plano se o usuário estiver logado
    permissions = None
    plan_key = 'free'
    if user:
        from utils.permissions import get_user_permissions
        try:
            user_perms = get_user_permissions(user['id'])
            permissions = user_perms['permissions']
            plan_key = user_perms['planKey']
        except Exception as e:
            print(f"Erro ao buscar permissões: {e}")
            # Se der erro, usar permissões do plano free
            from models.plans import PLANS_CONFIG
            permissions = PLANS_CONFIG['free'].copy()
            plan_key = 'free'
    else:
        # Usuário não logado - usar permissões do plano free
        from models.plans import PLANS_CONFIG
        permissions = PLANS_CONFIG['free'].copy()
        plan_key = 'free'
    
    return {
        'current_user': user,
        'permissions': permissions,
        'plan_key': plan_key,
        'has_teams': has_teams
    }

# ========================================
# ROTAS PRINCIPAIS
# ========================================

@app.route('/')
@login_required
@team_required
def index():
    try:
        print("[DEBUG INDEX] Iniciando função index()")
        user = get_current_user()
        print(f"[DEBUG INDEX] Usuário atual: {user}")
        
        # Verificar se o usuário tem times associados
        from models.teams import create_teams_table
        conn = get_db_connection()
        print("[DEBUG INDEX] Conexão com banco obtida")
        
        try:
            create_teams_table(conn)
            print("[DEBUG INDEX] Tabela de times criada/verificada")
            times = get_all_user_teams(conn, user['id'])
            print(f"[DEBUG INDEX] Times encontrados: {len(times) if times else 0}")
        finally:
            close_db_connection(conn)
            print("[DEBUG INDEX] Conexão com banco fechada")
        
        # Se não tiver times, redirecionar para página inicial (mais amigável)
        if not times or len(times) == 0:
            print("[DEBUG INDEX] Nenhum time encontrado, redirecionando para pagina_inicial")
            return redirect(url_for('pagina_inicial'))
        
        # Se tiver times, redirecionar para o dashboard
        print("[DEBUG INDEX] Redirecionando para dashboard")
        return redirect(url_for('dashboard'))
    except Exception as e:
        print(f"[ERRO INDEX] Erro na função index(): {e}")
        import traceback
        traceback.print_exc()
        flash(f'Erro ao carregar a página inicial: {str(e)}', 'error')
        return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Página e processamento de login"""
    print(f"[DEBUG LOGIN] Método: {request.method}")
    print(f"[DEBUG LOGIN] URL: {request.url}")
    print(f"[DEBUG LOGIN] Session flashes antes: {session.get('_flashes', [])}")
    
    if is_user_authenticated():
        return redirect(url_for('index'))
    
    # Limpar mensagens flash antigas se for um GET request (sem POST)
    # Isso evita que mensagens de registro apareçam na página de login
    if request.method == 'GET':
        # Limpar TODAS as mensagens flash antigas ao acessar /login
        session.pop('_flashes', None)
        print(f"[DEBUG LOGIN] Mensagens flash limpas no GET")
    
    if request.method == 'POST':
        username_or_email = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember_me = bool(request.form.get('remember'))
        
        if not username_or_email or not password:
            flash('Por favor, preencha todos os campos.', 'error')
            return render_template('login.html')
        
        auth_result = authenticate_user(username_or_email, password)
        
        if auth_result['success']:
            user = auth_result['user']
            # Configurar sessão permanente baseado no "Lembrar de mim"
            session.permanent = True
            
            # Configurar duração da sessão baseado no "Lembrar de mim"
            if remember_me:
                # Se "Lembrar de mim" marcado: sessão dura 30 dias
                app.permanent_session_lifetime = timedelta(days=30)
            else:
                # Se não marcado: sessão dura 1 dia
                app.permanent_session_lifetime = timedelta(days=1)
            
            # Marcar sessão como modificada para aplicar o novo tempo de expiração
            session.modified = True
            
            # Usar sessão do Flask diretamente (sem sessões customizadas)
            session['user_id'] = user['id']
            session['username'] = user['username']
            # Inicializar time selecionado com o primeiro time do usuário (se houver)
            from models.teams import create_teams_table
            conn = get_db_connection()
            try:
                create_teams_table(conn)
                times = get_all_user_teams(conn, user['id'])
                if times and len(times) > 0:
                    session['selected_team_id'] = times[0]['id']
            finally:
                close_db_connection(conn)
            flash(f'Bem-vindo, {user.get("full_name") or user["username"]}!', 'success')
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            return redirect(url_for('index'))
        else:
            flash(auth_result['error'], 'error')
    
    # GET request - renderizar página de login limpa
    print(f"[DEBUG LOGIN] Renderizando template (GET request)")
    print(f"[DEBUG LOGIN] Session flashes antes de renderizar: {session.get('_flashes', [])}")
    return render_template('login.html')

@app.route('/register', methods=['POST'])
def register():
    """Processamento de registro - apenas POST"""
    print(f"[DEBUG REGISTER] Método: {request.method}")
    print(f"[DEBUG REGISTER] URL: {request.url}")
    print(f"[DEBUG REGISTER] Form: {dict(request.form)}")
    print(f"[DEBUG REGISTER] Session flashes antes: {session.get('_flashes', [])}")
    
    if is_user_authenticated():
        return redirect(url_for('index'))
    
    # A rota /register só deve ser chamada via POST
    # GET requests devem ir para /login
    if request.method == 'GET':
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        full_name = request.form.get('full_name', '').strip() or None
        
        print(f"[DEBUG REGISTER] Dados recebidos - Username: {username}, Email: {email}, Password: {'*' * len(password) if password else 'vazio'}")
        
        # Validações básicas - verificar se os campos obrigatórios foram preenchidos
        if not username or not email or not password or not confirm_password:
            flash('Por favor, preencha todos os campos obrigatórios.', 'error')
            return render_template('login.html')
        
        # Validações de formato
        if len(username) < 3:
            flash('O nome de usuário deve ter pelo menos 3 caracteres.', 'error')
            return render_template('login.html')
        
        if len(password) < 6:
            flash('A senha deve ter pelo menos 6 caracteres.', 'error')
            return render_template('login.html')
        
        if password != confirm_password:
            flash('As senhas não coincidem.', 'error')
            return render_template('login.html')
        
        # Validar formato de email básico
        if '@' not in email or '.' not in email.split('@')[1]:
            flash('Por favor, insira um email válido.', 'error')
            return render_template('login.html')
        
        # Criar usuário
        print(f"[DEBUG REGISTER] Chamando create_user...")
        result = create_user(username, email, password, full_name, is_admin=False, email_verified=False)
        print(f"[DEBUG REGISTER] Resultado create_user: {result}")
        
        if result['success']:
            # Enviar email de verificação
            verification_token = result['verification_token']
            print(f"[DEBUG] Usuário criado com sucesso! ID: {result['user_id']}")
            print(f"[DEBUG] Token de verificação gerado: {verification_token[:20]}...")
            print(f"[DEBUG] Tentando enviar email de verificação para: {email}")
            email_result = send_verification_email(email, username, verification_token)
            
            if email_result['success']:
                flash('Conta criada com sucesso! Verifique seu email para ativar sua conta.', 'success')
            else:
                error_detail = email_result.get("error", "Erro desconhecido")
                print(f"[ERROR] Falha ao enviar email: {error_detail}")
                flash(f'Conta criada, mas houve um erro ao enviar o email de verificação: {error_detail}. Entre em contato com o suporte.', 'warning')
            
            return render_template('login.html')
        else:
            # Erro ao criar usuário
            error_msg = result.get('error', 'Erro desconhecido ao criar conta.')
            print(f"[DEBUG REGISTER] Erro ao criar usuário: {error_msg}")
            flash(error_msg, 'error')
            print(f"[DEBUG REGISTER] Session flashes após flash error: {session.get('_flashes', [])}")
            return render_template('login.html')
    
    # GET request - apenas renderizar a página
    print(f"[DEBUG REGISTER] Renderizando template (GET request)")
    print(f"[DEBUG REGISTER] Session flashes antes de renderizar: {session.get('_flashes', [])}")
    return render_template('login.html')

@app.route('/verify-email')
def verify_email():
    """Verifica o email do usuário através do token"""
    token = request.args.get('token', '').strip()
    
    if not token:
        flash('Token de verificação não fornecido.', 'error')
        return redirect(url_for('login'))
    
    result = verify_email_token(token)
    
    if result['success']:
        if result.get('already_verified'):
            flash('ℹ️ Seu email já estava verificado! Você já pode fazer login.', 'info')
        else:
            # Enviar email de boas-vindas
            try:
                user = result['user']
                send_welcome_email(user['email'], user['username'])
            except Exception as e:
                print(f"[WARNING] Erro ao enviar email de boas-vindas: {e}")
                # Não falhar a verificação se o email de boas-vindas falhar
            
            flash('✅ Email verificado com sucesso! Sua conta foi ativada. Agora você pode fazer login.', 'success')
        return redirect(url_for('login'))
    else:
        error_msg = result.get('error', 'Erro ao verificar email.')
        flash(f'❌ {error_msg}', 'error')
        return redirect(url_for('login'))

@app.route('/logout')
def logout():
    """Logout do usuário"""
    logout_user()
    flash('Você foi desconectado com sucesso.', 'success')
    return redirect(url_for('login'))


@app.route('/esqueceu-senha', methods=['GET', 'POST'])
def esqueceu_senha():
    """Página para recuperar senha - envia link para redefinir senha"""
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        
        if not email:
            flash('Por favor, informe seu email.', 'error')
            return render_template('esqueceu_senha.html')
        
        # Buscar usuário pelo email
        conn = get_db_connection()
        if not conn:
            flash('Erro ao conectar ao banco de dados.', 'error')
            return render_template('esqueceu_senha.html')
        
        try:
            import secrets
            from datetime import datetime, timedelta
            
            cursor = conn.cursor()
            cursor.execute('SELECT id, username, email FROM acw_users WHERE email = %s', (email,))
            user = cursor.fetchone()
            
            if not user:
                # Por segurança, não revelar se o email existe ou não
                flash('Se o email estiver cadastrado, você receberá um link para redefinir sua senha por email.', 'info')
                return render_template('esqueceu_senha.html')
            
            user_id, username, user_email = user
            
            # Gerar token de reset de senha (válido por 1 hora)
            reset_token = secrets.token_urlsafe(32)
            expires_at = datetime.now() + timedelta(hours=1)
            
            # Salvar token no banco
            cursor.execute('''
                UPDATE acw_users 
                SET password_reset_token = %s, password_reset_expires = %s
                WHERE id = %s
            ''', (reset_token, expires_at, user_id))
            conn.commit()
            
            # Enviar email com link de reset
            from utils.email_service import _send_email_smtp
            base_url = os.getenv('BASE_URL', 'http://localhost:5000')
            reset_url = f"{base_url}/redefinir-senha?token={reset_token}"
            
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
            </head>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #1a1a1a; background-color: #f5f5f5; margin: 0; padding: 20px;">
                <div class="email-wrapper" style="max-width: 600px; margin: 0 auto; background-color: #ffffff;">
                    <div class="header" style="background: linear-gradient(135deg, #0c4a6e 0%, #075985 100%); padding: 30px 20px; text-align: center; border-radius: 10px 10px 0 0;">
                        <h1 style="margin: 0; font-size: 28px; color: #ffffff; font-weight: bold;">⚽ Aero Cartola</h1>
                    </div>
                    <div class="content" style="background: #ffffff; color: #1a1a1a; padding: 40px 30px; border-radius: 0 0 10px 10px;">
                        <h2 style="color: #0c4a6e; margin-top: 0; font-size: 24px;">Recuperação de Senha</h2>
                        <p>Olá, <strong>{username}</strong>!</p>
                        <p>Você solicitou a recuperação de senha. Clique no botão abaixo para redefinir sua senha:</p>
                        <div style="text-align: center; margin: 30px 0;">
                            <a href="{reset_url}" style="display: inline-block; background: linear-gradient(135deg, #0ea5e9 0%, #0284c7 100%); color: #ffffff !important; padding: 15px 40px; text-decoration: none; border-radius: 5px; font-weight: bold; font-size: 16px; box-shadow: 0 2px 4px rgba(0,0,0,0.2);">Redefinir Senha</a>
                        </div>
                        <p style="text-align: center; color: #666; font-size: 14px;">Ou copie e cole este link no seu navegador:</p>
                        <div style="background-color: #f0f9ff; border-left: 4px solid #0ea5e9; padding: 15px; margin: 20px 0; border-radius: 4px; word-break: break-all;">
                            <code style="color: #0369a1; font-size: 14px; font-family: 'Courier New', monospace;">{reset_url}</code>
                        </div>
                        <p><strong>⚠️ Importante:</strong></p>
                        <ul style="color: #333333; margin: 15px 0; padding-left: 20px;">
                            <li>Este link é válido por 1 hora</li>
                            <li>Após clicar, você poderá definir uma nova senha</li>
                            <li>Se você não solicitou esta recuperação, ignore este email</li>
                        </ul>
                    </div>
                </div>
            </body>
            </html>
            """
            
            text_content = f"""
            Recuperação de Senha - Aero Cartola
            
            Olá, {username}!
            
            Você solicitou a recuperação de senha. Acesse o link abaixo para redefinir sua senha:
            
            {reset_url}
            
            ⚠️ IMPORTANTE:
            - Este link é válido por 1 hora
            - Após clicar, você poderá definir uma nova senha
            - Se você não solicitou esta recuperação, ignore este email
            """
            
            email_result = _send_email_smtp(
                to_email=user_email,
                to_name=username,
                subject="Recuperação de Senha - Aero Cartola",
                html_content=html_content,
                text_content=text_content
            )
            
            if email_result['success']:
                flash('Um link para redefinir sua senha foi enviado para seu email. Verifique sua caixa de entrada.', 'success')
            else:
                flash('Erro ao enviar email. Tente novamente mais tarde ou entre em contato com o suporte.', 'error')
            
        except Exception as e:
            conn.rollback()
            print(f"[ERROR] Erro ao processar esqueceu senha: {e}")
            import traceback
            traceback.print_exc()
            flash('Erro ao processar solicitação. Tente novamente.', 'error')
        finally:
            close_db_connection(conn)
    
    return render_template('esqueceu_senha.html')

@app.route('/redefinir-senha', methods=['GET', 'POST'])
def redefinir_senha():
    """Página para redefinir senha usando token"""
    token = request.args.get('token', '').strip() if request.method == 'GET' else request.form.get('token', '').strip()
    
    if not token:
        flash('Token de redefinição inválido ou ausente.', 'error')
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    if not conn:
        flash('Erro ao conectar ao banco de dados.', 'error')
        return redirect(url_for('login'))
    
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, username, email 
            FROM acw_users 
            WHERE password_reset_token = %s 
            AND password_reset_expires > CURRENT_TIMESTAMP
        ''', (token,))
        user = cursor.fetchone()
        
        if not user:
            flash('Token inválido ou expirado. Solicite uma nova recuperação de senha.', 'error')
            return redirect(url_for('esqueceu_senha'))
        
        user_id, username, user_email = user
        
        if request.method == 'POST':
            nova_senha = request.form.get('nova_senha', '')
            confirmar_senha = request.form.get('confirmar_senha', '')
            
            if not nova_senha or not confirmar_senha:
                flash('Por favor, preencha todos os campos.', 'error')
                return render_template('redefinir_senha.html', token=token)
            
            if nova_senha != confirmar_senha:
                flash('As senhas não coincidem.', 'error')
                return render_template('redefinir_senha.html', token=token)
            
            if len(nova_senha) < 6:
                flash('A senha deve ter pelo menos 6 caracteres.', 'error')
                return render_template('redefinir_senha.html', token=token)
            
            # Atualizar senha e limpar token
            from models.users import hash_password
            password_hash, salt, password_encrypted = hash_password(nova_senha)
            
            cursor.execute('''
                UPDATE acw_users 
                SET password_hash = %s, salt = %s, password_encrypted = %s,
                    password_reset_token = NULL, password_reset_expires = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            ''', (password_hash, salt, password_encrypted, user_id))
            conn.commit()
            
            flash('Senha redefinida com sucesso! Agora você pode fazer login com sua nova senha.', 'success')
            return redirect(url_for('login'))
        
        # GET - mostrar formulário
        return render_template('redefinir_senha.html', token=token)
        
    except Exception as e:
        conn.rollback()
        print(f"[ERROR] Erro ao redefinir senha: {e}")
        import traceback
        traceback.print_exc()
        flash('Erro ao processar solicitação. Tente novamente.', 'error')
        return redirect(url_for('login'))
    finally:
        close_db_connection(conn)

@app.route('/alterar-senha', methods=['GET', 'POST'])
@login_required
def alterar_senha():
    """Página para alterar senha do usuário"""
    user = get_current_user()
    
    if request.method == 'POST':
        senha_atual = request.form.get('senha_atual', '')
        senha_nova = request.form.get('senha_nova', '')
        senha_nova_confirmar = request.form.get('senha_nova_confirmar', '')
        
        if not senha_atual or not senha_nova or not senha_nova_confirmar:
            flash('Por favor, preencha todos os campos.', 'error')
            return render_template('alterar_senha.html', current_user=user)
        
        if senha_nova != senha_nova_confirmar:
            flash('As novas senhas não coincidem.', 'error')
            return render_template('alterar_senha.html', current_user=user)
        
        if len(senha_nova) < 6:
            flash('A nova senha deve ter pelo menos 6 caracteres.', 'error')
            return render_template('alterar_senha.html', current_user=user)
        
        # Verificar senha atual
        conn = get_db_connection()
        if not conn:
            flash('Erro ao conectar ao banco de dados.', 'error')
            return render_template('alterar_senha.html', current_user=user)
        
        try:
            from models.users import verify_password, hash_password
            cursor = conn.cursor()
            cursor.execute('SELECT password_hash, salt FROM acw_users WHERE id = %s', (user['id'],))
            result = cursor.fetchone()
            
            if not result:
                flash('Erro ao buscar dados do usuário.', 'error')
                return render_template('alterar_senha.html', current_user=user)
            
            stored_hash, stored_salt = result
            
            # Verificar senha atual
            if not verify_password(senha_atual, stored_hash, stored_salt):
                flash('Senha atual incorreta.', 'error')
                return render_template('alterar_senha.html', current_user=user)
            
            # Atualizar senha
            new_hash, new_salt, new_encrypted = hash_password(senha_nova)
            cursor.execute('UPDATE acw_users SET password_hash = %s, salt = %s, password_encrypted = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s', 
                         (new_hash, new_salt, new_encrypted, user['id']))
            conn.commit()
            
            flash('Senha alterada com sucesso!', 'success')
            return redirect(url_for('index'))
            
        except Exception as e:
            conn.rollback()
            print(f"[ERROR] Erro ao alterar senha: {e}")
            flash('Erro ao alterar senha. Tente novamente.', 'error')
            return render_template('alterar_senha.html', current_user=user)
        finally:
            close_db_connection(conn)
    
    return render_template('alterar_senha.html', current_user=user)

@app.route('/associar-credenciais', methods=['GET', 'POST'])
@login_required
def associar_credenciais():
    """Página para associar credenciais do Cartola ao usuário"""
    user = get_current_user()
    
    from models.teams import create_teams_table
    
    if request.method == 'POST':
        access_token = request.form.get('access_token', '').strip()
        refresh_token = request.form.get('refresh_token', '').strip()
        id_token = request.form.get('id_token', '').strip() or None
        team_name = request.form.get('team_name', '').strip() or None
        
        if not access_token or not refresh_token:
            flash('Por favor, preencha pelo menos o Access Token e Refresh Token.', 'error')
            return render_template('associar_credenciais.html', current_user=user)
        
        conn = get_db_connection()
        try:
            create_teams_table(conn)
            
            # Buscar dados do time da API do Cartola para obter nome
            from api_cartola import fetch_team_info_by_team_id
            final_team_name = team_name
            
            # Criar time temporário para buscar dados
            temp_id = create_team(
                conn, user['id'], access_token, refresh_token, id_token, team_name
            )
            
            # Buscar informações do time (nome)
            try:
                team_info = fetch_team_info_by_team_id(conn, temp_id)
                if team_info and 'time' in team_info and isinstance(team_info['time'], dict):
                    time_data = team_info['time']
                    if not final_team_name and 'nome' in time_data:
                        final_team_name = time_data['nome']
            except Exception as e:
                print(f"Erro ao buscar informações do time da API: {e}")
                # Continuar mesmo se não conseguir buscar dados
            
            # Atualizar time com nome
            from models.teams import update_team
            if final_team_name != team_name:
                update_team(conn, temp_id, user['id'], team_name=final_team_name)
            
            # Se não houver time selecionado, selecionar o novo
            if not session.get('selected_team_id'):
                session['selected_team_id'] = temp_id
            
            flash('Time associado com sucesso!', 'success')
            return redirect(url_for('credenciais'))
        except Exception as e:
            flash(f'Erro ao associar credenciais: {str(e)}', 'error')
            import traceback
            traceback.print_exc()
        finally:
            close_db_connection(conn)
    
    return render_template('associar_credenciais.html', current_user=user)

@app.route('/dashboard')
@login_required
def dashboard():
    """Dashboard principal com verificações de status do time"""
    print("[DEBUG DASHBOARD] Iniciando função dashboard()")
    
    conn = None
    try:
        user = get_current_user()
        print(f"[DEBUG DASHBOARD] Usuário atual: {user}")
        
        from models.teams import create_teams_table, get_team, get_all_user_teams
        from models.user_configurations import get_user_default_configuration, create_user_configurations_table
        from models.user_rankings import create_user_rankings_table
        from api_cartola import fetch_team_info_by_team_id
        from utils.team_shields import get_team_shield
        
        print("[DEBUG DASHBOARD] Imports realizados com sucesso")
        
        conn = get_db_connection()
        print("[DEBUG DASHBOARD] Conexão com banco obtida")
        
        create_teams_table(conn)
        create_user_configurations_table(conn)
        create_user_rankings_table(conn)
        
        # Verificar se há time selecionado
        team_id = session.get('selected_team_id')
        
        # Buscar limite de times do plano
        from models.plans import get_max_times
        max_times = get_max_times(user['id'])
        
        # Buscar todos os times do usuário
        all_teams = get_all_user_teams(conn, user['id'])
        if not all_teams or len(all_teams) == 0:
            flash('Por favor, associe suas credenciais do Cartola primeiro.', 'warning')
            return redirect(url_for('associar_credenciais'))
        
        # Verificar se o time selecionado ainda está disponível (dentro do limite)
        selected_team = None
        if team_id:
            # Encontrar o time selecionado e verificar se está disponível
            selected_index = None
            for idx, team in enumerate(all_teams):
                if team['id'] == team_id:
                    selected_index = idx
                    break
            
            # Verificar se o time está dentro do limite
            if selected_index is not None and selected_index < max_times:
                selected_team = get_team(conn, team_id, user['id'])
            else:
                # Time selecionado não está mais disponível
                print(f"[DEBUG DASHBOARD] Time selecionado {team_id} não está mais disponível (índice: {selected_index}, limite: {max_times})")
                team_id = None
                session.pop('selected_team_id', None)
        
        # Se não houver time selecionado, selecionar o primeiro disponível
        if not team_id:
            # Selecionar o primeiro time dentro do limite (índice 0, desde que max_times > 0)
            if max_times > 0 and len(all_teams) > 0:
                selected_team = all_teams[0]
                team_id = selected_team['id']
                session['selected_team_id'] = team_id
                print(f"[DEBUG DASHBOARD] Selecionando automaticamente o primeiro time disponível: {team_id}")
            else:
                flash('Nenhum time disponível no seu plano atual. Por favor, selecione um time.', 'warning')
                return redirect(url_for('credenciais'))
        
        # Verificar se o time foi encontrado
        if not selected_team:
            selected_team = get_team(conn, team_id, user['id'])
            if not selected_team:
                flash('Time não encontrado. Por favor, selecione um time.', 'warning')
                return redirect(url_for('credenciais'))
        
        # 1. Verificar se perfis foram configurados
        config = get_user_default_configuration(conn, user['id'], team_id)
        tem_perfis = config is not None and config.get('perfil_peso_jogo') and config.get('perfil_peso_sg')
        
        # 2. Verificar se posições foram calculadas (verificar se há dados em acw_rankings_teams)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT COUNT(*) FROM acw_rankings_teams 
            WHERE user_id = %s AND team_id = %s
        ''', (user['id'], team_id))
        count_rankings = cursor.fetchone()[0]
        tem_calculos = count_rankings > 0
        
        # 3. Verificar se tem escalação (verificar se há dados em acw_escalacao_config)
        cursor.execute('''
            SELECT COUNT(*) FROM acw_escalacao_config 
            WHERE user_id = %s AND team_id = %s
        ''', (user['id'], team_id))
        count_escalacao = cursor.fetchone()[0]
        tem_escalacao = count_escalacao > 0
        
        # Buscar informações do time do Cartola
        team_info_cartola = None
        team_shield_url = None
        try:
            team_info_cartola = fetch_team_info_by_team_id(conn, team_id)
            if team_info_cartola and team_info_cartola.get('time', {}).get('url_escudo_png'):
                team_shield_url = team_info_cartola['time']['url_escudo_png']
        except Exception as e:
            print(f"Erro ao buscar informações do time do Cartola: {e}")
            pass
        
        # Buscar informações do time
        team_info = {
            'id': selected_team['id'],
            'team_name': selected_team.get('team_name', 'Meu Time'),
            'team_slug': team_info_cartola.get('time', {}).get('slug') if team_info_cartola else None,
            'team_shield_url': team_shield_url
        }
        
        status = {
            'tem_perfis': tem_perfis,
            'tem_calculos': tem_calculos,
            'tem_escalacao': tem_escalacao,
            'perfis_info': config if (tem_perfis and config) else {}
        }
        
        print("[DEBUG DASHBOARD] Dashboard processado com sucesso, renderizando template")
        
        return render_template('dashboard.html', 
                             current_user=user, 
                             team=team_info,
                             status=status)
    
    except Exception as e:
        print(f"[ERRO DASHBOARD] Erro ao carregar dashboard: {e}")
        import traceback
        traceback.print_exc()
        flash(f'Erro ao carregar o dashboard: {str(e)}', 'error')
        return redirect(url_for('associar_credenciais'))
    finally:
        try:
            close_db_connection(conn)
            print("[DEBUG DASHBOARD] Conexão com banco fechada")
        except:
            print("[DEBUG DASHBOARD] Erro ao fechar conexão (conexão pode não ter sido criada)")
            pass

@app.route('/pagina-inicial')
@login_required
@team_required
def pagina_inicial():
    """Página inicial com seleção de perfis de peso de jogo e peso SG"""
    user = get_current_user()
    
    from models.teams import create_teams_table
    conn = get_db_connection()
    try:
        create_teams_table(conn)
        times = get_all_user_teams(conn, user['id'])
        if not times or len(times) == 0:
            flash('Bem-vindo ao Aero Cartola! Para começar, vamos adicionar seu primeiro time.', 'info')
            return redirect(url_for('associar_credenciais'))
    finally:
        close_db_connection(conn)
    
    # Buscar perfis disponíveis de peso de jogo com rankings (top 3 clubes)
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # Buscar rodada atual
        cursor.execute('SELECT MAX(rodada_atual) FROM acp_peso_jogo_perfis')
        rodada_result = cursor.fetchone()
        rodada_atual = rodada_result[0] if rodada_result and rodada_result[0] else 1
        
        # Buscar partidas da rodada atual para identificar adversários
        cursor.execute('''
            SELECT clube_casa_id, clube_visitante_id
            FROM acf_partidas
            WHERE rodada_id = %s AND valida = TRUE
        ''', (rodada_atual,))
        partidas = cursor.fetchall()
        
        # Criar dicionário de adversários: {clube_id: adversario_id}
        # E dicionário de local: {clube_id: 'C' (casa) ou 'F' (fora)}
        adversarios_dict = {}
        local_dict = {}  # 'C' para casa, 'F' para fora
        for casa_id, visitante_id in partidas:
            adversarios_dict[casa_id] = visitante_id
            adversarios_dict[visitante_id] = casa_id
            local_dict[casa_id] = 'C'  # Time joga em casa
            local_dict[visitante_id] = 'F'  # Time joga fora
        
        # Buscar perfis de peso de jogo com top 3 clubes
        cursor.execute('''
            SELECT DISTINCT pj.perfil_id, pj.ultimas_partidas
            FROM acp_peso_jogo_perfis pj
            WHERE pj.rodada_atual = %s
            ORDER BY pj.perfil_id
        ''', (rodada_atual,))
        perfis_raw = cursor.fetchall()
        
        perfis_peso_jogo = []
        for perfil_id, ultimas_partidas in perfis_raw:
            # Buscar TODOS os clubes para este perfil (ordenados por peso)
            cursor.execute('''
                SELECT clube_id, peso_jogo
                FROM acp_peso_jogo_perfis
                WHERE perfil_id = %s AND rodada_atual = %s
                ORDER BY peso_jogo DESC
            ''', (perfil_id, rodada_atual))
            todos_clubes = cursor.fetchall()
            
            descricoes = {
                1: "Muito recente (foca nas últimas partidas)",
                2: "Recente (padrão atual)",
                3: "Médio (balanço entre recente e histórico)",
                4: "Mais histórico (considera mais partidas)",
                5: "Recente com peso crescente",
                6: "Histórico com peso crescente",
                7: "Análise intermediária",
                8: "Análise abrangente",
                9: "Análise profunda",
                10: "Análise completa"
            }
            
            top_clubes_list = []
            pesos_values = [row[1] for row in todos_clubes]
            peso_min = min(pesos_values) if pesos_values else 0
            peso_max = max(pesos_values) if pesos_values else 1
            
            for row in todos_clubes:
                clube_id = row[0]
                adversario_id = adversarios_dict.get(clube_id)
                local = local_dict.get(clube_id, None)  # 'C' para casa, 'F' para fora, None se não encontrado
                adversario_local = local_dict.get(adversario_id, None) if adversario_id else None  # Local do adversário
                peso_value = round(row[1], 2)
                
                # Calcular cor baseada na posição entre min e max (0 a 1)
                # Verde para valores altos, vermelho para valores baixos
                if peso_max > peso_min:
                    normalized = (peso_value - peso_min) / (peso_max - peso_min)
                else:
                    normalized = 1.0
                
                # Gerar cor: verde (0,255,0) para 1.0, vermelho (255,0,0) para 0.0
                red = int(255 * (1 - normalized))
                green = int(255 * normalized)
                color_hex = f"#{red:02x}{green:02x}00"
                
                top_clubes_list.append({
                    'clube_id': clube_id,
                    'peso_jogo': peso_value,
                    'peso_jogo_str': f"{peso_value:.2f}",
                    'adversario_id': adversario_id,
                    'adversario_local': adversario_local,  # 'C' ou 'F' do adversário
                    'peso_color': color_hex,
                    'local': local  # 'C' ou 'F'
                })
            
            perfis_peso_jogo.append({
                'perfil_id': perfil_id,
                'ultimas_partidas': ultimas_partidas,
                'top_clubes': top_clubes_list,
                'descricao': descricoes.get(perfil_id, f"Analisa as últimas {ultimas_partidas} partidas")
            })
        
        # Buscar perfis de peso SG com top 3 clubes
        cursor.execute('''
            SELECT DISTINCT ps.perfil_id, ps.ultimas_partidas
            FROM acp_peso_sg_perfis ps
            WHERE ps.rodada_atual = %s
            ORDER BY ps.perfil_id
        ''', (rodada_atual,))
        perfis_raw = cursor.fetchall()
        
        perfis_peso_sg = []
        for perfil_id, ultimas_partidas in perfis_raw:
            # Buscar TODOS os clubes para este perfil (ordenados por peso)
            cursor.execute('''
                SELECT clube_id, peso_sg
                FROM acp_peso_sg_perfis
                WHERE perfil_id = %s AND rodada_atual = %s
                ORDER BY peso_sg DESC
            ''', (perfil_id, rodada_atual))
            todos_clubes = cursor.fetchall()
            
            top_clubes_list = []
            pesos_values = [row[1] for row in todos_clubes]
            peso_min = min(pesos_values) if pesos_values else 0
            peso_max = max(pesos_values) if pesos_values else 1
            
            for row in todos_clubes:
                clube_id = row[0]
                adversario_id = adversarios_dict.get(clube_id)
                local = local_dict.get(clube_id, None)  # 'C' para casa, 'F' para fora, None se não encontrado
                adversario_local = local_dict.get(adversario_id, None) if adversario_id else None  # Local do adversário
                peso_value = round(row[1], 2)
                
                # Calcular cor baseada na posição entre min e max (0 a 1)
                # Verde para valores altos, vermelho para valores baixos
                if peso_max > peso_min:
                    normalized = (peso_value - peso_min) / (peso_max - peso_min)
                else:
                    normalized = 1.0
                
                # Gerar cor: verde (0,255,0) para 1.0, vermelho (255,0,0) para 0.0
                red = int(255 * (1 - normalized))
                green = int(255 * normalized)
                color_hex = f"#{red:02x}{green:02x}00"
                
                top_clubes_list.append({
                    'clube_id': clube_id,
                    'peso_sg': peso_value,
                    'peso_sg_str': f"{peso_value:.2f}",
                    'adversario_id': adversario_id,
                    'adversario_local': adversario_local,  # 'C' ou 'F' do adversário
                    'peso_color': color_hex,
                    'local': local  # 'C' ou 'F'
                })
            
            perfis_peso_sg.append({
                'perfil_id': perfil_id,
                'ultimas_partidas': ultimas_partidas,
                'top_clubes': top_clubes_list,
                'descricao': descricoes.get(perfil_id, f"Analisa saldo de gols das últimas {ultimas_partidas} partidas")
            })
        
        # Buscar nomes dos clubes e escudos
        # Coletar todos os IDs de clubes que precisamos (dos perfis + adversários)
        clube_ids_set = set(adversarios_dict.keys()) | set(adversarios_dict.values())
        
        # Adicionar clubes dos perfis de peso de jogo
        for perfil in perfis_peso_jogo:
            for clube in perfil['top_clubes']:
                clube_ids_set.add(clube['clube_id'])
                if clube.get('adversario_id'):
                    clube_ids_set.add(clube['adversario_id'])
        
        # Adicionar clubes dos perfis de peso SG
        for perfil in perfis_peso_sg:
            for clube in perfil['top_clubes']:
                clube_ids_set.add(clube['clube_id'])
                if clube.get('adversario_id'):
                    clube_ids_set.add(clube['adversario_id'])
        
        # Buscar todos os clubes necessários
        if clube_ids_set:
            placeholders = ','.join(['%s'] * len(clube_ids_set))
            cursor.execute(f'SELECT id, nome, abreviacao FROM acf_clubes WHERE id IN ({placeholders})', list(clube_ids_set))
        else:
            cursor.execute('SELECT id, nome, abreviacao FROM acf_clubes LIMIT 50')
        clubes_data = cursor.fetchall()
        
        # Buscar escudos da API
        from utils.team_shields import get_team_shield
        clubes_dict = {}
        for row in clubes_data:
            clube_id = row[0]
            escudo_url = get_team_shield(clube_id, size='45x45')
            
            clubes_dict[clube_id] = {
                'nome': row[1], 
                'abreviacao': row[2],
                'escudo_url': escudo_url
            }
        
    except Exception as e:
        print(f"Erro ao buscar perfis: {e}")
        import traceback
        traceback.print_exc()
        perfis_peso_jogo = []
        perfis_peso_sg = []
        clubes_dict = {}
        rodada_atual = 1
    finally:
        close_db_connection(conn)
    
    # Buscar configuração padrão do usuário se existir
    from models.user_configurations import get_user_default_configuration, create_user_configurations_table
    conn = get_db_connection()
    try:
        create_user_configurations_table(conn)
        team_id = session.get('selected_team_id')
        config_default = get_user_default_configuration(conn, user['id'], team_id) if team_id else None
    finally:
        close_db_connection(conn)
    
    # Limitar perfis baseado no plano do usuário
    from models.plans import get_max_perfis_jogo, get_max_perfis_sg
    max_perfis_jogo = get_max_perfis_jogo(user['id'])
    max_perfis_sg = get_max_perfis_sg(user['id'])
    
    # Filtrar perfis de jogo
    perfis_peso_jogo_limitados = []
    for i, perfil in enumerate(perfis_peso_jogo):
        if i < max_perfis_jogo:
            perfis_peso_jogo_limitados.append(perfil)
        else:
            # Adicionar perfil bloqueado (com flag)
            perfil_bloqueado = perfil.copy()
            perfil_bloqueado['bloqueado'] = True
            perfis_peso_jogo_limitados.append(perfil_bloqueado)
    
    # Filtrar perfis de SG
    perfis_peso_sg_limitados = []
    for i, perfil in enumerate(perfis_peso_sg):
        if i < max_perfis_sg:
            perfis_peso_sg_limitados.append(perfil)
        else:
            # Adicionar perfil bloqueado (com flag)
            perfil_bloqueado = perfil.copy()
            perfil_bloqueado['bloqueado'] = True
            perfis_peso_sg_limitados.append(perfil_bloqueado)
    
    return render_template(
        'pagina_inicial.html',
        current_user=user,
        perfis_peso_jogo=perfis_peso_jogo_limitados,
        perfis_peso_sg=perfis_peso_sg_limitados,
        clubes_dict=clubes_dict,
        rodada_atual=rodada_atual,
        config_default=config_default,
        max_perfis_jogo=max_perfis_jogo,
        max_perfis_sg=max_perfis_sg
    )

@app.route('/salvar-configuracao-perfis', methods=['POST'])
@login_required
def salvar_configuracao_perfis():
    """Salva a configuração de perfis escolhidos pelo usuário"""
    user = get_current_user()
    
    perfil_peso_jogo = int(request.form.get('perfil_peso_jogo'))
    perfil_peso_sg = int(request.form.get('perfil_peso_sg'))
    
    from models.user_configurations import create_user_configuration, create_user_configurations_table
    
    # Obter team_id da sessão
    team_id = session.get('selected_team_id')
    if not team_id:
        flash('Selecione um time primeiro!', 'error')
        return redirect(url_for('credenciais'))
    
    conn = get_db_connection()
    try:
        create_user_configurations_table(conn)
        
        create_user_configuration(
            conn, user['id'], team_id, 'Configuração Padrão', 
            perfil_peso_jogo, perfil_peso_sg, is_default=True
        )
        
        flash('Perfis salvos com sucesso!', 'success')
        return redirect(url_for('modulos'))
    except Exception as e:
        flash(f'Erro ao salvar configuração: {str(e)}', 'error')
        return redirect(url_for('pagina_inicial'))
    finally:
        close_db_connection(conn)

@app.route('/credenciais')
@login_required
@team_required
def credenciais():
    """Página para visualizar e gerenciar todos os times do usuário"""
    user = get_current_user()
    
    from models.teams import get_all_user_teams, create_teams_table
    from api_cartola import fetch_team_info_by_team_id
    from models.plans import get_max_times
    
    conn = get_db_connection()
    try:
        create_teams_table(conn)
        all_times = get_all_user_teams(conn, user['id'])
        
        # Buscar limite de times do plano
        max_times = get_max_times(user['id'])
        total_times = len(all_times)
        
        # Buscar escudos dinamicamente para cada time
        for i, time in enumerate(all_times):
            time['team_shield_url'] = None
            time['token_error'] = False
            # Marcar times além do limite como bloqueados
            if i >= max_times:
                time['bloqueado'] = True
            else:
                time['bloqueado'] = False
                
            try:
                team_info = fetch_team_info_by_team_id(conn, time['id'])
                if team_info and 'time' in team_info and isinstance(team_info['time'], dict):
                    time_data = team_info['time']
                    # Priorizar url_escudo_png, depois url_escudo_svg, depois foto_perfil
                    if 'url_escudo_png' in time_data:
                        time['team_shield_url'] = time_data['url_escudo_png']
                    elif 'url_escudo_svg' in time_data:
                        time['team_shield_url'] = time_data['url_escudo_svg']
                    elif 'foto_perfil' in time_data:
                        time['team_shield_url'] = time_data['foto_perfil']
                elif team_info is None:
                    # Se team_info é None, provavelmente houve erro de token (401)
                    time['token_error'] = True
            except Exception as e:
                print(f"Erro ao buscar escudo do time {time['id']}: {e}")
                # Se o erro for relacionado a token, marcar como erro de token
                if '401' in str(e) or 'token' in str(e).lower():
                    time['token_error'] = True
    finally:
        close_db_connection(conn)
    
    return render_template('credenciais.html', current_user=user, all_times=all_times, max_times=max_times, total_times=total_times)

@app.route('/credenciais/editar/<int:time_id>', methods=['GET', 'POST'])
@login_required
def editar_credenciais(time_id):
    """Editar credenciais de um time específico"""
    user = get_current_user()
    
    from models.teams import get_all_user_teams, create_teams_table
    conn = get_db_connection()
    
    try:
        create_teams_table(conn)
        
        # Verificar se o time pertence ao usuário
        all_times = get_all_user_teams(conn, user['id'])
        time_to_edit = next((t for t in all_times if t['id'] == time_id), None)
        
        if not time_to_edit:
            flash('Time não encontrado ou não pertence ao usuário', 'error')
            return redirect(url_for('credenciais'))
        
        if request.method == 'POST':
            # Atualizar credenciais
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE acw_teams
                SET access_token = %s,
                    refresh_token = %s,
                    id_token = %s,
                    team_name = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s AND user_id = %s
            ''', (
                request.form.get('access_token', '').strip(),
                request.form.get('refresh_token', '').strip(),
                request.form.get('id_token', '').strip() or None,
                request.form.get('team_name', '').strip() or None,
                time_id,
                user['id']
            ))
            conn.commit()
            flash('Credenciais atualizadas com sucesso!', 'success')
            return redirect(url_for('credenciais'))
        
        # GET - mostrar formulário
        return render_template('editar_credenciais.html', current_user=user, credenciais=time_to_edit)
    finally:
        close_db_connection(conn)

@app.route('/modulos')
@login_required
@team_required
def modulos():
    """Página principal dos módulos individuais"""
    # Verificar se há time selecionado
    team_id = session.get('selected_team_id')
    if not team_id:
        flash('Associe um time primeiro para acessar os módulos', 'warning')
        return redirect(url_for('credenciais'))
    return render_template('modulos.html')

@app.route('/api/admin/limpar-rankings', methods=['POST'])
@login_required
def api_admin_limpar_rankings():
    """API para limpar todos os rankings (admin only)"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Contar antes
        cursor.execute("SELECT COUNT(*) FROM acw_rankings_teams")
        total_antes = cursor.fetchone()[0]
        
        # Deletar todos
        cursor.execute("DELETE FROM acw_rankings_teams")
        conn.commit()
        
        # Contar depois
        cursor.execute("SELECT COUNT(*) FROM acw_rankings_teams")
        total_depois = cursor.fetchone()[0]
        
        return jsonify({
            'success': True,
            'deletados': total_antes,
            'restantes': total_depois,
            'mensagem': f'✅ {total_antes} rankings deletados com sucesso!'
        })
        
    except Exception as e:
        conn.rollback()
        print(f"Erro ao limpar rankings: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        close_db_connection(conn)

@app.route('/api/debug/time/<int:team_id>')
@login_required
def api_debug_time(team_id):
    """API de debug para verificar por que um time não retorna rankings"""
    user = get_current_user()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        debug_info = {}
        
        # Buscar rodada
        cursor.execute('SELECT MAX(rodada_atual) FROM acp_peso_jogo_perfis')
        rodada_result = cursor.fetchone()
        rodada_atual = rodada_result[0] if rodada_result else 1
        debug_info['rodada_atual'] = rodada_atual
        
        # Buscar info do time
        cursor.execute("SELECT id, user_id, team_name FROM acw_teams WHERE id = %s", (team_id,))
        time_info = cursor.fetchone()
        if not time_info:
            return jsonify({'error': 'Time não encontrado'}), 404
        
        debug_info['time'] = {
            'id': time_info[0],
            'user_id': time_info[1],
            'team_name': time_info[2]
        }
        
        # Buscar configuração
        from models.user_configurations import get_user_default_configuration
        config = get_user_default_configuration(conn, time_info[1], team_id)
        
        debug_info['configuracao'] = {
            'existe': config is not None,
            'config_id': config.get('id') if config else None,
            'perfil_peso_jogo': config.get('perfil_peso_jogo') if config else None,
            'perfil_peso_sg': config.get('perfil_peso_sg') if config else None
        }
        
        # Verificar rankings - QUERY DIRETA
        cursor.execute("""
            SELECT posicao_id, configuration_id, 
                   CASE 
                       WHEN ranking_data::text = '[]' THEN 0
                       ELSE jsonb_array_length(ranking_data)
                   END as qtd_jogadores
            FROM acw_rankings_teams
            WHERE team_id = %s
              AND rodada_atual = %s
            ORDER BY posicao_id
        """, (team_id, rodada_atual))
        
        rankings_direto = cursor.fetchall()
        debug_info['rankings_direto'] = [
            {'posicao_id': r[0], 'configuration_id': r[1], 'qtd_jogadores': r[2]}
            for r in rankings_direto
        ]
        
        # Verificar rankings com configuration_id
        if config:
            cursor.execute("""
                SELECT posicao_id,
                       CASE 
                           WHEN ranking_data::text = '[]' THEN 0
                           ELSE jsonb_array_length(ranking_data)
                       END as qtd_jogadores
                FROM acw_rankings_teams
                WHERE team_id = %s
                  AND rodada_atual = %s
                  AND configuration_id = %s
                ORDER BY posicao_id
            """, (team_id, rodada_atual, config.get('id')))
            
            rankings_com_config = cursor.fetchall()
            debug_info['rankings_com_config_id'] = [
                {'posicao_id': r[0], 'qtd_jogadores': r[1]}
                for r in rankings_com_config
            ]
        else:
            debug_info['rankings_com_config_id'] = []
        
        # Usar a mesma função da API
        from models.user_rankings import get_team_rankings
        posicoes = {
            'goleiro': 1, 'lateral': 2, 'zagueiro': 3,
            'meia': 4, 'atacante': 5, 'treinador': 6
        }
        
        rankings_via_funcao = {}
        for pos_nome, pos_id in posicoes.items():
            rankings = get_team_rankings(
                conn,
                time_info[1],  # user_id
                team_id=team_id,
                configuration_id=config.get('id') if config else None,
                posicao_id=pos_id,
                rodada_atual=rodada_atual
            )
            
            if rankings:
                ranking_data = rankings[0].get('ranking_data', [])
                qtd = len(ranking_data) if isinstance(ranking_data, list) else 0
                rankings_via_funcao[pos_nome] = {'qtd_jogadores': qtd, 'tem_ranking': True}
            else:
                rankings_via_funcao[pos_nome] = {'qtd_jogadores': 0, 'tem_ranking': False}
        
        debug_info['rankings_via_funcao'] = rankings_via_funcao
        
        # Diagnóstico
        debug_info['diagnostico'] = []
        
        if not config:
            debug_info['diagnostico'].append('❌ TIME NÃO TEM CONFIGURAÇÃO - Precisa escolher perfis')
        
        if len(debug_info['rankings_direto']) == 0:
            debug_info['diagnostico'].append('❌ NENHUM RANKING SALVO - Precisa calcular os módulos')
        elif len(debug_info['rankings_direto']) < 6:
            debug_info['diagnostico'].append(f'⚠️  APENAS {len(debug_info["rankings_direto"])}/6 RANKINGS')
        
        if config and len(debug_info['rankings_com_config_id']) == 0:
            debug_info['diagnostico'].append('❌ RANKINGS SALVOS COM OUTRO configuration_id - Recalcular módulos')
        
        if not debug_info['diagnostico']:
            debug_info['diagnostico'].append('✅ Tudo parece OK')
        
        return jsonify(debug_info)
        
    except Exception as e:
        print(f"Erro no debug: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        close_db_connection(conn)

@app.route('/api/perfis/verificar')
@login_required
def api_perfis_verificar():
    """API para verificar se há perfis de peso de jogo e SG disponíveis"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Buscar rodada atual
        cursor.execute('SELECT MAX(rodada_atual) FROM acp_peso_jogo_perfis')
        rodada_result = cursor.fetchone()
        rodada_atual = rodada_result[0] if rodada_result and rodada_result[0] else None
        
        if not rodada_atual:
            return jsonify({
                'tem_perfis': False,
                'tem_peso_jogo': False,
                'tem_peso_sg': False,
                'rodada_atual': None,
                'mensagem': 'Nenhuma rodada encontrada. Execute o sistema de cálculo de perfis primeiro.'
            })
        
        # Verificar perfis de peso de jogo
        cursor.execute("""
            SELECT COUNT(*) FROM acp_peso_jogo_perfis 
            WHERE rodada_atual = %s
        """, (rodada_atual,))
        count_peso_jogo = cursor.fetchone()[0]
        
        # Verificar perfis de peso SG
        cursor.execute("""
            SELECT COUNT(*) FROM acp_peso_sg_perfis 
            WHERE rodada_atual = %s
        """, (rodada_atual,))
        count_peso_sg = cursor.fetchone()[0]
        
        tem_peso_jogo = count_peso_jogo > 0
        tem_peso_sg = count_peso_sg > 0
        tem_perfis = tem_peso_jogo and tem_peso_sg
        
        mensagem = None
        if not tem_perfis:
            if not tem_peso_jogo and not tem_peso_sg:
                mensagem = 'Não há perfis de Peso de Jogo nem Peso SG calculados. Execute o sistema de cálculo primeiro.'
            elif not tem_peso_jogo:
                mensagem = 'Não há perfis de Peso de Jogo calculados. Execute o sistema de cálculo primeiro.'
            elif not tem_peso_sg:
                mensagem = 'Não há perfis de Peso SG calculados. Execute o sistema de cálculo primeiro.'
        
        return jsonify({
            'tem_perfis': tem_perfis,
            'tem_peso_jogo': tem_peso_jogo,
            'tem_peso_sg': tem_peso_sg,
            'rodada_atual': rodada_atual,
            'count_peso_jogo': count_peso_jogo,
            'count_peso_sg': count_peso_sg,
            'mensagem': mensagem
        })
    except Exception as e:
        print(f"Erro ao verificar perfis: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        close_db_connection(conn)

@app.route('/api/modulos/status')
@login_required
def api_modulos_status():
    """API para verificar status de todos os módulos (se foram calculados)"""
    user = get_current_user()
    team_id = session.get('selected_team_id')
    
    if not team_id:
        return jsonify({'error': 'Nenhum time selecionado'}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Buscar rodada atual
        cursor.execute('SELECT MAX(rodada_atual) FROM acp_peso_jogo_perfis')
        rodada_result = cursor.fetchone()
        rodada_atual = rodada_result[0] if rodada_result and rodada_result[0] else 1
        
        # Mapeamento de módulos para posicao_id
        posicao_map = {
            'goleiro': 1, 
            'lateral': 2, 
            'zagueiro': 3, 
            'meia': 4, 
            'atacante': 5, 
            'treinador': 6
        }
        
        # Verificar cada módulo de posição
        modulos = ['goleiro', 'lateral', 'zagueiro', 'meia', 'atacante', 'treinador']
        status = {}
        
        for modulo in modulos:
            posicao_id = posicao_map[modulo]
            cursor.execute("""
                SELECT COUNT(*) > 0 as calculado
                FROM acw_rankings_teams
                WHERE team_id = %s
                  AND rodada_atual = %s
                  AND posicao_id = %s
            """, (team_id, rodada_atual, posicao_id))
            
            result = cursor.fetchone()
            status[modulo] = bool(result[0]) if result else False
        
        # Verificar se todos foram calculados
        todos_calculados = all(status.values())
        
        return jsonify({
            'status': status,
            'todos_calculados': todos_calculados,
            'rodada_atual': rodada_atual,
            'team_id': team_id
        })
    except Exception as e:
        print(f"Erro ao verificar status dos módulos: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        close_db_connection(conn)

@app.route('/modulos/<modulo>')
@login_required
@team_required
def modulo_individual(modulo):
    """Página individual de cada módulo (goleiro, lateral, etc)"""
    # Validar se o módulo é válido (apenas módulos de posição)
    modulos_validos = ['goleiro', 'lateral', 'zagueiro', 'meia', 'atacante', 'treinador']
    if modulo not in modulos_validos:
        flash('Módulo inválido', 'error')
        return redirect(url_for('modulos'))
    
    user = get_current_user()
    
    # Buscar rodada atual
    conn = get_db_connection()
    rodada_atual = 1
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT MAX(rodada_atual) FROM acp_peso_jogo_perfis')
        rodada_result = cursor.fetchone()
        rodada_atual = rodada_result[0] if rodada_result and rodada_result[0] else 1
    finally:
        close_db_connection(conn)
    
    # Defaults por posição (baseados nos pesos do Aero-RBSV)
    defaults_posicao = {
        'goleiro': {
            'FATOR_MEDIA': 1.5, 'FATOR_FF': 1.6, 'FATOR_FD': 2.0, 'FATOR_SG': 3.5,
            'FATOR_PESO_JOGO': 1.0, 'FATOR_GOL_ADVERSARIO': 3.5
        },
        'lateral': {
            'FATOR_MEDIA': 1.1, 'FATOR_DS': 1.6, 'FATOR_SG': 1.5, 'FATOR_ESCALACAO': 1.0,
            'FATOR_FF': 0.9, 'FATOR_FS': 0.8, 'FATOR_FD': 0.9, 'FATOR_G': 1.5,
            'FATOR_A': 2.5, 'FATOR_PESO_JOGO': 1.3
        },
        'zagueiro': {
            'FATOR_MEDIA': 0.4, 'FATOR_DS': 0.8, 'FATOR_SG': 2.2, 'FATOR_ESCALACAO': 0.7,
            'FATOR_PESO_JOGO': 2.2
        },
        'meia': {
            'FATOR_MEDIA': 3.1, 'FATOR_DS': 2.0, 'FATOR_FF': 2.0, 'FATOR_FS': 1.8,
            'FATOR_FD': 2.5, 'FATOR_G': 5.0, 'FATOR_A': 4.5, 'FATOR_ESCALACAO': 1.0,
            'FATOR_PESO_JOGO': 2.2
        },
        'atacante': {
            'FATOR_MEDIA': 2.4, 'FATOR_DS': 2.0, 'FATOR_FF': 3.3, 'FATOR_FS': 3.0,
            'FATOR_FD': 3.7, 'FATOR_G': 6.5, 'FATOR_A': 4.0, 'FATOR_ESCALACAO': 3.5,
            'FATOR_PESO_JOGO': 4.0
        },
        'treinador': {
            'FATOR_PESO_JOGO': 3.5
        }
    }
    
    defaults_modulo = defaults_posicao.get(modulo, defaults_posicao['goleiro'])
    
    # Buscar team_id da sessão
    team_id = session.get('selected_team_id')
    
    # Buscar pesos salvos para este time e módulo (se houver time selecionado)
    pesos_atuais = {}
    if team_id:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT weights_json FROM acw_posicao_weights
                WHERE user_id = %s AND team_id = %s AND posicao = %s
            ''', (user['id'], team_id, modulo))
            peso_row = cursor.fetchone()
            
            if peso_row and peso_row[0]:
                # Pesos salvos encontrados para este time
                pesos_salvos = peso_row[0] if isinstance(peso_row[0], dict) else json.loads(peso_row[0])
                for key, default in defaults_modulo.items():
                    pesos_atuais[key] = float(pesos_salvos.get(key, default))
            else:
                # Não há pesos salvos, usar defaults
                pesos_atuais = {key: float(default) for key, default in defaults_modulo.items()}
        finally:
            close_db_connection(conn)
    else:
        # Sem time selecionado, usar defaults
        pesos_atuais = {key: float(default) for key, default in defaults_modulo.items()}
    
    # Renderizar template específico para cada módulo
    template_map = {
        'goleiro': 'modulo_goleiro.html',
        'lateral': 'modulo_lateral.html',
        'zagueiro': 'modulo_zagueiro.html',
        'meia': 'modulo_meia.html',
        'atacante': 'modulo_atacante.html',
        'treinador': 'modulo_treinador.html'
    }
    
    template_name = template_map.get(modulo, 'modulo_goleiro.html')
    
    return render_template(template_name, 
                         modulo=modulo, 
                         rodada_atual=rodada_atual,
                         pesos_atuais=pesos_atuais)

@app.route('/modulos/<modulo>/recalcular')
@login_required
@team_required
def recalcular_modulo(modulo):
    """Endpoint para recalcular um módulo específico"""
    # Por enquanto apenas redireciona de volta (funcionalidade será implementada)
    flash('Funcionalidade de recálculo será implementada em breve', 'info')
    return redirect(url_for('modulo_individual', modulo=modulo))

@app.route('/api/modulos/<modulo>/verificar-ranking', methods=['GET'])
@login_required
def api_verificar_ranking(modulo):
    """API rápida para verificar se há ranking e pesos salvos antes de buscar todos os dados"""
    from flask import jsonify
    user = get_current_user()
    
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # Buscar rodada atual
        cursor.execute('SELECT MAX(rodada_atual) FROM acp_peso_jogo_perfis')
        rodada_result = cursor.fetchone()
        rodada_atual = rodada_result[0] if rodada_result and rodada_result[0] else 1
        
        # Obter team_id da sessão
        team_id = session.get('selected_team_id')
        if not team_id:
            return jsonify({'has_ranking': False, 'has_weights': False})
        
        # Buscar configuração do usuário para este time
        from models.user_configurations import get_user_default_configuration
        config = get_user_default_configuration(conn, user['id'], team_id)
        
        if not config:
            return jsonify({'has_ranking': False, 'has_weights': False})
        
        # Validar módulo
        posicao_map = {
            'goleiro': 1, 'lateral': 2, 'zagueiro': 3, 'meia': 4, 'atacante': 5, 'treinador': 6
        }
        posicao_id = posicao_map.get(modulo)
        
        if not posicao_id:
            return jsonify({'has_ranking': False, 'has_weights': False})
        
        # Verificar se há pesos salvos para este time e módulo
        cursor.execute('''
            SELECT weights_json FROM acw_posicao_weights
            WHERE user_id = %s AND team_id = %s AND posicao = %s
        ''', (user['id'], team_id, modulo))
        peso_row = cursor.fetchone()
        has_weights = peso_row is not None and peso_row[0] is not None
        
        # Verificar se há ranking salvo
        from models.user_rankings import get_team_rankings
        
        rankings = get_team_rankings(
            conn, 
            user['id'],
            team_id=team_id,
            configuration_id=config.get('id'),
            posicao_id=posicao_id,
            rodada_atual=rodada_atual
        )
        
        if rankings:
            ranking_salvo = rankings[0]
            ranking_data = ranking_salvo.get('ranking_data', [])
            
            if isinstance(ranking_data, dict):
                ranking_data = ranking_data.get('ranking', ranking_data.get('resultados', []))
            elif not isinstance(ranking_data, list):
                ranking_data = []
            
            has_ranking = isinstance(ranking_data, list) and len(ranking_data) > 0
            
            if has_ranking:
                return jsonify({
                    'has_ranking': True,
                    'has_weights': has_weights,
                    'rodada_atual': rodada_atual,
                    'ranking_count': len(ranking_data)
                })
        
        # Tentar sem configuration_id
        rankings_sem_config = get_team_rankings(
            conn, 
            user['id'], 
            configuration_id=None,
            posicao_id=posicao_id,
            rodada_atual=rodada_atual
        )
        
        if rankings_sem_config:
            ranking_dict = rankings_sem_config[0]
            ranking_data = ranking_dict.get('ranking_data', [])
            
            if isinstance(ranking_data, dict):
                ranking_data = ranking_data.get('ranking', ranking_data.get('resultados', []))
            elif not isinstance(ranking_data, list):
                ranking_data = []
            
            has_ranking = isinstance(ranking_data, list) and len(ranking_data) > 0
            
            if has_ranking:
                return jsonify({
                    'has_ranking': True,
                    'has_weights': has_weights,
                    'rodada_atual': rodada_atual,
                    'ranking_count': len(ranking_data)
                })
        
        return jsonify({'has_ranking': False, 'has_weights': has_weights})
        
    except Exception as e:
        print(f"Erro ao verificar ranking: {e}")
        return jsonify({'has_ranking': False, 'has_weights': False})
    finally:
        close_db_connection(conn)

@app.route('/api/modulos/<modulo>/salvar-ranking', methods=['POST'])
@login_required
def api_salvar_ranking(modulo):
    """API para salvar ranking calculado pelo frontend"""
    from flask import jsonify, request
    user = get_current_user()
    
    try:
        data = request.get_json()
        ranking_data = data.get('ranking_data')
        rodada_atual = data.get('rodada_atual')
        configuration_id = data.get('configuration_id')
        
        if not ranking_data or not rodada_atual:
            return jsonify({'error': 'Dados incompletos'}), 400
        
        # Validar módulo
        posicao_map = {
            'goleiro': 1, 'lateral': 2, 'zagueiro': 3, 'meia': 4, 'atacante': 5, 'treinador': 6
        }
        posicao_id = posicao_map.get(modulo)
        
        if not posicao_id:
            return jsonify({'error': 'Módulo inválido'}), 400
        
        # Obter team_id da sessão
        team_id = session.get('selected_team_id')
        if not team_id:
            return jsonify({'error': 'Nenhum time selecionado'}), 400
        
        # Salvar ranking
        conn = get_db_connection()
        try:
            from models.user_rankings import save_team_ranking
            ranking_id = save_team_ranking(
                conn,
                user['id'],
                team_id,
                configuration_id if configuration_id else None,
                posicao_id,
                rodada_atual,
                ranking_data
            )
            print(f"[RANKING SALVO] Usuário {user['id']}, Módulo {modulo}, Rodada {rodada_atual}, ID: {ranking_id}")
            return jsonify({'success': True, 'ranking_id': ranking_id, 'message': 'Ranking salvo com sucesso'})
        finally:
            close_db_connection(conn)
            
    except Exception as e:
        print(f"Erro ao salvar ranking: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/modulos/atacante/detalhes/<int:atleta_id>')
@login_required
def api_atacante_detalhes(atleta_id):
    """API para buscar detalhes completos de um atacante"""
    from flask import jsonify
    user = get_current_user()
    
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # Buscar rodada atual
        cursor.execute('SELECT MAX(rodada_atual) FROM acp_peso_jogo_perfis')
        rodada_result = cursor.fetchone()
        rodada_atual = rodada_result[0] if rodada_result and rodada_result[0] else 1
        
        # Buscar dados do atacante (mesma estrutura da query em api_modulo_dados)
        cursor.execute('''
            SELECT a.atleta_id, a.apelido, a.nome, a.clube_id, a.pontos_num, a.media_num, 
                   a.preco_num, a.jogos_num,
                   c.nome as clube_nome, c.abreviacao as clube_abrev
            FROM acf_atletas a
            JOIN acf_clubes c ON a.clube_id = c.id
            WHERE a.atleta_id = %s AND a.posicao_id = 5 AND a.status_id = 7
        ''', (atleta_id,))
        
        atleta_row = cursor.fetchone()
        if not atleta_row:
            return jsonify({'error': 'Atacante não encontrado'}), 404
        
        # Extrair dados do atleta de forma segura
        try:
            atleta_id_val = atleta_row[0]
            apelido = atleta_row[1]
            nome = atleta_row[2]
            clube_id = atleta_row[3]
            pontos_num = atleta_row[4]
            media_num = atleta_row[5]
            preco_num = atleta_row[6]
            jogos_num = atleta_row[7]
            clube_nome = atleta_row[8]
            clube_abrev = atleta_row[9]
            
            # Buscar escudo do clube usando a função utilitária
            from utils.team_shields import get_team_shield
            clube_escudo_url = get_team_shield(clube_id, size='45x45')
        except (IndexError, TypeError) as e:
            print(f"Erro ao extrair dados do atleta: {e}")
            print(f"Row length: {len(atleta_row) if atleta_row else 0}")
            print(f"Row content: {atleta_row}")
            return jsonify({'error': f'Erro ao processar dados do atacante: {str(e)}'}), 500
        
        if not clube_id:
            return jsonify({'error': 'Dados do atacante incompletos (clube_id ausente)'}), 500
        
        # Buscar adversário
        adversario_id = None
        try:
            cursor.execute('''
                SELECT clube_casa_id, clube_visitante_id
                FROM acf_partidas
                WHERE rodada_id = %s AND valida = TRUE
                AND (clube_casa_id = %s OR clube_visitante_id = %s)
            ''', (rodada_atual, clube_id, clube_id))
            
            partida = cursor.fetchone()
            if partida and len(partida) >= 2:
                adversario_id = partida[1] if partida[0] == clube_id else partida[0]
        except Exception as e:
            print(f"Erro ao buscar adversário: {e}")
        
        # Buscar dados do adversário
        adversario_nome = 'N/A'
        adversario_escudo_url = ''
        if adversario_id:
            try:
                cursor.execute('''
                    SELECT nome FROM acf_clubes WHERE id = %s
                ''', (adversario_id,))
                adv_row = cursor.fetchone()
                if adv_row and len(adv_row) >= 1:
                    adversario_nome = adv_row[0] if adv_row[0] else 'N/A'
                    # Buscar escudo do adversário usando a função utilitária
                    adversario_escudo_url = get_team_shield(adversario_id, size='45x45')
            except Exception as e:
                print(f"Erro ao buscar dados do adversário: {e}")
        
        # Buscar peso do jogo
        team_id = session.get('selected_team_id')
        peso_jogo = 0
        if team_id and clube_id:
            try:
                from models.user_configurations import get_user_default_configuration
                config = get_user_default_configuration(conn, user['id'], team_id)
                if config and config.get('perfil_peso_jogo'):
                    cursor.execute('''
                        SELECT peso_jogo FROM acp_peso_jogo_perfis
                        WHERE perfil_id = %s AND rodada_atual = %s AND clube_id = %s
                    ''', (config['perfil_peso_jogo'], rodada_atual, clube_id))
                    peso_row = cursor.fetchone()
                    if peso_row and len(peso_row) > 0 and peso_row[0] is not None:
                        peso_jogo = float(peso_row[0])
            except Exception as e:
                print(f"Erro ao buscar peso do jogo: {e}")
        
        # Buscar médias de scouts
        media_ds = 0
        media_ff = 0
        media_fs = 0
        media_fd = 0
        media_g = 0
        media_a = 0
        
        try:
            cursor.execute('''
                SELECT 
                    AVG(COALESCE(scout_ds, 0)) as avg_ds,
                    AVG(COALESCE(scout_ff, 0)) as avg_ff,
                    AVG(COALESCE(scout_fs, 0)) as avg_fs,
                    AVG(COALESCE(scout_fd, 0)) as avg_fd,
                    AVG(COALESCE(scout_g, 0)) as avg_g,
                    AVG(COALESCE(scout_a, 0)) as avg_a
                FROM acf_pontuados
                WHERE atleta_id = %s AND rodada_id < %s AND entrou_em_campo = TRUE
            ''', (atleta_id, rodada_atual))
            
            stats_row = cursor.fetchone()
            if stats_row and len(stats_row) >= 6:
                media_ds = float(stats_row[0]) if stats_row[0] is not None else 0
                media_ff = float(stats_row[1]) if stats_row[1] is not None else 0
                media_fs = float(stats_row[2]) if stats_row[2] is not None else 0
                media_fd = float(stats_row[3]) if stats_row[3] is not None else 0
                media_g = float(stats_row[4]) if stats_row[4] is not None else 0
                media_a = float(stats_row[5]) if stats_row[5] is not None else 0
        except Exception as e:
            print(f"Erro ao buscar médias de scouts: {e}")
        
        # Buscar número de escalações
        escalacoes = 0
        try:
            cursor.execute('''
                SELECT escalacoes FROM acf_destaques WHERE atleta_id = %s
            ''', (atleta_id,))
            escalacoes_row = cursor.fetchone()
            if escalacoes_row and escalacoes_row[0] is not None:
                escalacoes = int(escalacoes_row[0]) if escalacoes_row[0] > 0 else 0
        except Exception as e:
            print(f"Erro ao buscar escalações: {e}")
        
        # Buscar gols sofridos pelo adversário (casa e fora)
        adversario_gols_sofridos_casa = 0
        adversario_gols_sofridos_fora = 0
        adversario_jogos_casa = 0
        adversario_jogos_fora = 0
        if adversario_id:
            try:
                # Gols sofridos em casa
                cursor.execute('''
                    SELECT 
                        SUM(placar_oficial_visitante) as gols_sofridos,
                        COUNT(*) as jogos
                    FROM acf_partidas
                    WHERE clube_casa_id = %s AND rodada_id < %s AND valida = TRUE
                      AND placar_oficial_visitante IS NOT NULL
                ''', (adversario_id, rodada_atual))
                casa_row = cursor.fetchone()
                if casa_row and casa_row[1] and casa_row[1] > 0:
                    adversario_gols_sofridos_casa = float(casa_row[0]) if casa_row[0] else 0
                    adversario_jogos_casa = int(casa_row[1])
                
                # Gols sofridos fora
                cursor.execute('''
                    SELECT 
                        SUM(placar_oficial_mandante) as gols_sofridos,
                        COUNT(*) as jogos
                    FROM acf_partidas
                    WHERE clube_visitante_id = %s AND rodada_id < %s AND valida = TRUE
                      AND placar_oficial_mandante IS NOT NULL
                ''', (adversario_id, rodada_atual))
                fora_row = cursor.fetchone()
                if fora_row and fora_row[1] and fora_row[1] > 0:
                    adversario_gols_sofridos_fora = float(fora_row[0]) if fora_row[0] else 0
                    adversario_jogos_fora = int(fora_row[1])
            except Exception as e:
                print(f"Erro ao buscar gols sofridos do adversário: {e}")
        
        # Verificar se o atacante joga em casa ou fora
        joga_em_casa = False
        if adversario_id:
            try:
                cursor.execute('''
                    SELECT clube_casa_id, clube_visitante_id FROM acf_partidas
                    WHERE rodada_id = %s AND valida = TRUE
                    AND (clube_casa_id = %s OR clube_visitante_id = %s)
                ''', (rodada_atual, clube_id, clube_id))
                partida_row = cursor.fetchone()
                if partida_row and len(partida_row) >= 2:
                    joga_em_casa = (partida_row[0] == clube_id)
            except Exception as e:
                print(f"Erro ao verificar se joga em casa: {e}")
        
        # Buscar gols feitos pelo atacante nas últimas 5 rodadas
        gols_ultimas_rodadas = 0
        rodadas_analisadas = 5
        try:
            cursor.execute('''
                SELECT SUM(scout_g) as total_gols
                FROM acf_pontuados
                WHERE atleta_id = %s AND rodada_id >= %s AND rodada_id < %s
                  AND entrou_em_campo = TRUE
            ''', (atleta_id, rodada_atual - rodadas_analisadas, rodada_atual))
            gols_row = cursor.fetchone()
            if gols_row and gols_row[0] is not None:
                gols_ultimas_rodadas = int(gols_row[0]) if gols_row[0] > 0 else 0
        except Exception as e:
            print(f"Erro ao buscar gols nas últimas rodadas: {e}")
        
        # Buscar faltas cometidas e cartões nas últimas rodadas
        faltas_cometidas_ultimas = 0
        cartoes_amarelos_ultimas = 0
        cartoes_vermelhos_ultimas = 0
        try:
            cursor.execute('''
                SELECT 
                    SUM(COALESCE(scout_fc, 0)) as total_fc,
                    SUM(COALESCE(scout_ca, 0)) as total_ca,
                    SUM(COALESCE(scout_cv, 0)) as total_cv
                FROM acf_pontuados
                WHERE atleta_id = %s AND rodada_id >= %s AND rodada_id < %s
                  AND entrou_em_campo = TRUE
            ''', (atleta_id, rodada_atual - rodadas_analisadas, rodada_atual))
            faltas_cartoes_row = cursor.fetchone()
            if faltas_cartoes_row:
                faltas_cometidas_ultimas = int(faltas_cartoes_row[0]) if faltas_cartoes_row[0] else 0
                cartoes_amarelos_ultimas = int(faltas_cartoes_row[1]) if faltas_cartoes_row[1] else 0
                cartoes_vermelhos_ultimas = int(faltas_cartoes_row[2]) if faltas_cartoes_row[2] else 0
        except Exception as e:
            print(f"Erro ao buscar faltas e cartões: {e}")
        
        # Buscar pontuação total do ranking salvo (se existir)
        pontuacao_total = 0
        if team_id:
            try:
                from models.user_configurations import get_user_default_configuration
                config = get_user_default_configuration(conn, user['id'], team_id)
                if config:
                    from models.user_rankings import get_team_rankings
                    rankings = get_team_rankings(
                        conn, user['id'], team_id=team_id,
                        configuration_id=config.get('id'), posicao_id=5,
                        rodada_atual=rodada_atual
                    )
                    if rankings and len(rankings) > 0:
                        ranking_data = rankings[0].get('ranking_data', [])
                        if isinstance(ranking_data, dict):
                            ranking_data = ranking_data.get('ranking', ranking_data.get('resultados', []))
                        if isinstance(ranking_data, list):
                            for item in ranking_data:
                                if isinstance(item, dict) and item.get('atleta_id') == atleta_id:
                                    pontuacao_total = item.get('pontuacao_total', 0)
                                    break
            except Exception as e:
                print(f"Erro ao buscar pontuação do ranking: {e}")
        
        return jsonify({
            'atleta_id': atleta_id_val,
            'apelido': apelido or nome or 'N/A',
            'nome': nome or apelido or 'N/A',
            'clube_id': clube_id,
            'clube_nome': clube_nome or 'N/A',
            'clube_abrev': clube_abrev or 'N/A',
            'clube_escudo_url': clube_escudo_url or '',
            'foto_url': '',  # Fotos são carregadas via JavaScript usando getPlayerImage
            'pontos_num': float(pontos_num) if pontos_num is not None else 0,
            'media': float(media_num) if media_num is not None else 0,
            'preco': float(preco_num) if preco_num is not None else 0,
            'jogos': int(jogos_num) if jogos_num is not None else 0,
            'adversario_id': adversario_id,
            'adversario_nome': adversario_nome,
            'adversario_escudo_url': adversario_escudo_url,
            'peso_jogo': peso_jogo,
            'media_ds': media_ds,
            'media_ff': media_ff,
            'media_fs': media_fs,
            'media_fd': media_fd,
            'media_g': media_g,
            'media_a': media_a,
            'pontuacao_total': pontuacao_total,
            'escalacoes': escalacoes,
            'adversario_gols_sofridos_casa': adversario_gols_sofridos_casa,
            'adversario_gols_sofridos_fora': adversario_gols_sofridos_fora,
            'adversario_jogos_casa': adversario_jogos_casa,
            'adversario_jogos_fora': adversario_jogos_fora,
            'joga_em_casa': joga_em_casa,
            'gols_ultimas_rodadas': gols_ultimas_rodadas,
            'rodadas_analisadas': rodadas_analisadas,
            'faltas_cometidas_ultimas': faltas_cometidas_ultimas,
            'cartoes_amarelos_ultimas': cartoes_amarelos_ultimas,
            'cartoes_vermelhos_ultimas': cartoes_vermelhos_ultimas
        })
        
    except Exception as e:
        print(f"Erro ao buscar detalhes do atacante: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        close_db_connection(conn)

@app.route('/api/modulos/<modulo>/pesos', methods=['POST'])
@login_required
def api_salvar_pesos(modulo):
    """API para salvar pesos de um módulo específico por time"""
    from flask import jsonify, request
    user = get_current_user()
    
    try:
        pesos = request.get_json()
        
        # Validar módulo
        modulos_validos = ['goleiro', 'lateral', 'zagueiro', 'meia', 'atacante', 'treinador']
        if modulo not in modulos_validos:
            return jsonify({'error': 'Módulo inválido'}), 400
        
        # Obter time selecionado
        team_id = session.get('selected_team_id')
        if not team_id:
            return jsonify({'error': 'Nenhum time selecionado. Selecione um time primeiro.'}), 400
        
        # Salvar pesos no banco
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            
            # Verificar se existe registro
            cursor.execute('''
                SELECT id FROM acw_posicao_weights 
                WHERE user_id = %s AND team_id = %s AND posicao = %s
            ''', (user['id'], team_id, modulo))
            existing = cursor.fetchone()
            
            if existing:
                # Atualizar
                cursor.execute('''
                    UPDATE acw_posicao_weights 
                    SET weights_json = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = %s AND team_id = %s AND posicao = %s
                ''', (json.dumps(pesos, ensure_ascii=False), user['id'], team_id, modulo))
            else:
                # Inserir
                cursor.execute('''
                    INSERT INTO acw_posicao_weights (user_id, team_id, posicao, weights_json)
                    VALUES (%s, %s, %s, %s)
                ''', (user['id'], team_id, modulo, json.dumps(pesos, ensure_ascii=False)))
            
            conn.commit()
            return jsonify({'success': True, 'message': 'Pesos salvos com sucesso'})
        finally:
            close_db_connection(conn)
            
    except Exception as e:
        print(f"Erro ao salvar pesos: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/modulos/<modulo>/pesos-padrao', methods=['GET'])
@login_required
def api_pesos_padrao(modulo):
    """API para buscar pesos padrão recomendados de um módulo"""
    from flask import jsonify
    
    # Defaults por posição (baseados nos pesos do Aero-RBSV)
    defaults_posicao = {
        'goleiro': {
            'FATOR_MEDIA': 1.5, 'FATOR_FF': 1.6, 'FATOR_FD': 2.0, 'FATOR_SG': 3.5,
            'FATOR_PESO_JOGO': 1.0, 'FATOR_GOL_ADVERSARIO': 3.5
        },
        'lateral': {
            'FATOR_MEDIA': 1.1, 'FATOR_DS': 1.6, 'FATOR_SG': 1.5, 'FATOR_ESCALACAO': 1.0,
            'FATOR_FF': 0.9, 'FATOR_FS': 0.8, 'FATOR_FD': 0.9, 'FATOR_G': 1.5,
            'FATOR_A': 2.5, 'FATOR_PESO_JOGO': 1.3
        },
        'zagueiro': {
            'FATOR_MEDIA': 0.4, 'FATOR_DS': 0.8, 'FATOR_SG': 2.2, 'FATOR_ESCALACAO': 0.7,
            'FATOR_PESO_JOGO': 2.2
        },
        'meia': {
            'FATOR_MEDIA': 3.1, 'FATOR_DS': 2.0, 'FATOR_FF': 2.0, 'FATOR_FS': 1.8,
            'FATOR_FD': 2.5, 'FATOR_G': 5.0, 'FATOR_A': 4.5, 'FATOR_ESCALACAO': 1.0,
            'FATOR_PESO_JOGO': 2.2
        },
        'atacante': {
            'FATOR_MEDIA': 2.4, 'FATOR_DS': 2.0, 'FATOR_FF': 3.3, 'FATOR_FS': 3.0,
            'FATOR_FD': 3.7, 'FATOR_G': 6.5, 'FATOR_A': 4.0, 'FATOR_ESCALACAO': 3.5,
            'FATOR_PESO_JOGO': 4.0
        },
        'treinador': {
            'FATOR_PESO_JOGO': 3.5
        }
    }
    
    # Validar módulo
    modulos_validos = ['goleiro', 'lateral', 'zagueiro', 'meia', 'atacante', 'treinador']
    if modulo not in modulos_validos:
        return jsonify({'error': 'Módulo inválido'}), 400
    
    pesos_padrao = defaults_posicao.get(modulo, {})
    
    return jsonify({
        'success': True,
        'pesos': pesos_padrao,
        'message': 'Pesos padrão recomendados baseados no Aero-RBSV'
    })

@app.route('/api/modulos/lateral/detalhes/<int:atleta_id>')
@login_required
def api_lateral_detalhes(atleta_id):
    """API para buscar detalhes completos de um lateral"""
    from flask import jsonify
    user = get_current_user()
    
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # Buscar rodada atual
        cursor.execute('SELECT MAX(rodada_atual) FROM acp_peso_jogo_perfis')
        rodada_result = cursor.fetchone()
        rodada_atual = rodada_result[0] if rodada_result and rodada_result[0] else 1
        
        # Buscar dados do lateral
        cursor.execute('''
            SELECT a.atleta_id, a.apelido, a.nome, a.clube_id, a.pontos_num, a.media_num, 
                   a.preco_num, a.jogos_num,
                   c.nome as clube_nome, c.abreviacao as clube_abrev
            FROM acf_atletas a
            JOIN acf_clubes c ON a.clube_id = c.id
            WHERE a.atleta_id = %s AND a.posicao_id = 2 AND a.status_id = 7
        ''', (atleta_id,))
        
        atleta_row = cursor.fetchone()
        if not atleta_row:
            return jsonify({'error': 'Lateral não encontrado'}), 404
        
        # Extrair dados
        try:
            atleta_id_val = atleta_row[0]
            apelido = atleta_row[1]
            nome = atleta_row[2]
            clube_id = atleta_row[3]
            pontos_num = atleta_row[4]
            media_num = atleta_row[5]
            preco_num = atleta_row[6]
            jogos_num = atleta_row[7]
            clube_nome = atleta_row[8]
            clube_abrev = atleta_row[9]
            
            from utils.team_shields import get_team_shield
            clube_escudo_url = get_team_shield(clube_id, size='45x45')
        except (IndexError, TypeError) as e:
            print(f"Erro ao extrair dados do lateral: {e}")
            return jsonify({'error': f'Erro ao processar dados: {str(e)}'}), 500
        
        # Buscar adversário
        adversario_id = None
        try:
            cursor.execute('''
                SELECT clube_casa_id, clube_visitante_id
                FROM acf_partidas
                WHERE rodada_id = %s AND valida = TRUE
                AND (clube_casa_id = %s OR clube_visitante_id = %s)
            ''', (rodada_atual, clube_id, clube_id))
            partida = cursor.fetchone()
            if partida and len(partida) >= 2:
                adversario_id = partida[1] if partida[0] == clube_id else partida[0]
        except Exception as e:
            print(f"Erro ao buscar adversário: {e}")
        
        # Buscar dados do adversário
        adversario_nome = 'N/A'
        adversario_escudo_url = ''
        if adversario_id:
            try:
                cursor.execute('SELECT nome FROM acf_clubes WHERE id = %s', (adversario_id,))
                adv_row = cursor.fetchone()
                if adv_row and len(adv_row) >= 1:
                    adversario_nome = adv_row[0] if adv_row[0] else 'N/A'
                    adversario_escudo_url = get_team_shield(adversario_id, size='45x45')
            except Exception as e:
                print(f"Erro ao buscar dados do adversário: {e}")
        
        # Buscar peso do jogo e saldo de gol
        team_id = session.get('selected_team_id')
        peso_jogo = 0
        peso_sg = 0
        if team_id and clube_id:
            try:
                from models.user_configurations import get_user_default_configuration
                config = get_user_default_configuration(conn, user['id'], team_id)
                if config:
                    if config.get('perfil_peso_jogo'):
                        cursor.execute('''
                            SELECT peso_jogo FROM acp_peso_jogo_perfis
                            WHERE perfil_id = %s AND rodada_atual = %s AND clube_id = %s
                        ''', (config['perfil_peso_jogo'], rodada_atual, clube_id))
                        peso_row = cursor.fetchone()
                        if peso_row and len(peso_row) > 0 and peso_row[0] is not None:
                            peso_jogo = float(peso_row[0])
                    
                    if config.get('perfil_peso_sg'):
                        cursor.execute('''
                            SELECT peso_sg FROM acp_peso_sg_perfis
                            WHERE perfil_id = %s AND rodada_atual = %s AND clube_id = %s
                        ''', (config['perfil_peso_sg'], rodada_atual, clube_id))
                        sg_row = cursor.fetchone()
                        if sg_row and len(sg_row) > 0 and sg_row[0] is not None:
                            peso_sg = float(sg_row[0])
            except Exception as e:
                print(f"Erro ao buscar pesos: {e}")
        
        # Buscar médias de scouts (foco em DS, A, SG)
        media_ds = 0
        media_a = 0
        media_g = 0
        media_ff = 0
        media_fs = 0
        media_fd = 0
        
        try:
            cursor.execute('''
                SELECT 
                    AVG(COALESCE(scout_ds, 0)) as avg_ds,
                    AVG(COALESCE(scout_a, 0)) as avg_a,
                    AVG(COALESCE(scout_g, 0)) as avg_g,
                    AVG(COALESCE(scout_ff, 0)) as avg_ff,
                    AVG(COALESCE(scout_fs, 0)) as avg_fs,
                    AVG(COALESCE(scout_fd, 0)) as avg_fd
                FROM acf_pontuados
                WHERE atleta_id = %s AND rodada_id < %s AND entrou_em_campo = TRUE
            ''', (atleta_id, rodada_atual))
            
            stats_row = cursor.fetchone()
            if stats_row and len(stats_row) >= 6:
                media_ds = float(stats_row[0]) if stats_row[0] is not None else 0
                media_a = float(stats_row[1]) if stats_row[1] is not None else 0
                media_g = float(stats_row[2]) if stats_row[2] is not None else 0
                media_ff = float(stats_row[3]) if stats_row[3] is not None else 0
                media_fs = float(stats_row[4]) if stats_row[4] is not None else 0
                media_fd = float(stats_row[5]) if stats_row[5] is not None else 0
        except Exception as e:
            print(f"Erro ao buscar médias de scouts: {e}")
        
        # Buscar número de escalações
        escalacoes = 0
        try:
            cursor.execute('SELECT escalacoes FROM acf_destaques WHERE atleta_id = %s', (atleta_id,))
            escalacoes_row = cursor.fetchone()
            if escalacoes_row and escalacoes_row[0] is not None:
                escalacoes = int(escalacoes_row[0]) if escalacoes_row[0] > 0 else 0
        except Exception as e:
            print(f"Erro ao buscar escalações: {e}")
        
        # Buscar pontuação total do ranking
        pontuacao_total = 0
        if team_id:
            try:
                from models.user_configurations import get_user_default_configuration
                config = get_user_default_configuration(conn, user['id'], team_id)
                if config:
                    from models.user_rankings import get_team_rankings
                    rankings = get_team_rankings(
                        conn, user['id'], team_id=team_id,
                        configuration_id=config.get('id'), posicao_id=2,
                        rodada_atual=rodada_atual
                    )
                    if rankings and len(rankings) > 0:
                        ranking_data = rankings[0].get('ranking_data', [])
                        if isinstance(ranking_data, dict):
                            ranking_data = ranking_data.get('ranking', ranking_data.get('resultados', []))
                        if isinstance(ranking_data, list):
                            for item in ranking_data:
                                if isinstance(item, dict) and item.get('atleta_id') == atleta_id:
                                    pontuacao_total = item.get('pontuacao_total', 0)
                                    break
            except Exception as e:
                print(f"Erro ao buscar pontuação do ranking: {e}")
        
        return jsonify({
            'atleta_id': atleta_id_val,
            'apelido': apelido or nome or 'N/A',
            'nome': nome or apelido or 'N/A',
            'clube_id': clube_id,
            'clube_nome': clube_nome or 'N/A',
            'clube_abrev': clube_abrev or 'N/A',
            'clube_escudo_url': clube_escudo_url or '',
            'foto_url': '',
            'pontos_num': float(pontos_num) if pontos_num is not None else 0,
            'media': float(media_num) if media_num is not None else 0,
            'preco': float(preco_num) if preco_num is not None else 0,
            'jogos': int(jogos_num) if jogos_num is not None else 0,
            'adversario_id': adversario_id,
            'adversario_nome': adversario_nome,
            'adversario_escudo_url': adversario_escudo_url,
            'peso_jogo': peso_jogo,
            'peso_sg': peso_sg,
            'media_ds': media_ds,
            'media_a': media_a,
            'media_g': media_g,
            'media_ff': media_ff,
            'media_fs': media_fs,
            'media_fd': media_fd,
            'pontuacao_total': pontuacao_total,
            'escalacoes': escalacoes
        })
        
    except Exception as e:
        print(f"Erro ao buscar detalhes do lateral: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        close_db_connection(conn)

@app.route('/api/modulos/goleiro/detalhes/<int:atleta_id>')
@login_required
def api_goleiro_detalhes(atleta_id):
    """API para buscar detalhes completos de um goleiro"""
    from flask import jsonify
    user = get_current_user()
    
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        cursor.execute('SELECT MAX(rodada_atual) FROM acp_peso_jogo_perfis')
        rodada_result = cursor.fetchone()
        rodada_atual = rodada_result[0] if rodada_result and rodada_result[0] else 1
        
        cursor.execute('''
            SELECT a.atleta_id, a.apelido, a.nome, a.clube_id, a.pontos_num, a.media_num, 
                   a.preco_num, a.jogos_num,
                   c.nome as clube_nome, c.abreviacao as clube_abrev
            FROM acf_atletas a
            JOIN acf_clubes c ON a.clube_id = c.id
            WHERE a.atleta_id = %s AND a.posicao_id = 1 AND a.status_id = 7
        ''', (atleta_id,))
        
        atleta_row = cursor.fetchone()
        if not atleta_row:
            return jsonify({'error': 'Goleiro não encontrado'}), 404
        
        try:
            atleta_id_val = atleta_row[0]
            apelido = atleta_row[1]
            nome = atleta_row[2]
            clube_id = atleta_row[3]
            pontos_num = atleta_row[4]
            media_num = atleta_row[5]
            preco_num = atleta_row[6]
            jogos_num = atleta_row[7]
            clube_nome = atleta_row[8]
            clube_abrev = atleta_row[9]
            
            from utils.team_shields import get_team_shield
            clube_escudo_url = get_team_shield(clube_id, size='45x45')
        except (IndexError, TypeError) as e:
            return jsonify({'error': f'Erro ao processar dados: {str(e)}'}), 500
        
        # Buscar adversário
        adversario_id = None
        try:
            cursor.execute('''
                SELECT clube_casa_id, clube_visitante_id
                FROM acf_partidas
                WHERE rodada_id = %s AND valida = TRUE
                AND (clube_casa_id = %s OR clube_visitante_id = %s)
            ''', (rodada_atual, clube_id, clube_id))
            partida = cursor.fetchone()
            if partida and len(partida) >= 2:
                adversario_id = partida[1] if partida[0] == clube_id else partida[0]
        except Exception as e:
            print(f"Erro ao buscar adversário: {e}")
        
        adversario_nome = 'N/A'
        adversario_escudo_url = ''
        if adversario_id:
            try:
                cursor.execute('SELECT nome FROM acf_clubes WHERE id = %s', (adversario_id,))
                adv_row = cursor.fetchone()
                if adv_row and len(adv_row) >= 1:
                    adversario_nome = adv_row[0] if adv_row[0] else 'N/A'
                    adversario_escudo_url = get_team_shield(adversario_id, size='45x45')
            except Exception as e:
                print(f"Erro ao buscar dados do adversário: {e}")
        
        # Buscar peso do jogo e saldo de gol
        team_id = session.get('selected_team_id')
        peso_jogo = 0
        peso_sg = 0
        if team_id and clube_id:
            try:
                from models.user_configurations import get_user_default_configuration
                config = get_user_default_configuration(conn, user['id'], team_id)
                if config:
                    if config.get('perfil_peso_jogo'):
                        cursor.execute('''
                            SELECT peso_jogo FROM acp_peso_jogo_perfis
                            WHERE perfil_id = %s AND rodada_atual = %s AND clube_id = %s
                        ''', (config['perfil_peso_jogo'], rodada_atual, clube_id))
                        peso_row = cursor.fetchone()
                        if peso_row and len(peso_row) > 0 and peso_row[0] is not None:
                            peso_jogo = float(peso_row[0])
                    
                    if config.get('perfil_peso_sg'):
                        cursor.execute('''
                            SELECT peso_sg FROM acp_peso_sg_perfis
                            WHERE perfil_id = %s AND rodada_atual = %s AND clube_id = %s
                        ''', (config['perfil_peso_sg'], rodada_atual, clube_id))
                        sg_row = cursor.fetchone()
                        if sg_row and len(sg_row) > 0 and sg_row[0] is not None:
                            peso_sg = float(sg_row[0])
            except Exception as e:
                print(f"Erro ao buscar pesos: {e}")
        
        # Buscar médias de scouts (foco em DE - defesas)
        media_de = 0
        media_gols_sofridos = 0
        
        try:
            cursor.execute('''
                SELECT 
                    AVG(COALESCE(scout_de, 0)) as avg_de
                FROM acf_pontuados
                WHERE atleta_id = %s AND rodada_id < %s AND entrou_em_campo = TRUE
            ''', (atleta_id, rodada_atual))
            
            stats_row = cursor.fetchone()
            if stats_row and stats_row[0] is not None:
                media_de = float(stats_row[0])
            
            # Buscar média de gols sofridos
            cursor.execute('''
                SELECT AVG(COALESCE(pontos_num, 0))
                FROM acf_pontuados
                WHERE atleta_id = %s AND rodada_id < %s AND entrou_em_campo = TRUE
            ''', (atleta_id, rodada_atual))
            gols_row = cursor.fetchone()
            # Gols sofridos são calculados negativamente na pontuação
            # Vamos buscar das partidas
            if clube_id:
                cursor.execute('''
                    SELECT 
                        AVG(CASE WHEN clube_casa_id = %s THEN placar_oficial_visitante 
                                 WHEN clube_visitante_id = %s THEN placar_oficial_mandante 
                                 ELSE 0 END) as media_gols_sofridos
                    FROM acf_partidas
                    WHERE (clube_casa_id = %s OR clube_visitante_id = %s)
                      AND rodada_id < %s AND valida = TRUE
                      AND (placar_oficial_mandante IS NOT NULL AND placar_oficial_visitante IS NOT NULL)
                ''', (clube_id, clube_id, clube_id, clube_id, rodada_atual))
                gols_sofridos_row = cursor.fetchone()
                if gols_sofridos_row and gols_sofridos_row[0] is not None:
                    media_gols_sofridos = float(gols_sofridos_row[0])
        except Exception as e:
            print(f"Erro ao buscar médias de scouts: {e}")
        
        # Buscar número de escalações
        escalacoes = 0
        try:
            cursor.execute('SELECT escalacoes FROM acf_destaques WHERE atleta_id = %s', (atleta_id,))
            escalacoes_row = cursor.fetchone()
            if escalacoes_row and escalacoes_row[0] is not None:
                escalacoes = int(escalacoes_row[0]) if escalacoes_row[0] > 0 else 0
        except Exception as e:
            print(f"Erro ao buscar escalações: {e}")
        
        # Buscar pontuação total do ranking
        pontuacao_total = 0
        if team_id:
            try:
                from models.user_configurations import get_user_default_configuration
                config = get_user_default_configuration(conn, user['id'], team_id)
                if config:
                    from models.user_rankings import get_team_rankings
                    rankings = get_team_rankings(
                        conn, user['id'], team_id=team_id,
                        configuration_id=config.get('id'), posicao_id=1,
                        rodada_atual=rodada_atual
                    )
                    if rankings and len(rankings) > 0:
                        ranking_data = rankings[0].get('ranking_data', [])
                        if isinstance(ranking_data, dict):
                            ranking_data = ranking_data.get('ranking', ranking_data.get('resultados', []))
                        if isinstance(ranking_data, list):
                            for item in ranking_data:
                                if isinstance(item, dict) and item.get('atleta_id') == atleta_id:
                                    pontuacao_total = item.get('pontuacao_total', 0)
                                    break
            except Exception as e:
                print(f"Erro ao buscar pontuação do ranking: {e}")
        
        return jsonify({
            'atleta_id': atleta_id_val,
            'apelido': apelido or nome or 'N/A',
            'nome': nome or apelido or 'N/A',
            'clube_id': clube_id,
            'clube_nome': clube_nome or 'N/A',
            'clube_abrev': clube_abrev or 'N/A',
            'clube_escudo_url': clube_escudo_url or '',
            'foto_url': '',
            'pontos_num': float(pontos_num) if pontos_num is not None else 0,
            'media': float(media_num) if media_num is not None else 0,
            'preco': float(preco_num) if preco_num is not None else 0,
            'jogos': int(jogos_num) if jogos_num is not None else 0,
            'adversario_id': adversario_id,
            'adversario_nome': adversario_nome,
            'adversario_escudo_url': adversario_escudo_url,
            'peso_jogo': peso_jogo,
            'peso_sg': peso_sg,
            'media_de': media_de,
            'media_gols_sofridos': media_gols_sofridos,
            'pontuacao_total': pontuacao_total,
            'escalacoes': escalacoes
        })
        
    except Exception as e:
        print(f"Erro ao buscar detalhes do goleiro: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        close_db_connection(conn)

@app.route('/api/modulos/zagueiro/detalhes/<int:atleta_id>')
@login_required
def api_zagueiro_detalhes(atleta_id):
    """API para buscar detalhes completos de um zagueiro"""
    from flask import jsonify
    user = get_current_user()
    
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        cursor.execute('SELECT MAX(rodada_atual) FROM acp_peso_jogo_perfis')
        rodada_result = cursor.fetchone()
        rodada_atual = rodada_result[0] if rodada_result and rodada_result[0] else 1
        
        cursor.execute('''
            SELECT a.atleta_id, a.apelido, a.nome, a.clube_id, a.pontos_num, a.media_num, 
                   a.preco_num, a.jogos_num,
                   c.nome as clube_nome, c.abreviacao as clube_abrev
            FROM acf_atletas a
            JOIN acf_clubes c ON a.clube_id = c.id
            WHERE a.atleta_id = %s AND a.posicao_id = 3 AND a.status_id = 7
        ''', (atleta_id,))
        
        atleta_row = cursor.fetchone()
        if not atleta_row:
            return jsonify({'error': 'Zagueiro não encontrado'}), 404
        
        try:
            atleta_id_val = atleta_row[0]
            apelido = atleta_row[1]
            nome = atleta_row[2]
            clube_id = atleta_row[3]
            pontos_num = atleta_row[4]
            media_num = atleta_row[5]
            preco_num = atleta_row[6]
            jogos_num = atleta_row[7]
            clube_nome = atleta_row[8]
            clube_abrev = atleta_row[9]
            
            from utils.team_shields import get_team_shield
            clube_escudo_url = get_team_shield(clube_id, size='45x45')
        except (IndexError, TypeError) as e:
            return jsonify({'error': f'Erro ao processar dados: {str(e)}'}), 500
        
        # Buscar adversário
        adversario_id = None
        try:
            cursor.execute('''
                SELECT clube_casa_id, clube_visitante_id
                FROM acf_partidas
                WHERE rodada_id = %s AND valida = TRUE
                AND (clube_casa_id = %s OR clube_visitante_id = %s)
            ''', (rodada_atual, clube_id, clube_id))
            partida = cursor.fetchone()
            if partida and len(partida) >= 2:
                adversario_id = partida[1] if partida[0] == clube_id else partida[0]
        except Exception as e:
            print(f"Erro ao buscar adversário: {e}")
        
        adversario_nome = 'N/A'
        adversario_escudo_url = ''
        if adversario_id:
            try:
                cursor.execute('SELECT nome FROM acf_clubes WHERE id = %s', (adversario_id,))
                adv_row = cursor.fetchone()
                if adv_row and len(adv_row) >= 1:
                    adversario_nome = adv_row[0] if adv_row[0] else 'N/A'
                    adversario_escudo_url = get_team_shield(adversario_id, size='45x45')
            except Exception as e:
                print(f"Erro ao buscar dados do adversário: {e}")
        
        # Buscar peso do jogo e saldo de gol
        team_id = session.get('selected_team_id')
        peso_jogo = 0
        peso_sg = 0
        if team_id and clube_id:
            try:
                from models.user_configurations import get_user_default_configuration
                config = get_user_default_configuration(conn, user['id'], team_id)
                if config:
                    if config.get('perfil_peso_jogo'):
                        cursor.execute('''
                            SELECT peso_jogo FROM acp_peso_jogo_perfis
                            WHERE perfil_id = %s AND rodada_atual = %s AND clube_id = %s
                        ''', (config['perfil_peso_jogo'], rodada_atual, clube_id))
                        peso_row = cursor.fetchone()
                        if peso_row and len(peso_row) > 0 and peso_row[0] is not None:
                            peso_jogo = float(peso_row[0])
                    
                    if config.get('perfil_peso_sg'):
                        cursor.execute('''
                            SELECT peso_sg FROM acp_peso_sg_perfis
                            WHERE perfil_id = %s AND rodada_atual = %s AND clube_id = %s
                        ''', (config['perfil_peso_sg'], rodada_atual, clube_id))
                        sg_row = cursor.fetchone()
                        if sg_row and len(sg_row) > 0 and sg_row[0] is not None:
                            peso_sg = float(sg_row[0])
            except Exception as e:
                print(f"Erro ao buscar pesos: {e}")
        
        # Buscar médias de scouts (foco em DS - desarmes)
        media_ds = 0
        
        try:
            cursor.execute('''
                SELECT AVG(COALESCE(scout_ds, 0)) as avg_ds
                FROM acf_pontuados
                WHERE atleta_id = %s AND rodada_id < %s AND entrou_em_campo = TRUE
            ''', (atleta_id, rodada_atual))
            
            stats_row = cursor.fetchone()
            if stats_row and stats_row[0] is not None:
                media_ds = float(stats_row[0])
        except Exception as e:
            print(f"Erro ao buscar médias de scouts: {e}")
        
        # Buscar número de escalações
        escalacoes = 0
        try:
            cursor.execute('SELECT escalacoes FROM acf_destaques WHERE atleta_id = %s', (atleta_id,))
            escalacoes_row = cursor.fetchone()
            if escalacoes_row and escalacoes_row[0] is not None:
                escalacoes = int(escalacoes_row[0]) if escalacoes_row[0] > 0 else 0
        except Exception as e:
            print(f"Erro ao buscar escalações: {e}")
        
        # Buscar pontuação total do ranking
        pontuacao_total = 0
        if team_id:
            try:
                from models.user_configurations import get_user_default_configuration
                config = get_user_default_configuration(conn, user['id'], team_id)
                if config:
                    from models.user_rankings import get_team_rankings
                    rankings = get_team_rankings(
                        conn, user['id'], team_id=team_id,
                        configuration_id=config.get('id'), posicao_id=3,
                        rodada_atual=rodada_atual
                    )
                    if rankings and len(rankings) > 0:
                        ranking_data = rankings[0].get('ranking_data', [])
                        if isinstance(ranking_data, dict):
                            ranking_data = ranking_data.get('ranking', ranking_data.get('resultados', []))
                        if isinstance(ranking_data, list):
                            for item in ranking_data:
                                if isinstance(item, dict) and item.get('atleta_id') == atleta_id:
                                    pontuacao_total = item.get('pontuacao_total', 0)
                                    break
            except Exception as e:
                print(f"Erro ao buscar pontuação do ranking: {e}")
        
        return jsonify({
            'atleta_id': atleta_id_val,
            'apelido': apelido or nome or 'N/A',
            'nome': nome or apelido or 'N/A',
            'clube_id': clube_id,
            'clube_nome': clube_nome or 'N/A',
            'clube_abrev': clube_abrev or 'N/A',
            'clube_escudo_url': clube_escudo_url or '',
            'foto_url': '',
            'pontos_num': float(pontos_num) if pontos_num is not None else 0,
            'media': float(media_num) if media_num is not None else 0,
            'preco': float(preco_num) if preco_num is not None else 0,
            'jogos': int(jogos_num) if jogos_num is not None else 0,
            'adversario_id': adversario_id,
            'adversario_nome': adversario_nome,
            'adversario_escudo_url': adversario_escudo_url,
            'peso_jogo': peso_jogo,
            'peso_sg': peso_sg,
            'media_ds': media_ds,
            'pontuacao_total': pontuacao_total,
            'escalacoes': escalacoes
        })
        
    except Exception as e:
        print(f"Erro ao buscar detalhes do zagueiro: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        close_db_connection(conn)

@app.route('/api/modulos/meia/detalhes/<int:atleta_id>')
@login_required
def api_meia_detalhes(atleta_id):
    """API para buscar detalhes completos de um meia"""
    from flask import jsonify
    user = get_current_user()
    
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        cursor.execute('SELECT MAX(rodada_atual) FROM acp_peso_jogo_perfis')
        rodada_result = cursor.fetchone()
        rodada_atual = rodada_result[0] if rodada_result and rodada_result[0] else 1
        
        cursor.execute('''
            SELECT a.atleta_id, a.apelido, a.nome, a.clube_id, a.pontos_num, a.media_num, 
                   a.preco_num, a.jogos_num,
                   c.nome as clube_nome, c.abreviacao as clube_abrev
            FROM acf_atletas a
            JOIN acf_clubes c ON a.clube_id = c.id
            WHERE a.atleta_id = %s AND a.posicao_id = 4 AND a.status_id = 7
        ''', (atleta_id,))
        
        atleta_row = cursor.fetchone()
        if not atleta_row:
            return jsonify({'error': 'Meia não encontrado'}), 404
        
        try:
            atleta_id_val = atleta_row[0]
            apelido = atleta_row[1]
            nome = atleta_row[2]
            clube_id = atleta_row[3]
            pontos_num = atleta_row[4]
            media_num = atleta_row[5]
            preco_num = atleta_row[6]
            jogos_num = atleta_row[7]
            clube_nome = atleta_row[8]
            clube_abrev = atleta_row[9]
            
            from utils.team_shields import get_team_shield
            clube_escudo_url = get_team_shield(clube_id, size='45x45')
        except (IndexError, TypeError) as e:
            return jsonify({'error': f'Erro ao processar dados: {str(e)}'}), 500
        
        # Buscar adversário
        adversario_id = None
        try:
            cursor.execute('''
                SELECT clube_casa_id, clube_visitante_id
                FROM acf_partidas
                WHERE rodada_id = %s AND valida = TRUE
                AND (clube_casa_id = %s OR clube_visitante_id = %s)
            ''', (rodada_atual, clube_id, clube_id))
            partida = cursor.fetchone()
            if partida and len(partida) >= 2:
                adversario_id = partida[1] if partida[0] == clube_id else partida[0]
        except Exception as e:
            print(f"Erro ao buscar adversário: {e}")
        
        adversario_nome = 'N/A'
        adversario_escudo_url = ''
        if adversario_id:
            try:
                cursor.execute('SELECT nome FROM acf_clubes WHERE id = %s', (adversario_id,))
                adv_row = cursor.fetchone()
                if adv_row and len(adv_row) >= 1:
                    adversario_nome = adv_row[0] if adv_row[0] else 'N/A'
                    adversario_escudo_url = get_team_shield(adversario_id, size='45x45')
            except Exception as e:
                print(f"Erro ao buscar dados do adversário: {e}")
        
        # Buscar peso do jogo
        team_id = session.get('selected_team_id')
        peso_jogo = 0
        if team_id and clube_id:
            try:
                from models.user_configurations import get_user_default_configuration
                config = get_user_default_configuration(conn, user['id'], team_id)
                if config and config.get('perfil_peso_jogo'):
                    cursor.execute('''
                        SELECT peso_jogo FROM acp_peso_jogo_perfis
                        WHERE perfil_id = %s AND rodada_atual = %s AND clube_id = %s
                    ''', (config['perfil_peso_jogo'], rodada_atual, clube_id))
                    peso_row = cursor.fetchone()
                    if peso_row and len(peso_row) > 0 and peso_row[0] is not None:
                        peso_jogo = float(peso_row[0])
            except Exception as e:
                print(f"Erro ao buscar peso do jogo: {e}")
        
        # Buscar médias de scouts (foco em A - assistências e G - gols)
        media_a = 0
        media_g = 0
        media_ds = 0
        media_ff = 0
        media_fs = 0
        media_fd = 0
        
        try:
            cursor.execute('''
                SELECT 
                    AVG(COALESCE(scout_a, 0)) as avg_a,
                    AVG(COALESCE(scout_g, 0)) as avg_g,
                    AVG(COALESCE(scout_ds, 0)) as avg_ds,
                    AVG(COALESCE(scout_ff, 0)) as avg_ff,
                    AVG(COALESCE(scout_fs, 0)) as avg_fs,
                    AVG(COALESCE(scout_fd, 0)) as avg_fd
                FROM acf_pontuados
                WHERE atleta_id = %s AND rodada_id < %s AND entrou_em_campo = TRUE
            ''', (atleta_id, rodada_atual))
            
            stats_row = cursor.fetchone()
            if stats_row and len(stats_row) >= 6:
                media_a = float(stats_row[0]) if stats_row[0] is not None else 0
                media_g = float(stats_row[1]) if stats_row[1] is not None else 0
                media_ds = float(stats_row[2]) if stats_row[2] is not None else 0
                media_ff = float(stats_row[3]) if stats_row[3] is not None else 0
                media_fs = float(stats_row[4]) if stats_row[4] is not None else 0
                media_fd = float(stats_row[5]) if stats_row[5] is not None else 0
        except Exception as e:
            print(f"Erro ao buscar médias de scouts: {e}")
        
        # Buscar número de escalações
        escalacoes = 0
        try:
            cursor.execute('SELECT escalacoes FROM acf_destaques WHERE atleta_id = %s', (atleta_id,))
            escalacoes_row = cursor.fetchone()
            if escalacoes_row and escalacoes_row[0] is not None:
                escalacoes = int(escalacoes_row[0]) if escalacoes_row[0] > 0 else 0
        except Exception as e:
            print(f"Erro ao buscar escalações: {e}")
        
        # Buscar pontuação total do ranking
        pontuacao_total = 0
        if team_id:
            try:
                from models.user_configurations import get_user_default_configuration
                config = get_user_default_configuration(conn, user['id'], team_id)
                if config:
                    from models.user_rankings import get_team_rankings
                    rankings = get_team_rankings(
                        conn, user['id'], team_id=team_id,
                        configuration_id=config.get('id'), posicao_id=4,
                        rodada_atual=rodada_atual
                    )
                    if rankings and len(rankings) > 0:
                        ranking_data = rankings[0].get('ranking_data', [])
                        if isinstance(ranking_data, dict):
                            ranking_data = ranking_data.get('ranking', ranking_data.get('resultados', []))
                        if isinstance(ranking_data, list):
                            for item in ranking_data:
                                if isinstance(item, dict) and item.get('atleta_id') == atleta_id:
                                    pontuacao_total = item.get('pontuacao_total', 0)
                                    break
            except Exception as e:
                print(f"Erro ao buscar pontuação do ranking: {e}")
        
        return jsonify({
            'atleta_id': atleta_id_val,
            'apelido': apelido or nome or 'N/A',
            'nome': nome or apelido or 'N/A',
            'clube_id': clube_id,
            'clube_nome': clube_nome or 'N/A',
            'clube_abrev': clube_abrev or 'N/A',
            'clube_escudo_url': clube_escudo_url or '',
            'foto_url': '',
            'pontos_num': float(pontos_num) if pontos_num is not None else 0,
            'media': float(media_num) if media_num is not None else 0,
            'preco': float(preco_num) if preco_num is not None else 0,
            'jogos': int(jogos_num) if jogos_num is not None else 0,
            'adversario_id': adversario_id,
            'adversario_nome': adversario_nome,
            'adversario_escudo_url': adversario_escudo_url,
            'peso_jogo': peso_jogo,
            'media_a': media_a,
            'media_g': media_g,
            'media_ds': media_ds,
            'media_ff': media_ff,
            'media_fs': media_fs,
            'media_fd': media_fd,
            'pontuacao_total': pontuacao_total,
            'escalacoes': escalacoes
        })
        
    except Exception as e:
        print(f"Erro ao buscar detalhes do meia: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        close_db_connection(conn)

@app.route('/api/modulos/<modulo>/dados')
@login_required
def api_modulo_dados(modulo):
    """API para fornecer dados necessários para cálculos JavaScript"""
    from flask import jsonify
    user = get_current_user()
    
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # Buscar rodada atual
        cursor.execute('SELECT MAX(rodada_atual) FROM acp_peso_jogo_perfis')
        rodada_result = cursor.fetchone()
        rodada_atual = rodada_result[0] if rodada_result and rodada_result[0] else 1
        
        # ⭐ OBTER TEAM_ID DA SESSÃO - ISSO É CRÍTICO!
        team_id = session.get('selected_team_id')
        if not team_id:
            return jsonify({'error': 'Nenhum time selecionado'}), 400
        
        # Buscar configuração DO TIME (não só do usuário!)
        from models.user_configurations import get_user_default_configuration
        config = get_user_default_configuration(conn, user['id'], team_id)
        
        if not config:
            return jsonify({'error': 'Configuração não encontrada para este time'}), 404
        
        # Buscar partidas da rodada atual
        cursor.execute('''
            SELECT clube_casa_id, clube_visitante_id
            FROM acf_partidas
            WHERE rodada_id = %s AND valida = TRUE
        ''', (rodada_atual,))
        partidas = cursor.fetchall()
        
        adversarios_dict = {}
        for casa_id, visitante_id in partidas:
            adversarios_dict[casa_id] = visitante_id
            adversarios_dict[visitante_id] = casa_id
        
        # Buscar dados de atletas baseado no módulo
        posicao_map = {
            'goleiro': 1,
            'lateral': 2,
            'zagueiro': 3,
            'meia': 4,
            'atacante': 5,
            'treinador': 6
        }
        
        posicao_id = posicao_map.get(modulo)
        
        if not posicao_id:
            return jsonify({'error': 'Módulo inválido'}), 400
        
        # Buscar atletas com dados necessários (sem peso_jogo e peso_sg, eles vêm das tabelas de perfis)
        # Incluir status de lateral esquerdo
        cursor.execute('''
            SELECT a.atleta_id, a.apelido, a.clube_id, a.pontos_num, a.media_num, 
                   a.preco_num, a.jogos_num, c.nome as clube_nome,
                   c.abreviacao as clube_abrev,
                   CASE WHEN le.atleta_id IS NOT NULL THEN TRUE ELSE FALSE END as is_esquerdo
            FROM acf_atletas a
            JOIN acf_clubes c ON a.clube_id = c.id
            LEFT JOIN laterais_esquerdos le ON a.atleta_id = le.atleta_id
            WHERE a.posicao_id = %s AND a.status_id = 7
        ''', (posicao_id,))
        atletas_raw = cursor.fetchall()
        
        # Buscar peso_jogo e peso_sg das tabelas de perfis baseado na configuração do usuário
        perfil_peso_jogo = config['perfil_peso_jogo']
        perfil_peso_sg = config['perfil_peso_sg']
        
        # Buscar peso_jogo para todos os clubes dos atletas
        clube_ids = []
        if atletas_raw:
            clube_ids = [row[2] for row in atletas_raw if len(row) > 2]  # clube_id é o terceiro campo
        
        peso_jogo_dict = {}
        if clube_ids and len(clube_ids) > 0 and perfil_peso_jogo:
            try:
                placeholders = ','.join(['%s'] * len(clube_ids))
                cursor.execute(f'''
                    SELECT clube_id, peso_jogo
                    FROM acp_peso_jogo_perfis
                    WHERE perfil_id = %s AND rodada_atual = %s AND clube_id IN ({placeholders})
                ''', [perfil_peso_jogo, rodada_atual] + clube_ids)
                
                for row in cursor.fetchall():
                    if row and len(row) >= 2:
                        clube_id, peso_jogo = row
                        peso_jogo_dict[clube_id] = float(peso_jogo) if peso_jogo else 0
            except Exception as e:
                print(f"Erro ao buscar peso_jogo: {e}")
        
        # Buscar peso_sg para todos os clubes dos atletas
        peso_sg_dict = {}
        if clube_ids and len(clube_ids) > 0 and perfil_peso_sg:
            try:
                placeholders = ','.join(['%s'] * len(clube_ids))
                cursor.execute(f'''
                    SELECT clube_id, peso_sg
                    FROM acp_peso_sg_perfis
                    WHERE perfil_id = %s AND rodada_atual = %s AND clube_id IN ({placeholders})
                ''', [perfil_peso_sg, rodada_atual] + clube_ids)
                
                for row in cursor.fetchall():
                    if row and len(row) >= 2:
                        clube_id, peso_sg = row
                        peso_sg_dict[clube_id] = float(peso_sg) if peso_sg else 0
            except Exception as e:
                print(f"Erro ao buscar peso_sg: {e}")
        
        # Buscar escudos
        from utils.team_shields import get_team_shield
        
        atletas = []
        for row in atletas_raw:
            if not row or len(row) < 10: # Agora são 10 colunas
                continue
            try:
                atleta_id, apelido, clube_id, pontos, media, preco, jogos, clube_nome, clube_abrev, is_esquerdo = row
                escudo_url = get_team_shield(clube_id, size='45x45')
                adversario_id = adversarios_dict.get(clube_id)
                
                atletas.append({
                    'atleta_id': atleta_id,
                    'apelido': apelido,
                    'clube_id': clube_id,
                    'clube_nome': clube_nome,
                    'clube_abrev': clube_abrev,
                    'clube_escudo_url': escudo_url,
                    'pontos_num': float(pontos) if pontos else 0,
                    'media_num': float(media) if media else 0,
                    'preco_num': float(preco) if preco else 0,
                    'jogos_num': int(jogos) if jogos else 0,
                    'peso_jogo': peso_jogo_dict.get(clube_id, 0),
                    'peso_sg': peso_sg_dict.get(clube_id, 0),
                    'adversario_id': adversario_id,
                    'is_esquerdo': is_esquerdo
                })
            except Exception as e:
                print(f"Erro ao processar atleta: {e}, row: {row}")
                continue
        
        # Buscar dados de pontuados para cálculos
        # 1. Buscar médias de scouts por atleta
        atleta_ids = [a['atleta_id'] for a in atletas]
        pontuados_data = {}
        
        if atleta_ids:
            placeholders = ','.join(['%s'] * len(atleta_ids))
            try:
                cursor.execute(f'''
                    SELECT atleta_id, 
                           AVG(scout_ds) as avg_ds,
                           AVG(scout_ff) as avg_ff, 
                           AVG(scout_fd) as avg_fd,
                           AVG(scout_fs) as avg_fs,
                           AVG(scout_g) as avg_g,
                           AVG(scout_a) as avg_a
                    FROM acf_pontuados
                    WHERE atleta_id IN ({placeholders}) AND rodada_id <= %s AND entrou_em_campo = TRUE
                    GROUP BY atleta_id
                ''', atleta_ids + [rodada_atual - 1])
                
                for row in cursor.fetchall():
                    if row and len(row) >= 7:
                        atleta_id, avg_ds, avg_ff, avg_fd, avg_fs, avg_g, avg_a = row
                        pontuados_data[atleta_id] = {
                            'avg_ds': float(avg_ds) if avg_ds else 0,
                            'avg_ff': float(avg_ff) if avg_ff else 0,
                            'avg_fd': float(avg_fd) if avg_fd else 0,
                            'avg_fs': float(avg_fs) if avg_fs else 0,
                            'avg_g': float(avg_g) if avg_g else 0,
                            'avg_a': float(avg_a) if avg_a else 0
                        }
            except Exception as e:
                print(f"Erro ao buscar dados de pontuados por atleta: {e}")
        
        # 2. Buscar médias de scouts cedidos por adversários (por posição)
        if adversarios_dict and posicao_id:
            adversario_ids = list(set(adversarios_dict.values()))
            if adversario_ids and len(adversario_ids) > 0:
                placeholders = ','.join(['%s'] * len(adversario_ids))
                try:
                    # Buscar média de scouts cedidos pelos adversários para esta posição
                    # Com distinção entre laterais esquerdos e direitos se for lateral (posicao_id = 2)
                    
                    if posicao_id == 2: # Lateral
                        cursor.execute(f'''
                            SELECT 
                                   CASE 
                                       WHEN p.clube_id = pt.clube_casa_id THEN pt.clube_visitante_id
                                       ELSE pt.clube_casa_id
                                   END as adversario_id,
                                   AVG(p.scout_ds) as avg_ds_cedidos,
                                   AVG(CASE WHEN le.atleta_id IS NOT NULL THEN p.scout_ds END) as avg_ds_cedidos_esq,
                                   AVG(CASE WHEN le.atleta_id IS NULL THEN p.scout_ds END) as avg_ds_cedidos_dir,
                                   
                                   AVG(p.scout_ff) as avg_ff_cedidos,
                                   AVG(CASE WHEN le.atleta_id IS NOT NULL THEN p.scout_ff END) as avg_ff_cedidos_esq,
                                   AVG(CASE WHEN le.atleta_id IS NULL THEN p.scout_ff END) as avg_ff_cedidos_dir,
                                   
                                   AVG(p.scout_fs) as avg_fs_cedidos,
                                   AVG(CASE WHEN le.atleta_id IS NOT NULL THEN p.scout_fs END) as avg_fs_cedidos_esq,
                                   AVG(CASE WHEN le.atleta_id IS NULL THEN p.scout_fs END) as avg_fs_cedidos_dir,
                                   
                                   AVG(p.scout_fd) as avg_fd_cedidos,
                                   AVG(CASE WHEN le.atleta_id IS NOT NULL THEN p.scout_fd END) as avg_fd_cedidos_esq,
                                   AVG(CASE WHEN le.atleta_id IS NULL THEN p.scout_fd END) as avg_fd_cedidos_dir,
                                   
                                   AVG(p.scout_g) as avg_g_cedidos,
                                   AVG(CASE WHEN le.atleta_id IS NOT NULL THEN p.scout_g END) as avg_g_cedidos_esq,
                                   AVG(CASE WHEN le.atleta_id IS NULL THEN p.scout_g END) as avg_g_cedidos_dir,
                                   
                                   AVG(p.scout_a) as avg_a_cedidos,
                                   AVG(CASE WHEN le.atleta_id IS NOT NULL THEN p.scout_a END) as avg_a_cedidos_esq,
                                   AVG(CASE WHEN le.atleta_id IS NULL THEN p.scout_a END) as avg_a_cedidos_dir
                            FROM acf_pontuados p
                            JOIN acf_partidas pt ON p.rodada_id = pt.rodada_id
                            LEFT JOIN laterais_esquerdos le ON p.atleta_id = le.atleta_id
                            WHERE p.posicao_id = %s 
                              AND ((pt.clube_casa_id IN ({placeholders}) AND p.clube_id = pt.clube_visitante_id)
                                   OR (pt.clube_visitante_id IN ({placeholders}) AND p.clube_id = pt.clube_casa_id))
                              AND p.rodada_id <= %s AND p.entrou_em_campo = TRUE
                            GROUP BY adversario_id
                        ''', [posicao_id] + adversario_ids + adversario_ids + [rodada_atual - 1])
                        
                        for row in cursor.fetchall():
                            if row:
                                clube_id = row[0]
                                if clube_id not in pontuados_data:
                                    pontuados_data[clube_id] = {}
                                
                                # Mapear colunas para o dicionário
                                # DS
                                pontuados_data[clube_id]['avg_ds_cedidos'] = float(row[1]) if row[1] is not None else 0
                                pontuados_data[clube_id]['avg_ds_cedidos_esq'] = float(row[2]) if row[2] is not None else 0
                                pontuados_data[clube_id]['avg_ds_cedidos_dir'] = float(row[3]) if row[3] is not None else 0
                                
                                # FF
                                pontuados_data[clube_id]['avg_ff_cedidos'] = float(row[4]) if row[4] is not None else 0
                                pontuados_data[clube_id]['avg_ff_cedidos_esq'] = float(row[5]) if row[5] is not None else 0
                                pontuados_data[clube_id]['avg_ff_cedidos_dir'] = float(row[6]) if row[6] is not None else 0
                                
                                # FS
                                pontuados_data[clube_id]['avg_fs_cedidos'] = float(row[7]) if row[7] is not None else 0
                                pontuados_data[clube_id]['avg_fs_cedidos_esq'] = float(row[8]) if row[8] is not None else 0
                                pontuados_data[clube_id]['avg_fs_cedidos_dir'] = float(row[9]) if row[9] is not None else 0
                                
                                # FD
                                pontuados_data[clube_id]['avg_fd_cedidos'] = float(row[10]) if row[10] is not None else 0
                                pontuados_data[clube_id]['avg_fd_cedidos_esq'] = float(row[11]) if row[11] is not None else 0
                                pontuados_data[clube_id]['avg_fd_cedidos_dir'] = float(row[12]) if row[12] is not None else 0
                                
                                # G
                                pontuados_data[clube_id]['avg_g_cedidos'] = float(row[13]) if row[13] is not None else 0
                                pontuados_data[clube_id]['avg_g_cedidos_esq'] = float(row[14]) if row[14] is not None else 0
                                pontuados_data[clube_id]['avg_g_cedidos_dir'] = float(row[15]) if row[15] is not None else 0
                                
                                # A
                                pontuados_data[clube_id]['avg_a_cedidos'] = float(row[16]) if row[16] is not None else 0
                                pontuados_data[clube_id]['avg_a_cedidos_esq'] = float(row[17]) if row[17] is not None else 0
                                pontuados_data[clube_id]['avg_a_cedidos_dir'] = float(row[18]) if row[18] is not None else 0
                                
                    else:
                        # Comportamento padrão para outras posições (sem distinção)
                        # AGORA BUSCANDO TODOS OS SCOUTS CEDIDOS
                        cursor.execute(f'''
                            SELECT 
                                   CASE 
                                       WHEN p.clube_id = pt.clube_casa_id THEN pt.clube_visitante_id
                                       ELSE pt.clube_casa_id
                                   END as adversario_id,
                                   AVG(p.scout_ds) as avg_ds_cedidos,
                                   AVG(p.scout_ff) as avg_ff_cedidos,
                                   AVG(p.scout_fs) as avg_fs_cedidos,
                                   AVG(p.scout_fd) as avg_fd_cedidos,
                                   AVG(p.scout_g) as avg_g_cedidos,
                                   AVG(p.scout_a) as avg_a_cedidos
                            FROM acf_pontuados p
                            JOIN acf_partidas pt ON p.rodada_id = pt.rodada_id
                            WHERE p.posicao_id = %s 
                              AND ((pt.clube_casa_id IN ({placeholders}) AND p.clube_id = pt.clube_visitante_id)
                                   OR (pt.clube_visitante_id IN ({placeholders}) AND p.clube_id = pt.clube_casa_id))
                              AND p.rodada_id <= %s AND p.entrou_em_campo = TRUE
                            GROUP BY adversario_id
                        ''', [posicao_id] + adversario_ids + adversario_ids + [rodada_atual - 1])
                        
                        for row in cursor.fetchall():
                            if row:
                                clube_id = row[0]
                                if clube_id not in pontuados_data:
                                    pontuados_data[clube_id] = {}
                                
                                pontuados_data[clube_id]['avg_ds_cedidos'] = float(row[1]) if row[1] is not None else 0
                                pontuados_data[clube_id]['avg_ff_cedidos'] = float(row[2]) if row[2] is not None else 0
                                pontuados_data[clube_id]['avg_fs_cedidos'] = float(row[3]) if row[3] is not None else 0
                                pontuados_data[clube_id]['avg_fd_cedidos'] = float(row[4]) if row[4] is not None else 0
                                pontuados_data[clube_id]['avg_g_cedidos'] = float(row[5]) if row[5] is not None else 0
                                pontuados_data[clube_id]['avg_a_cedidos'] = float(row[6]) if row[6] is not None else 0
                except Exception as e:
                    print(f"Erro ao buscar scouts cedidos por adversários: {e}")
        
        # 3. Buscar escalações (top 20 destaques)
        escalacoes_data = {}
        try:
            cursor.execute('''
                SELECT atleta_id, escalacoes
                FROM acf_destaques
                ORDER BY escalacoes DESC
                LIMIT 20
            ''')
            for row in cursor.fetchall():
                if row and len(row) >= 2:
                    atleta_id, escalacoes = row
                    escalacoes_data[atleta_id] = float(escalacoes) if escalacoes else 0
        except Exception as e:
            print(f"Erro ao buscar escalações: {e}")
        
        # Buscar dados de partidas para média de gols
        gols_data = {}
        if adversarios_dict:
            adversario_ids = list(set(adversarios_dict.values()))
            if adversario_ids and len(adversario_ids) > 0:
                placeholders = ','.join(['%s'] * len(adversario_ids))
                try:
                    # Query simplificada: buscar gols marcados por cada clube adversário
                    cursor.execute(f'''
                        SELECT 
                            clube_casa_id as clube_id,
                            SUM(placar_oficial_mandante) as gols_marcados,
                            COUNT(*) as jogos
                        FROM acf_partidas
                        WHERE clube_casa_id IN ({placeholders})
                          AND rodada_id < %s AND valida = TRUE 
                          AND placar_oficial_mandante IS NOT NULL
                        GROUP BY clube_casa_id
                    ''', adversario_ids + [rodada_atual])
                    
                    for row in cursor.fetchall():
                        if row and len(row) >= 3:
                            clube_id, gols_marcados, jogos = row
                            if jogos and jogos > 0:
                                gols_data[clube_id] = {
                                    'gols_marcados': float(gols_marcados) if gols_marcados else 0,
                                    'jogos': int(jogos),
                                    'media_gols': float(gols_marcados) / float(jogos) if jogos > 0 else 0
                                }
                    
                    # Também buscar para clubes visitantes
                    cursor.execute(f'''
                        SELECT 
                            clube_visitante_id as clube_id,
                            SUM(placar_oficial_visitante) as gols_marcados,
                            COUNT(*) as jogos
                        FROM acf_partidas
                        WHERE clube_visitante_id IN ({placeholders})
                          AND rodada_id < %s AND valida = TRUE 
                          AND placar_oficial_visitante IS NOT NULL
                        GROUP BY clube_visitante_id
                    ''', adversario_ids + [rodada_atual])
                    
                    for row in cursor.fetchall():
                        if row and len(row) >= 3:
                            clube_id, gols_marcados, jogos = row
                            if clube_id in gols_data:
                                # Somar aos dados existentes
                                gols_data[clube_id]['gols_marcados'] += float(gols_marcados) if gols_marcados else 0
                                gols_data[clube_id]['jogos'] += int(jogos)
                                total_jogos = gols_data[clube_id]['jogos']
                                gols_data[clube_id]['media_gols'] = gols_data[clube_id]['gols_marcados'] / total_jogos if total_jogos > 0 else 0
                            elif jogos and jogos > 0:
                                gols_data[clube_id] = {
                                    'gols_marcados': float(gols_marcados) if gols_marcados else 0,
                                    'jogos': int(jogos),
                                    'media_gols': float(gols_marcados) / float(jogos) if jogos > 0 else 0
                                }
                except Exception as e:
                    print(f"Erro ao buscar dados de gols: {e}")
                    import traceback
                    traceback.print_exc()
        
        # Buscar nomes dos clubes adversários
        clubes_dict = {}
        if adversarios_dict:
            todos_clube_ids = set(adversarios_dict.keys()) | set(adversarios_dict.values())
            if todos_clube_ids:
                placeholders = ','.join(['%s'] * len(todos_clube_ids))
                cursor.execute(f'''
                    SELECT id, nome, abreviacao
                    FROM acf_clubes
                    WHERE id IN ({placeholders})
                ''', list(todos_clube_ids))
                
                for row in cursor.fetchall():
                    clube_id, nome, abreviacao = row
                    escudo_url = get_team_shield(clube_id, size='45x45')
                    clubes_dict[clube_id] = {
                        'nome': nome,
                        'abreviacao': abreviacao,
                        'escudo_url': escudo_url
                    }
        
        # Adicionar nome do adversário aos atletas
        for atleta in atletas:
            if atleta['adversario_id'] and atleta['adversario_id'] in clubes_dict:
                atleta['adversario_nome'] = clubes_dict[atleta['adversario_id']]['nome']
            else:
                atleta['adversario_nome'] = 'N/A'
        
        # Buscar pesos do módulo
        from utils.weights import get_weight
        
        # Defaults por posição (baseados nos pesos do Aero-RBSV)
        defaults_posicao = {
            'goleiro': {
                'FATOR_MEDIA': 1.5, 'FATOR_FF': 1.6, 'FATOR_FD': 2.0, 'FATOR_SG': 3.5,
                'FATOR_PESO_JOGO': 1.0, 'FATOR_GOL_ADVERSARIO': 3.5
            },
            'lateral': {
                'FATOR_MEDIA': 1.1, 'FATOR_DS': 1.6, 'FATOR_SG': 1.5, 'FATOR_ESCALACAO': 1.0,
                'FATOR_FF': 0.9, 'FATOR_FS': 0.8, 'FATOR_FD': 0.9, 'FATOR_G': 1.5,
                'FATOR_A': 2.5, 'FATOR_PESO_JOGO': 1.3
            },
            'zagueiro': {
                'FATOR_MEDIA': 0.4, 'FATOR_DS': 0.8, 'FATOR_SG': 2.2, 'FATOR_ESCALACAO': 0.7,
                'FATOR_PESO_JOGO': 2.2
            },
            'meia': {
                'FATOR_MEDIA': 3.1, 'FATOR_DS': 2.0, 'FATOR_FF': 2.0, 'FATOR_FS': 1.8,
                'FATOR_FD': 2.5, 'FATOR_G': 5.0, 'FATOR_A': 4.5, 'FATOR_ESCALACAO': 1.0,
                'FATOR_PESO_JOGO': 2.2
            },
            'atacante': {
                'FATOR_MEDIA': 2.4, 'FATOR_DS': 2.0, 'FATOR_FF': 3.3, 'FATOR_FS': 3.0,
                'FATOR_FD': 3.7, 'FATOR_G': 6.5, 'FATOR_A': 4.0, 'FATOR_ESCALACAO': 3.5,
                'FATOR_PESO_JOGO': 4.0
            },
            'treinador': {
                'FATOR_PESO_JOGO': 3.5
            }
        }
        
        defaults_modulo = defaults_posicao.get(modulo, defaults_posicao['goleiro'])
        
        # Buscar pesos do time selecionado
        team_id = session.get('selected_team_id')
        if not team_id:
            return jsonify({'error': 'Nenhum time selecionado. Selecione um time primeiro.'}), 400
        
        # Buscar pesos salvos para este time e módulo
        cursor.execute('''
            SELECT weights_json FROM acw_posicao_weights
            WHERE user_id = %s AND team_id = %s AND posicao = %s
        ''', (user['id'], team_id, modulo))
        peso_row = cursor.fetchone()
        
        if peso_row and peso_row[0]:
            pesos_salvos = peso_row[0] if isinstance(peso_row[0], dict) else json.loads(peso_row[0])
        else:
            # Se não houver pesos salvos, usar defaults
            pesos_salvos = {}
        
        pesos = {}
        for key, default in defaults_modulo.items():
            pesos[key] = float(pesos_salvos.get(key, default))
        
        # Verificar se já existe ranking salvo para esta rodada e módulo
        from models.user_rankings import get_team_rankings
        posicao_map = {
            'goleiro': 1, 'lateral': 2, 'zagueiro': 3, 'meia': 4, 'atacante': 5, 'treinador': 6
        }
        posicao_id = posicao_map.get(modulo)
        
        ranking_salvo = None
        if posicao_id:
            rankings = get_team_rankings(
                conn, 
                user['id'],
                team_id=team_id,
                configuration_id=config.get('id'),
                posicao_id=posicao_id,
                rodada_atual=rodada_atual
            )
            if rankings:
                ranking_salvo = rankings[0]  # Pegar o mais recente
                # Converter ranking_data para lista se for dict
                ranking_data = ranking_salvo.get('ranking_data', [])
                # Garantir que seja uma lista
                if isinstance(ranking_data, dict):
                    # Se for dict, tentar extrair lista
                    ranking_data = ranking_data.get('ranking', ranking_data.get('resultados', []))
                elif not isinstance(ranking_data, list):
                    ranking_data = []
                ranking_salvo = ranking_data if (isinstance(ranking_data, list) and len(ranking_data) > 0) else None
                if ranking_salvo:
                    print(f"[API] [OK] Ranking encontrado com configuration_id - tamanho: {len(ranking_data)}")
                else:
                    print(f"[API] [AVISO] Ranking encontrado mas vazio ou formato incorreto - tipo: {type(ranking_data)}")
            
            # Se não encontrou com configuration_id, tentar buscar sem (para compatibilidade)
            if not ranking_salvo:
                rankings_sem_config = get_team_rankings(
                    conn, 
                    user['id'],
                    team_id=team_id,
                    configuration_id=None,
                    posicao_id=posicao_id,
                    rodada_atual=rodada_atual
                )
                if rankings_sem_config:
                    ranking_dict = rankings_sem_config[0]
                    ranking_data = ranking_dict.get('ranking_data', [])
                    # Garantir que seja uma lista
                    if isinstance(ranking_data, dict):
                        ranking_data = ranking_data.get('ranking', ranking_data.get('resultados', []))
                    elif not isinstance(ranking_data, list):
                        ranking_data = []
                    ranking_salvo = ranking_data if (isinstance(ranking_data, list) and len(ranking_data) > 0) else None
                    if ranking_salvo:
                        print(f"[API] [OK] Ranking encontrado sem configuration_id - tamanho: {len(ranking_data)}")
        
        # Log final decisivo
        if ranking_salvo and isinstance(ranking_salvo, list) and len(ranking_salvo) > 0:
            print(f"[API] [OK] Ranking salvo VALIDO encontrado: {len(ranking_salvo)} itens - NAO VAI CALCULAR")
            print(f"[API] Primeiro item do ranking: {ranking_salvo[0] if ranking_salvo else 'N/A'}")
        else:
            print("[API] [ERRO] Nenhum ranking salvo encontrado ou invalido - VAI CALCULAR AUTOMATICAMENTE")
            ranking_salvo = None  # Garantir que seja None se inválido
        
        # Garantir que ranking_salvo seja uma lista ou None antes de retornar
        ranking_para_json = ranking_salvo if (ranking_salvo and isinstance(ranking_salvo, list) and len(ranking_salvo) > 0) else None
        
        print(f"[API] Retornando ranking_salvo para JSON: tipo={type(ranking_para_json)}, tamanho={len(ranking_para_json) if ranking_para_json else 0}")
        
        return jsonify({
            'rodada_atual': rodada_atual,
            'perfil_peso_jogo': config['perfil_peso_jogo'],
            'perfil_peso_sg': config['perfil_peso_sg'],
            'atletas': atletas,
            'adversarios_dict': adversarios_dict,
            'clubes_dict': clubes_dict,
            'pontuados_data': pontuados_data,
            'gols_data': gols_data,
            'escalacoes_data': escalacoes_data,
            'pesos': pesos,
            'ranking_salvo': ranking_para_json,  # Usar versão validada
            'configuration_id': config.get('id')
        })
        
    except Exception as e:
        print(f"Erro ao buscar dados do módulo: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        close_db_connection(conn)

@app.route('/modulos/escalacao-ideal')
@login_required
@team_required
def modulo_escalacao_ideal():
    """Página do módulo de escalação ideal"""
    # Verificar se há time selecionado
    team_id = session.get('selected_team_id')
    if not team_id:
        flash('Selecione um time primeiro na sidebar para calcular a escalação ideal', 'warning')
        return redirect(url_for('modulos'))
    
    # Buscar permissões do usuário
    from utils.permissions import get_user_permissions
    from models.plans import check_permission
    user = get_current_user()
    permissions = get_user_permissions(user['id'])
    
    # Se não tiver permissão para ver escalação ideal (usuário Free), redirecionar para upgrade
    if not check_permission(user['id'], 'verEscalacaoIdealCompleta'):
        flash('A Escalação Ideal está disponível apenas no plano Avançado ou Pro. Faça upgrade para acessar!', 'warning')
        return redirect(url_for('pagamento.index'))
    
    return render_template('modulo_escalacao_ideal.html', permissions=permissions['permissions'])

@app.route('/api/credenciais/lista')
@login_required
def api_credenciais_lista():
    """API para listar todas as credenciais (times) de um usuário"""
    user = get_current_user()
    conn = get_db_connection()
    
    try:
        from models.teams import get_all_user_teams, create_teams_table
        from models.plans import get_max_times
        create_teams_table(conn)
        
        times = get_all_user_teams(conn, user['id'])
        selected_id = session.get('selected_team_id')
        
        # Buscar limite de times do plano
        max_times = get_max_times(user['id'])
        
        # Verificar se o time selecionado ainda está disponível (dentro do limite)
        selected_team_disponivel = False
        if selected_id:
            # Encontrar o índice do time selecionado
            selected_index = None
            for idx, time in enumerate(times):
                if time['id'] == selected_id:
                    selected_index = idx
                    break
            
            # Verificar se o time está dentro do limite
            if selected_index is not None and selected_index < max_times:
                selected_team_disponivel = True
            else:
                # Time selecionado não está mais disponível
                print(f"[DEBUG API] Time selecionado {selected_id} não está mais disponível (índice: {selected_index}, limite: {max_times})")
                selected_id = None
                session.pop('selected_team_id', None)
        
        # Se não houver time selecionado e houver times disponíveis, selecionar o primeiro disponível
        if not selected_id and times and len(times) > 0:
            # Selecionar o primeiro time dentro do limite (índice 0, desde que max_times > 0)
            if max_times > 0 and len(times) > 0:
                selected_id = times[0]['id']
                session['selected_team_id'] = selected_id
                print(f"[DEBUG API] Selecionando automaticamente o primeiro time disponível: {selected_id}")
        
        # Buscar escudos dinamicamente para cada time
        from api_cartola import fetch_team_info_by_team_id
        times_list = []
        for idx, time in enumerate(times):
            team_shield_url = None
            token_error = False
            try:
                print(f"[DEBUG API] Buscando escudo do time {idx + 1}/{len(times)}: ID={time['id']}, Nome={time.get('team_name', 'N/A')}")
                team_info = fetch_team_info_by_team_id(conn, time['id'])
                if team_info and 'time' in team_info and isinstance(team_info['time'], dict):
                    time_data = team_info['time']
                    # Priorizar url_escudo_png, depois url_escudo_svg, depois foto_perfil
                    if 'url_escudo_png' in time_data and time_data['url_escudo_png']:
                        team_shield_url = time_data['url_escudo_png']
                        print(f"[DEBUG API] Time {time['id']}: Escudo encontrado (url_escudo_png): {team_shield_url}")
                    elif 'url_escudo_svg' in time_data and time_data['url_escudo_svg']:
                        team_shield_url = time_data['url_escudo_svg']
                        print(f"[DEBUG API] Time {time['id']}: Escudo encontrado (url_escudo_svg): {team_shield_url}")
                    elif 'foto_perfil' in time_data and time_data['foto_perfil']:
                        team_shield_url = time_data['foto_perfil']
                        print(f"[DEBUG API] Time {time['id']}: Escudo encontrado (foto_perfil): {team_shield_url}")
                    else:
                        print(f"[DEBUG API] Time {time['id']}: Nenhum escudo encontrado na resposta. Chaves disponíveis: {list(time_data.keys())}")
                elif team_info is None:
                    # Se team_info é None, provavelmente houve erro de token (401)
                    print(f"[DEBUG API] Time {time['id']}: team_info é None - provável erro de token (401)")
                    token_error = True
                else:
                    print(f"[DEBUG API] Time {time['id']}: Resposta inválida ou sem 'time'. team_info: {team_info}")
            except Exception as e:
                print(f"[DEBUG API] Erro ao buscar escudo do time {time['id']}: {e}")
                import traceback
                traceback.print_exc()
                # Se o erro for relacionado a token, marcar como erro de token
                if '401' in str(e) or 'token' in str(e).lower():
                    token_error = True
            
            # Verificar se o time está disponível (dentro do limite do plano)
            is_disponivel = idx < max_times
            
            times_list.append({
                'id': time['id'],
                'team_name': time['team_name'] or f"Time {time['id']}",
                'team_shield_url': team_shield_url,
                'token_error': token_error,  # Indicador de erro de token
                'created_at': time['created_at'].isoformat() if time['created_at'] else None,
                'selected': time['id'] == selected_id,
                'disponivel': is_disponivel  # Indica se o time está disponível no plano atual
            })
            print(f"[DEBUG API] Time {time['id']} adicionado à lista com shield_url: {team_shield_url}, token_error: {token_error}")
        
        return jsonify({
            'times': times_list,
            'selected_id': selected_id
        })
    except Exception as e:
        print(f"Erro ao listar credenciais: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        close_db_connection(conn)

@app.route('/api/time/selecionar', methods=['POST'])
@login_required
def api_selecionar_time():
    """API para selecionar o time ativo"""
    user = get_current_user()
    data = request.get_json()
    team_id = data.get('team_id')
    
    if not team_id:
        return jsonify({'error': 'team_id é obrigatório'}), 400
    
    # Verificar se o time pertence ao usuário
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id FROM acw_teams
            WHERE id = %s AND user_id = %s
        ''', (team_id, user['id']))
        
        if not cursor.fetchone():
            return jsonify({'error': 'Time não encontrado ou não pertence ao usuário'}), 404
        
        session['selected_team_id'] = team_id
        return jsonify({'success': True, 'selected_id': team_id})
    except Exception as e:
        print(f"Erro ao selecionar time: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        close_db_connection(conn)

@app.route('/api/time/<int:team_id>/escudo')
@login_required
def api_time_escudo(team_id):
    """API para buscar o escudo de um time dinamicamente"""
    user = get_current_user()
    conn = get_db_connection()
    
    try:
        from models.teams import get_team
        from api_cartola import fetch_team_info_by_team_id
        
        print(f"[DEBUG API] /api/time/{team_id}/escudo - Buscando escudo para time {team_id}")
        
        # Verificar se o time pertence ao usuário
        team = get_team(conn, team_id, user['id'])
        if not team:
            print(f"[DEBUG API] Time {team_id} não encontrado ou não pertence ao usuário {user['id']}")
            return jsonify({'error': 'Time não encontrado ou não pertence ao usuário'}), 404
        
        print(f"[DEBUG API] Time {team_id} encontrado: {team.get('team_name', 'N/A')}")
        
        # Buscar informações do time
        team_info = fetch_team_info_by_team_id(conn, team_id)
        print(f"[DEBUG API] Resposta fetch_team_info_by_team_id para time {team_id}:", team_info is not None)
        
        if not team_info or 'time' not in team_info:
            print(f"[DEBUG API] Time {team_id}: Resposta inválida ou sem 'time'. team_info: {team_info}")
            # Se team_info é None, provavelmente houve erro de token (401)
            if team_info is None:
                return jsonify({'team_shield_url': None, 'token_error': True})
            return jsonify({'team_shield_url': None, 'token_error': False})
        
        time_data = team_info['time']
        print(f"[DEBUG API] Time {team_id}: Chaves disponíveis em time_data: {list(time_data.keys()) if isinstance(time_data, dict) else 'N/A'}")
        
        team_shield_url = None
        
        # Priorizar url_escudo_png, depois url_escudo_svg, depois foto_perfil
        if 'url_escudo_png' in time_data and time_data['url_escudo_png']:
            team_shield_url = time_data['url_escudo_png']
            print(f"[DEBUG API] Time {team_id}: Escudo encontrado (url_escudo_png): {team_shield_url}")
        elif 'url_escudo_svg' in time_data and time_data['url_escudo_svg']:
            team_shield_url = time_data['url_escudo_svg']
            print(f"[DEBUG API] Time {team_id}: Escudo encontrado (url_escudo_svg): {team_shield_url}")
        elif 'foto_perfil' in time_data and time_data['foto_perfil']:
            team_shield_url = time_data['foto_perfil']
            print(f"[DEBUG API] Time {team_id}: Escudo encontrado (foto_perfil): {team_shield_url}")
        else:
            print(f"[DEBUG API] Time {team_id}: Nenhum escudo encontrado. url_escudo_png: {time_data.get('url_escudo_png')}, url_escudo_svg: {time_data.get('url_escudo_svg')}, foto_perfil: {time_data.get('foto_perfil')}")
        
        return jsonify({'team_shield_url': team_shield_url, 'token_error': False})
    except Exception as e:
        print(f"[DEBUG API] Erro ao buscar escudo do time {team_id}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        close_db_connection(conn)

@app.route('/api/time/excluir/<int:team_id>', methods=['DELETE'])
@login_required
def api_excluir_time(team_id):
    """API para excluir um time"""
    user = get_current_user()
    conn = get_db_connection()
    
    try:
        from models.teams import get_team, delete_team
        
        # Verificar se o time pertence ao usuário
        team = get_team(conn, team_id, user['id'])
        if not team:
            return jsonify({'error': 'Time não encontrado ou não pertence ao usuário'}), 404
        
        # Verificar se é o último time do usuário
        from models.teams import get_all_user_teams
        all_teams = get_all_user_teams(conn, user['id'])
        if len(all_teams) <= 1:
            return jsonify({'error': 'Não é possível excluir o último time. Você precisa ter pelo menos um time associado.'}), 400
        
        # Verificar se é o time selecionado
        selected_team_id = session.get('selected_team_id')
        if selected_team_id == team_id:
            # Selecionar outro time antes de excluir
            other_teams = [t for t in all_teams if t['id'] != team_id]
            if other_teams:
                session['selected_team_id'] = other_teams[0]['id']
        
        # Excluir o time
        deleted = delete_team(conn, team_id, user['id'])
        
        if deleted:
            return jsonify({'success': True, 'message': 'Time excluído com sucesso!'})
        else:
            return jsonify({'error': 'Erro ao excluir time'}), 500
            
    except Exception as e:
        conn.rollback()
        print(f"Erro ao excluir time: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        close_db_connection(conn)

@app.route('/api/time/atualizar-tokens/<int:team_id>', methods=['POST'])
@login_required
def api_atualizar_tokens(team_id):
    """API para atualizar tokens de um time (testa e atualiza se necessário)"""
    user = get_current_user()
    conn = get_db_connection()
    
    try:
        from models.teams import get_team, update_team
        from api_cartola import fetch_team_data_by_team_id, refresh_access_token_by_team_id
        
        # Verificar se o time pertence ao usuário
        team = get_team(conn, team_id, user['id'])
        if not team:
            return jsonify({'error': 'Time não encontrado ou não pertence ao usuário'}), 404
        
        # Tentar buscar dados do time (isso já testa os tokens)
        from api_cartola import fetch_team_info_by_team_id
        team_info = fetch_team_info_by_team_id(conn, team_id)
        
        if not team_info:
            # Se não conseguiu, tentar atualizar tokens
            new_token = refresh_access_token_by_team_id(conn, team_id)
            if new_token:
                # Tentar novamente após atualizar
                team_info = fetch_team_info_by_team_id(conn, team_id)
        
        if not team_info:
            return jsonify({'error': 'Não foi possível atualizar os tokens. Verifique se as credenciais estão corretas.'}), 400
        
        # Extrair nome atualizado
        final_team_name = team.get('team_name')
        team_shield_url = None
        
        if 'time' in team_info and isinstance(team_info['time'], dict):
            time_data = team_info['time']
            if 'nome' in time_data:
                final_team_name = time_data['nome']
            
            # Extrair escudo
            if 'url_escudo_png' in time_data:
                team_shield_url = time_data['url_escudo_png']
            elif 'url_escudo_svg' in time_data:
                team_shield_url = time_data['url_escudo_svg']
            elif 'foto_perfil' in time_data:
                team_shield_url = time_data['foto_perfil']
        
        # Atualizar nome no banco (escudo não é salvo, é buscado dinamicamente)
        if final_team_name != team.get('team_name'):
            update_team(conn, team_id, user['id'], team_name=final_team_name)
        
        return jsonify({
            'success': True,
            'message': 'Tokens atualizados com sucesso!',
            'team_name': final_team_name,
            'team_shield_url': team_shield_url
        })
    except Exception as e:
        print(f"Erro ao atualizar tokens: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        close_db_connection(conn)

@app.route('/api/escalacao-ideal/config', methods=['GET', 'POST'])
@login_required
def api_escalacao_config():
    """API para obter ou salvar configurações de escalação ideal"""
    user = get_current_user()
    conn = get_db_connection()
    
    try:
        from models.user_escalacao_config import get_user_escalacao_config, upsert_user_escalacao_config
        from models.user_escalacao_config import create_user_escalacao_config_table
        create_user_escalacao_config_table(conn)  # Garantir que a tabela existe
        
        if request.method == 'GET':
            # Usar time selecionado na sessão
            team_id = session.get('selected_team_id')
            if not team_id:
                # Se não houver time selecionado, buscar o primeiro
                from models.teams import get_all_user_teams, create_teams_table
                create_teams_table(conn)
                times = get_all_user_teams(conn, user['id'])
                if times and len(times) > 0:
                    team_id = times[0]['id']
                    session['selected_team_id'] = team_id
            
            config = get_user_escalacao_config(conn, user['id'], team_id)
            if config:
                return jsonify({
                    'formation': config['formation'],
                    'hack_goleiro': config['hack_goleiro'],
                    'fechar_defesa': config['fechar_defesa'],
                    'posicao_capitao': config['posicao_capitao'],
                    'posicao_reserva_luxo': config.get('posicao_reserva_luxo', 'atacantes'),
                    'prioridades': config.get('prioridades', 'atacantes,laterais,meias,zagueiros,goleiros,tecnicos')
                })
            else:
                # Retornar valores padrão
                return jsonify({
                    'formation': '4-3-3',
                    'hack_goleiro': False,
                    'fechar_defesa': False,
                    'posicao_capitao': 'atacantes',
                    'posicao_reserva_luxo': 'atacantes',
                    'prioridades': 'atacantes,laterais,meias,zagueiros,goleiros,tecnicos'
                })
        else:  # POST
            data = request.get_json()
            # Usar time selecionado na sessão
            team_id = session.get('selected_team_id')
            if not team_id:
                return jsonify({'error': 'Nenhum time selecionado'}), 400
            
            formation = data.get('formation', '4-3-3')
            hack_goleiro = data.get('hack_goleiro', False)
            fechar_defesa = data.get('fechar_defesa', False)
            posicao_capitao = data.get('posicao_capitao', 'atacantes')
            posicao_reserva_luxo = data.get('posicao_reserva_luxo', 'atacantes')
            prioridades = data.get('prioridades', 'atacantes,laterais,meias,zagueiros,goleiros,tecnicos')
            
            upsert_user_escalacao_config(
                conn, user['id'], team_id, formation, hack_goleiro, fechar_defesa, posicao_capitao, posicao_reserva_luxo, prioridades
            )
            return jsonify({'success': True})
    except Exception as e:
        print(f"Erro em api_escalacao_config: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        close_db_connection(conn)

@app.route('/api/escalacao-ideal/dados')
@login_required
def api_escalacao_dados():
    """API para fornecer dados necessários para cálculo de escalação ideal"""
    user = get_current_user()
    conn = get_db_connection()
    
    try:
        from models.user_escalacao_config import create_user_escalacao_config_table
        create_user_escalacao_config_table(conn)  # Garantir que a tabela existe
        
        # Usar time selecionado na sessão
        team_id = session.get('selected_team_id')
        if not team_id:
            # Se não houver time selecionado, buscar o primeiro
            from models.teams import get_all_user_teams, create_teams_table
            create_teams_table(conn)
            times = get_all_user_teams(conn, user['id'])
            if times and len(times) > 0:
                team_id = times[0]['id']
                session['selected_team_id'] = team_id
            else:
                return jsonify({'error': 'Nenhum time cadastrado'}), 404
        
        # Buscar rodada atual
        cursor = conn.cursor()
        cursor.execute('SELECT MAX(rodada_atual) FROM acp_peso_jogo_perfis')
        rodada_result = cursor.fetchone()
        rodada_atual = rodada_result[0] if rodada_result and rodada_result[0] else 1
        
        # Buscar configuração padrão do usuário para este time
        from models.user_configurations import get_user_default_configuration
        config = get_user_default_configuration(conn, user['id'], team_id)
        if not config:
            return jsonify({'error': 'Configuração não encontrada'}), 404
        
        # Buscar rankings salvos de todas as posições
        from models.user_rankings import get_team_rankings
        posicao_map = {
            'goleiro': 1, 'lateral': 2, 'zagueiro': 3, 
            'meia': 4, 'atacante': 5, 'treinador': 6
        }
        
        rankings_por_posicao = {}
        for pos_nome, pos_id in posicao_map.items():
            rankings = get_team_rankings(
                conn, user['id'],
                team_id=team_id,
                configuration_id=config.get('id'),
                posicao_id=pos_id,
                rodada_atual=rodada_atual
            )
            if rankings:
                ranking_data = rankings[0].get('ranking_data', [])
                if isinstance(ranking_data, list) and len(ranking_data) > 0:
                    # Normalizar campos: garantir que preco_num exista
                    # Se não estiver no ranking salvo, buscar da tabela atletas
                    ranking_normalizado = []
                    atleta_ids_sem_preco = []
                    
                    # Primeira passagem: identificar jogadores sem preço
                    print(f"[DEBUG] Processando ranking {pos_nome} com {len(ranking_data)} jogadores")
                    for jogador in ranking_data:
                        jogador_norm = dict(jogador)
                        # Verificar se tem preço válido (> 0)
                        preco_num_val = jogador_norm.get('preco_num', 0)
                        preco_val = jogador_norm.get('preco', 0)
                        
                        # Tentar converter para float
                        try:
                            if preco_num_val:
                                preco_num_val = float(preco_num_val)
                            else:
                                preco_num_val = 0
                            if preco_val:
                                preco_val = float(preco_val)
                            else:
                                preco_val = 0
                        except (ValueError, TypeError):
                            preco_num_val = 0
                            preco_val = 0
                        
                        preco_existe = (preco_num_val and preco_num_val > 0) or (preco_val and preco_val > 0)
                        
                        if not preco_existe and jogador_norm.get('atleta_id'):
                            atleta_ids_sem_preco.append(jogador_norm['atleta_id'])
                            # Log para debug (apenas primeiros 3)
                            if len(atleta_ids_sem_preco) <= 3:
                                print(f"[DEBUG] Jogador {jogador_norm.get('apelido', 'N/A')} (ID: {jogador_norm.get('atleta_id')}) sem preço válido. preco_num={preco_num_val}, preco={preco_val}")
                    
                    # Buscar preços e status_id da tabela atletas
                    preco_dict = {}
                    status_dict = {}
                    
                    # Buscar para todos os atletas do ranking (para garantir status_id atualizado)
                    atleta_ids_ranking = [j['atleta_id'] for j in ranking_data if j.get('atleta_id')]
                    if atleta_ids_ranking:
                        placeholders = ','.join(['%s'] * len(atleta_ids_ranking))
                        cursor.execute(f'''
                            SELECT atleta_id, preco_num, status_id
                            FROM acf_atletas
                            WHERE atleta_id IN ({placeholders})
                        ''', atleta_ids_ranking)
                        rows_atletas = cursor.fetchall()
                        
                        for row in rows_atletas:
                            atleta_id = row[0]
                            preco_val = float(row[1]) if row[1] else 0.0
                            status_val = int(row[2]) if row[2] else 0
                            
                            preco_dict[atleta_id] = preco_val
                            status_dict[atleta_id] = status_val
                        
                        print(f"[DEBUG] Buscados preços e status para {len(rows_atletas)} atletas da posição {pos_nome}")
                    
                    if atleta_ids_sem_preco:
                        print(f"[DEBUG] {len(atleta_ids_sem_preco)} atletas sem preço na posição {pos_nome}")
                    
                    # Segunda passagem: normalizar todos os jogadores
                    for jogador in ranking_data:
                        jogador_norm = dict(jogador)
                        atleta_id = jogador_norm.get('atleta_id')
                        
                        # Normalizar preço: tentar preco_num, depois preco, depois buscar da tabela
                        preco_valor = None
                        if 'preco_num' in jogador_norm and jogador_norm.get('preco_num'):
                            try:
                                preco_valor = float(jogador_norm['preco_num'])
                            except (ValueError, TypeError):
                                pass
                        
                        if preco_valor is None or preco_valor <= 0:
                            if 'preco' in jogador_norm and jogador_norm.get('preco'):
                                try:
                                    preco_valor = float(jogador_norm['preco'])
                                except (ValueError, TypeError):
                                    pass
                        
                        if (preco_valor is None or preco_valor <= 0) and atleta_id and atleta_id in preco_dict:
                            preco_valor = preco_dict[atleta_id]
                        
                        # Garantir que preco_valor seja um número válido
                        if preco_valor is None or preco_valor <= 0:
                            preco_valor = 0.0
                        
                        # Atualizar campos de preço
                        jogador_norm['preco_num'] = preco_valor
                        jogador_norm['preco'] = preco_valor
                        
                        # Adicionar status_id atual da tabela (não do ranking salvo)
                        if atleta_id and atleta_id in status_dict:
                            jogador_norm['status_id'] = status_dict[atleta_id]
                        else:
                            jogador_norm['status_id'] = 0  # Status desconhecido
                        
                        ranking_normalizado.append(jogador_norm)
                    
                    rankings_por_posicao[pos_nome] = ranking_normalizado
                    print(f"[DEBUG] Ranking {pos_nome}: {len(ranking_normalizado)} jogadores normalizados")
                    if ranking_normalizado:
                        sample = ranking_normalizado[0]
                        print(f"[DEBUG] Exemplo de jogador normalizado: atleta_id={sample.get('atleta_id')}, preco_num={sample.get('preco_num')}, preco={sample.get('preco')}")
        
        # Buscar configuração de escalação
        from models.user_escalacao_config import get_user_escalacao_config
        escalacao_config = get_user_escalacao_config(conn, user['id'], team_id)
        
        # Buscar time para obter patrimônio e informações
        from models.teams import get_team
        from api_cartola import fetch_team_info_by_team_id
        team_data_db = None
        team_name = None
        team_shield_url = None
        
        if team_id:
            team_data_db = get_team(conn, team_id, user['id'])
            # Buscar nome e escudo do time
            try:
                team_info = fetch_team_info_by_team_id(conn, team_id)
                if team_info and 'time' in team_info and isinstance(team_info['time'], dict):
                    time_data = team_info['time']
                    team_name = time_data.get('nome', None) or time_data.get('nome_cartola', None)
                    # Priorizar url_escudo_png, depois url_escudo_svg, depois foto_perfil
                    if 'url_escudo_png' in time_data:
                        team_shield_url = time_data['url_escudo_png']
                    elif 'url_escudo_svg' in time_data:
                        team_shield_url = time_data['url_escudo_svg']
                    elif 'foto_perfil' in time_data:
                        team_shield_url = time_data['foto_perfil']
            except Exception as e:
                print(f"Erro ao buscar informações do time {team_id}: {e}")
        
        # Buscar patrimônio via API do Cartola
        patrimonio = 0
        patrimonio_error = None
        
        if not team_id:
            patrimonio_error = "Time não selecionado"
        else:
            try:
                from api_cartola import fetch_team_data_by_team_id
                print(f"[DEBUG] Buscando patrimônio para time {team_id}...")
                team_data, token_used = fetch_team_data_by_team_id(conn, team_id)
                
                if team_data:
                    # A API do Cartola retorna o patrimônio em time.time_mercado.patrimonio
                    # E também pode ter no nível raiz como time.patrimonio
                    if 'time' in team_data and isinstance(team_data['time'], dict):
                        time_info = team_data['time']
                        # Tentar time_mercado.patrimonio primeiro (estrutura mais comum)
                        if 'time_mercado' in time_info and isinstance(time_info['time_mercado'], dict):
                            patrimonio = time_info['time_mercado'].get('patrimonio', 0)
                        
                        # Se não encontrou, tentar no nível time
                        if not patrimonio or patrimonio <= 0:
                            patrimonio = time_info.get('patrimonio', 0)
                        
                        # Se ainda não encontrou, tentar no nível raiz
                        if not patrimonio or patrimonio <= 0:
                            patrimonio = team_data.get('patrimonio', 0)
                    
                    # Garantir que patrimonio seja um número válido
                    try:
                        patrimonio = float(patrimonio) if patrimonio else 0
                    except (ValueError, TypeError):
                        patrimonio = 0
                    
                    if patrimonio <= 0:
                        print(f"[AVISO] Patrimônio não encontrado ou inválido. Estrutura da resposta: {list(team_data.keys())}")
                        if 'time' in team_data:
                            print(f"[AVISO] Estrutura de 'time': {list(team_data['time'].keys()) if isinstance(team_data['time'], dict) else type(team_data['time'])}")
                        patrimonio_error = "Patrimônio não encontrado na resposta da API do Cartola. Verifique se as credenciais estão corretas."
                    else:
                        print(f"[DEBUG] Patrimônio encontrado: {patrimonio}")
                else:
                    print(f"[AVISO] team_data está vazio ou None. Credenciais podem estar inválidas.")
                    patrimonio_error = "Não foi possível obter dados do time da API do Cartola. Verifique se as credenciais estão corretas."
                    
            except Exception as e:
                print(f"[ERRO] Erro ao buscar patrimônio: {e}")
                import traceback
                traceback.print_exc()
                patrimonio_error = f"Erro ao buscar patrimônio: {str(e)}"
        
        # Buscar clubes para obter informações de SG - usar o perfil configurado pelo usuário
        perfil_peso_sg = config.get('perfil_peso_sg', 2)  # Usar perfil 2 como padrão
        cursor.execute('''
            SELECT clube_id, peso_sg
            FROM acp_peso_sg_perfis
            WHERE perfil_id = %s AND rodada_atual = %s
            ORDER BY peso_sg DESC
            LIMIT 10
        ''', (perfil_peso_sg, rodada_atual))
        clubes_sg = [{'clube_id': row[0], 'peso_sg': float(row[1])} for row in cursor.fetchall()]
        
        # Buscar TODOS os goleiros (para hack do goleiro) - incluindo não prováveis
        print("[DEBUG] Buscando TODOS os goleiros da tabela acf_atletas...")
        cursor.execute('''
            SELECT a.atleta_id, a.apelido, a.clube_id, a.preco_num, a.status_id
            FROM acf_atletas a
            WHERE a.posicao_id = 1
            ORDER BY a.preco_num DESC
        ''')
        
        rows_goleiros = cursor.fetchall()
        print(f"[DEBUG] Query retornou {len(rows_goleiros)} goleiros da tabela acf_atletas")
        
        todos_goleiros = []
        goleiros_nulos_count = 0
        goleiros_provaveis_count = 0
        
        for row in rows_goleiros:
            if row and len(row) >= 5:
                status_id = int(row[4]) if row[4] else 0
                
                # Contar por status
                if status_id in [2, 7]:
                    goleiros_provaveis_count += 1
                else:
                    goleiros_nulos_count += 1
                
                goleiro_data = {
                    'atleta_id': row[0],
                    'apelido': row[1],
                    'clube_id': row[2],
                    'preco_num': float(row[3]) if row[3] else 0,
                    'preco': float(row[3]) if row[3] else 0,
                    'status_id': status_id,
                    'pontuacao_total': 0  # Goleiros nulos não precisam de pontuação
                }
                todos_goleiros.append(goleiro_data)
        
        print(f"[DEBUG] Total de goleiros processados: {len(todos_goleiros)}")
        print(f"[DEBUG] Goleiros prováveis (status 2 ou 7): {goleiros_provaveis_count}")
        print(f"[DEBUG] Goleiros NULOS (outros status): {goleiros_nulos_count}")
        
        if todos_goleiros:
            # Mostrar os 5 goleiros nulos mais caros
            goleiros_nulos_lista = [g for g in todos_goleiros if g['status_id'] not in [2, 7]]
            goleiros_nulos_lista.sort(key=lambda x: x['preco_num'], reverse=True)
            
            if goleiros_nulos_lista:
                print(f"[DEBUG] Top 5 goleiros NULOS mais caros:")
                for g in goleiros_nulos_lista[:5]:
                    print(f"  - {g['apelido']} - R$ {g['preco_num']:.2f} - status_id: {g['status_id']}")
            else:
                print("[DEBUG] ATENÇÃO: Nenhum goleiro NULO encontrado!")
        else:
            print("[DEBUG] ATENÇÃO: Lista de todos_goleiros está VAZIA!")
        
        # Buscar top 5 de peso de jogo
        perfil_peso_jogo = config.get('perfil_peso_jogo', 2)
        cursor.execute('''
            SELECT clube_id, peso_jogo
            FROM acp_peso_jogo_perfis
            WHERE perfil_id = %s AND rodada_atual = %s
            ORDER BY peso_jogo DESC
            LIMIT 5
        ''', (perfil_peso_jogo, rodada_atual))
        top5_peso_jogo = [{'clube_id': row[0], 'peso_jogo': float(row[1])} for row in cursor.fetchall()]
        
        # Buscar top 5 de peso SG
        cursor.execute('''
            SELECT clube_id, peso_sg
            FROM acp_peso_sg_perfis
            WHERE perfil_id = %s AND rodada_atual = %s
            ORDER BY peso_sg DESC
            LIMIT 5
        ''', (perfil_peso_sg, rodada_atual))
        top5_peso_sg = [{'clube_id': row[0], 'peso_sg': float(row[1])} for row in cursor.fetchall()]
        
        # Buscar dados de clubes com escudos para os cards
        from utils.team_shields import get_team_shield
        clube_ids_set = set()
        
        # Coletar IDs de clubes dos rankings
        for pos_nome, ranking in rankings_por_posicao.items():
            for jogador in ranking[:5]:  # Top 5 apenas
                if jogador.get('clube_id'):
                    clube_ids_set.add(jogador['clube_id'])
        
        # Coletar IDs dos top 5 de pesos
        for item in top5_peso_jogo:
            clube_ids_set.add(item['clube_id'])
        for item in top5_peso_sg:
            clube_ids_set.add(item['clube_id'])
        
        # Buscar dados dos clubes
        clubes_dict = {}
        if clube_ids_set:
            placeholders = ','.join(['%s'] * len(clube_ids_set))
            cursor.execute(f'''
                SELECT id, nome, abreviacao
                FROM acf_clubes
                WHERE id IN ({placeholders})
            ''', list(clube_ids_set))
            
            for row in cursor.fetchall():
                clube_id = row[0]
                escudo_url = get_team_shield(clube_id, size='45x45')
                clubes_dict[clube_id] = {
                    'nome': row[1],
                    'abreviacao': row[2],
                    'escudo_url': escudo_url
                }
        
        response_data = {
            'team_id': team_id,
            'team_name': team_name,
            'team_shield_url': team_shield_url,
            'rodada_atual': rodada_atual,
            'rankings_por_posicao': rankings_por_posicao,
            'todos_goleiros': todos_goleiros,  # Lista completa de goleiros para hack
            'config': {
                'formation': escalacao_config['formation'] if escalacao_config else '4-3-3',
                'hack_goleiro': escalacao_config['hack_goleiro'] if escalacao_config else False,
                'fechar_defesa': escalacao_config['fechar_defesa'] if escalacao_config else False,
                'posicao_capitao': escalacao_config['posicao_capitao'] if escalacao_config else 'atacantes'
            },
            'patrimonio': patrimonio,
            'clubes_sg': clubes_sg,
            'top5_peso_jogo': top5_peso_jogo,
            'top5_peso_sg': top5_peso_sg,
            'clubes_dict': clubes_dict
        }
        
        # Adicionar erro de patrimônio se houver
        if patrimonio_error:
            response_data['patrimonio_error'] = patrimonio_error
        
        print(f"[DEBUG] Retornando patrimônio: {patrimonio}, erro: {patrimonio_error}")
        print(f"[DEBUG] Enviando {len(todos_goleiros)} goleiros no campo 'todos_goleiros' da resposta")
        
        return jsonify(response_data)
    except Exception as e:
        print(f"Erro ao buscar dados de escalação: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        close_db_connection(conn)

@app.route('/diagnostico/goleiros-nulos')
@login_required
def diagnostico_goleiros_nulos():
    """Página de diagnóstico para visualizar goleiros nulos"""
    return render_template('diagnostico_goleiros.html')

@app.route('/api/escalacao-ideal/goleiros-nulos')
@login_required
def api_goleiros_nulos():
    """API para buscar goleiros nulos diretamente da tabela acf_atletas"""
    conn = get_db_connection()
    
    try:
        # Parâmetro opcional: preço mínimo do goleiro titular
        preco_minimo = request.args.get('preco_minimo', 0, type=float)
        
        cursor = conn.cursor()
        
        # Buscar TODOS os goleiros da tabela
        cursor.execute('''
            SELECT a.atleta_id, a.apelido, a.clube_id, a.preco_num, a.status_id,
                   c.nome as clube_nome, c.abreviacao as clube_abrev
            FROM acf_atletas a
            LEFT JOIN acf_clubes c ON a.clube_id = c.id
            WHERE a.posicao_id = 1
            ORDER BY a.preco_num DESC
        ''')
        
        todos_goleiros = []
        goleiros_nulos = []
        goleiros_provaveis = []
        
        for row in cursor.fetchall():
            if row and len(row) >= 5:
                goleiro = {
                    'atleta_id': row[0],
                    'apelido': row[1],
                    'clube_id': row[2],
                    'preco_num': float(row[3]) if row[3] else 0,
                    'status_id': int(row[4]) if row[4] else 0,
                    'clube_nome': row[5] if len(row) > 5 else None,
                    'clube_abrev': row[6] if len(row) > 6 else None
                }
                
                todos_goleiros.append(goleiro)
                
                # Classificar por status
                if goleiro['status_id'] in [2, 7]:  # Provável ou dúvida
                    goleiros_provaveis.append(goleiro)
                else:  # Nulo (qualquer outro status)
                    goleiros_nulos.append(goleiro)
        
        # Filtrar goleiros nulos mais caros que o preço mínimo
        goleiros_nulos_mais_caros = [
            g for g in goleiros_nulos 
            if g['preco_num'] > preco_minimo
        ]
        
        # Ordenar por preço (mais caros primeiro)
        goleiros_nulos_mais_caros.sort(key=lambda x: x['preco_num'], reverse=True)
        
        response = {
            'total_goleiros': len(todos_goleiros),
            'total_goleiros_provaveis': len(goleiros_provaveis),
            'total_goleiros_nulos': len(goleiros_nulos),
            'total_goleiros_nulos_mais_caros': len(goleiros_nulos_mais_caros),
            'preco_minimo_filtro': preco_minimo,
            'todos_goleiros': todos_goleiros,
            'goleiros_provaveis': goleiros_provaveis,
            'goleiros_nulos': goleiros_nulos,
            'goleiros_nulos_mais_caros': goleiros_nulos_mais_caros,
            'status_ids': {
                '2': 'Dúvida',
                '3': 'Suspenso',
                '5': 'Contundido',
                '6': 'Nulo',
                '7': 'Provável'
            }
        }
        
        print(f"[DEBUG] Goleiros na base: {len(todos_goleiros)}")
        print(f"[DEBUG] Goleiros prováveis (status 2 ou 7): {len(goleiros_provaveis)}")
        print(f"[DEBUG] Goleiros nulos (outros status): {len(goleiros_nulos)}")
        print(f"[DEBUG] Goleiros nulos mais caros que R$ {preco_minimo:.2f}: {len(goleiros_nulos_mais_caros)}")
        
        if goleiros_nulos_mais_caros:
            top5 = goleiros_nulos_mais_caros[:5]
            print(f"[DEBUG] Top 5 goleiros nulos mais caros:")
            for g in top5:
                print(f"  - {g['apelido']} ({g['clube_abrev']}) - R$ {g['preco_num']:.2f} - status_id: {g['status_id']}")
        
        return jsonify(response)
        
    except Exception as e:
        print(f"Erro ao buscar goleiros nulos: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        close_db_connection(conn)

@app.route('/api/escalacao-ideal/escalar', methods=['POST'])
@login_required
def api_escalar_time():
    """API para escalar o time no Cartola FC"""
    from api_cartola import salvar_time_no_cartola
    from models.teams import get_team
    
    user = get_current_user()
    conn = get_db_connection()
    
    try:
        # Receber dados da escalação
        data = request.get_json()
        print(f"[DEBUG] Dados recebidos: {data}")
        
        escalacao = data.get('escalacao') if data else None
        
        if not escalacao:
            print(f"[ERROR] Escalação não fornecida. Data: {data}")
            return jsonify({'error': 'Escalação não fornecida'}), 400
        
        # Obter team_id da sessão
        team_id = session.get('selected_team_id')
        if not team_id:
            return jsonify({'error': 'Nenhum time selecionado'}), 400
        
        # Buscar team no banco
        team = get_team(conn, team_id)
        if not team:
            return jsonify({'error': 'Time não encontrado'}), 404
        
        access_token = team.get('access_token')
        if not access_token:
            return jsonify({'error': 'Token de acesso não encontrado'}), 401
        
        # Mapear posições para IDs numéricos (usado pela API do Cartola)
        posicao_id_map = {
            'goleiros': 1,
            'laterais': 2,
            'zagueiros': 3,
            'meias': 4,
            'atacantes': 5,
            'treinadores': 6
        }
        
        # Preparar payload para API do Cartola
        titulares = escalacao.get('titulares', {})
        reservas = escalacao.get('reservas', {})
        
        # Array de IDs dos titulares (12 atletas)
        atletas_ids = []
        for posicao in ['goleiros', 'zagueiros', 'laterais', 'meias', 'atacantes', 'treinadores']:
            jogadores = titulares.get(posicao, [])
            print(f"[DEBUG] Posição {posicao}: {len(jogadores)} jogadores")
            for jogador in jogadores:
                atleta_id = jogador.get('atleta_id')
                print(f"[DEBUG]   - Jogador: {jogador.get('apelido', 'N/A')} (ID: {atleta_id})")
                atletas_ids.append(atleta_id)
        
        print(f"[DEBUG] Total de atletas: {len(atletas_ids)}")
        
        # Validar 12 atletas
        if len(atletas_ids) != 12:
            print(f"[ERROR] Escalação inválida: {len(atletas_ids)} atletas")
            print(f"[ERROR] Titulares: {titulares}")
            return jsonify({
                'error': f'Escalação inválida: {len(atletas_ids)} atletas. Esperado: 12',
                'detalhes': {
                    'atletas_encontrados': len(atletas_ids),
                    'por_posicao': {pos: len(titulares.get(pos, [])) for pos in ['goleiros', 'zagueiros', 'laterais', 'meias', 'atacantes', 'treinadores']}
                }
            }), 400
        
        # Identificar capitão
        capitao_id = None
        for posicao_jogadores in titulares.values():
            for jogador in posicao_jogadores:
                if jogador.get('eh_capitao'):
                    capitao_id = jogador.get('atleta_id')
                    break
            if capitao_id:
                break
        
        # Mapear reservas {posicao_id: atleta_id}
        # IMPORTANTE: Reserva de luxo também deve estar aqui!
        # As chaves devem ser STRINGS com os IDs das posições
        reservas_map = {}
        for posicao, jogadores in reservas.items():
            for jogador in jogadores:
                posicao_id = posicao_id_map.get(posicao)
                if posicao_id:
                    atleta_id = jogador.get('atleta_id')
                    reservas_map[str(posicao_id)] = atleta_id  # String!
                    print(f"[DEBUG] Reserva posição {posicao_id} ({posicao}): {jogador.get('apelido')} (ID: {atleta_id}) - Luxo: {jogador.get('eh_reserva_luxo', False)}")
        
        # Identificar reserva de luxo
        reserva_luxo_id = None
        for jogadores in reservas.values():
            for jogador in jogadores:
                if jogador.get('eh_reserva_luxo'):
                    reserva_luxo_id = jogador.get('atleta_id')
                    print(f"[DEBUG] Reserva de luxo identificado: {jogador.get('apelido')} (ID: {reserva_luxo_id})")
                    break
            if reserva_luxo_id:
                break
        
        print(f"[DEBUG] Reservas completas: {reservas_map}")
        print(f"[DEBUG] Capitão: {capitao_id}")
        print(f"[DEBUG] Reserva luxo: {reserva_luxo_id}")
        
        # Obter esquema da formação (mapear 4-3-3 -> ID 3, etc)
        esquema_map = {
            '4-3-3': 3,
            '4-4-2': 1,
            '3-5-2': 2,
            '3-4-3': 4,
            '4-5-1': 5,
            '5-4-1': 6
        }
        formacao = data.get('formacao', '4-3-3')
        esquema_id = esquema_map.get(formacao, 3)
        
        # Montar payload
        time_para_escalacao = {
            'esquema': esquema_id,
            'atletas': atletas_ids,
            'capitao': capitao_id,
            'reservas': reservas_map,
            'reserva_luxo_id': reserva_luxo_id
        }
        
        print(f"[DEBUG] Escalando time {team_id}")
        print(f"[DEBUG] Payload: {time_para_escalacao}")
        
        # Enviar para API do Cartola
        # Criar uma função auxiliar que usa team_id
        from api_cartola import API_URL_SALVAR_TIME, refresh_access_token_by_team_id
        import requests
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json;charset=UTF-8",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Origin": "https://cartola.globo.com",
            "Referer": "https://cartola.globo.com/",
            "x-glb-app": "cartola_web",
            "x-glb-auth": "oidc",
        }
        
        try:
            # Timeout de 10 segundos para não travar o cliente
            response = requests.post(API_URL_SALVAR_TIME, json=time_para_escalacao, headers=headers, timeout=10)
            
            if response.status_code == 401:
                # Token expirado, tentar refresh
                print(f"[DEBUG] Token expirado, tentando refresh...")
                new_token = refresh_access_token_by_team_id(conn, team_id)
                if new_token:
                    headers["Authorization"] = f"Bearer {new_token}"
                    response = requests.post(API_URL_SALVAR_TIME, json=time_para_escalacao, headers=headers, timeout=10)
                else:
                    return jsonify({'error': 'Falha ao atualizar token'}), 401
            
            # Processar resposta
            if 200 <= response.status_code < 300:
                try:
                    response_data = response.json()
                    if response_data.get("mensagem") == "Time Escalado! Boa Sorte!":
                        return jsonify({
                            'success': True,
                            'mensagem': 'Time escalado com sucesso!',
                            'detalhes': response_data
                        })
                    else:
                        return jsonify({
                            'error': response_data.get('mensagem', 'Erro desconhecido'),
                            'detalhes': response_data
                        }), 400
                except Exception:
                    return jsonify({
                        'error': 'Resposta inesperada da API',
                        'status': response.status_code
                    }), 400
            else:
                try:
                    error_data = response.json()
                    return jsonify({
                        'error': error_data.get('mensagem', f'Erro HTTP {response.status_code}'),
                        'detalhes': error_data
                    }), response.status_code
                except Exception:
                    return jsonify({
                        'error': f'Erro HTTP {response.status_code}',
                        'mensagem': response.text[:200]
                    }), response.status_code
                    
        except requests.exceptions.Timeout:
            print(f"[ERROR] Timeout ao escalar time")
            return jsonify({'error': 'A API do Cartola demorou demais para responder. Tente novamente.'}), 504
        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Erro ao escalar: {e}")
            return jsonify({'error': f'Erro de conexão: {str(e)}'}), 500
        
    except Exception as e:
        print(f"[ERROR] Erro no endpoint escalar: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        close_db_connection(conn)

@app.route('/api/user/permissions')
@login_required
def api_user_permissions():
    """API para retornar permissões do usuário baseadas no plano"""
    from utils.permissions import get_user_permissions
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Usuário não autenticado'}), 401
    
    permissions = get_user_permissions(user['id'])
    return jsonify(permissions)

@app.route('/admin/planos')
@login_required
def admin_planos():
    """Página de administração de planos (apenas para admins)"""
    user = get_current_user()
    if not user or not user.get('is_admin', False):
        flash('Você precisa ser administrador para acessar esta página.', 'error')
        return redirect(url_for('index'))
    
    return render_template('admin_planos.html')

@app.route('/admin/classes')
@login_required
def admin_classes():
    """Página para visualizar as classes de planos (apenas para admins)"""
    user = get_current_user()
    if not user or not user.get('is_admin', False):
        flash('Você precisa ser administrador para acessar esta página.', 'error')
        return redirect(url_for('index'))
    
    from models.plans import PLANS_CONFIG
    return render_template('admin_classes.html', plans_config=PLANS_CONFIG)

@app.route('/api/admin/alterar-plano', methods=['POST'])
@login_required
def api_admin_alterar_plano():
    """API para alterar plano do próprio usuário (apenas para admins)"""
    from models.plans import set_user_plan
    from flask import request
    
    user = get_current_user()
    if not user or not user.get('is_admin', False):
        return jsonify({'success': False, 'error': 'Acesso negado'}), 403
    
    data = request.get_json()
    plano = data.get('plano')
    
    if not plano or plano not in ['free', 'avancado', 'pro']:
        return jsonify({'success': False, 'error': 'Plano inválido'}), 400
    
    if set_user_plan(user['id'], plano, motivo='Alteração via painel admin'):
        return jsonify({'success': True, 'message': f'Plano alterado para {plano}'})
    else:
        return jsonify({'success': False, 'error': 'Erro ao alterar plano'}), 500

@app.route('/health')
def health_check():
    """Health check endpoint"""
    try:
        conn = get_db_connection()
        if conn:
            conn.cursor().execute('SELECT 1')
            close_db_connection(conn)
            return jsonify({"status": "healthy"}), 200
    except Exception:
        pass
    return jsonify({"status": "unhealthy"}), 500

# ========================================
# ADMIN LATERAIS
# ========================================

@app.route('/admin/laterais')
@admin_required
def admin_laterais():
    """Página de administração de laterais"""
    return render_template('admin_laterais.html')

@app.route('/api/admin/laterais')
@admin_required
def api_admin_laterais():
    """API para listar laterais e status de esquerdo"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        # Buscar todos os laterais (posicao_id = 2)
        # Join com laterais_esquerdos para saber se é esquerdo
        cursor.execute('''
            SELECT a.atleta_id, a.apelido, c.nome as clube_nome, 
                   CASE WHEN le.atleta_id IS NOT NULL THEN TRUE ELSE FALSE END as is_esquerdo,
                   a.foto
            FROM acf_atletas a
            JOIN acf_clubes c ON a.clube_id = c.id
            LEFT JOIN laterais_esquerdos le ON a.atleta_id = le.atleta_id
            WHERE a.posicao_id = 2
            ORDER BY c.nome, a.apelido
        ''')
        laterais = cursor.fetchall()
        
        result = []
        for lat in laterais:
            result.append({
                'atleta_id': lat[0],
                'apelido': lat[1],
                'clube_nome': lat[2],
                'is_esquerdo': lat[3],
                'foto': lat[4]
            })
            
        return jsonify(result)
    except Exception as e:
        print(f"Erro API laterais: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        close_db_connection(conn)

@app.route('/api/admin/laterais/toggle', methods=['POST'])
@admin_required
def api_admin_laterais_toggle():
    """API para alternar status de lateral esquerdo"""
    data = request.get_json()
    atleta_id = data.get('atleta_id')
    is_esquerdo = data.get('is_esquerdo')
    
    if not atleta_id:
        return jsonify({'success': False, 'error': 'ID do atleta obrigatório'}), 400
        
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        if is_esquerdo:
            # Adicionar à tabela
            cursor.execute('''
                INSERT INTO laterais_esquerdos (atleta_id) 
                VALUES (%s) 
                ON CONFLICT (atleta_id) DO NOTHING
            ''', (atleta_id,))
        else:
            # Remover da tabela
            cursor.execute('DELETE FROM laterais_esquerdos WHERE atleta_id = %s', (atleta_id,))
            
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        print(f"Erro toggle lateral: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        close_db_connection(conn)

# ========================================
# ADMIN FOTOS ATLETAS
# ========================================

@app.route('/admin/fotos-atletas')
@admin_required
def admin_fotos_atletas():
    """Página de administração de fotos dos atletas"""
    return render_template('admin_fotos_atletas.html')

@app.route('/admin/visualizar-atletas')
@admin_required
def admin_visualizar_atletas():
    """Página para visualizar atletas e adicionar URLs de fotos"""
    return render_template('admin_visualizar_atletas.html')

@app.route('/api/admin/fotos-atletas')
@admin_required
def api_admin_fotos_atletas():
    """API para listar atletas com múltiplas fotos (que ainda precisam de confirmação)"""
    import os
    from pathlib import Path
    
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        # Buscar todos os atletas
        cursor.execute('''
            SELECT a.atleta_id, a.apelido, a.nome, c.nome as clube_nome
            FROM acf_atletas a
            LEFT JOIN acf_clubes c ON a.clube_id = c.id
            ORDER BY c.nome, a.apelido
        ''')
        atletas = cursor.fetchall()
        
        # Diretório de fotos
        foto_dir = Path('static/cartola_imgs/foto_atletas')
        
        result = []
        for atleta_id, apelido, nome, clube_nome in atletas:
            # Buscar fotos disponíveis (apenas as que têm sufixo de fonte)
            fotos_disponiveis = []
            
            # Verificar foto ogol
            for ext in ['.jpg', '.jpeg', '.png']:
                foto_path = foto_dir / f"{atleta_id}_ogol{ext}"
                if foto_path.exists():
                    fotos_disponiveis.append({
                        'fonte': 'ogol',
                        'arquivo': foto_path.name,
                        'url': f"/static/cartola_imgs/foto_atletas/{foto_path.name}"
                    })
                    break
            
            # Verificar foto transfermarkt
            for ext in ['.jpg', '.jpeg', '.png']:
                foto_path = foto_dir / f"{atleta_id}_transfermarkt{ext}"
                if foto_path.exists():
                    fotos_disponiveis.append({
                        'fonte': 'transfermarkt',
                        'arquivo': foto_path.name,
                        'url': f"/static/cartola_imgs/foto_atletas/{foto_path.name}"
                    })
                    break
            
            # Verificar foto custom
            for ext in ['.jpg', '.jpeg', '.png', '.gif']:
                foto_path = foto_dir / f"{atleta_id}_custom{ext}"
                if foto_path.exists():
                    fotos_disponiveis.append({
                        'fonte': 'custom',
                        'arquivo': foto_path.name,
                        'url': f"/static/cartola_imgs/foto_atletas/{foto_path.name}"
                    })
                    break
            
            # Verificar se já tem foto processada (sem sufixo)
            tem_foto_processada = False
            for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
                foto_processada = foto_dir / f"{atleta_id}{ext}"
                if foto_processada.exists():
                    tem_foto_processada = True
                    break
            
            # Adicionar se:
            # 1. Tiver múltiplas fotos com sufixo (precisa escolher)
            # 2. OU tiver pelo menos 1 foto com sufixo mas NÃO tiver foto processada (precisa confirmar)
            if len(fotos_disponiveis) > 1 or (len(fotos_disponiveis) == 1 and not tem_foto_processada):
                result.append({
                    'atleta_id': atleta_id,
                    'apelido': apelido or nome or f"Atleta {atleta_id}",
                    'nome': nome or '',
                    'clube_nome': clube_nome or 'Sem clube',
                    'fotos': fotos_disponiveis
                })
        
        # Paginação
        total = len(result)
        start = (page - 1) * per_page
        end = start + per_page
        paginated_result = result[start:end]
        
        return jsonify({
            'atletas': paginated_result,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'pages': (total + per_page - 1) // per_page
            }
        })
    except Exception as e:
        print(f"Erro API fotos atletas: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        close_db_connection(conn)

@app.route('/api/admin/fotos-atletas/selecionar', methods=['POST'])
@admin_required
def api_admin_fotos_atletas_selecionar():
    """API para selecionar uma foto e excluir a(s) outra(s)"""
    import os
    from pathlib import Path
    
    data = request.get_json()
    atleta_id = data.get('atleta_id')
    foto_selecionada = data.get('foto_selecionada')  # Nome do arquivo selecionado
    excluir_todas = data.get('excluir_todas', False)  # Se True, exclui todas as fotos
    
    if not atleta_id:
        return jsonify({'success': False, 'error': 'ID do atleta obrigatório'}), 400
    
    foto_dir = Path('static/cartola_imgs/foto_atletas')
    
    try:
        if excluir_todas:
            # Excluir todas as fotos do atleta
            for ext in ['.jpg', '.jpeg', '.png']:
                for fonte in ['ogol', 'transfermarkt']:
                    foto_path = foto_dir / f"{atleta_id}_{fonte}{ext}"
                    if foto_path.exists():
                        os.remove(foto_path)
            
            return jsonify({'success': True, 'message': 'Todas as fotos foram excluídas'})
        else:
            if not foto_selecionada:
                return jsonify({'success': False, 'error': 'Foto selecionada obrigatória'}), 400
            
            # Excluir todas as fotos exceto a selecionada
            for ext in ['.jpg', '.jpeg', '.png']:
                for fonte in ['ogol', 'transfermarkt']:
                    foto_path = foto_dir / f"{atleta_id}_{fonte}{ext}"
                    if foto_path.exists() and foto_path.name != foto_selecionada:
                        os.remove(foto_path)
            
            return jsonify({'success': True, 'message': 'Foto selecionada e outras excluídas'})
            
    except Exception as e:
        print(f"Erro ao selecionar/excluir foto: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admin/fotos-atletas/baixar-url', methods=['POST'])
@admin_required
def api_admin_fotos_atletas_baixar_url():
    """API para baixar foto de uma URL e salvar com ID do atleta"""
    import os
    import requests
    from pathlib import Path
    from urllib.parse import urlparse
    
    data = request.get_json()
    atleta_id = data.get('atleta_id')
    url_foto = data.get('url_foto')
    
    if not atleta_id:
        return jsonify({'success': False, 'error': 'ID do atleta obrigatório'}), 400
    
    if not url_foto:
        return jsonify({'success': False, 'error': 'URL da foto obrigatória'}), 400
    
    foto_dir = Path('static/cartola_imgs/foto_atletas')
    foto_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        # Headers para evitar bloqueios
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
            'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8'
        }
        
        # Fazer download da imagem com timeout maior
        print(f"Baixando foto de: {url_foto}")
        response = requests.get(url_foto, headers=headers, timeout=30, stream=True, allow_redirects=True)
        response.raise_for_status()
        
        # Verificar se é realmente uma imagem
        content_type = response.headers.get('content-type', '').lower()
        if 'image' not in content_type:
            return jsonify({
                'success': False, 
                'error': f'URL não é uma imagem válida. Content-Type: {content_type}'
            }), 400
        
        # Verificar tamanho máximo (10MB)
        content_length = response.headers.get('content-length')
        if content_length and int(content_length) > 10 * 1024 * 1024:
            return jsonify({
                'success': False,
                'error': 'Imagem muito grande (máximo 10MB)'
            }), 400
        
        # Detectar extensão do arquivo
        parsed_url = urlparse(url_foto)
        path = parsed_url.path.lower()
        
        if path.endswith('.jpg') or path.endswith('.jpeg'):
            ext = '.jpg'
        elif path.endswith('.png'):
            ext = '.png'
        elif path.endswith('.gif'):
            ext = '.gif'
        elif path.endswith('.webp'):
            ext = '.webp'
        else:
            # Tentar detectar pelo content-type
            if 'jpeg' in content_type or 'jpg' in content_type:
                ext = '.jpg'
            elif 'png' in content_type:
                ext = '.png'
            elif 'gif' in content_type:
                ext = '.gif'
            elif 'webp' in content_type:
                ext = '.webp'
            else:
                ext = '.jpg'  # Padrão
        
        # Salvar arquivo como "atleta_id_custom.ext"
        foto_path = foto_dir / f"{atleta_id}_custom{ext}"
        
        print(f"[DOWNLOAD] Salvando foto do atleta {atleta_id} em: {foto_path}")
        
        # Baixar em chunks para não travar
        total_size = 0
        max_size = 10 * 1024 * 1024  # 10MB
        
        with open(foto_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    total_size += len(chunk)
                    if total_size > max_size:
                        # Remover arquivo parcial
                        foto_path.unlink()
                        return jsonify({
                            'success': False,
                            'error': 'Imagem muito grande (máximo 10MB)'
                        }), 400
        
        # Verificar se o arquivo foi salvo corretamente
        if not foto_path.exists():
            print(f"[DOWNLOAD] ERRO: Arquivo não foi criado: {foto_path}")
            return jsonify({
                'success': False,
                'error': 'Erro ao salvar arquivo (arquivo não foi criado)'
            }), 500
        
        file_size = foto_path.stat().st_size
        if file_size == 0:
            foto_path.unlink()  # Remover arquivo vazio
            print(f"[DOWNLOAD] ERRO: Arquivo vazio foi removido: {foto_path}")
            return jsonify({
                'success': False,
                'error': 'Erro ao salvar arquivo (arquivo vazio)'
            }), 500
        
        tamanho_kb = file_size / 1024
        print(f"[DOWNLOAD] ✅ Foto baixada: {foto_path.name} ({tamanho_kb:.1f} KB) - Atleta {atleta_id}")
        
        return jsonify({
            'success': True,
            'message': f'Foto baixada com sucesso ({tamanho_kb:.1f} KB)',
            'arquivo': foto_path.name,
            'url': f"/static/cartola_imgs/foto_atletas/{foto_path.name}"
        })
        
    except requests.exceptions.Timeout:
        return jsonify({
            'success': False,
            'error': 'Timeout: A URL demorou muito para responder (máximo 30 segundos)'
        }), 408
    except requests.exceptions.ConnectionError as e:
        return jsonify({
            'success': False,
            'error': f'Erro de conexão: Não foi possível conectar à URL. Verifique se a URL está correta.'
        }), 400
    except requests.exceptions.HTTPError as e:
        return jsonify({
            'success': False,
            'error': f'Erro HTTP {e.response.status_code}: {e.response.reason}'
        }), 400
    except requests.exceptions.RequestException as e:
        return jsonify({
            'success': False,
            'error': f'Erro na requisição: {str(e)}'
        }), 400
    except Exception as e:
        print(f"Erro ao baixar foto: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f'Erro inesperado: {str(e)}'
        }), 500

@app.route('/api/admin/fotos-atletas/salvar-multiplas', methods=['POST'])
@admin_required
def api_admin_fotos_atletas_salvar_multiplas():
    """API para salvar múltiplas seleções de uma vez"""
    import os
    from pathlib import Path
    
    data = request.get_json()
    selecoes = data.get('selecoes', [])  # Lista de {atleta_id, foto_selecionada, excluir_todas}
    
    if not selecoes:
        return jsonify({'success': False, 'error': 'Nenhuma seleção fornecida'}), 400
    
    foto_dir = Path('static/cartola_imgs/foto_atletas')
    resultados = []
    erros = []
    
    for selecao in selecoes:
        atleta_id = selecao.get('atleta_id')
        foto_selecionada = selecao.get('foto_selecionada')
        excluir_todas = selecao.get('excluir_todas', False)
        
        if not atleta_id:
            erros.append(f"ID do atleta obrigatório para seleção: {selecao}")
            continue
        
        try:
            if excluir_todas:
                # Excluir todas as fotos do atleta
                for ext in ['.jpg', '.jpeg', '.png', '.gif']:
                    for fonte in ['ogol', 'transfermarkt', 'custom']:
                        foto_path = foto_dir / f"{atleta_id}_{fonte}{ext}"
                        if foto_path.exists():
                            os.remove(foto_path)
                resultados.append({'atleta_id': atleta_id, 'status': 'todas_excluidas'})
            else:
                if not foto_selecionada:
                    erros.append(f"Foto selecionada obrigatória para atleta {atleta_id}")
                    continue
                
                # Encontrar a foto selecionada
                foto_selecionada_path = foto_dir / foto_selecionada
                if not foto_selecionada_path.exists():
                    erros.append(f"Foto selecionada não encontrada para atleta {atleta_id}: {foto_selecionada}")
                    continue
                
                # Extrair extensão do arquivo selecionado
                ext = foto_selecionada_path.suffix
                
                # Renomear a foto selecionada removendo o sufixo da fonte (ex: 100084_ogol.jpg -> 100084.jpg)
                novo_nome = f"{atleta_id}{ext}"
                novo_path = foto_dir / novo_nome
                
                # Se já existe uma foto sem sufixo, excluir primeiro
                if novo_path.exists() and novo_path != foto_selecionada_path:
                    os.remove(novo_path)
                
                # Renomear a foto selecionada
                print(f"[SALVAR] Renomeando: {foto_selecionada} -> {novo_nome} (Atleta {atleta_id})")
                os.rename(foto_selecionada_path, novo_path)
                
                # Excluir todas as outras fotos (com sufixo de fonte)
                # IMPORTANTE: A foto renomeada (novo_path) já não tem sufixo, então não será excluída
                # Mas ainda pode haver outras fotos com sufixo que precisam ser removidas
                fotos_removidas = []
                for ext_other in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
                    for fonte in ['ogol', 'transfermarkt', 'custom']:
                        foto_path = foto_dir / f"{atleta_id}_{fonte}{ext_other}"
                        # Excluir apenas se existir (a foto original já foi renomeada, então não existe mais)
                        if foto_path.exists():
                            os.remove(foto_path)
                            fotos_removidas.append(foto_path.name)
                            print(f"  [SALVAR] Removida: {foto_path.name}")
                
                print(f"[SALVAR] ✅ Atleta {atleta_id}: {novo_nome} salvo. {len(fotos_removidas)} foto(s) removida(s).")
                resultados.append({'atleta_id': atleta_id, 'status': 'selecionada', 'foto': novo_nome})
        except Exception as e:
            erros.append(f"Erro ao processar atleta {atleta_id}: {str(e)}")
    
    return jsonify({
        'success': len(erros) == 0,
        'resultados': resultados,
        'erros': erros,
        'total_processados': len(resultados),
        'total_erros': len(erros)
    })

@app.route('/api/admin/visualizar-atletas')
@admin_required
def api_admin_visualizar_atletas():
    """API para listar todos os atletas com suas fotos"""
    from pathlib import Path
    
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT a.atleta_id, a.apelido, a.nome, c.nome as clube_nome, c.id as clube_id
            FROM acf_atletas a
            LEFT JOIN acf_clubes c ON a.clube_id = c.id
            ORDER BY c.nome, a.apelido, a.nome
        ''')
        atletas_raw = cursor.fetchall()
        
        foto_dir = Path('static/cartola_imgs/foto_atletas')
        from utils.team_shields import get_team_shield
        
        result = []
        for atleta_id, apelido, nome, clube_nome, clube_id in atletas_raw:
            # Verificar se tem foto (sem sufixo ou com sufixo)
            tem_foto = False
            foto_url = None
            
            # Primeiro verificar foto processada (sem sufixo)
            for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
                foto_path = foto_dir / f"{atleta_id}{ext}"
                if foto_path.exists():
                    tem_foto = True
                    foto_url = f"/static/cartola_imgs/foto_atletas/{foto_path.name}"
                    break
            
            # Se não tem foto processada, verificar fotos com sufixo
            if not tem_foto:
                for fonte in ['transfermarkt', 'ogol', 'custom']:
                    for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
                        foto_path = foto_dir / f"{atleta_id}_{fonte}{ext}"
                        if foto_path.exists():
                            tem_foto = True
                            foto_url = f"/static/cartola_imgs/foto_atletas/{foto_path.name}"
                            break
                    if tem_foto:
                        break
            
            escudo_url = get_team_shield(clube_id, size='45x45') if clube_id else ''
            
            result.append({
                'atleta_id': atleta_id,
                'apelido': apelido or '',
                'nome': nome or '',
                'clube_nome': clube_nome or 'Sem clube',
                'clube_id': clube_id,
                'clube_escudo_url': escudo_url,
                'tem_foto': tem_foto,
                'foto_url': foto_url
            })
        
        return jsonify({'atletas': result})
    except Exception as e:
        print(f"Erro API visualizar atletas: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        close_db_connection(conn)

@app.route('/api/admin/visualizar-atletas/salvar-urls', methods=['POST'])
@admin_required
def api_admin_visualizar_atletas_salvar_urls():
    """API para salvar múltiplas URLs de fotos de uma vez"""
    import os
    import requests
    from pathlib import Path
    from urllib.parse import urlparse
    
    data = request.get_json()
    urls = data.get('urls', [])  # Lista de {atleta_id, url}
    
    if not urls:
        return jsonify({'success': False, 'error': 'Nenhuma URL fornecida'}), 400
    
    foto_dir = Path('static/cartola_imgs/foto_atletas')
    foto_dir.mkdir(parents=True, exist_ok=True)
    
    resultados = []
    
    for item in urls:
        atleta_id = item.get('atleta_id')
        url_foto = item.get('url')
        
        if not atleta_id:
            resultados.append({
                'atleta_id': None,
                'success': False,
                'error': 'ID do atleta obrigatório'
            })
            continue
        
        if not url_foto:
            resultados.append({
                'atleta_id': atleta_id,
                'success': False,
                'error': 'URL obrigatória'
            })
            continue
        
        try:
            # Headers para evitar bloqueios
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
                'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8'
            }
            
            # Fazer download da imagem
            print(f"[DOWNLOAD] Baixando foto do atleta {atleta_id} de: {url_foto}")
            response = requests.get(url_foto, headers=headers, timeout=30, stream=True, allow_redirects=True)
            response.raise_for_status()
            
            # Verificar se é realmente uma imagem
            content_type = response.headers.get('content-type', '').lower()
            if 'image' not in content_type:
                resultados.append({
                    'atleta_id': atleta_id,
                    'success': False,
                    'error': f'URL não é uma imagem válida. Content-Type: {content_type}'
                })
                continue
            
            # Verificar tamanho máximo (10MB)
            content_length = response.headers.get('content-length')
            if content_length and int(content_length) > 10 * 1024 * 1024:
                resultados.append({
                    'atleta_id': atleta_id,
                    'success': False,
                    'error': 'Imagem muito grande (máximo 10MB)'
                })
                continue
            
            # Detectar extensão
            parsed_url = urlparse(url_foto)
            path = parsed_url.path.lower()
            
            if path.endswith('.jpg') or path.endswith('.jpeg'):
                ext = '.jpg'
            elif path.endswith('.png'):
                ext = '.png'
            elif path.endswith('.gif'):
                ext = '.gif'
            elif path.endswith('.webp'):
                ext = '.webp'
            else:
                if 'jpeg' in content_type or 'jpg' in content_type:
                    ext = '.jpg'
                elif 'png' in content_type:
                    ext = '.png'
                elif 'gif' in content_type:
                    ext = '.gif'
                elif 'webp' in content_type:
                    ext = '.webp'
                else:
                    ext = '.jpg'
            
            # Salvar como foto processada (sem sufixo)
            foto_path = foto_dir / f"{atleta_id}{ext}"
            
            # Remover foto antiga se existir (com ou sem sufixo)
            for ext_old in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
                # Remover foto processada antiga
                old_path = foto_dir / f"{atleta_id}{ext_old}"
                if old_path.exists() and old_path != foto_path:
                    old_path.unlink()
                
                # Remover fotos com sufixo
                for fonte in ['transfermarkt', 'ogol', 'custom']:
                    old_path = foto_dir / f"{atleta_id}_{fonte}{ext_old}"
                    if old_path.exists():
                        old_path.unlink()
            
            # Baixar em chunks
            total_size = 0
            max_size = 10 * 1024 * 1024
            
            with open(foto_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        total_size += len(chunk)
                        if total_size > max_size:
                            if foto_path.exists():
                                foto_path.unlink()
                            resultados.append({
                                'atleta_id': atleta_id,
                                'success': False,
                                'error': 'Imagem muito grande (máximo 10MB)'
                            })
                            break
                else:
                    # Verificar se foi salvo corretamente
                    if foto_path.exists() and foto_path.stat().st_size > 0:
                        tamanho_kb = foto_path.stat().st_size / 1024
                        print(f"[DOWNLOAD] ✅ Foto salva: {foto_path.name} ({tamanho_kb:.1f} KB)")
                        resultados.append({
                            'atleta_id': atleta_id,
                            'success': True,
                            'arquivo': foto_path.name,
                            'tamanho_kb': round(tamanho_kb, 1)
                        })
                    else:
                        if foto_path.exists():
                            foto_path.unlink()
                        resultados.append({
                            'atleta_id': atleta_id,
                            'success': False,
                            'error': 'Arquivo vazio ou não foi criado'
                        })
                    continue
                # Se saiu do loop por break (tamanho excedido), já foi tratado acima
                continue
        
        except requests.exceptions.Timeout:
            resultados.append({
                'atleta_id': atleta_id,
                'success': False,
                'error': 'Timeout: A URL demorou muito para responder'
            })
        except requests.exceptions.ConnectionError:
            resultados.append({
                'atleta_id': atleta_id,
                'success': False,
                'error': 'Erro de conexão: Não foi possível conectar à URL'
            })
        except requests.exceptions.HTTPError as e:
            resultados.append({
                'atleta_id': atleta_id,
                'success': False,
                'error': f'Erro HTTP {e.response.status_code}: {e.response.reason}'
            })
        except Exception as e:
            print(f"Erro ao baixar foto do atleta {atleta_id}: {e}")
            resultados.append({
                'atleta_id': atleta_id,
                'success': False,
                'error': str(e)[:100]
            })
    
    sucesso = len([r for r in resultados if r.get('success')])
    erros = len([r for r in resultados if not r.get('success')])
    
    return jsonify({
        'success': erros == 0,
        'resultados': resultados,
        'total_sucesso': sucesso,
        'total_erros': erros
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

