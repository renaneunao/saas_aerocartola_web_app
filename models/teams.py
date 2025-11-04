"""
Modelo para gerenciamento de times do Cartola por usuário
"""
import psycopg2
from typing import Dict, Optional, List
from database import get_db_connection, close_db_connection

def create_teams_table(conn: psycopg2.extensions.connection):
    """Cria a tabela de times do Cartola por usuário (permite múltiplos times)"""
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS acw_teams (
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
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_teams_user_id ON acw_teams(user_id)')
    conn.commit()

def get_team(conn: psycopg2.extensions.connection, team_id: int, user_id: Optional[int] = None) -> Optional[Dict]:
    """Busca um time específico por ID"""
    cursor = conn.cursor()
    if user_id:
        cursor.execute('''
            SELECT id, user_id, access_token, refresh_token, id_token, team_name, created_at, updated_at
            FROM acw_teams
            WHERE id = %s AND user_id = %s
        ''', (team_id, user_id))
    else:
        cursor.execute('''
            SELECT id, user_id, access_token, refresh_token, id_token, team_name, created_at, updated_at
            FROM acw_teams
            WHERE id = %s
        ''', (team_id,))
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

def get_all_user_teams(conn: psycopg2.extensions.connection, user_id: int) -> List[Dict]:
    """Busca todos os times de um usuário"""
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, user_id, access_token, refresh_token, id_token, team_name, created_at, updated_at
        FROM acw_teams
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

def create_team(
    conn: psycopg2.extensions.connection,
    user_id: int,
    access_token: str,
    refresh_token: str,
    id_token: str = None,
    team_name: str = None
) -> int:
    """Cria um novo time. Retorna o ID."""
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO acw_teams (user_id, access_token, refresh_token, id_token, team_name)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
    ''', (user_id, access_token, refresh_token, id_token, team_name))
    team_id = cursor.fetchone()[0]
    conn.commit()
    return team_id

def update_team(
    conn: psycopg2.extensions.connection,
    team_id: int,
    user_id: int,
    access_token: str = None,
    refresh_token: str = None,
    id_token: str = None,
    team_name: str = None
) -> bool:
    """Atualiza um time existente"""
    cursor = conn.cursor()
    updates = []
    params = []
    
    if access_token is not None:
        updates.append('access_token = %s')
        params.append(access_token)
    if refresh_token is not None:
        updates.append('refresh_token = %s')
        params.append(refresh_token)
    if id_token is not None:
        updates.append('id_token = %s')
        params.append(id_token)
    if team_name is not None:
        updates.append('team_name = %s')
        params.append(team_name)
    
    if not updates:
        return False
    
    updates.append('updated_at = CURRENT_TIMESTAMP')
    params.extend([team_id, user_id])
    
    cursor.execute(f'''
        UPDATE acw_teams
        SET {', '.join(updates)}
        WHERE id = %s AND user_id = %s
    ''', params)
    conn.commit()
    return cursor.rowcount > 0

def update_team_tokens(
    conn: psycopg2.extensions.connection,
    team_id: int,
    access_token: str = None,
    refresh_token: str = None,
    id_token: str = None
) -> bool:
    """Atualiza apenas os tokens de um time (usado para refresh)"""
    cursor = conn.cursor()
    updates = []
    params = []
    
    if access_token is not None:
        updates.append('access_token = %s')
        params.append(access_token)
    if refresh_token is not None:
        updates.append('refresh_token = %s')
        params.append(refresh_token)
    if id_token is not None:
        updates.append('id_token = %s')
        params.append(id_token)
    
    if not updates:
        return False
    
    updates.append('updated_at = CURRENT_TIMESTAMP')
    params.append(team_id)
    
    cursor.execute(f'''
        UPDATE acw_teams
        SET {', '.join(updates)}
        WHERE id = %s
    ''', params)
    conn.commit()
    return cursor.rowcount > 0

def delete_team(conn: psycopg2.extensions.connection, team_id: int, user_id: int) -> bool:
    """Deleta um time"""
    cursor = conn.cursor()
    cursor.execute('''
        DELETE FROM acw_teams
        WHERE id = %s AND user_id = %s
    ''', (team_id, user_id))
    conn.commit()
    return cursor.rowcount > 0

