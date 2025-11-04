import psycopg2
from typing import List, Dict

def create_credenciais_table(conn: psycopg2.extensions.connection):
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS acf_credenciais (
            id SERIAL PRIMARY KEY,
            nome TEXT NOT NULL,
            env_key TEXT UNIQUE,
            access_token TEXT,
            refresh_token TEXT,
            id_token TEXT,
            estrategia INTEGER DEFAULT 1,
            essential_cookies TEXT
        )
    ''')
    conn.commit()

def insert_credencial(conn: psycopg2.extensions.connection, nome: str, env_key: str, access_token: str = None, refresh_token: str = None, id_token: str = None, estrategia: int = 1, essential_cookies: str = None):
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO acf_credenciais (nome, env_key, access_token, refresh_token, id_token, estrategia, essential_cookies)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (env_key) DO UPDATE SET
            nome = EXCLUDED.nome,
            access_token = EXCLUDED.access_token,
            refresh_token = EXCLUDED.refresh_token,
            id_token = EXCLUDED.id_token,
            estrategia = EXCLUDED.estrategia,
            essential_cookies = EXCLUDED.essential_cookies
    ''', (nome, env_key, access_token, refresh_token, id_token, estrategia, essential_cookies))
    conn.commit()

def update_tokens_by_env_key(conn: psycopg2.extensions.connection, env_key: str, access_token: str = None, refresh_token: str = None, id_token: str = None):
    cursor = conn.cursor()
    # Build dynamic set
    sets = []
    params = []
    if access_token is not None:
        sets.append('access_token = %s')
        params.append(access_token)
    if refresh_token is not None:
        sets.append('refresh_token = %s')
        params.append(refresh_token)
    if id_token is not None:
        sets.append('id_token = %s')
        params.append(id_token)
    if not sets:
        return
    params.append(env_key)
    query = f"UPDATE acf_credenciais SET {', '.join(sets)} WHERE env_key = %s"
    cursor.execute(query, params)
    conn.commit()

def get_all_credenciais(conn: psycopg2.extensions.connection) -> List[Dict]:
    cursor = conn.cursor()
    cursor.execute('SELECT id, nome, env_key, access_token, refresh_token, id_token, estrategia, essential_cookies FROM acf_credenciais')
    rows = cursor.fetchall()
    result = []
    for r in rows:
        result.append({
            'id': r[0], 
            'nome': r[1], 
            'env_key': r[2], 
            'access_token': r[3], 
            'refresh_token': r[4], 
            'id_token': r[5], 
            'estrategia': r[6],
            'essential_cookies': r[7]
        })
    return result

def get_credencial_by_env_key(conn: psycopg2.extensions.connection, env_key: str) -> Dict:
    """Retorna uma única credencial pelo env_key ou None se não existir."""
    cursor = conn.cursor()
    cursor.execute('SELECT id, nome, env_key, access_token, refresh_token, id_token, estrategia, essential_cookies FROM acf_credenciais WHERE env_key = %s LIMIT 1', (env_key,))
    r = cursor.fetchone()
    if not r:
        return None
    return {
        'id': r[0], 
        'nome': r[1], 
        'env_key': r[2], 
        'access_token': r[3], 
        'refresh_token': r[4], 
        'id_token': r[5], 
        'estrategia': r[6],
        'essential_cookies': r[7]
    }
