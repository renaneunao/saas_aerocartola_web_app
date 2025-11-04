"""
Script para verificar tabelas antigas que não têm prefixo acw_, acp_ ou acf_
"""
import os
from dotenv import load_dotenv
load_dotenv()

from database import get_db_connection, close_db_connection

def verificar_tabelas():
    """Verifica tabelas antigas sem prefixo"""
    print("🔍 Verificando tabelas no banco de dados...")
    
    conn = get_db_connection()
    if not conn:
        print("❌ Erro: Não foi possível conectar ao banco de dados")
        return False
    
    cursor = conn.cursor()
    
    try:
        # Listar todas as tabelas
        cursor.execute('''
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_type = 'BASE TABLE'
            ORDER BY table_name
        ''')
        
        tabelas = [row[0] for row in cursor.fetchall()]
        
        print(f"\n📋 Total de tabelas encontradas: {len(tabelas)}\n")
        
        tabelas_antigas = []
        tabelas_web = []
        tabelas_profiles = []
        tabelas_api = []
        
        for tabela in tabelas:
            if tabela.startswith('acw_'):
                tabelas_web.append(tabela)
            elif tabela.startswith('acp_'):
                tabelas_profiles.append(tabela)
            elif tabela.startswith('acf_'):
                tabelas_api.append(tabela)
            else:
                tabelas_antigas.append(tabela)
        
        print("✅ Tabelas do Web App (acw_*):")
        for tabela in sorted(tabelas_web):
            print(f"   - {tabela}")
        
        print(f"\n✅ Tabelas de Profiles (acp_*):")
        for tabela in sorted(tabelas_profiles):
            print(f"   - {tabela}")
        
        print(f"\n✅ Tabelas da API (acf_*):")
        for tabela in sorted(tabelas_api):
            print(f"   - {tabela}")
        
        if tabelas_antigas:
            print(f"\n⚠️  Tabelas ANTIGAS (sem prefixo):")
            for tabela in sorted(tabelas_antigas):
                print(f"   - {tabela}")
            print(f"\n❌ Total de tabelas antigas: {len(tabelas_antigas)}")
            return False
        else:
            print(f"\n✅ Nenhuma tabela antiga encontrada! Todas as tabelas têm prefixo correto.")
            return True
        
    except Exception as e:
        print(f"❌ Erro ao verificar tabelas: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        close_db_connection(conn)

if __name__ == "__main__":
    verificar_tabelas()

