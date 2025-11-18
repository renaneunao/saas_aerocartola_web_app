"""
Script completo para configurar o sistema de planos
Verifica banco, cria estruturas necessárias e aplica planos
"""
import os
from dotenv import load_dotenv

# Carregar .env
load_dotenv()

from database import get_db_connection, close_db_connection
from models.plans import add_plano_column_to_users, create_plan_history_table, set_user_plan, get_user_plan

def verificar_e_configurar():
    """Verifica e configura tudo"""
    print("=" * 70)
    print("CONFIGURACAO DO SISTEMA DE PLANOS")
    print("=" * 70)
    print()
    
    # 1. Verificar conexão
    print("1. Verificando conexão com banco...")
    conn = get_db_connection()
    if not conn:
        print("[ERRO] Erro ao conectar ao banco!")
        return False
        print("[OK] Conectado!")
    print()
    
    # 2. Verificar estrutura da tabela acw_users
    print("2. Verificando estrutura da tabela acw_users...")
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = 'acw_users'
            ORDER BY ordinal_position
        """)
        colunas = cursor.fetchall()
        print(f"   Colunas encontradas: {len(colunas)}")
        for col in colunas:
            print(f"   - {col[0]}: {col[1]} (nullable: {col[2]}, default: {col[3]})")
        
        # Verificar se coluna plano existe
        tem_plano = any(col[0] == 'plano' for col in colunas)
        if tem_plano:
            print("   [OK] Coluna 'plano' ja existe")
        else:
            print("   [AVISO] Coluna 'plano' nao existe - sera criada")
    except Exception as e:
        print(f"   ❌ Erro: {e}")
    finally:
        close_db_connection(conn)
    print()
    
    # 3. Adicionar coluna plano
    print("3. Configurando coluna 'plano'...")
    if add_plano_column_to_users():
        print("   [OK] Coluna 'plano' configurada!")
    else:
        print("   [AVISO] Aviso ao configurar coluna")
    print()
    
    # 4. Criar tabela de histórico
    print("4. Criando tabela de histórico...")
    if create_plan_history_table():
        print("   [OK] Tabela de historico criada!")
    else:
        print("   [AVISO] Aviso ao criar tabela de historico")
    print()
    
    # 5. Buscar usuários e aplicar planos
    print("5. Aplicando planos aos usuários...")
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id, username, is_admin FROM acw_users WHERE is_active = TRUE")
            usuarios = cursor.fetchall()
            
            print(f"   Usuários encontrados: {len(usuarios)}")
            for user_id, username, is_admin in usuarios:
                plano_atual = get_user_plan(user_id)
                
                if is_admin and plano_atual == 'free':
                    print(f"   [USER] {username} (Admin) -> Aplicando 'pro'")
                    set_user_plan(user_id, 'pro', motivo='Setup inicial - Admin')
                else:
                    print(f"   [USER] {username} -> Plano atual: {plano_atual}")
        except Exception as e:
            print(f"   [ERRO] Erro: {e}")
        finally:
            close_db_connection(conn)
    print()
    
    print("=" * 70)
    print("[OK] CONFIGURACAO CONCLUIDA!")
    print("=" * 70)
    return True

if __name__ == "__main__":
    verificar_e_configurar()

