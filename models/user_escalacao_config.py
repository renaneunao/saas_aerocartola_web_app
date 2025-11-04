"""
Modelo para gerenciamento de configurações de escalação ideal por usuário e time
"""
import psycopg2
import json
from typing import Optional, Dict, List
from database import get_db_connection, close_db_connection

def create_user_escalacao_config_table(conn: psycopg2.extensions.connection):
    """Cria a tabela de configurações de escalação ideal por usuário e time"""
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS acw_escalacao_config (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            team_id INTEGER NOT NULL,
            formation VARCHAR(20) DEFAULT '4-3-3',
            hack_goleiro BOOLEAN DEFAULT FALSE,
            fechar_defesa BOOLEAN DEFAULT FALSE,
            posicao_capitao VARCHAR(50) DEFAULT 'atacantes',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES acw_users(id) ON DELETE CASCADE,
            FOREIGN KEY (team_id) REFERENCES acw_teams(id) ON DELETE CASCADE,
            UNIQUE(user_id, team_id)
        )
    ''')
    # Criar índices apenas se as colunas existirem
    try:
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_escalacao_config_user_id ON acw_escalacao_config(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_escalacao_config_team_id ON acw_escalacao_config(team_id)')
    except Exception:
        pass  # Índices podem já existir
    conn.commit()

def get_user_escalacao_config(conn: psycopg2.extensions.connection, user_id: int, team_id: Optional[int] = None) -> Optional[Dict]:
    """Busca a configuração de escalação ideal de um usuário para um time específico"""
    cursor = conn.cursor()
    
    if team_id:
        cursor.execute('''
            SELECT id, user_id, team_id, formation, hack_goleiro, fechar_defesa, posicao_capitao, created_at, updated_at
            FROM acw_escalacao_config
            WHERE user_id = %s AND team_id = %s
            LIMIT 1
        ''', (user_id, team_id))
    else:
        # Se não especificar, busca a primeira configuração do usuário
        cursor.execute('''
            SELECT id, user_id, team_id, formation, hack_goleiro, fechar_defesa, posicao_capitao, created_at, updated_at
            FROM acw_escalacao_config
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT 1
        ''', (user_id,))
    
    row = cursor.fetchone()
    if not row:
        return None
    return {
        'id': row[0],
        'user_id': row[1],
        'team_id': row[2],
        'formation': row[3],
        'hack_goleiro': row[4],
        'fechar_defesa': row[5],
        'posicao_capitao': row[6],
        'created_at': row[7],
        'updated_at': row[8]
    }

def get_all_user_escalacao_configs(conn: psycopg2.extensions.connection, user_id: int) -> List[Dict]:
    """Busca todas as configurações de escalação ideal de um usuário"""
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, user_id, team_id, formation, hack_goleiro, fechar_defesa, posicao_capitao, created_at, updated_at
        FROM acw_escalacao_config
        WHERE user_id = %s
        ORDER BY created_at DESC
    ''', (user_id,))
    rows = cursor.fetchall()
    return [
        {
            'id': row[0],
            'user_id': row[1],
            'team_id': row[2],
            'formation': row[3],
            'hack_goleiro': row[4],
            'fechar_defesa': row[5],
            'posicao_capitao': row[6],
            'created_at': row[7],
            'updated_at': row[8]
        }
        for row in rows
    ]

def upsert_user_escalacao_config(
    conn: psycopg2.extensions.connection,
    user_id: int,
    team_id: int,
    formation: str = '4-3-3',
    hack_goleiro: bool = False,
    fechar_defesa: bool = False,
    posicao_capitao: str = 'atacantes'
) -> int:
    """Cria ou atualiza a configuração de escalação ideal de um usuário para um time específico"""
    cursor = conn.cursor()
    
    # Verificar se já existe
    cursor.execute('''
        SELECT id FROM acw_escalacao_config
        WHERE user_id = %s AND team_id = %s
    ''', (user_id, team_id))
    existing = cursor.fetchone()
    
    if existing:
        # Atualizar
        cursor.execute('''
            UPDATE acw_escalacao_config
            SET formation = %s, hack_goleiro = %s, fechar_defesa = %s, posicao_capitao = %s, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = %s AND team_id = %s
            RETURNING id
        ''', (formation, hack_goleiro, fechar_defesa, posicao_capitao, user_id, team_id))
        config_id = cursor.fetchone()[0]
    else:
        # Criar novo
        cursor.execute('''
            INSERT INTO acw_escalacao_config (user_id, team_id, formation, hack_goleiro, fechar_defesa, posicao_capitao)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
        ''', (user_id, team_id, formation, hack_goleiro, fechar_defesa, posicao_capitao))
        config_id = cursor.fetchone()[0]
    
    conn.commit()
    return config_id

