import os
import sys
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

from database import get_db_connection, close_db_connection

def verify_all_scouts_backend():
    conn = get_db_connection()
    if not conn:
        print("Failed to connect to database")
        return

    try:
        cursor = conn.cursor()
        
        # Get max rodada
        cursor.execute('SELECT MAX(rodada_atual) FROM acp_peso_jogo_perfis')
        rodada_result = cursor.fetchone()
        rodada_atual = rodada_result[0] if rodada_result and rodada_result[0] else 1
        print(f"Rodada atual: {rodada_atual}")
        
        # Get some adversaries
        cursor.execute("SELECT id FROM acf_clubes LIMIT 5")
        adversario_ids = [row[0] for row in cursor.fetchall()]
        
        if not adversario_ids:
            print("No clubs found.")
            return
            
        placeholders = ','.join(['%s'] * len(adversario_ids))
        posicao_id = 5 # Atacante (Non-lateral)
        
        print(f"\nTesting for Posicao ID: {posicao_id} (Atacante)")
        
        query = f'''
            SELECT p.clube_id, 
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
            GROUP BY p.clube_id
        '''
        
        params = [posicao_id] + adversario_ids + adversario_ids + [rodada_atual - 1]
        
        cursor.execute(query, params)
        results = cursor.fetchall()
        
        print(f"Query returned {len(results)} rows.")
        if len(results) > 0:
            print("First row sample:")
            row = results[0]
            print(f"Clube ID: {row[0]}")
            print(f"Avg DS: {row[1]}")
            print(f"Avg FF: {row[2]}")
            print(f"Avg FS: {row[3]}")
            print(f"Avg FD: {row[4]}")
            print(f"Avg G:  {row[5]}")
            print(f"Avg A:  {row[6]}")
            
            # Check if we have data (some might be None/0, but checking structure)
            if len(row) >= 7:
                 print("\n✅ SUCCESS: All 6 scout types are being returned!")
            else:
                 print("\n❌ ERROR: Missing columns in result.")
        else:
            print("\n⚠️ No data returned.")

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        close_db_connection(conn)

if __name__ == "__main__":
    verify_all_scouts_backend()
