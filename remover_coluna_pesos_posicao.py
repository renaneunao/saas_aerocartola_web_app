#!/usr/bin/env python3
"""
Script inteligente para remover a coluna pesos_posicao
Tenta diferentes métodos de conexão com o banco de dados
Data: 2025-11-06
"""

import sys
import os

def tentar_importar_database():
    """Tenta importar o módulo database.py"""
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from database import get_db_connection, close_db_connection
        return get_db_connection, close_db_connection
    except Exception as e:
        return None, None

def conectar_direto():
    """Tenta conectar diretamente usando psycopg2"""
    try:
        import psycopg2
        
        # Verificar variáveis de ambiente
        required_vars = ['POSTGRES_HOST', 'POSTGRES_USER', 'POSTGRES_PASSWORD', 'POSTGRES_DB']
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        
        if missing_vars:
            return None, f"Variáveis de ambiente faltando: {', '.join(missing_vars)}"
        
        conn = psycopg2.connect(
            host=os.getenv('POSTGRES_HOST'),
            port=int(os.getenv('POSTGRES_PORT', '5432')),
            user=os.getenv('POSTGRES_USER'),
            password=os.getenv('POSTGRES_PASSWORD'),
            database=os.getenv('POSTGRES_DB')
        )
        return conn, None
        
    except ImportError:
        return None, "Módulo psycopg2 não instalado"
    except Exception as e:
        return None, f"Erro ao conectar: {str(e)}"

def remover_coluna(conn):
    """Remove a coluna pesos_posicao"""
    cursor = conn.cursor()
    
    try:
        # Verificar se a coluna existe
        print("🔍 Verificando se a coluna existe...")
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'acw_weight_configurations' 
            AND column_name = 'pesos_posicao'
        """)
        
        coluna_existe = cursor.fetchone()
        
        if not coluna_existe:
            print("ℹ️  A coluna 'pesos_posicao' já foi removida anteriormente.")
            print()
            mostrar_colunas(cursor)
            return True
        
        print("✅ Coluna 'pesos_posicao' encontrada")
        print()
        
        # Mostrar estrutura antes
        print("📋 Estrutura ANTES da remoção:")
        mostrar_colunas(cursor)
        print()
        
        # Confirmar remoção
        print("⚠️  ATENÇÃO: Você está prestes a remover a coluna 'pesos_posicao'")
        print("   da tabela 'acw_weight_configurations'.")
        print()
        resposta = input("   Deseja continuar? (sim/não): ").strip().lower()
        
        if resposta not in ['sim', 's', 'yes', 'y']:
            print("❌ Operação cancelada pelo usuário")
            return False
        
        print()
        print("🗑️  Removendo coluna 'pesos_posicao'...")
        
        # Remover a coluna
        cursor.execute("""
            ALTER TABLE acw_weight_configurations 
            DROP COLUMN pesos_posicao
        """)
        
        conn.commit()
        print("✅ Coluna removida com sucesso!")
        print()
        
        # Mostrar estrutura depois
        print("📋 Estrutura DEPOIS da remoção:")
        mostrar_colunas(cursor)
        print()
        
        # Verificar integridade
        print("🔍 Verificando integridade da tabela...")
        cursor.execute("SELECT COUNT(*) FROM acw_weight_configurations")
        count = cursor.fetchone()[0]
        print(f"✅ Tabela OK - {count} registro(s) mantido(s)")
        
        return True
        
    except Exception as e:
        print(f"❌ ERRO: {str(e)}")
        conn.rollback()
        import traceback
        traceback.print_exc()
        return False

def mostrar_colunas(cursor):
    """Mostra as colunas da tabela"""
    cursor.execute("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns 
        WHERE table_name = 'acw_weight_configurations'
        ORDER BY ordinal_position
    """)
    
    colunas = cursor.fetchall()
    print("   " + "-" * 70)
    print(f"   {'Coluna':<30} {'Tipo':<25} {'Nulo?':<10}")
    print("   " + "-" * 70)
    for col in colunas:
        print(f"   {col[0]:<30} {col[1]:<25} {col[2]:<10}")
    print("   " + "-" * 70)
    print(f"   Total: {len(colunas)} colunas")

def main():
    print("=" * 80)
    print("🔧 SCRIPT DE REMOÇÃO DA COLUNA pesos_posicao")
    print("=" * 80)
    print()
    
    # Tentar método 1: Usar database.py
    print("📡 Tentando conectar ao banco de dados...")
    get_conn, close_conn = tentar_importar_database()
    
    conn = None
    metodo_usado = None
    
    if get_conn and close_conn:
        print("   Método: database.py")
        try:
            conn = get_conn()
            metodo_usado = "database"
        except Exception as e:
            print(f"   ❌ Falhou: {e}")
    
    # Tentar método 2: Conexão direta
    if not conn:
        print("   Método: conexão direta com psycopg2")
        conn, erro = conectar_direto()
        if conn:
            metodo_usado = "direto"
        else:
            print(f"   ❌ Falhou: {erro}")
    
    if not conn:
        print()
        print("=" * 80)
        print("❌ NÃO FOI POSSÍVEL CONECTAR AO BANCO DE DADOS")
        print("=" * 80)
        print()
        print("💡 Opções:")
        print()
        print("1. Execute dentro do container Docker:")
        print("   docker exec -it cartola-aero-web-app-container \\")
        print("     python3 remover_coluna_pesos_posicao.py")
        print()
        print("2. Configure as variáveis de ambiente e execute:")
        print("   export POSTGRES_HOST=...")
        print("   export POSTGRES_USER=...")
        print("   export POSTGRES_PASSWORD=...")
        print("   export POSTGRES_DB=...")
        print("   python3 remover_coluna_pesos_posicao.py")
        print()
        print("3. Execute o SQL manualmente:")
        print("   psql -h HOST -U USER -d DB -f migration_remover_pesos_posicao.sql")
        print()
        print("4. Consulte: INSTRUCOES_REMOCAO_COLUNA.md")
        print()
        return 1
    
    print(f"✅ Conectado ao banco com sucesso!")
    print()
    
    # Executar remoção
    sucesso = remover_coluna(conn)
    
    # Fechar conexão
    if metodo_usado == "database" and close_conn:
        close_conn(conn)
    elif metodo_usado == "direto":
        conn.close()
    
    print()
    if sucesso:
        print("=" * 80)
        print("🎉 REMOÇÃO CONCLUÍDA COM SUCESSO!")
        print("=" * 80)
        return 0
    else:
        print("=" * 80)
        print("❌ REMOÇÃO NÃO FOI CONCLUÍDA")
        print("=" * 80)
        return 1

if __name__ == "__main__":
    sys.exit(main())
