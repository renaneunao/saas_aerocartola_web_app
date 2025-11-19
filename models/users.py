"""
Modelo para gerenciamento de usuários do sistema
"""

import psycopg2
import hashlib
import secrets
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from database import get_db_connection, close_db_connection, execute_query, execute_query

# Para criptografia reversível da senha (para recuperação)
try:
    from cryptography.fernet import Fernet
    CRYPTO_AVAILABLE = True
    # Gerar ou usar chave de criptografia
    CRYPTO_KEY = os.getenv('CRYPTO_KEY', Fernet.generate_key().decode())
    if isinstance(CRYPTO_KEY, str):
        CRYPTO_KEY = CRYPTO_KEY.encode()
    fernet = Fernet(CRYPTO_KEY)
except ImportError:
    CRYPTO_AVAILABLE = False
    fernet = None


def create_users_table():
    """Cria a tabela de usuários se não existir"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS acw_users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                email VARCHAR(100) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                salt VARCHAR(32) NOT NULL,
                password_encrypted TEXT,
                full_name VARCHAR(100),
                is_active BOOLEAN DEFAULT TRUE,
                is_admin BOOLEAN DEFAULT FALSE,
                email_verified BOOLEAN DEFAULT FALSE,
                email_verification_token VARCHAR(255),
                password_reset_token VARCHAR(255),
                password_reset_expires TIMESTAMP,
                last_login TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Adicionar colunas se não existirem
        try:
            cursor.execute('''
                ALTER TABLE acw_users 
                ADD COLUMN IF NOT EXISTS password_encrypted TEXT
            ''')
            cursor.execute('''
                ALTER TABLE acw_users 
                ADD COLUMN IF NOT EXISTS password_reset_token VARCHAR(255)
            ''')
            cursor.execute('''
                ALTER TABLE acw_users 
                ADD COLUMN IF NOT EXISTS password_reset_expires TIMESTAMP
            ''')
        except psycopg2.Error:
            pass  # Colunas já existem
        
        # Adicionar colunas de verificação de email se não existirem (para tabelas antigas)
        try:
            cursor.execute('''
                ALTER TABLE acw_users 
                ADD COLUMN IF NOT EXISTS email_verified BOOLEAN DEFAULT FALSE
            ''')
            cursor.execute('''
                ALTER TABLE acw_users 
                ADD COLUMN IF NOT EXISTS email_verification_token VARCHAR(255)
            ''')
        except psycopg2.Error:
            pass  # Colunas já existem ou erro ao adicionar
        
        # Criar índices para melhor performance
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_username ON acw_users (username)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_email ON acw_users (email)')
        
        conn.commit()
        print("✅ Tabela de usuários criada com sucesso!")
        
    except psycopg2.Error as e:
        print(f"Erro ao criar tabelas: {e}")
        conn.rollback()
    finally:
        close_db_connection(conn)


def hash_password(password: str) -> tuple:
    """Gera hash da senha com salt e também criptografa para recuperação"""
    salt = secrets.token_hex(16)
    password_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000)
    
    # Criptografar senha para recuperação (reversível)
    password_encrypted = None
    if CRYPTO_AVAILABLE and fernet:
        try:
            password_encrypted = fernet.encrypt(password.encode('utf-8')).decode('utf-8')
        except Exception as e:
            print(f"[WARNING] Erro ao criptografar senha: {e}")
    
    return password_hash.hex(), salt, password_encrypted

def decrypt_password(encrypted_password: str) -> Optional[str]:
    """Descriptografa a senha armazenada"""
    if not CRYPTO_AVAILABLE or not fernet or not encrypted_password:
        return None
    try:
        return fernet.decrypt(encrypted_password.encode('utf-8')).decode('utf-8')
    except Exception as e:
        print(f"[WARNING] Erro ao descriptografar senha: {e}")
        return None


def verify_password(password: str, password_hash: str, salt: str) -> bool:
    """Verifica se a senha está correta"""
    computed_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000)
    return computed_hash.hex() == password_hash


def create_user(username: str, email: str, password: str, full_name: str = None, is_admin: bool = False, email_verified: bool = False) -> dict:
    """Cria um novo usuário"""
    conn = get_db_connection()
    if not conn:
        return {'success': False, 'error': 'Erro ao conectar ao banco de dados'}
    
    cursor = conn.cursor()
    
    try:
        # Verificar se usuário ou email já existem
        print(f"[DEBUG create_user] Verificando se usuário/email já existem: username={username}, email={email}")
        cursor.execute('SELECT id, username, email FROM acw_users WHERE username = %s OR email = %s', (username, email))
        existing = cursor.fetchone()
        if existing:
            existing_id, existing_username, existing_email = existing
            print(f"[DEBUG create_user] Usuário/email já existe! ID: {existing_id}, Username: {existing_username}, Email: {existing_email}")
            if existing_username == username:
                return {'success': False, 'error': f'Nome de usuário "{username}" já está em uso.'}
            elif existing_email == email:
                return {'success': False, 'error': f'Email "{email}" já está cadastrado.'}
            return {'success': False, 'error': 'Usuário ou email já existem'}
        
        # Gerar hash da senha e criptografar para recuperação
        password_hash, salt, password_encrypted = hash_password(password)
        
        # Gerar token de verificação de email
        verification_token = secrets.token_urlsafe(32)
        
        # Inserir usuário
        cursor.execute('''
            INSERT INTO acw_users (username, email, password_hash, salt, password_encrypted, full_name, is_admin, email_verified, email_verification_token)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        ''', (username, email, password_hash, salt, password_encrypted, full_name, is_admin, email_verified, verification_token))
        
        user_id = cursor.fetchone()[0]
        conn.commit()
        
        return {
            'success': True, 
            'user_id': user_id,
            'verification_token': verification_token,
            'message': 'Usuário criado com sucesso!'
        }
        
    except psycopg2.Error as e:
        conn.rollback()
        return {'success': False, 'error': f'Erro ao criar usuário: {str(e)}'}
    
    finally:
        close_db_connection(conn)


def authenticate_user(username_or_email: str, password: str) -> dict:
    """Autentica um usuário"""
    conn = get_db_connection()
    if not conn:
        return {'success': False, 'error': 'Erro ao conectar ao banco de dados'}
    
    cursor = conn.cursor()
    
    try:
        # Buscar usuário por username ou email
        cursor.execute('''
            SELECT id, username, email, password_hash, salt, full_name, is_active, is_admin, email_verified
            FROM acw_users 
            WHERE (username = %s OR email = %s) AND is_active = TRUE
        ''', (username_or_email, username_or_email))
        
        user = cursor.fetchone()
        if not user:
            return {'success': False, 'error': 'Usuário não encontrado ou inativo'}
        
        user_id, username, email, stored_hash, salt, full_name, is_active, is_admin, email_verified = user
        
        # Verificar senha
        if not verify_password(password, stored_hash, salt):
            return {'success': False, 'error': 'Senha incorreta'}
        
        # Verificar se email foi verificado
        if not email_verified:
            return {
                'success': False, 
                'error': 'Email não verificado. Por favor, verifique seu email antes de fazer login.',
                'email_not_verified': True
            }
        
        # Atualizar último login
        cursor.execute('UPDATE acw_users SET last_login = CURRENT_TIMESTAMP WHERE id = %s', (user_id,))
        conn.commit()
        
        return {
            'success': True,
            'user': {
                'id': user_id,
                'username': username,
                'email': email,
                'full_name': full_name,
                'is_admin': is_admin
            }
        }
        
    except psycopg2.Error as e:
        return {'success': False, 'error': f'Erro na autenticação: {str(e)}'}
    
    finally:
        close_db_connection(conn)


def verify_email_token(token: str) -> Dict[str, Any]:
    """Verifica o token de email e marca o email como verificado"""
    conn = get_db_connection()
    if not conn:
        return {'success': False, 'error': 'Erro ao conectar ao banco de dados'}
    
    cursor = conn.cursor()
    
    try:
        # Buscar usuário pelo token
        cursor.execute('''
            SELECT id, username, email, email_verified
            FROM acw_users 
            WHERE email_verification_token = %s
        ''', (token,))
        
        user = cursor.fetchone()
        if not user:
            return {'success': False, 'error': 'Token inválido ou expirado'}
        
        user_id, username, email, already_verified = user
        
        if already_verified:
            return {'success': True, 'message': 'Email já estava verificado', 'already_verified': True}
        
        # Marcar email como verificado e limpar token
        cursor.execute('''
            UPDATE acw_users 
            SET email_verified = TRUE, email_verification_token = NULL, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        ''', (user_id,))
        
        conn.commit()
        
        return {
            'success': True,
            'message': 'Email verificado com sucesso!',
            'user': {
                'id': user_id,
                'username': username,
                'email': email
            }
        }
        
    except psycopg2.Error as e:
        conn.rollback()
        return {'success': False, 'error': f'Erro ao verificar email: {str(e)}'}
    
    finally:
        close_db_connection(conn)


def get_user_by_verification_token(token: str) -> Optional[Dict[str, Any]]:
    """Busca usuário pelo token de verificação"""
    conn = get_db_connection()
    if not conn:
        return None
    
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT id, username, email, email_verified
            FROM acw_users 
            WHERE email_verification_token = %s
        ''', (token,))
        
        user = cursor.fetchone()
        if not user:
            return None
        
        return {
            'id': user[0],
            'username': user[1],
            'email': user[2],
            'email_verified': user[3]
        }
        
    except psycopg2.Error as e:
        return None
    
    finally:
        close_db_connection(conn)


def create_session(user_id: int, user_agent: str = None, ip_address: str = None, remember_me: bool = False) -> str:
    """Cria uma sessão para o usuário"""
    conn = get_db_connection()
    if not conn:
        return None
    
    cursor = conn.cursor()
    
    try:
        # Gerar token único
        session_token = secrets.token_urlsafe(32)
        
        # Definir expiração (7 dias se remember_me, senão 1 dia)
        expires_at = datetime.now() + timedelta(days=7 if remember_me else 1)
        
        # Inserir sessão
        cursor.execute('''
            INSERT INTO acw_sessions (user_id, session_token, expires_at, user_agent, ip_address)
            VALUES (%s, %s, %s, %s, %s)
        ''', (user_id, session_token, expires_at, user_agent, ip_address))
        
        conn.commit()
        return session_token
        
    except psycopg2.Error as e:
        print(f"Erro ao criar sessão: {e}")
        return None
    
    finally:
        close_db_connection(conn)


def get_user_by_session(session_token: str) -> dict:
    """Busca usuário por token de sessão"""
    conn = get_db_connection()
    if not conn:
        return None
    
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT u.id, u.username, u.email, u.full_name, u.is_admin, s.expires_at
            FROM acw_users u
            JOIN acw_sessions s ON u.id = s.user_id
            WHERE s.session_token = %s AND s.expires_at > CURRENT_TIMESTAMP AND u.is_active = TRUE
        ''', (session_token,))
        
        result = cursor.fetchone()
        if not result:
            return None
        
        user_id, username, email, full_name, is_admin, expires_at = result
        
        return {
            'id': user_id,
            'username': username,
            'email': email,
            'full_name': full_name,
            'is_admin': is_admin,
            'session_expires': expires_at
        }
        
    except psycopg2.Error as e:
        print(f"Erro ao buscar usuário por sessão: {e}")
        return None
    
    finally:
        close_db_connection(conn)


def delete_session(session_token: str) -> bool:
    """Remove uma sessão (logout)"""
    conn = get_db_connection()
    if not conn:
        return False
    
    cursor = conn.cursor()
    
    try:
        cursor.execute('DELETE FROM acw_sessions WHERE session_token = %s', (session_token,))
        conn.commit()
        return cursor.rowcount > 0
        
    except psycopg2.Error as e:
        print(f"Erro ao deletar sessão: {e}")
        return False
    
    finally:
        close_db_connection(conn)


def cleanup_expired_sessions():
    """Remove sessões expiradas"""
    conn = get_db_connection()
    if not conn:
        return 0
    
    cursor = conn.cursor()
    
    try:
        cursor.execute('DELETE FROM acw_sessions WHERE expires_at < CURRENT_TIMESTAMP')
        deleted_count = cursor.rowcount
        conn.commit()
        
        if deleted_count > 0:
            print(f"🧹 {deleted_count} sessões expiradas removidas")
        
        return deleted_count
        
    except psycopg2.Error as e:
        print(f"Erro ao limpar sessões expiradas: {e}")
        return 0
    
    finally:
        close_db_connection(conn)


def get_all_users() -> list:
    """Lista todos os usuários (para admin)"""
    conn = get_db_connection()
    if not conn:
        return []
    
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT id, username, email, full_name, is_active, is_admin, last_login, created_at
            FROM acw_users
            ORDER BY created_at DESC
        ''')
        
        users = []
        for row in cursor.fetchall():
            users.append({
                'id': row[0],
                'username': row[1],
                'email': row[2],
                'full_name': row[3],
                'is_active': bool(row[4]),
                'is_admin': bool(row[5]),
                'last_login': row[6],
                'created_at': row[7]
            })
        
        return users
        
    except psycopg2.Error as e:
        print(f"Erro ao listar usuários: {e}")
        return []
    
    finally:
        close_db_connection(conn)


def create_default_users():
    """Cria usuários padrão se não existirem"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        created_users = []
        
        # Verificar se admin existe
        cursor.execute('SELECT COUNT(*) FROM acw_users WHERE username = %s', ('admin',))
        if cursor.fetchone()[0] == 0:
            result = create_user(
                username='admin',
                email='admin@cartolamanager.com',
                password='admin123',
                full_name='Administrador',
                is_admin=True
            )
            if result['success']:
                created_users.append({'username': 'admin', 'password': 'admin123'})
        
        # Verificar se renaneunao existe
        cursor.execute('SELECT COUNT(*) FROM acw_users WHERE username = %s', ('renaneunao',))
        if cursor.fetchone()[0] == 0:
            result = create_user(
                username='renaneunao',
                email='renan@cartolamanager.com',
                password='!Senhas123',
                full_name='Renan',
                is_admin=True
            )
            if result['success']:
                created_users.append({'username': 'renaneunao', 'password': '!Senhas123'})
        
        if created_users:
            print("🔐 Usuários padrão criados:")
            for user in created_users:
                print(f"   Username: {user['username']}")
                print(f"   Password: {user['password']}")
            print("   ⚠️  ALTERE AS SENHAS APÓS O PRIMEIRO LOGIN!")
        
    except psycopg2.Error as e:
        print(f"Erro ao criar usuários padrão: {e}")
    
    finally:
        close_db_connection(conn)


def update_user_password(user_id: int, new_password: str) -> bool:
    """Atualiza a senha de um usuário"""
    conn = get_db_connection()
    if not conn:
        return False
    
    cursor = conn.cursor()
    
    try:
        password_hash, salt, password_encrypted = hash_password(new_password)
        
        cursor.execute('''
            UPDATE acw_users 
            SET password_hash = %s, salt = %s, password_encrypted = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        ''', (password_hash, salt, password_encrypted, user_id))
        
        conn.commit()
        return cursor.rowcount > 0
        
    except psycopg2.Error as e:
        print(f"Erro ao atualizar senha: {e}")
        return False
    
    finally:
        close_db_connection(conn)
