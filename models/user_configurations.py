"""
Modelo para gerenciamento de configurações de pesos por usuário
"""
import psycopg2
import json
from typing import List, Dict, Optional
from database import get_db_connection, close_db_connection

def create_user_configurations_table(conn: psycopg2.extensions.connection):
    """Cria a tabela de configurações de pesos por usuário"""
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS acw_weight_configurations (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            name VARCHAR(255) NOT NULL,
            perfil_peso_jogo INTEGER NOT NULL,
            perfil_peso_sg INTEGER NOT NULL,
            is_default BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES acw_users(id) ON DELETE CASCADE,
            team_id INTEGER NOT NULL,
            FOREIGN KEY (team_id) REFERENCES acw_teams(id) ON DELETE CASCADE,
            UNIQUE(user_id, team_id)
        )
    ''')
    # Criar índices apenas se as colunas existirem
    try:
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_weight_configurations_user_id ON acw_weight_configurations(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_weight_configurations_team_id ON acw_weight_configurations(team_id)')
    except Exception:
        pass  # Índices podem já existir
    conn.commit()

def get_user_configurations(conn: psycopg2.extensions.connection, user_id: int, team_id: Optional[int] = None) -> List[Dict]:
    """Busca todas as configurações de um usuário"""
    cursor = conn.cursor()
    query = '''
        SELECT id, user_id, team_id, name, perfil_peso_jogo, perfil_peso_sg, is_default, created_at, updated_at
        FROM acw_weight_configurations
        WHERE user_id = %s
    '''
    params = [user_id]
    if team_id:
        query += ' AND team_id = %s'
        params.append(team_id)
    query += ' ORDER BY is_default DESC, created_at DESC'
    cursor.execute(query, params)
    rows = cursor.fetchall()
    result = []
    for row in rows:
        result.append({
            'id': row[0],
            'user_id': row[1],
            'team_id': row[2],
            'name': row[3],
            'perfil_peso_jogo': row[4],
            'perfil_peso_sg': row[5],
            'is_default': row[6],
            'created_at': row[7],
            'updated_at': row[8]
        })
    return result

def get_user_default_configuration(conn: psycopg2.extensions.connection, user_id: int, team_id: Optional[int] = None) -> Optional[Dict]:
    """Busca a configuração padrão de um usuário"""
    cursor = conn.cursor()
    query = '''
        SELECT id, user_id, team_id, name, perfil_peso_jogo, perfil_peso_sg, is_default, created_at, updated_at
        FROM acw_weight_configurations
        WHERE user_id = %s AND is_default = TRUE
    '''
    params = [user_id]
    if team_id:
        query += ' AND team_id = %s'
        params.append(team_id)
    query += ' LIMIT 1'
    cursor.execute(query, params)
    row = cursor.fetchone()
    if not row:
        return None
    return {
        'id': row[0],
        'user_id': row[1],
        'team_id': row[2],
        'name': row[3],
        'perfil_peso_jogo': row[4],
        'perfil_peso_sg': row[5],
        'is_default': row[6],
        'created_at': row[7],
        'updated_at': row[8]
    }

def create_user_configuration(
    conn: psycopg2.extensions.connection,
    user_id: int,
    team_id: int,
    name: str,
    perfil_peso_jogo: int,
    perfil_peso_sg: int,
    is_default: bool = False
) -> int:
    """Cria ou atualiza uma configuração de pesos para um time"""
    cursor = conn.cursor()
    
    # Se for padrão, remover padrão de outras configurações do mesmo time
    if is_default:
        cursor.execute('''
            UPDATE acw_weight_configurations
            SET is_default = FALSE
            WHERE user_id = %s AND team_id = %s
        ''', (user_id, team_id))
    
    # Usar UPSERT (INSERT ... ON CONFLICT UPDATE) para atualizar se já existir
    cursor.execute('''
        INSERT INTO acw_weight_configurations (user_id, team_id, name, perfil_peso_jogo, perfil_peso_sg, is_default)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (user_id, team_id) 
        DO UPDATE SET
            name = EXCLUDED.name,
            perfil_peso_jogo = EXCLUDED.perfil_peso_jogo,
            perfil_peso_sg = EXCLUDED.perfil_peso_sg,
            is_default = EXCLUDED.is_default,
            updated_at = CURRENT_TIMESTAMP
        RETURNING id
    ''', (user_id, team_id, name, perfil_peso_jogo, perfil_peso_sg, is_default))
    
    config_id = cursor.fetchone()[0]
    conn.commit()
    return config_id

