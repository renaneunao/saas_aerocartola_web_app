#!/usr/bin/env python3
"""
Script para remover a coluna pesos_posicao da tabela acw_weight_configurations
Esta coluna não é mais utilizada e está causando erros ao salvar pesos.
"""
import os
import sys
from database import get_db_connection, close_db_connection

def fix_pesos_posicao_column():
    """Remove a coluna pesos_posicao se existir"""
    print("\n🔧 CORRIGINDO ERRO: Removendo coluna obsoleta pesos_posicao")
    print("=" * 70)
    
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Verificar se a coluna existe
        print("\n1️⃣  Verificando se a coluna pesos_posicao existe...")
        cursor.execute('''
            SELECT EXISTS (
                SELECT FROM information_schema.columns 
                WHERE table_schema = 'public' 
                AND table_name = 'acw_weight_configurations'
                AND column_name = 'pesos_posicao'
            )
        ''')
        
        column_exists = cursor.fetchone()[0]
        
        if column_exists:
            print("   ✅ Coluna pesos_posicao encontrada")
            print("\n2️⃣  Removendo coluna pesos_posicao...")
            cursor.execute('ALTER TABLE acw_weight_configurations DROP COLUMN pesos_posicao')
            conn.commit()
            print("   ✅ Coluna removida com sucesso!")
        else:
            print("   ℹ️  Coluna pesos_posicao já foi removida anteriormente")
        
        # Verificar estrutura final
        print("\n3️⃣  Verificando estrutura final da tabela...")
        cursor.execute('''
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'acw_weight_configurations'
            ORDER BY ordinal_position
        ''')
        
        columns = cursor.fetchall()
        print("   Colunas atuais:")
        for col_name, col_type in columns:
            print(f"      - {col_name} ({col_type})")
        
        print("\n" + "=" * 70)
        print("✅ CORREÇÃO CONCLUÍDA COM SUCESSO!")
        print("Agora você pode salvar os pesos sem problemas.")
        print("=" * 70 + "\n")
        
        return True
        
    except Exception as e:
        print(f"\n❌ ERRO: {e}")
        import traceback
        traceback.print_exc()
        if conn:
            conn.rollback()
        return False
        
    finally:
        if conn:
            close_db_connection(conn)

if __name__ == '__main__':
    success = fix_pesos_posicao_column()
    sys.exit(0 if success else 1)
