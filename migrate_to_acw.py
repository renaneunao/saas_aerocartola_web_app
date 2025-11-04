"""
Script de migração para renomear tabelas para acw_* e adicionar cartola_credentials_id
"""
import os
from dotenv import load_dotenv
load_dotenv()

from database import get_db_connection, close_db_connection

def migrate_tables():
    """Migra todas as tabelas para acw_* e adiciona cartola_credentials_id onde necessário"""
    print("🔄 Iniciando migração de tabelas para acw_*...")
    
    conn = get_db_connection()
    if not conn:
        print("❌ Erro: Não foi possível conectar ao banco de dados")
        return False
    
    cursor = conn.cursor()
    
    try:
        # 1. Renomear users -> acw_users
        print("📋 Migrando users -> acw_users...")
        cursor.execute('''
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'users'
            )
        ''')
        if cursor.fetchone()[0]:
            cursor.execute('ALTER TABLE users RENAME TO acw_users')
            cursor.execute('ALTER TABLE user_sessions RENAME TO acw_sessions')
            cursor.execute('ALTER TABLE acw_sessions RENAME CONSTRAINT user_sessions_user_id_fkey TO acw_sessions_user_id_fkey')
            print("   ✅ users -> acw_users")
        
        # 2. Renomear user_cartola_credentials -> acw_cartola_credentials
        print("📋 Migrando user_cartola_credentials -> acw_cartola_credentials...")
        cursor.execute('''
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'user_cartola_credentials'
            )
        ''')
        if cursor.fetchone()[0]:
            cursor.execute('ALTER TABLE user_cartola_credentials RENAME TO acw_cartola_credentials')
            # Atualizar foreign keys
            cursor.execute('''
                ALTER TABLE acw_cartola_credentials 
                RENAME CONSTRAINT user_cartola_credentials_user_id_fkey 
                TO acw_cartola_credentials_user_id_fkey
            ''')
            print("   ✅ user_cartola_credentials -> acw_cartola_credentials")
        
        # 3. Renomear user_weight_configurations -> acw_weight_configurations e adicionar cartola_credentials_id
        print("📋 Migrando user_weight_configurations -> acw_weight_configurations...")
        cursor.execute('''
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'user_weight_configurations'
            )
        ''')
        if cursor.fetchone()[0]:
            cursor.execute('ALTER TABLE user_weight_configurations RENAME TO acw_weight_configurations')
            # Atualizar foreign key
            cursor.execute('''
                ALTER TABLE acw_weight_configurations 
                RENAME CONSTRAINT user_weight_configurations_user_id_fkey 
                TO acw_weight_configurations_user_id_fkey
            ''')
            
            # Adicionar cartola_credentials_id se não existir
            cursor.execute('''
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'acw_weight_configurations' 
                AND column_name = 'cartola_credentials_id'
            ''')
            if cursor.fetchone() is None:
                print("   Adicionando cartola_credentials_id...")
                cursor.execute('''
                    ALTER TABLE acw_weight_configurations 
                    ADD COLUMN cartola_credentials_id INTEGER
                ''')
                # Para cada registro, buscar o primeiro time do usuário
                cursor.execute('''
                    UPDATE acw_weight_configurations uwc
                    SET cartola_credentials_id = (
                        SELECT id FROM acw_cartola_credentials 
                        WHERE user_id = uwc.user_id 
                        LIMIT 1
                    )
                    WHERE cartola_credentials_id IS NULL
                ''')
                # Tornar NOT NULL após preencher
                cursor.execute('''
                    ALTER TABLE acw_weight_configurations 
                    ALTER COLUMN cartola_credentials_id SET NOT NULL
                ''')
                cursor.execute('''
                    ALTER TABLE acw_weight_configurations 
                    ADD CONSTRAINT acw_weight_configurations_cartola_credentials_id_fkey 
                    FOREIGN KEY (cartola_credentials_id) 
                    REFERENCES acw_cartola_credentials(id) ON DELETE CASCADE
                ''')
                # Atualizar UNIQUE constraint
                cursor.execute('''
                    ALTER TABLE acw_weight_configurations 
                    DROP CONSTRAINT IF EXISTS user_weight_configurations_user_id_key
                ''')
                cursor.execute('''
                    ALTER TABLE acw_weight_configurations 
                    ADD CONSTRAINT acw_weight_configurations_user_credentials_key 
                    UNIQUE(user_id, cartola_credentials_id)
                ''')
            print("   ✅ user_weight_configurations -> acw_weight_configurations")
        
        # 4. Renomear user_rankings -> acw_rankings e adicionar cartola_credentials_id
        print("📋 Migrando user_rankings -> acw_rankings...")
        cursor.execute('''
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'user_rankings'
            )
        ''')
        if cursor.fetchone()[0]:
            cursor.execute('ALTER TABLE user_rankings RENAME TO acw_rankings')
            # Atualizar foreign keys
            cursor.execute('''
                ALTER TABLE acw_rankings 
                RENAME CONSTRAINT user_rankings_user_id_fkey 
                TO acw_rankings_user_id_fkey
            ''')
            
            # Adicionar cartola_credentials_id se não existir
            cursor.execute('''
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'acw_rankings' 
                AND column_name = 'cartola_credentials_id'
            ''')
            if cursor.fetchone() is None:
                print("   Adicionando cartola_credentials_id...")
                cursor.execute('''
                    ALTER TABLE acw_rankings 
                    ADD COLUMN cartola_credentials_id INTEGER
                ''')
                # Para cada registro, buscar o primeiro time do usuário
                cursor.execute('''
                    UPDATE acw_rankings ur
                    SET cartola_credentials_id = (
                        SELECT id FROM acw_cartola_credentials 
                        WHERE user_id = ur.user_id 
                        LIMIT 1
                    )
                    WHERE cartola_credentials_id IS NULL
                ''')
                # Tornar NOT NULL após preencher
                cursor.execute('''
                    ALTER TABLE acw_rankings 
                    ALTER COLUMN cartola_credentials_id SET NOT NULL
                ''')
                cursor.execute('''
                    ALTER TABLE acw_rankings 
                    ADD CONSTRAINT acw_rankings_cartola_credentials_id_fkey 
                    FOREIGN KEY (cartola_credentials_id) 
                    REFERENCES acw_cartola_credentials(id) ON DELETE CASCADE
                ''')
            print("   ✅ user_rankings -> acw_rankings")
        
        # 5. Renomear user_escalacao_config -> acw_escalacao_config
        print("📋 Migrando user_escalacao_config -> acw_escalacao_config...")
        cursor.execute('''
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'user_escalacao_config'
            )
        ''')
        if cursor.fetchone()[0]:
            cursor.execute('ALTER TABLE user_escalacao_config RENAME TO acw_escalacao_config')
            # Atualizar foreign keys
            cursor.execute('''
                ALTER TABLE acw_escalacao_config 
                RENAME CONSTRAINT user_escalacao_config_user_id_fkey 
                TO acw_escalacao_config_user_id_fkey
            ''')
            cursor.execute('''
                ALTER TABLE acw_escalacao_config 
                RENAME CONSTRAINT user_escalacao_config_cartola_credentials_id_fkey 
                TO acw_escalacao_config_cartola_credentials_id_fkey
            ''')
            print("   ✅ user_escalacao_config -> acw_escalacao_config")
        
        # 6. Renomear posicao_weights -> acw_posicao_weights
        print("📋 Migrando posicao_weights -> acw_posicao_weights...")
        cursor.execute('''
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'posicao_weights'
            )
        ''')
        if cursor.fetchone()[0]:
            cursor.execute('ALTER TABLE posicao_weights RENAME TO acw_posicao_weights')
            # Atualizar foreign keys
            cursor.execute('''
                ALTER TABLE acw_posicao_weights 
                RENAME CONSTRAINT posicao_weights_user_id_fkey 
                TO acw_posicao_weights_user_id_fkey
            ''')
            cursor.execute('''
                ALTER TABLE acw_posicao_weights 
                RENAME CONSTRAINT posicao_weights_cartola_credentials_id_fkey 
                TO acw_posicao_weights_cartola_credentials_id_fkey
            ''')
            # Atualizar referências em outras tabelas
            cursor.execute('''
                ALTER TABLE acw_posicao_weights 
                DROP CONSTRAINT IF EXISTS posicao_weights_user_id_cartola_credentials_id_posicao_key
            ''')
            cursor.execute('''
                ALTER TABLE acw_posicao_weights 
                ADD CONSTRAINT acw_posicao_weights_user_credentials_posicao_key 
                UNIQUE(user_id, cartola_credentials_id, posicao)
            ''')
            print("   ✅ posicao_weights -> acw_posicao_weights")
        
        # Atualizar referências de foreign keys em outras tabelas
        print("📋 Atualizando referências de foreign keys...")
        
        # Atualizar acw_sessions
        try:
            cursor.execute('''
                ALTER TABLE acw_sessions 
                DROP CONSTRAINT IF EXISTS user_sessions_user_id_fkey,
                ADD CONSTRAINT acw_sessions_user_id_fkey 
                FOREIGN KEY (user_id) REFERENCES acw_users(id) ON DELETE CASCADE
            ''')
        except Exception as e:
            print(f"   ⚠️ Aviso ao atualizar acw_sessions: {e}")
        
        # Atualizar acw_cartola_credentials
        try:
            cursor.execute('''
                ALTER TABLE acw_cartola_credentials 
                DROP CONSTRAINT IF EXISTS user_cartola_credentials_user_id_fkey,
                ADD CONSTRAINT acw_cartola_credentials_user_id_fkey 
                FOREIGN KEY (user_id) REFERENCES acw_users(id) ON DELETE CASCADE
            ''')
        except Exception as e:
            print(f"   ⚠️ Aviso ao atualizar acw_cartola_credentials: {e}")
        
        # Atualizar acw_weight_configurations
        try:
            cursor.execute('''
                ALTER TABLE acw_weight_configurations 
                DROP CONSTRAINT IF EXISTS user_weight_configurations_user_id_fkey,
                ADD CONSTRAINT acw_weight_configurations_user_id_fkey 
                FOREIGN KEY (user_id) REFERENCES acw_users(id) ON DELETE CASCADE
            ''')
        except Exception as e:
            print(f"   ⚠️ Aviso ao atualizar acw_weight_configurations: {e}")
        
        # Atualizar acw_rankings
        try:
            cursor.execute('''
                ALTER TABLE acw_rankings 
                DROP CONSTRAINT IF EXISTS user_rankings_user_id_fkey,
                ADD CONSTRAINT acw_rankings_user_id_fkey 
                FOREIGN KEY (user_id) REFERENCES acw_users(id) ON DELETE CASCADE
            ''')
        except Exception as e:
            print(f"   ⚠️ Aviso ao atualizar acw_rankings: {e}")
        
        # Atualizar acw_escalacao_config
        try:
            cursor.execute('''
                ALTER TABLE acw_escalacao_config 
                DROP CONSTRAINT IF EXISTS user_escalacao_config_user_id_fkey,
                ADD CONSTRAINT acw_escalacao_config_user_id_fkey 
                FOREIGN KEY (user_id) REFERENCES acw_users(id) ON DELETE CASCADE
            ''')
            cursor.execute('''
                ALTER TABLE acw_escalacao_config 
                DROP CONSTRAINT IF EXISTS user_escalacao_config_cartola_credentials_id_fkey,
                ADD CONSTRAINT acw_escalacao_config_cartola_credentials_id_fkey 
                FOREIGN KEY (cartola_credentials_id) REFERENCES acw_cartola_credentials(id) ON DELETE CASCADE
            ''')
        except Exception as e:
            print(f"   ⚠️ Aviso ao atualizar acw_escalacao_config: {e}")
        
        # Atualizar acw_posicao_weights
        try:
            cursor.execute('''
                ALTER TABLE acw_posicao_weights 
                DROP CONSTRAINT IF EXISTS posicao_weights_user_id_fkey,
                ADD CONSTRAINT acw_posicao_weights_user_id_fkey 
                FOREIGN KEY (user_id) REFERENCES acw_users(id) ON DELETE CASCADE
            ''')
            cursor.execute('''
                ALTER TABLE acw_posicao_weights 
                DROP CONSTRAINT IF EXISTS posicao_weights_cartola_credentials_id_fkey,
                ADD CONSTRAINT acw_posicao_weights_cartola_credentials_id_fkey 
                FOREIGN KEY (cartola_credentials_id) REFERENCES acw_cartola_credentials(id) ON DELETE CASCADE
            ''')
        except Exception as e:
            print(f"   ⚠️ Aviso ao atualizar acw_posicao_weights: {e}")
        
        conn.commit()
        print("\n✅ Migração concluída com sucesso!")
        print("\n📋 Tabelas migradas:")
        print("   - users -> acw_users")
        print("   - user_sessions -> acw_sessions")
        print("   - user_cartola_credentials -> acw_cartola_credentials")
        print("   - user_weight_configurations -> acw_weight_configurations")
        print("   - user_rankings -> acw_rankings")
        print("   - user_escalacao_config -> acw_escalacao_config")
        print("   - posicao_weights -> acw_posicao_weights")
        return True
        
    except Exception as e:
        print(f"❌ Erro durante migração: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        return False
    finally:
        cursor.close()
        close_db_connection(conn)

if __name__ == "__main__":
    print("⚠️  ATENÇÃO: Esta migração irá renomear todas as tabelas para acw_*")
    print("⚠️  Certifique-se de ter um backup do banco de dados antes de continuar!")
    response = input("Deseja continuar? (sim/não): ")
    if response.lower() in ['sim', 's', 'yes', 'y']:
        migrate_tables()
    else:
        print("Migração cancelada.")

