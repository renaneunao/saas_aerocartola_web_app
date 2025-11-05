#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para limpar rankings antigos e resolver problema de configuration_id
"""

import sys
import os

# Adicionar diretório ao path
sys.path.insert(0, os.path.dirname(__file__))

from database import get_db_connection, close_db_connection

def mostrar_estado_atual():
    """Mostra o estado atual antes de limpar"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    print("\n" + "="*80)
    print("  ESTADO ATUAL DO BANCO")
    print("="*80)
    
    # Configurações
    print("\n📋 CONFIGURAÇÕES (acw_weight_configurations):")
    cursor.execute("""
        SELECT id, user_id, team_id, perfil_peso_jogo, perfil_peso_sg, created_at
        FROM acw_weight_configurations
        ORDER BY id
    """)
    configs = cursor.fetchall()
    
    for cfg in configs:
        print(f"   Config ID {cfg[0]}: user_id={cfg[1]}, team_id={cfg[2]}, " +
              f"perfil_jogo={cfg[3]}, perfil_sg={cfg[4]}, criado={cfg[5]}")
    
    # Rankings por configuration_id
    print("\n📊 RANKINGS POR CONFIGURATION_ID:")
    cursor.execute("""
        SELECT configuration_id, COUNT(*) as total
        FROM acw_rankings_teams
        GROUP BY configuration_id
        ORDER BY configuration_id
    """)
    rankings_por_config = cursor.fetchall()
    
    for row in rankings_por_config:
        config_id, total = row
        print(f"   Configuration ID {config_id}: {total} rankings")
    
    # Rankings por time
    print("\n🏆 RANKINGS POR TIME:")
    cursor.execute("""
        SELECT r.team_id, t.team_name, r.configuration_id, COUNT(*) as total
        FROM acw_rankings_teams r
        LEFT JOIN acw_teams t ON r.team_id = t.id
        GROUP BY r.team_id, t.team_name, r.configuration_id
        ORDER BY r.team_id, r.configuration_id
    """)
    rankings_por_time = cursor.fetchall()
    
    for row in rankings_por_time:
        team_id, team_name, config_id, total = row
        print(f"   Time {team_id} ({team_name}): {total} rankings com config_id={config_id}")
    
    # Total de rankings
    cursor.execute("SELECT COUNT(*) FROM acw_rankings_teams")
    total_rankings = cursor.fetchone()[0]
    
    print(f"\n📈 TOTAL DE RANKINGS: {total_rankings}")
    
    cursor.close()
    close_db_connection(conn)

def limpar_rankings():
    """Limpa TODOS os rankings, mantendo configurações"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    print("\n" + "="*80)
    print("  LIMPANDO RANKINGS")
    print("="*80)
    
    # Contar quantos vão ser deletados
    cursor.execute("SELECT COUNT(*) FROM acw_rankings_teams")
    total_antes = cursor.fetchone()[0]
    
    print(f"\n⚠️  ATENÇÃO: Isso vai deletar {total_antes} rankings!")
    print("   As CONFIGURAÇÕES serão MANTIDAS")
    print("   Você precisará recalcular todos os módulos de todos os times")
    
    resposta = input("\n❓ Tem certeza que deseja continuar? (sim/não): ")
    
    if resposta.lower() != 'sim':
        print("\n❌ Operação cancelada!")
        cursor.close()
        close_db_connection(conn)
        return
    
    # Deletar todos os rankings
    print("\n🗑️  Deletando rankings...")
    cursor.execute("DELETE FROM acw_rankings_teams")
    conn.commit()
    
    # Verificar
    cursor.execute("SELECT COUNT(*) FROM acw_rankings_teams")
    total_depois = cursor.fetchone()[0]
    
    print(f"✅ Feito! Deletados: {total_antes} rankings")
    print(f"   Restantes: {total_depois} rankings")
    
    cursor.close()
    close_db_connection(conn)

def verificar_configuracoes():
    """Verifica se as configurações estão corretas"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    print("\n" + "="*80)
    print("  VERIFICAÇÃO DE CONFIGURAÇÕES")
    print("="*80)
    
    # Verificar times sem configuração
    cursor.execute("""
        SELECT t.id, t.team_name
        FROM acw_teams t
        LEFT JOIN acw_weight_configurations c ON t.user_id = c.user_id AND t.id = c.team_id
        WHERE c.id IS NULL
    """)
    times_sem_config = cursor.fetchall()
    
    if times_sem_config:
        print("\n⚠️  TIMES SEM CONFIGURAÇÃO:")
        for row in times_sem_config:
            print(f"   Time {row[0]}: {row[1]}")
        print("\n   → Estes times precisam escolher perfis na página inicial")
    else:
        print("\n✅ Todos os times têm configuração")
    
    # Verificar duplicatas
    cursor.execute("""
        SELECT user_id, team_id, COUNT(*) as total
        FROM acw_weight_configurations
        GROUP BY user_id, team_id
        HAVING COUNT(*) > 1
    """)
    duplicatas = cursor.fetchall()
    
    if duplicatas:
        print("\n⚠️  CONFIGURAÇÕES DUPLICADAS (NÃO DEVERIA ACONTECER):")
        for row in duplicatas:
            print(f"   user_id={row[0]}, team_id={row[1]}: {row[2]} configurações")
    else:
        print("✅ Sem duplicatas de configuração")
    
    cursor.close()
    close_db_connection(conn)

def menu():
    """Menu interativo"""
    while True:
        print("\n" + "="*80)
        print("  FERRAMENTA DE LIMPEZA DE RANKINGS")
        print("="*80)
        print("\n1. Mostrar estado atual")
        print("2. Verificar configurações")
        print("3. LIMPAR TODOS OS RANKINGS (irreversível!)")
        print("4. Sair")
        
        escolha = input("\nEscolha uma opção (1-4): ")
        
        if escolha == '1':
            mostrar_estado_atual()
        elif escolha == '2':
            verificar_configuracoes()
        elif escolha == '3':
            limpar_rankings()
        elif escolha == '4':
            print("\n👋 Até logo!")
            break
        else:
            print("\n❌ Opção inválida!")

if __name__ == '__main__':
    try:
        menu()
    except KeyboardInterrupt:
        print("\n\n⚠️  Operação interrompida pelo usuário")
    except Exception as e:
        print(f"\n❌ ERRO: {e}")
        import traceback
        traceback.print_exc()

