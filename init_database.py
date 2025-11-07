"""
Script de inicialização do banco de dados
Cria todas as tabelas necessárias para a aplicação web
"""
import os
from dotenv import load_dotenv

# Carregar variáveis de ambiente do .env
load_dotenv()

from database import get_db_connection, close_db_connection
from models.users import create_users_table, create_user, get_all_users

def init_all_tables():
    """Inicializa todas as tabelas necessárias"""
    print("🔄 Iniciando criação de tabelas...")
    
    conn = get_db_connection()
    if not conn:
        print("❌ Erro: Não foi possível conectar ao banco de dados")
        print("   Verifique as variáveis de ambiente no arquivo .env")
        return False
    
    try:
        # Criar tabela de usuários
        print("📋 Criando tabela users...")
        create_users_table()
        
        # Criar usuário admin padrão
        print("👤 Verificando usuário admin...")
        users = get_all_users()
        admin_exists = any(user.get('username') == 'renaneunao' for user in users)
        
        if not admin_exists:
            print("   Criando usuário admin (renaneunao)...")
            result = create_user(
                username='renaneunao',
                email='renan@cartolamanager.com',
                password='!Senhas123',
                full_name='Renan',
                is_admin=True
            )
            if result['success']:
                print(f"   ✅ Usuário admin criado com sucesso!")
            else:
                print(f"   ⚠️ Erro ao criar usuário admin: {result.get('error', 'Erro desconhecido')}")
        else:
            print("   ✅ Usuário admin já existe")
        
        # Criar tabela de times do Cartola por usuário
        from models.teams import create_teams_table
        print("📋 Criando tabela acw_teams...")
        create_teams_table(conn)
        
        # Remover coluna team_shield_url se existir (não deve ser salva, é buscada dinamicamente)
        cursor = conn.cursor()
        try:
            cursor.execute('''
                SELECT EXISTS (
                    SELECT FROM information_schema.columns 
                    WHERE table_schema = 'public' 
                    AND table_name = 'acw_teams'
                    AND column_name = 'team_shield_url'
                )
            ''')
            if cursor.fetchone()[0]:
                print("   Removendo coluna team_shield_url (obsoleta)...")
                cursor.execute('ALTER TABLE acw_teams DROP COLUMN IF EXISTS team_shield_url')
                conn.commit()
                print("   ✅ Coluna team_shield_url removida")
        except Exception as e:
            print(f"   ⚠️ Erro ao verificar/remover coluna team_shield_url: {e}")
        
        # Criar tabela de configurações de pesos por usuário
        from models.user_configurations import create_user_configurations_table
        print("📋 Criando tabela acw_weight_configurations...")
        cursor = conn.cursor()
        
        # Verificar se a tabela existe com estrutura antiga
        cursor.execute('''
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'acw_weight_configurations'
            )
        ''')
        table_exists = cursor.fetchone()[0]
        
        if table_exists:
            # Verificar se tem coluna antiga
            cursor.execute('''
                SELECT EXISTS (
                    SELECT FROM information_schema.columns 
                    WHERE table_schema = 'public' 
                    AND table_name = 'acw_weight_configurations'
                    AND column_name = 'cartola_credentials_id'
                )
            ''')
            if cursor.fetchone()[0]:
                print("   Migrando acw_weight_configurations para nova estrutura...")
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
                    # Migrar dados se houver (assumindo que podemos mapear cartola_credentials_id para team_id)
                    # Por enquanto, deixar NULL e o usuário precisará recriar
                    cursor.execute('ALTER TABLE acw_weight_configurations DROP CONSTRAINT IF EXISTS acw_weight_configurations_cartola_credentials_id_fkey')
                    cursor.execute('ALTER TABLE acw_weight_configurations DROP COLUMN IF EXISTS cartola_credentials_id')
                    cursor.execute('ALTER TABLE acw_weight_configurations DROP CONSTRAINT IF EXISTS acw_weight_configurations_user_id_cartola_credentials_id_key')
                    cursor.execute('ALTER TABLE acw_weight_configurations ADD CONSTRAINT acw_weight_configurations_team_id_fkey FOREIGN KEY (team_id) REFERENCES acw_teams(id) ON DELETE CASCADE')
                    cursor.execute('ALTER TABLE acw_weight_configurations ADD CONSTRAINT acw_weight_configurations_user_id_team_id_key UNIQUE(user_id, team_id)')
                    conn.commit()
                    print("   ✅ Estrutura migrada")
        
        create_user_configurations_table(conn)
        
        # Remover coluna pesos_posicao se existir (migration)
        cursor.execute('''
            SELECT EXISTS (
                SELECT FROM information_schema.columns 
                WHERE table_schema = 'public' 
                AND table_name = 'acw_weight_configurations'
                AND column_name = 'pesos_posicao'
            )
        ''')
        if cursor.fetchone()[0]:
            print("   🗑️  Removendo coluna obsoleta pesos_posicao...")
            cursor.execute('ALTER TABLE acw_weight_configurations DROP COLUMN pesos_posicao')
            conn.commit()
            print("   ✅ Coluna pesos_posicao removida")
        
        # Criar tabela de rankings por time
        from models.user_rankings import create_rankings_teams_table
        print("📋 Criando tabela acw_rankings_teams...")
        create_rankings_teams_table(conn)
        
        # Criar tabela de configurações de escalação ideal por usuário
        from models.user_escalacao_config import create_user_escalacao_config_table
        print("📋 Criando tabela acw_escalacao_config...")
        cursor = conn.cursor()
        
        # Verificar se a tabela existe com estrutura antiga
        cursor.execute('''
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'acw_escalacao_config'
            )
        ''')
        table_exists = cursor.fetchone()[0]
        
        if table_exists:
            # Verificar se tem coluna antiga
            cursor.execute('''
                SELECT EXISTS (
                    SELECT FROM information_schema.columns 
                    WHERE table_schema = 'public' 
                    AND table_name = 'acw_escalacao_config'
                    AND column_name = 'cartola_credentials_id'
                )
            ''')
            if cursor.fetchone()[0]:
                print("   Migrando acw_escalacao_config para nova estrutura...")
                # Adicionar coluna team_id se não existir
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
                    cursor.execute('ALTER TABLE acw_escalacao_config DROP CONSTRAINT IF EXISTS acw_escalacao_config_cartola_credentials_id_fkey')
                    cursor.execute('ALTER TABLE acw_escalacao_config DROP COLUMN IF EXISTS cartola_credentials_id')
                    cursor.execute('ALTER TABLE acw_escalacao_config DROP CONSTRAINT IF EXISTS acw_escalacao_config_user_id_cartola_credentials_id_key')
                    cursor.execute('ALTER TABLE acw_escalacao_config ADD CONSTRAINT acw_escalacao_config_team_id_fkey FOREIGN KEY (team_id) REFERENCES acw_teams(id) ON DELETE CASCADE')
                    cursor.execute('ALTER TABLE acw_escalacao_config ADD CONSTRAINT acw_escalacao_config_user_id_team_id_key UNIQUE(user_id, team_id)')
                    conn.commit()
                    print("   ✅ Estrutura migrada")
        
        create_user_escalacao_config_table(conn)
        
        # Migração: Adicionar colunas novas se não existirem
        cursor = conn.cursor()
        try:
            # Verificar e adicionar posicao_reserva_luxo
            cursor.execute("""
                SELECT column_name FROM information_schema.columns 
                WHERE table_name='acw_escalacao_config' AND column_name='posicao_reserva_luxo'
            """)
            if not cursor.fetchone():
                print("   🔄 Adicionando coluna posicao_reserva_luxo...")
                cursor.execute("ALTER TABLE acw_escalacao_config ADD COLUMN posicao_reserva_luxo VARCHAR(50) DEFAULT 'atacantes'")
                conn.commit()
            
            # Verificar e adicionar prioridades
            cursor.execute("""
                SELECT column_name FROM information_schema.columns 
                WHERE table_name='acw_escalacao_config' AND column_name='prioridades'
            """)
            if not cursor.fetchone():
                print("   🔄 Adicionando coluna prioridades...")
                cursor.execute("ALTER TABLE acw_escalacao_config ADD COLUMN prioridades TEXT DEFAULT 'atacantes,laterais,meias,zagueiros,goleiros,treinadores'")
                conn.commit()
        except Exception as e:
            print(f"   ⚠️ Aviso ao migrar acw_escalacao_config: {e}")
            conn.rollback()
        
        # Criar tabela de pesos por posição por time
        print("📋 Criando tabela acw_posicao_weights...")
        cursor = conn.cursor()
        
        # Verificar se a tabela existe (pode ser posicao_weights antiga ou acw_posicao_weights com estrutura antiga)
        cursor.execute('''
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name IN ('posicao_weights', 'acw_posicao_weights')
            )
        ''')
        table_exists = cursor.fetchone()[0]
        
        if table_exists:
            # Verificar se é a tabela antiga (posicao_weights) sem prefixo
            cursor.execute('''
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'posicao_weights'
                )
            ''')
            if cursor.fetchone()[0]:
                print("   Migrando tabela posicao_weights -> acw_posicao_weights...")
                cursor.execute('DROP TABLE IF EXISTS posicao_weights CASCADE')
                conn.commit()
            
            # Verificar se acw_posicao_weights tem estrutura antiga (com cartola_credentials_id)
            cursor.execute('''
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'acw_posicao_weights'
                )
            ''')
            if cursor.fetchone()[0]:
                cursor.execute('''
                    SELECT EXISTS (
                        SELECT FROM information_schema.columns 
                        WHERE table_schema = 'public' 
                        AND table_name = 'acw_posicao_weights'
                        AND column_name = 'cartola_credentials_id'
                    )
                ''')
                if cursor.fetchone()[0]:
                    print("   Migrando acw_posicao_weights para nova estrutura...")
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
                        cursor.execute('ALTER TABLE acw_posicao_weights DROP CONSTRAINT IF EXISTS acw_posicao_weights_cartola_credentials_id_fkey')
                        cursor.execute('ALTER TABLE acw_posicao_weights DROP COLUMN IF EXISTS cartola_credentials_id')
                        cursor.execute('ALTER TABLE acw_posicao_weights DROP CONSTRAINT IF EXISTS acw_posicao_weights_user_id_cartola_credentials_id_posicao_key')
                        cursor.execute('ALTER TABLE acw_posicao_weights ADD CONSTRAINT acw_posicao_weights_team_id_fkey FOREIGN KEY (team_id) REFERENCES acw_teams(id) ON DELETE CASCADE')
                        cursor.execute('ALTER TABLE acw_posicao_weights ADD CONSTRAINT acw_posicao_weights_user_id_team_id_posicao_key UNIQUE(user_id, team_id, posicao)')
                        conn.commit()
                        print("   ✅ Estrutura migrada")
        
        # Criar tabela com nova estrutura
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS acw_posicao_weights (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                team_id INTEGER NOT NULL,
                posicao VARCHAR(50) NOT NULL,
                weights_json JSONB NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES acw_users(id) ON DELETE CASCADE,
                FOREIGN KEY (team_id) REFERENCES acw_teams(id) ON DELETE CASCADE,
                UNIQUE(user_id, team_id, posicao)
            )
        ''')
        # Criar índices apenas se as colunas existirem
        try:
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_posicao_weights_user_team ON acw_posicao_weights(user_id, team_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_posicao_weights_posicao ON acw_posicao_weights(posicao)')
        except Exception:
            pass  # Índices podem já existir
        conn.commit()
        
        print("✅ Todas as tabelas foram criadas com sucesso!")
        return True
        
    except Exception as e:
        print(f"❌ Erro ao criar tabelas: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        close_db_connection(conn)

if __name__ == "__main__":
    init_all_tables()

