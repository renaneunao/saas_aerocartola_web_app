"""
Modelo para gerenciamento de rankings calculados por usuário
"""
import psycopg2
import json
from typing import List, Dict, Optional
from database import get_db_connection, close_db_connection

def create_rankings_teams_table(conn: psycopg2.extensions.connection):
    """Cria a tabela de rankings calculados por time"""
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS acw_rankings_teams (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            team_id INTEGER NOT NULL,
            configuration_id INTEGER REFERENCES acw_weight_configurations(id) ON DELETE CASCADE,
            posicao_id INTEGER NOT NULL,
            rodada_atual INTEGER NOT NULL,
            ranking_data JSONB NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES acw_users(id) ON DELETE CASCADE,
            FOREIGN KEY (team_id) REFERENCES acw_teams(id) ON DELETE CASCADE
        )
    ''')
    # Criar índices
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_rankings_teams_user_team ON acw_rankings_teams(user_id, team_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_rankings_teams_config ON acw_rankings_teams(team_id, configuration_id, posicao_id, rodada_atual)')
    conn.commit()

# Alias para compatibilidade com o nome esperado pelo app.py
def create_user_rankings_table(conn: psycopg2.extensions.connection):
    """Alias para create_rankings_teams_table por compatibilidade"""
    return create_rankings_teams_table(conn)

def save_team_ranking(
    conn: psycopg2.extensions.connection,
    user_id: int,
    team_id: int,
    configuration_id: Optional[int],
    posicao_id: int,
    rodada_atual: int,
    ranking_data
) -> int:
    """Salva um ranking calculado para um time"""
    cursor = conn.cursor()
    
    # Verificar se já existe ranking para esta combinação
    if configuration_id:
        cursor.execute('''
            SELECT id FROM acw_rankings_teams
            WHERE user_id = %s AND team_id = %s AND configuration_id = %s AND posicao_id = %s AND rodada_atual = %s
        ''', (user_id, team_id, configuration_id, posicao_id, rodada_atual))
    else:
        cursor.execute('''
            SELECT id FROM acw_rankings_teams
            WHERE user_id = %s AND team_id = %s AND configuration_id IS NULL AND posicao_id = %s AND rodada_atual = %s
        ''', (user_id, team_id, posicao_id, rodada_atual))
    
    existing = cursor.fetchone()
    
    # Garantir que ranking_data seja serializável
    if not isinstance(ranking_data, (dict, list)):
        ranking_data = list(ranking_data) if hasattr(ranking_data, '__iter__') else []
    
    ranking_json = json.dumps(ranking_data, ensure_ascii=False)
    
    if existing:
        # Atualizar
        cursor.execute('''
            UPDATE acw_rankings_teams
            SET ranking_data = %s, created_at = CURRENT_TIMESTAMP
            WHERE id = %s
        ''', (ranking_json, existing[0]))
        conn.commit()
        return existing[0]
    else:
        # Criar novo
        cursor.execute('''
            INSERT INTO acw_rankings_teams (user_id, team_id, configuration_id, posicao_id, rodada_atual, ranking_data)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
        ''', (user_id, team_id, configuration_id, posicao_id, rodada_atual, ranking_json))
        ranking_id = cursor.fetchone()[0]
        conn.commit()
        return ranking_id

def get_team_rankings(
    conn: psycopg2.extensions.connection,
    user_id: int,
    team_id: Optional[int] = None,
    configuration_id: Optional[int] = None,
    posicao_id: Optional[int] = None,
    rodada_atual: Optional[int] = None
) -> List[Dict]:
    """Busca rankings salvos de um time"""
    cursor = conn.cursor()
    
    query = '''
        SELECT id, user_id, team_id, configuration_id, posicao_id, rodada_atual, ranking_data, created_at
        FROM acw_rankings_teams
        WHERE user_id = %s
    '''
    params = [user_id]
    
    if team_id:
        query += ' AND team_id = %s'
        params.append(team_id)
    
    if configuration_id:
        query += ' AND configuration_id = %s'
        params.append(configuration_id)
    
    if posicao_id:
        query += ' AND posicao_id = %s'
        params.append(posicao_id)
    
    if rodada_atual:
        query += ' AND rodada_atual = %s'
        params.append(rodada_atual)
    
    query += ' ORDER BY rodada_atual DESC, posicao_id'
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    
    result = []
    for row in rows:
        ranking_data = row[6]  # ranking_data está na posição 6
        
        # PostgreSQL JSONB pode retornar dict, list ou str dependendo da versão
        if ranking_data is None:
            ranking_data = []
        elif isinstance(ranking_data, (dict, list)):
            # Já está no formato correto (dict ou list)
            pass
        elif isinstance(ranking_data, str):
            # É uma string JSON, precisa fazer parse
            try:
                ranking_data = json.loads(ranking_data)
            except (json.JSONDecodeError, TypeError):
                ranking_data = []
        else:
            # Outro tipo não esperado
            ranking_data = []
        
        result.append({
            'id': row[0],
            'user_id': row[1],
            'team_id': row[2],
            'configuration_id': row[3],
            'posicao_id': row[4],
            'rodada_atual': row[5],
            'ranking_data': ranking_data,
            'created_at': row[7]
        })
    return result

