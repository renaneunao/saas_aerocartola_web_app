"""
Script de migração para converter de acw_cartola_credentials para acw_teams
e atualizar todas as referências de cartola_credentials_id para team_id
"""
import os
from dotenv import load_dotenv
load_dotenv()

from database import get_db_connection, close_db_connection

def migrate_to_teams():
    """Migra dados de acw_cartola_credentials para acw_teams e atualiza referências"""
    print("🔄 Iniciando migração para acw_teams...")
    
    conn = get_db_connection()
    if not conn:
        print("❌ Erro: Não foi possível conectar ao banco de dados")
        return False
    
    cursor = conn.cursor()
    
    try:
        # 1. Criar tabela acw_teams se não existir
        print("📋 Criando tabela acw_teams...")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS acw_teams (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                access_token TEXT NOT NULL,
                refresh_token TEXT NOT NULL,
                id_token TEXT,
                team_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES acw_users(id) ON DELETE CASCADE
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_teams_user_id ON acw_teams(user_id)')
        conn.commit()
        
        # 2. Migrar dados de acw_cartola_credentials para acw_teams
        print("📋 Migrando dados de acw_cartola_credentials para acw_teams...")
        cursor.execute('''
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'acw_cartola_credentials'
            )
        ''')
        if cursor.fetchone()[0]:
            cursor.execute('''
                INSERT INTO acw_teams (user_id, access_token, refresh_token, id_token, team_name, created_at, updated_at)
                SELECT user_id, access_token, refresh_token, id_token, team_name, created_at, updated_at
                FROM acw_cartola_credentials
                WHERE NOT EXISTS (
                    SELECT 1 FROM acw_teams WHERE acw_teams.user_id = acw_cartola_credentials.user_id
                )
            ''')
            conn.commit()
            print(f"   ✅ {cursor.rowcount} times migrados")
        
        # 3. Criar mapeamento de cartola_credentials_id -> team_id
        print("📋 Criando mapeamento de IDs...")
        cursor.execute('''
            SELECT c.id as old_id, t.id as new_id
            FROM acw_cartola_credentials c
            JOIN acw_teams t ON c.user_id = t.user_id AND c.access_token = t.access_token
        ''')
        id_mapping = {row[0]: row[1] for row in cursor.fetchall()}
        print(f"   ✅ {len(id_mapping)} mapeamentos criados")
        
        # 4. Atualizar acw_weight_configurations
        print("📋 Atualizando acw_weight_configurations...")
        cursor.execute('''
            SELECT EXISTS (
                SELECT FROM information_schema.columns 
                WHERE table_schema = 'public' 
                AND table_name = 'acw_weight_configurations'
                AND column_name = 'cartola_credentials_id'
            )
        ''')
        if cursor.fetchone()[0]:
            # Adicionar coluna team_id se não existir
            cursor.execute('''
                SELECT EXISTS (
                    SELECT FROM information_schema.columns 
                    WHERE table_schema = 'public' 
                    AND table_name = 'acw_weight_configurations'
                    AND column_name = 'team_id'
                )
            ''')
            if not cursor.fetchone()[0]:
                cursor.execute('ALTER TABLE acw_weight_configurations ADD COLUMN team_id INTEGER')
                cursor.execute('ALTER TABLE acw_weight_configurations ADD CONSTRAINT acw_weight_configurations_team_id_fkey FOREIGN KEY (team_id) REFERENCES acw_teams(id) ON DELETE CASCADE')
                
                # Migrar dados
                for old_id, new_id in id_mapping.items():
                    cursor.execute('''
                        UPDATE acw_weight_configurations
                        SET team_id = %s
                        WHERE cartola_credentials_id = %s
                    ''', (new_id, old_id))
                
                # Remover constraint antiga e coluna
                cursor.execute('ALTER TABLE acw_weight_configurations DROP CONSTRAINT IF EXISTS acw_weight_configurations_cartola_credentials_id_fkey')
                cursor.execute('ALTER TABLE acw_weight_configurations DROP COLUMN IF EXISTS cartola_credentials_id')
                cursor.execute('ALTER TABLE acw_weight_configurations DROP CONSTRAINT IF EXISTS acw_weight_configurations_user_id_cartola_credentials_id_key')
                cursor.execute('ALTER TABLE acw_weight_configurations ADD CONSTRAINT acw_weight_configurations_user_id_team_id_key UNIQUE(user_id, team_id)')
                conn.commit()
                print("   ✅ acw_weight_configurations atualizada")
        
        # 5. Atualizar acw_rankings para acw_rankings_teams
        print("📋 Atualizando rankings...")
        cursor.execute('''
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'acw_rankings'
            )
        ''')
        if cursor.fetchone()[0]:
            # Criar nova tabela se não existir
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS acw_rankings_teams (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    team_id INTEGER NOT NULL,
                    configuration_id INTEGER REFERENCES acw_weight_configurations(id),
                    posicao_id INTEGER NOT NULL,
                    rodada_atual INTEGER NOT NULL,
                    ranking_data JSONB NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES acw_users(id) ON DELETE CASCADE,
                    FOREIGN KEY (team_id) REFERENCES acw_teams(id) ON DELETE CASCADE
                )
            ''')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_rankings_teams_user_team ON acw_rankings_teams(user_id, team_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_rankings_teams_config ON acw_rankings_teams(team_id, configuration_id, posicao_id, rodada_atual)')
            
            # Migrar dados
            cursor.execute('''
                INSERT INTO acw_rankings_teams (user_id, team_id, configuration_id, posicao_id, rodada_atual, ranking_data, created_at)
                SELECT 
                    r.user_id,
                    t.id as team_id,
                    r.configuration_id,
                    r.posicao_id,
                    r.rodada_atual,
                    r.ranking_data,
                    r.created_at
                FROM acw_rankings r
                JOIN acw_cartola_credentials c ON r.cartola_credentials_id = c.id
                JOIN acw_teams t ON c.user_id = t.user_id AND c.access_token = t.access_token
                WHERE NOT EXISTS (
                    SELECT 1 FROM acw_rankings_teams rt 
                    WHERE rt.user_id = r.user_id 
                    AND rt.team_id = t.id 
                    AND rt.posicao_id = r.posicao_id 
                    AND rt.rodada_atual = r.rodada_atual
                )
            ''')
            conn.commit()
            print(f"   ✅ {cursor.rowcount} rankings migrados")
            
            # Remover tabela antiga (comentado por segurança - descomente depois de verificar)
            # cursor.execute('DROP TABLE IF EXISTS acw_rankings CASCADE')
            # conn.commit()
        
        # 6. Atualizar acw_escalacao_config
        print("📋 Atualizando acw_escalacao_config...")
        cursor.execute('''
            SELECT EXISTS (
                SELECT FROM information_schema.columns 
                WHERE table_schema = 'public' 
                AND table_name = 'acw_escalacao_config'
                AND column_name = 'cartola_credentials_id'
            )
        ''')
        if cursor.fetchone()[0]:
            cursor.execute('''
                SELECT EXISTS (
                    SELECT FROM information_schema.columns 
                    WHERE table_schema = 'public' 
                    AND table_name = 'acw_escalacao_config'
                    AND column_name = 'team_id'
                )
            ''')
            if not cursor.fetchone()[0]:
                cursor.execute('ALTER TABLE acw_escalacao_config ADD COLUMN team_id INTEGER')
                cursor.execute('ALTER TABLE acw_escalacao_config ADD CONSTRAINT acw_escalacao_config_team_id_fkey FOREIGN KEY (team_id) REFERENCES acw_teams(id) ON DELETE CASCADE')
                
                # Migrar dados
                for old_id, new_id in id_mapping.items():
                    cursor.execute('''
                        UPDATE acw_escalacao_config
                        SET team_id = %s
                        WHERE cartola_credentials_id = %s
                    ''', (new_id, old_id))
                
                cursor.execute('ALTER TABLE acw_escalacao_config DROP CONSTRAINT IF EXISTS acw_escalacao_config_cartola_credentials_id_fkey')
                cursor.execute('ALTER TABLE acw_escalacao_config DROP COLUMN IF EXISTS cartola_credentials_id')
                cursor.execute('ALTER TABLE acw_escalacao_config DROP CONSTRAINT IF EXISTS acw_escalacao_config_user_id_cartola_credentials_id_key')
                cursor.execute('ALTER TABLE acw_escalacao_config ADD CONSTRAINT acw_escalacao_config_user_id_team_id_key UNIQUE(user_id, team_id)')
                conn.commit()
                print("   ✅ acw_escalacao_config atualizada")
        
        # 7. Atualizar acw_posicao_weights
        print("📋 Atualizando acw_posicao_weights...")
        cursor.execute('''
            SELECT EXISTS (
                SELECT FROM information_schema.columns 
                WHERE table_schema = 'public' 
                AND table_name = 'acw_posicao_weights'
                AND column_name = 'cartola_credentials_id'
            )
        ''')
        if cursor.fetchone()[0]:
            cursor.execute('''
                SELECT EXISTS (
                    SELECT FROM information_schema.columns 
                    WHERE table_schema = 'public' 
                    AND table_name = 'acw_posicao_weights'
                    AND column_name = 'team_id'
                )
            ''')
            if not cursor.fetchone()[0]:
                cursor.execute('ALTER TABLE acw_posicao_weights ADD COLUMN team_id INTEGER')
                cursor.execute('ALTER TABLE acw_posicao_weights ADD CONSTRAINT acw_posicao_weights_team_id_fkey FOREIGN KEY (team_id) REFERENCES acw_teams(id) ON DELETE CASCADE')
                
                # Migrar dados
                for old_id, new_id in id_mapping.items():
                    cursor.execute('''
                        UPDATE acw_posicao_weights
                        SET team_id = %s
                        WHERE cartola_credentials_id = %s
                    ''', (new_id, old_id))
                
                cursor.execute('ALTER TABLE acw_posicao_weights DROP CONSTRAINT IF EXISTS acw_posicao_weights_cartola_credentials_id_fkey')
                cursor.execute('ALTER TABLE acw_posicao_weights DROP COLUMN IF EXISTS cartola_credentials_id')
                cursor.execute('ALTER TABLE acw_posicao_weights DROP CONSTRAINT IF EXISTS acw_posicao_weights_user_id_cartola_credentials_id_posicao_key')
                cursor.execute('ALTER TABLE acw_posicao_weights ADD CONSTRAINT acw_posicao_weights_user_id_team_id_posicao_key UNIQUE(user_id, team_id, posicao)')
                conn.commit()
                print("   ✅ acw_posicao_weights atualizada")
        
        print("✅ Migração concluída com sucesso!")
        return True
        
    except Exception as e:
        print(f"❌ Erro durante migração: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        return False
    finally:
        close_db_connection(conn)

if __name__ == "__main__":
    migrate_to_teams()

