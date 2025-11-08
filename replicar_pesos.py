#!/usr/bin/env python3
"""
Script para replicar pesos do time 'aero-rbsv' para todos os outros times do mesmo usuário.

Uso:
    python replicar_pesos.py

O script irá:
1. Buscar o time 'aero-rbsv' e identificar o usuário
2. Buscar todos os pesos por posição desse time
3. Buscar a configuração de peso de jogo e peso de saldo de gols
4. Replicar tudo para todos os outros times do mesmo usuário
"""

import os
from dotenv import load_dotenv

# Carregar variáveis de ambiente do .env
load_dotenv()

import psycopg2
import json
import sys
import argparse
from database import get_db_connection, close_db_connection

# Nome do time de origem (case-insensitive)
SOURCE_TEAM_NAME = 'Aero-RBSV'

def get_team_by_name(conn, team_name):
    """Busca um time pelo nome (case-insensitive)"""
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, user_id, team_name
        FROM acw_teams
        WHERE LOWER(team_name) = LOWER(%s)
    ''', (team_name,))
    row = cursor.fetchone()
    if not row:
        return None
    return {
        'id': row[0],
        'user_id': row[1],
        'team_name': row[2]
    }

def get_all_user_teams(conn, user_id, exclude_team_id=None):
    """Busca todos os times de um usuário, excluindo um time específico"""
    cursor = conn.cursor()
    if exclude_team_id:
        cursor.execute('''
            SELECT id, user_id, team_name
            FROM acw_teams
            WHERE user_id = %s AND id != %s
            ORDER BY created_at DESC
        ''', (user_id, exclude_team_id))
    else:
        cursor.execute('''
            SELECT id, user_id, team_name
            FROM acw_teams
            WHERE user_id = %s
            ORDER BY created_at DESC
        ''', (user_id,))
    rows = cursor.fetchall()
    return [
        {
            'id': row[0],
            'user_id': row[1],
            'team_name': row[2]
        }
        for row in rows
    ]

def get_position_weights(conn, user_id, team_id):
    """Busca todos os pesos por posição de um time"""
    cursor = conn.cursor()
    cursor.execute('''
        SELECT posicao, weights_json
        FROM acw_posicao_weights
        WHERE user_id = %s AND team_id = %s
    ''', (user_id, team_id))
    rows = cursor.fetchall()
    return {
        row[0]: row[1] if isinstance(row[1], dict) else json.loads(row[1]) if row[1] else {}
        for row in rows
    }

def get_weight_configuration(conn, user_id, team_id):
    """Busca a configuração de peso de jogo e peso de saldo de gols"""
    cursor = conn.cursor()
    cursor.execute('''
        SELECT name, perfil_peso_jogo, perfil_peso_sg, is_default
        FROM acw_weight_configurations
        WHERE user_id = %s AND team_id = %s
    ''', (user_id, team_id))
    row = cursor.fetchone()
    if not row:
        return None
    return {
        'name': row[0],
        'perfil_peso_jogo': row[1],
        'perfil_peso_sg': row[2],
        'is_default': row[3]
    }

def replicate_position_weights(conn, source_user_id, source_team_id, target_user_id, target_team_id, position_weights):
    """Replica os pesos por posição para outro time
    
    Usa UPSERT (INSERT ... ON CONFLICT UPDATE) para:
    - Criar novos registros se não existirem
    - Atualizar registros existentes se já existirem
    """
    cursor = conn.cursor()
    replicated_count = 0
    
    for posicao, weights_json in position_weights.items():
        # Garantir que weights_json seja um dict válido
        if isinstance(weights_json, str):
            try:
                weights_json = json.loads(weights_json)
            except json.JSONDecodeError:
                print(f"   [AVISO] Erro ao fazer parse do JSON para posicao {posicao}, pulando...")
                continue
        
        # Converter para JSON string para inserção no banco
        weights_json_str = json.dumps(weights_json) if isinstance(weights_json, dict) else str(weights_json)
        
        # Usar UPSERT (INSERT ... ON CONFLICT UPDATE)
        # A constraint UNIQUE é (user_id, team_id, posicao)
        cursor.execute('''
            INSERT INTO acw_posicao_weights (user_id, team_id, posicao, weights_json, updated_at)
            VALUES (%s, %s, %s, %s::jsonb, CURRENT_TIMESTAMP)
            ON CONFLICT (user_id, team_id, posicao)
            DO UPDATE SET
                weights_json = EXCLUDED.weights_json,
                updated_at = CURRENT_TIMESTAMP
        ''', (target_user_id, target_team_id, posicao, weights_json_str))
        replicated_count += 1
    
    return replicated_count

def replicate_weight_configuration(conn, source_user_id, source_team_id, target_user_id, target_team_id, config):
    """Replica a configuração de peso de jogo e peso de saldo de gols
    
    Usa UPSERT (INSERT ... ON CONFLICT UPDATE) para:
    - Criar nova configuração se não existir
    - Atualizar configuração existente se já existir
    A constraint UNIQUE é (user_id, team_id)
    """
    if not config:
        return False
    
    cursor = conn.cursor()
    # Usar UPSERT (INSERT ... ON CONFLICT UPDATE)
    # A constraint UNIQUE é (user_id, team_id)
    cursor.execute('''
        INSERT INTO acw_weight_configurations (user_id, team_id, name, perfil_peso_jogo, perfil_peso_sg, is_default, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
        ON CONFLICT (user_id, team_id)
        DO UPDATE SET
            name = EXCLUDED.name,
            perfil_peso_jogo = EXCLUDED.perfil_peso_jogo,
            perfil_peso_sg = EXCLUDED.perfil_peso_sg,
            is_default = EXCLUDED.is_default,
            updated_at = CURRENT_TIMESTAMP
    ''', (target_user_id, target_team_id, config['name'], config['perfil_peso_jogo'], config['perfil_peso_sg'], config['is_default']))
    
    return True

def main():
    """Função principal"""
    print(f"[*] Iniciando replicacao de pesos do time '{SOURCE_TEAM_NAME}'...")
    print()
    
    # Conectar ao banco
    conn = get_db_connection()
    if not conn:
        print("[ERRO] Erro ao conectar ao banco de dados")
        sys.exit(1)
    
    try:
        # 1. Buscar o time de origem
        print(f"[*] Buscando time '{SOURCE_TEAM_NAME}'...")
        source_team = get_team_by_name(conn, SOURCE_TEAM_NAME)
        if not source_team:
            print(f"[ERRO] Time '{SOURCE_TEAM_NAME}' nao encontrado!")
            sys.exit(1)
        
        print(f"[OK] Time encontrado: ID={source_team['id']}, User ID={source_team['user_id']}")
        print()
        
        # 2. Buscar todos os pesos por posição
        print("[*] Buscando pesos por posicao...")
        position_weights = get_position_weights(conn, source_team['user_id'], source_team['id'])
        print(f"[OK] Encontrados pesos para {len(position_weights)} posicoes: {', '.join(position_weights.keys())}")
        print()
        
        # 3. Buscar configuração de peso de jogo e peso de saldo de gols
        print("[*] Buscando configuracao de peso de jogo e peso de saldo de gols...")
        weight_config = get_weight_configuration(conn, source_team['user_id'], source_team['id'])
        if weight_config:
            print(f"[OK] Configuracao encontrada:")
            print(f"   - Nome: {weight_config['name']}")
            print(f"   - Perfil Peso de Jogo: {weight_config['perfil_peso_jogo']}")
            print(f"   - Perfil Peso de Saldo de Gols: {weight_config['perfil_peso_sg']}")
            print(f"   - Padrao: {weight_config['is_default']}")
        else:
            print("[AVISO] Nenhuma configuracao encontrada (sera ignorada)")
        print()
        
        # 4. Buscar todos os outros times do mesmo usuário
        print("[*] Buscando outros times do mesmo usuario...")
        target_teams = get_all_user_teams(conn, source_team['user_id'], exclude_team_id=source_team['id'])
        if not target_teams:
            print("[AVISO] Nenhum outro time encontrado para replicar")
            sys.exit(0)
        
        print(f"[OK] Encontrados {len(target_teams)} times para replicar:")
        for team in target_teams:
            print(f"   - {team['team_name']} (ID: {team['id']})")
        print()
        
        # 5. Confirmar antes de replicar
        print("[ATENCAO] Esta operacao ira SOBRESCREVER os pesos existentes nos times acima!")
        
        # Verificar se foi passado --yes como argumento
        auto_confirm = '--yes' in sys.argv or '-y' in sys.argv
        
        if not auto_confirm:
            try:
                resposta = input("Deseja continuar? (s/N): ").strip().lower()
                if resposta not in ['s', 'sim', 'y', 'yes']:
                    print("[CANCELADO] Operacao cancelada pelo usuario")
                    sys.exit(0)
            except EOFError:
                print("[ERRO] Nao foi possivel ler a entrada. Use --yes para executar automaticamente.")
                sys.exit(1)
        else:
            print("[*] Modo automatico ativado (--yes), continuando...")
        print()
        
        # 6. Replicar para cada time
        print("[*] Iniciando replicacao...")
        total_position_weights = 0
        total_configs = 0
        
        for target_team in target_teams:
            print(f"\n[*] Replicando para '{target_team['team_name']}' (ID: {target_team['id']})...")
            
            # Replicar pesos por posição
            if position_weights:
                count = replicate_position_weights(
                    conn, source_team['user_id'], source_team['id'],
                    target_team['user_id'], target_team['id'],
                    position_weights
                )
                total_position_weights += count
                print(f"   [OK] {count} posicoes replicadas")
            else:
                print("   [AVISO] Nenhum peso por posicao para replicar")
            
            # Replicar configuração de peso de jogo e peso de saldo de gols
            if weight_config:
                if replicate_weight_configuration(
                    conn, source_team['user_id'], source_team['id'],
                    target_team['user_id'], target_team['id'],
                    weight_config
                ):
                    total_configs += 1
                    print(f"   [OK] Configuracao de pesos replicada")
                else:
                    print(f"   [AVISO] Erro ao replicar configuracao")
            else:
                print("   [AVISO] Nenhuma configuracao para replicar")
        
        # Commit das alterações
        conn.commit()
        
        print()
        print("=" * 60)
        print("[OK] REPLICACAO CONCLUIDA COM SUCESSO!")
        print("=" * 60)
        print(f"[*] Resumo:")
        print(f"   - Times processados: {len(target_teams)}")
        print(f"   - Posicoes replicadas: {total_position_weights}")
        print(f"   - Configuracoes replicadas: {total_configs}")
        print()
        
    except Exception as e:
        conn.rollback()
        print(f"[ERRO] Erro durante a replicacao: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        close_db_connection(conn)

if __name__ == "__main__":
    main()

