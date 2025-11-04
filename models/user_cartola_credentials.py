"""
Modelo para gerenciamento de credenciais do Cartola por usuário
"""
import psycopg2
from typing import Dict, Optional, List
from database import get_db_connection, close_db_connection

def create_user_cartola_credentials_table(conn: psycopg2.extensions.connection):
    """Cria a tabela de credenciais do Cartola por usuário (permite múltiplos times)"""
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS acw_cartola_credentials (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            access_token TEXT NOT NULL,
            refresh_token TEXT NOT NULL,
            id_token TEXT,
            team_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES acw_users(id) ON DELETE CASCADE
        )
    ''')
    # Remover constraint UNIQUE se existir (para permitir múltiplos times)
    try:
        cursor.execute('ALTER TABLE acw_cartola_credentials DROP CONSTRAINT IF EXISTS acw_cartola_credentials_user_id_key')
    except Exception:
        pass  # Pode não existir
    conn.commit()

def get_user_cartola_credentials(conn: psycopg2.extensions.connection, user_id: int) -> Optional[Dict]:
    """Busca credenciais do Cartola de um usuário"""
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, user_id, access_token, refresh_token, id_token, team_name, created_at, updated_at
        FROM acw_cartola_credentials
        WHERE user_id = %s
    ''', (user_id,))
    row = cursor.fetchone()
    if not row:
        return None
    return {
        'id': row[0],
        'user_id': row[1],
        'access_token': row[2],
        'refresh_token': row[3],
        'id_token': row[4],
        'team_name': row[5],
        'created_at': row[6],
        'updated_at': row[7]
    }

def get_all_user_cartola_credentials(conn: psycopg2.extensions.connection, user_id: int) -> List[Dict]:
    """Busca todas as credenciais do Cartola de um usuário (múltiplos times)"""
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, user_id, access_token, refresh_token, id_token, team_name, created_at, updated_at
        FROM acw_cartola_credentials
        WHERE user_id = %s
        ORDER BY created_at DESC
    ''', (user_id,))
    rows = cursor.fetchall()
    return [
        {
            'id': row[0],
            'user_id': row[1],
            'access_token': row[2],
            'refresh_token': row[3],
            'id_token': row[4],
            'team_name': row[5],
            'created_at': row[6],
            'updated_at': row[7]
        }
        for row in rows
    ]

def upsert_user_cartola_credentials(
    conn: psycopg2.extensions.connection,
    user_id: int,
    access_token: str,
    refresh_token: str,
    id_token: str = None,
    team_name: str = None
) -> int:
    """Cria credenciais do Cartola de um usuário. Retorna o ID."""
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO acw_cartola_credentials (user_id, access_token, refresh_token, id_token, team_name)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
    ''', (user_id, access_token, refresh_token, id_token, team_name))
    cred_id = cursor.fetchone()[0]
    conn.commit()
    return cred_id

