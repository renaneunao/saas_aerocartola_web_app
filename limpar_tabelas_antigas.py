"""
Script para remover tabelas antigas que já foram migradas
"""
import os
from dotenv import load_dotenv
load_dotenv()

from database import get_db_connection, close_db_connection

def limpar_tabelas_antigas():
    """Remove tabelas antigas que já foram migradas"""
    print("🧹 Limpando tabelas antigas...")
    
    conn = get_db_connection()
    if not conn:
        print("❌ Erro: Não foi possível conectar ao banco de dados")
        return False
    
    cursor = conn.cursor()
    
    # Tabelas antigas que já foram migradas para acw_*
    tabelas_para_remover = [
        'user_cartola_credentials',  # Migrado para acw_teams
        'user_rankings',              # Migrado para acw_rankings_teams
        'user_sessions',              # Não usamos mais (removido)
        'user_weight_configurations', # Migrado para acw_weight_configurations
        'user_escalacao_config',      # Migrado para acw_escalacao_config
        'users',                      # Migrado para acw_users
        'acw_cartola_credentials',    # Migrado para acw_teams
        'acw_rankings',               # Migrado para acw_rankings_teams
        'acw_sessions',               # Não usamos mais
        # Tabelas que parecem ser de outros containers ou antigas
        'configuracoes',
        'executions',
        'ranking_por_posicao',
        'updates_tracking',
    ]
    
    try:
        removidas = 0
        nao_encontradas = []
        
        for tabela in tabelas_para_remover:
            # Verificar se a tabela existe
            cursor.execute('''
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = %s
                )
            ''', (tabela,))
            
            if cursor.fetchone()[0]:
                try:
                    print(f"   Removendo {tabela}...")
                    cursor.execute(f'DROP TABLE IF EXISTS {tabela} CASCADE')
                    conn.commit()
                    removidas += 1
                    print(f"   ✅ {tabela} removida")
                except Exception as e:
                    print(f"   ⚠️  Erro ao remover {tabela}: {e}")
                    conn.rollback()
            else:
                nao_encontradas.append(tabela)
        
        print(f"\n✅ Total de tabelas removidas: {removidas}")
        if nao_encontradas:
            print(f"ℹ️  Tabelas não encontradas (já foram removidas ou não existiam): {len(nao_encontradas)}")
            for tabela in nao_encontradas:
                print(f"   - {tabela}")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro ao limpar tabelas: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        return False
    finally:
        close_db_connection(conn)

if __name__ == "__main__":
    import sys
    print("⚠️  ATENÇÃO: Este script irá remover tabelas antigas!")
    print("   Certifique-se de que os dados foram migrados corretamente.")
    resposta = input("   Deseja continuar? (sim/não): ")
    if resposta.lower() in ['sim', 's', 'yes', 'y']:
        limpar_tabelas_antigas()
        print("\n✅ Limpeza concluída! Execute verificar_tabelas.py para confirmar.")
    else:
        print("❌ Operação cancelada.")

