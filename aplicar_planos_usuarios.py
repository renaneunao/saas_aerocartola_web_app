"""
Script para aplicar planos aos usuários existentes
"""

from database import get_db_connection, close_db_connection
from models.plans import add_plano_column_to_users, set_user_plan, get_user_plan
from models.users import get_all_users

def aplicar_planos():
    """Aplica planos aos usuários existentes"""
    print("🚀 Aplicando planos aos usuários existentes...")
    print("-" * 70)
    
    # 1. Garantir que a coluna plano existe
    print("1. Verificando coluna 'plano' na tabela acw_users...")
    if not add_plano_column_to_users():
        print("❌ Erro ao adicionar coluna 'plano'")
        return False
    print()
    
    # 2. Buscar todos os usuários
    print("2. Buscando usuários existentes...")
    usuarios = get_all_users()
    
    if not usuarios:
        print("⚠️  Nenhum usuário encontrado")
        return False
    
    print(f"   ✅ {len(usuarios)} usuário(s) encontrado(s)")
    print()
    
    # 3. Aplicar planos
    print("3. Aplicando planos:")
    print("-" * 70)
    
    for usuario in usuarios:
        user_id = usuario['id']
        username = usuario['username']
        is_admin = usuario.get('is_admin', False)
        
        # Verificar plano atual
        plano_atual = get_user_plan(user_id)
        
        # Se for admin e não tiver plano definido, aplicar 'pro' para teste
        if is_admin and plano_atual == 'free':
            print(f"   👤 {username} (Admin) -> Aplicando plano 'pro' para testes")
            set_user_plan(user_id, 'pro', motivo='Aplicação inicial - Admin')
        elif plano_atual == 'free':
            # Usuários normais mantêm 'free'
            print(f"   👤 {username} -> Mantendo plano 'free' (padrão)")
        else:
            print(f"   👤 {username} -> Já possui plano '{plano_atual}'")
    
    print()
    print("=" * 70)
    print("✅ Planos aplicados com sucesso!")
    print("=" * 70)
    
    # 4. Mostrar resumo
    print()
    print("📊 RESUMO:")
    print("-" * 70)
    for usuario in usuarios:
        user_id = usuario['id']
        username = usuario['username']
        plano = get_user_plan(user_id)
        is_admin = " (Admin)" if usuario.get('is_admin', False) else ""
        print(f"   {username}{is_admin}: {plano}")
    
    return True

if __name__ == "__main__":
    aplicar_planos()

