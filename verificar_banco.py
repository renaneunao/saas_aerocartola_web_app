"""
Script para verificar completamente a estrutura do banco de dados
"""

from database import get_db_connection, close_db_connection

def verificar_banco_completo():
    """Verifica todas as tabelas e estruturas do banco"""
    conn = get_db_connection()
    if not conn:
        print("❌ Erro ao conectar ao banco de dados")
        return
    
    cursor = conn.cursor()
    
    try:
        print("=" * 70)
        print("🔍 VERIFICAÇÃO COMPLETA DO BANCO DE DADOS")
        print("=" * 70)
        print()
        
        # 1. Listar todas as tabelas
        print("📋 TABELAS EXISTENTES:")
        print("-" * 70)
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            ORDER BY table_name
        """)
        tabelas = cursor.fetchall()
        
        if not tabelas:
            print("   ⚠️  Nenhuma tabela encontrada")
        else:
            for (tabela,) in tabelas:
                print(f"   ✅ {tabela}")
        print()
        
        # 2. Verificar estrutura da tabela de usuários
        print("👤 ESTRUTURA DA TABELA acw_users:")
        print("-" * 70)
        cursor.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = 'acw_users'
            ORDER BY ordinal_position
        """)
        colunas = cursor.fetchall()
        
        if colunas:
            for coluna in colunas:
                nome, tipo, nullable, default = coluna
                null_str = "NULL" if nullable == "YES" else "NOT NULL"
                default_str = f" DEFAULT {default}" if default else ""
                print(f"   - {nome}: {tipo} {null_str}{default_str}")
        else:
            print("   ⚠️  Tabela acw_users não encontrada")
        print()
        
        # 3. Verificar se existe tabela de planos
        print("💳 VERIFICAÇÃO DE TABELAS DE PLANOS:")
        print("-" * 70)
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name IN ('acw_subscriptions', 'acw_plan_history', 'acw_user_plans')
        """)
        tabelas_planos = cursor.fetchall()
        
        if tabelas_planos:
            for (tabela,) in tabelas_planos:
                print(f"   ✅ {tabela} existe")
                # Mostrar estrutura
                cursor.execute(f"""
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns
                    WHERE table_name = '{tabela}'
                    ORDER BY ordinal_position
                """)
                cols = cursor.fetchall()
                for col in cols:
                    print(f"      - {col[0]}: {col[1]}")
        else:
            print("   ⚠️  Nenhuma tabela de planos encontrada")
        print()
        
        # 4. Verificar se existe coluna de plano na tabela de usuários
        print("🔍 VERIFICAÇÃO DE CAMPO DE PLANO EM acw_users:")
        print("-" * 70)
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns
            WHERE table_name = 'acw_users' 
            AND column_name IN ('plano', 'plan', 'subscription_plan')
        """)
        campo_plano = cursor.fetchone()
        
        if campo_plano:
            print(f"   ✅ Campo '{campo_plano[0]}' encontrado em acw_users")
        else:
            print("   ⚠️  Nenhum campo de plano encontrado em acw_users")
        print()
        
        # 5. Contar usuários
        print("📊 ESTATÍSTICAS:")
        print("-" * 70)
        try:
            cursor.execute("SELECT COUNT(*) FROM acw_users")
            total_usuarios = cursor.fetchone()[0]
            print(f"   Total de usuários: {total_usuarios}")
            
            cursor.execute("SELECT COUNT(*) FROM acw_teams")
            total_times = cursor.fetchone()[0]
            print(f"   Total de times: {total_times}")
        except Exception as e:
            print(f"   ⚠️  Erro ao contar: {e}")
        print()
        
        # 6. Verificar outras tabelas importantes
        print("📦 OUTRAS TABELAS IMPORTANTES:")
        print("-" * 70)
        tabelas_importantes = [
            'acw_teams',
            'acw_weight_configurations',
            'acw_rankings_teams',
            'acw_escalacao_config',
            'acw_posicao_weights'
        ]
        
        for tabela in tabelas_importantes:
            cursor.execute(f"""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = '{tabela}'
                )
            """)
            existe = cursor.fetchone()[0]
            status = "✅" if existe else "❌"
            print(f"   {status} {tabela}")
        print()
        
        print("=" * 70)
        print("✅ Verificação concluída!")
        print("=" * 70)
        
    except Exception as e:
        print(f"❌ Erro durante verificação: {e}")
        import traceback
        traceback.print_exc()
    finally:
        close_db_connection(conn)

if __name__ == "__main__":
    verificar_banco_completo()

