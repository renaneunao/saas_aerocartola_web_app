import os
import sys
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

from database import get_db_connection, close_db_connection

def verify_sql_logic():
    conn = get_db_connection()
    if not conn:
        print("Failed to connect to database")
        return

    try:
        cursor = conn.cursor()
        
        # 1. Check if there are any entries in laterais_esquerdos
        cursor.execute("SELECT COUNT(*) FROM laterais_esquerdos")
        count = cursor.fetchone()[0]
        print(f"Entries in laterais_esquerdos: {count}")
        
        # If empty, insert a dummy one for testing (find a lateral first)
        if count == 0:
            print("Inserting dummy lateral esquerdo for testing...")
            cursor.execute("SELECT atleta_id FROM acf_atletas WHERE posicao_id = 2 LIMIT 1")
            row = cursor.fetchone()
            if row:
                atleta_id = row[0]
                cursor.execute("INSERT INTO laterais_esquerdos (atleta_id) VALUES (%s)", (atleta_id,))
                conn.commit()
                print(f"Inserted atleta_id {atleta_id} as lateral esquerdo")
            else:
                print("No laterais found in acf_atletas to test with.")
                return

        # 2. Run the complex query from app.py
        print("\nRunning aggregation query...")
        
        # Get max rodada
        cursor.execute('SELECT MAX(rodada_atual) FROM acp_peso_jogo_perfis')
        rodada_result = cursor.fetchone()
        rodada_atual = rodada_result[0] if rodada_result and rodada_result[0] else 1
        print(f"Rodada atual: {rodada_atual}")
        
        # Get some adversaries (simulate)
        cursor.execute("SELECT id FROM acf_clubes LIMIT 5")
        adversario_ids = [row[0] for row in cursor.fetchall()]
        
        if not adversario_ids:
            print("No clubs found.")
            return
            
        placeholders = ','.join(['%s'] * len(adversario_ids))
        posicao_id = 2 # Lateral
        
        query = f'''
            SELECT p.clube_id, 
                   AVG(p.scout_ds) as avg_ds_cedidos,
                   AVG(CASE WHEN le.atleta_id IS NOT NULL THEN p.scout_ds END) as avg_ds_cedidos_esq,
                   AVG(CASE WHEN le.atleta_id IS NULL THEN p.scout_ds END) as avg_ds_cedidos_dir,
                   
                   AVG(p.scout_ff) as avg_ff_cedidos,
                   AVG(CASE WHEN le.atleta_id IS NOT NULL THEN p.scout_ff END) as avg_ff_cedidos_esq,
                   AVG(CASE WHEN le.atleta_id IS NULL THEN p.scout_ff END) as avg_ff_cedidos_dir
            FROM acf_pontuados p
            JOIN acf_partidas pt ON p.rodada_id = pt.rodada_id
            LEFT JOIN laterais_esquerdos le ON p.atleta_id = le.atleta_id
            WHERE p.posicao_id = %s 
              AND ((pt.clube_casa_id IN ({placeholders}) AND p.clube_id = pt.clube_visitante_id)
                   OR (pt.clube_visitante_id IN ({placeholders}) AND p.clube_id = pt.clube_casa_id))
              AND p.rodada_id <= %s AND p.entrou_em_campo = TRUE
            GROUP BY p.clube_id
        '''
        
        params = [posicao_id] + adversario_ids + adversario_ids + [rodada_atual - 1]
        
        cursor.execute(query, params)
        results = cursor.fetchall()
        
        print(f"\nQuery returned {len(results)} rows.")
        if len(results) > 0:
            print("First row sample:")
            print(f"Clube ID: {results[0][0]}")
            print(f"Avg DS: {results[0][1]}")
            print(f"Avg DS Esq: {results[0][2]}")
            print(f"Avg DS Dir: {results[0][3]}")
            print(f"Avg FF: {results[0][4]}")
            print(f"Avg FF Esq: {results[0][5]}")
            print(f"Avg FF Dir: {results[0][6]}")
            
            if results[0][2] is not None or results[0][3] is not None:
                 print("\n✅ SUCCESS: Split stats are being calculated!")
            else:
                 print("\n⚠️ WARNING: Split stats are None (might be lack of data, but query ran)")
        else:
            print("\n⚠️ No data returned (might be expected if no matches/scouts yet)")

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        close_db_connection(conn)

if __name__ == "__main__":
    verify_sql_logic()
