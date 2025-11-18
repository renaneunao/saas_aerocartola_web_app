"""
Modelo para gerenciamento de planos e permissões do sistema
Baseado na documentação oficial de planos e funcionalidades

Sistema simplificado: plano armazenado diretamente na tabela de usuários
Sem dependências do Stripe por enquanto
"""

import psycopg2
from typing import Optional, Dict, Any
from database import get_db_connection, close_db_connection

# JSON Oficial dos Planos (conforme documentação)
PLANS_CONFIG = {
    "free": {
        "name": "Free",
        "rankingCompleto": False,
        "pesosJogo": 2,
        "pesosSG": 2,
        "editarPesosModulos": False,
        "verEscalacaoIdealCompleta": False,
        "podeEscalar": False,
        "timesMaximos": 1,
        "estatisticasAvancadas": False,
        "fecharDefesa": False,
        "hackGoleiro": False,
        "multiEscalacao": False,
        "reordenarPrioridades": False,
        "nivelRisco": 1
    },
    "avancado": {
        "name": "Avançado",
        "rankingCompleto": True,
        "pesosJogo": 5,
        "pesosSG": 5,
        "editarPesosModulos": True,
        "verEscalacaoIdealCompleta": True,
        "podeEscalar": True,
        "timesMaximos": 2,
        "estatisticasAvancadas": True,
        "fecharDefesa": False,
        "hackGoleiro": False,
        "multiEscalacao": False,
        "reordenarPrioridades": False,
        "nivelRisco": 3
    },
    "pro": {
        "name": "Pro",
        "rankingCompleto": True,
        "pesosJogo": 15,
        "pesosSG": 10,
        "editarPesosModulos": True,
        "verEscalacaoIdealCompleta": True,
        "podeEscalar": True,
        "timesMaximos": "infinite",
        "estatisticasAvancadas": True,
        "fecharDefesa": True,
        "hackGoleiro": True,
        "multiEscalacao": True,
        "reordenarPrioridades": True,
        "nivelRisco": 10
    }
}

# Mapeamento de lookup_keys do Stripe para planos internos
STRIPE_PLAN_MAPPING = {
    'aero-cartola-avancado': 'avancado',
    'aero-cartola-pro': 'pro',
    # Mantendo compatibilidade com nomes antigos
    'aero-cartola-starter': 'avancado',  # Starter mapeia para Avançado
    'aero-cartola-pro-plus': 'pro',  # Pro+ mapeia para Pro
}


def add_plano_column_to_users():
    """
    Adiciona coluna 'plano' na tabela acw_users se não existir.
    Sistema simplificado: plano armazenado diretamente no usuário.
    """
    conn = get_db_connection()
    if not conn:
        return False
    
    cursor = conn.cursor()
    
    try:
        # Verificar se a coluna já existe
        cursor.execute('''
            SELECT EXISTS (
                SELECT FROM information_schema.columns 
                WHERE table_schema = 'public' 
                AND table_name = 'acw_users'
                AND column_name = 'plano'
            )
        ''')
        
        coluna_existe = cursor.fetchone()[0]
        
        if not coluna_existe:
            # Adicionar coluna plano
            cursor.execute('''
                ALTER TABLE acw_users 
                ADD COLUMN plano VARCHAR(50) NOT NULL DEFAULT 'free'
            ''')
            
            # Adicionar constraint para garantir valores válidos
            cursor.execute('''
                ALTER TABLE acw_users 
                ADD CONSTRAINT check_plano_valido 
                CHECK (plano IN ('free', 'avancado', 'pro'))
            ''')
            
            # Criar índice
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_plano ON acw_users(plano)')
            
            conn.commit()
            print("[OK] Coluna 'plano' adicionada a tabela acw_users!")
            return True
        else:
            print("[OK] Coluna 'plano' ja existe na tabela acw_users")
            return True
        
    except psycopg2.Error as e:
        print(f"[ERRO] Erro ao adicionar coluna plano: {e}")
        conn.rollback()
        return False
    finally:
        close_db_connection(conn)


def create_plan_history_table():
    """
    Cria tabela de histórico de planos (opcional, para auditoria)
    """
    conn = get_db_connection()
    if not conn:
        return False
    
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS acw_plan_history (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES acw_users(id) ON DELETE CASCADE,
                plano_anterior VARCHAR(50),
                plano_novo VARCHAR(50) NOT NULL,
                motivo VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_plan_history_user_id ON acw_plan_history(user_id)')
        
        conn.commit()
        print("[OK] Tabela acw_plan_history criada com sucesso!")
        return True
        
    except psycopg2.Error as e:
        print(f"[ERRO] Erro ao criar tabela de historico: {e}")
        conn.rollback()
        return False
    finally:
        close_db_connection(conn)


def get_user_plan(user_id: int) -> str:
    """
    Retorna o plano atual do usuário.
    Sistema simplificado: busca diretamente da tabela acw_users.
    Retorna 'free' como padrão se não encontrar.
    """
    conn = get_db_connection()
    if not conn:
        return 'free'
    
    cursor = conn.cursor()
    
    try:
        # Verificar se a coluna plano existe
        cursor.execute('''
            SELECT EXISTS (
                SELECT FROM information_schema.columns 
                WHERE table_schema = 'public' 
                AND table_name = 'acw_users'
                AND column_name = 'plano'
            )
        ''')
        
        coluna_existe = cursor.fetchone()[0]
        
        if not coluna_existe:
            # Se a coluna não existe, retornar free e tentar criar
            print("[AVISO] Coluna 'plano' nao existe. Execute add_plano_column_to_users() primeiro.")
            return 'free'
        
        # Buscar plano do usuário
        cursor.execute('''
            SELECT plano FROM acw_users
            WHERE id = %s
        ''', (user_id,))
        
        result = cursor.fetchone()
        if result and result[0]:
            plano = result[0]
            # Validar se o plano é válido
            if plano in PLANS_CONFIG:
                return plano
            else:
                print(f"[AVISO] Plano invalido '{plano}' para usuario {user_id}. Retornando 'free'.")
                return 'free'
        
        return 'free'
        
    except psycopg2.Error as e:
        print(f"Erro ao buscar plano do usuário: {e}")
        return 'free'
    finally:
        close_db_connection(conn)


def get_user_plan_config(user_id: int) -> Dict[str, Any]:
    """
    Retorna a configuração completa do plano do usuário.
    """
    plan_key = get_user_plan(user_id)
    return PLANS_CONFIG.get(plan_key, PLANS_CONFIG['free']).copy()


def set_user_plan(user_id: int, plano: str, motivo: str = None) -> bool:
    """
    Define o plano do usuário.
    Sistema simplificado: atualiza diretamente na tabela acw_users.
    plano: 'free', 'avancado', 'pro'
    """
    if plano not in PLANS_CONFIG:
        print(f"[ERRO] Plano invalido: {plano}")
        return False
    
    conn = get_db_connection()
    if not conn:
        return False
    
    cursor = conn.cursor()
    
    try:
        # Verificar se a coluna existe
        cursor.execute('''
            SELECT EXISTS (
                SELECT FROM information_schema.columns 
                WHERE table_schema = 'public' 
                AND table_name = 'acw_users'
                AND column_name = 'plano'
            )
        ''')
        
        coluna_existe = cursor.fetchone()[0]
        
        if not coluna_existe:
            print("❌ Coluna 'plano' não existe. Execute add_plano_column_to_users() primeiro.")
            return False
        
        # Buscar plano anterior
        plano_anterior = get_user_plan(user_id)
        
        # Se o plano não mudou, não fazer nada
        if plano_anterior == plano:
            return True
        
        # Atualizar plano do usuário
        cursor.execute('''
            UPDATE acw_users
            SET plano = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        ''', (plano, user_id))
        
        # Registrar no histórico (se a tabela existir)
        try:
            cursor.execute('''
                INSERT INTO acw_plan_history (user_id, plano_anterior, plano_novo, motivo)
                VALUES (%s, %s, %s, %s)
            ''', (user_id, plano_anterior, plano, motivo or 'Alteração manual'))
        except psycopg2.Error:
            # Tabela de histórico pode não existir, não é crítico
            pass
        
        conn.commit()
        print(f"[OK] Plano do usuario {user_id} alterado de '{plano_anterior}' para '{plano}'")
        return True
        
    except psycopg2.Error as e:
        print(f"[ERRO] Erro ao definir plano do usuario: {e}")
        conn.rollback()
        return False
    finally:
        close_db_connection(conn)




def check_permission(user_id: int, feature: str) -> bool:
    """
    Verifica se o usuário tem permissão para uma funcionalidade específica.
    
    Features disponíveis:
    - rankingCompleto
    - editarPesosModulos
    - verEscalacaoIdealCompleta
    - podeEscalar
    - estatisticasAvancadas
    - fecharDefesa
    - hackGoleiro
    - multiEscalacao
    """
    plan_config = get_user_plan_config(user_id)
    return plan_config.get(feature, False)


def get_max_perfis_jogo(user_id: int) -> int:
    """Retorna o número máximo de perfis de jogo permitidos"""
    plan_config = get_user_plan_config(user_id)
    return plan_config.get('pesosJogo', 2)


def get_max_perfis_sg(user_id: int) -> int:
    """Retorna o número máximo de perfis de SG permitidos"""
    plan_config = get_user_plan_config(user_id)
    return plan_config.get('pesosSG', 2)


def get_max_times(user_id: int) -> int:
    """Retorna o número máximo de times permitidos"""
    plan_config = get_user_plan_config(user_id)
    times_max = plan_config.get('timesMaximos', 1)
    if times_max == 'infinite':
        return 999999  # Praticamente infinito
    return int(times_max)


def get_nivel_risco(user_id: int) -> int:
    """Retorna o nível de risco permitido"""
    plan_config = get_user_plan_config(user_id)
    return plan_config.get('nivelRisco', 1)


if __name__ == "__main__":
    # Teste das funções
    print("🔧 Inicializando sistema de planos...")
    add_plano_column_to_users()
    create_plan_history_table()
    print("✅ Modelo de planos inicializado!")

