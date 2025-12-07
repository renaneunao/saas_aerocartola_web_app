import psycopg2
from psycopg2.extras import RealDictCursor
import os

# Configurações do PostgreSQL - OBRIGATÓRIO usar variáveis de ambiente
POSTGRES_CONFIG = {
    'host': os.getenv('POSTGRES_HOST'),
    'port': int(os.getenv('POSTGRES_PORT', '5432')),
    'user': os.getenv('POSTGRES_USER'),
    'password': os.getenv('POSTGRES_PASSWORD'),
    'database': os.getenv('POSTGRES_DB')
}

# Validar que todas as variáveis estão definidas
required_vars = ['POSTGRES_HOST', 'POSTGRES_USER', 'POSTGRES_PASSWORD', 'POSTGRES_DB']
missing_vars = [var for var in required_vars if not os.getenv(var)]
if missing_vars:
    raise ValueError(f"Variáveis de ambiente obrigatórias não definidas: {', '.join(missing_vars)}")

def get_db_connection():
    """Conecta ao banco de dados PostgreSQL"""
    try:
        conn = psycopg2.connect(**POSTGRES_CONFIG)
        conn.autocommit = False
        return conn
    except psycopg2.Error as e:
        print(f"Erro ao conectar ao PostgreSQL: {e}")
        return None

def close_db_connection(conn):
    """Fecha a conexão com o banco de dados"""
    if conn:
        try:
            # Sempre tentar fazer rollback antes de fechar para evitar "current transaction is aborted"
            # Isso é seguro mesmo se não houver transação ativa ou se já foi commitado
            try:
                conn.rollback()
            except Exception as rollback_error:
                # Se o rollback falhar (ex: já foi commitado ou fechado), ignorar
                pass
            conn.close()
        except psycopg2.Error as e:
            print(f"Erro ao fechar conexão: {e}")
        except Exception as e:
            # Capturar qualquer outro erro ao fechar
            print(f"Erro inesperado ao fechar conexão: {e}")

def execute_query(query, params=None, fetch_one=False, fetch_all=False):
    """Executa uma query e retorna o resultado"""
    conn = get_db_connection()
    if not conn:
        return None
    
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(query, params)
        
        if fetch_one:
            result = cursor.fetchone()
        elif fetch_all:
            result = cursor.fetchall()
        else:
            result = cursor.rowcount
        
        conn.commit()
        cursor.close()
        return result
        
    except psycopg2.Error as e:
        conn.rollback()
        print(f"Erro na query: {e}")
        return None
    finally:
        close_db_connection(conn)

def test_connection():
    """Testa a conexão com o banco"""
    conn = get_db_connection()
    if conn:
        print("✅ Conexão com PostgreSQL estabelecida com sucesso!")
        close_db_connection(conn)
        return True
    else:
        print("❌ Falha na conexão com PostgreSQL")
        return False