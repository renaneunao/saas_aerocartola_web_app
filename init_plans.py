"""
Script de inicialização do sistema de planos
Executa a criação das colunas e tabelas necessárias
Sistema simplificado: plano armazenado diretamente na tabela de usuários
"""

from models.plans import add_plano_column_to_users, create_plan_history_table
from models.users import create_users_table
from database import test_connection

def main():
    print("🚀 Inicializando sistema de planos...")
    print("-" * 50)
    
    # Testar conexão
    print("1. Testando conexão com banco de dados...")
    if not test_connection():
        print("❌ Falha na conexão com o banco de dados!")
        return False
    print("✅ Conexão estabelecida!")
    print()
    
    # Verificar/criar tabela de usuários (se não existir)
    print("2. Verificando tabela de usuários...")
    try:
        from models.users import create_users_table
        create_users_table()
        print("✅ Tabela de usuários verificada!")
    except Exception as e:
        print(f"⚠️  Aviso ao verificar tabela de usuários: {e}")
    print()
    
    # Adicionar coluna plano na tabela de usuários
    print("3. Adicionando coluna 'plano' na tabela acw_users...")
    if add_plano_column_to_users():
        print("✅ Coluna 'plano' configurada com sucesso!")
    else:
        print("❌ Erro ao adicionar coluna 'plano'!")
        return False
    print()
    
    # Criar tabela de histórico (opcional)
    print("4. Criando tabela de histórico de planos...")
    if create_plan_history_table():
        print("✅ Tabela de histórico criada com sucesso!")
    else:
        print("⚠️  Aviso: Tabela de histórico não foi criada (não é crítico)")
    print()
    
    print("=" * 50)
    print("✅ Sistema de planos inicializado com sucesso!")
    print("=" * 50)
    print()
    print("📋 Planos disponíveis:")
    print("   - free: Plano gratuito (padrão)")
    print("   - avancado: Plano avançado")
    print("   - pro: Plano profissional")
    print()
    print("💡 Use set_user_plan(user_id, 'avancado') para alterar planos")
    return True

if __name__ == "__main__":
    main()

