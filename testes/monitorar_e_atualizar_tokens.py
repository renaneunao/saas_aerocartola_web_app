"""
Script para monitorar quando os id_tokens vão expirar e fazer refresh automático
"""
import os
import sys
import json
import base64
from datetime import datetime, timedelta
from dotenv import load_dotenv
import time

# Configurar encoding para Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Adicionar o diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Carregar variáveis de ambiente
load_dotenv()

from database import get_db_connection, close_db_connection
from models.teams import get_team, update_team_tokens
from api_cartola import refresh_access_token_by_team_id
import requests

def decode_jwt_payload(token):
    """Decodifica o payload de um JWT"""
    try:
        parts = token.split('.')
        if len(parts) != 3:
            return None
        payload = parts[1]
        padding = 4 - len(payload) % 4
        if padding != 4:
            payload += '=' * padding
        decoded = base64.urlsafe_b64decode(payload)
        return json.loads(decoded)
    except:
        return None

def check_token_expiration(token):
    """Verifica expiração do token"""
    if not token:
        return None, None
    payload = decode_jwt_payload(token)
    if not payload:
        return None, None
    exp = payload.get('exp')
    if not exp:
        return None, None
    exp_datetime = datetime.fromtimestamp(exp)
    is_expired = datetime.now() > exp_datetime
    return exp_datetime, is_expired

def monitor_and_refresh_teams():
    """Monitora e atualiza tokens dos times"""
    print("\n" + "="*80)
    print("MONITORAMENTO E ATUALIZACAO DE TOKENS")
    print("="*80 + "\n")
    
    conn = get_db_connection()
    if not conn:
        print("[ERRO] Nao foi possivel conectar ao banco de dados")
        return
    
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT t.id, t.team_name
            FROM acw_teams t
            JOIN acw_users u ON t.user_id = u.id
            WHERE u.username = 'renaneunao'
            ORDER BY t.id
        ''')
        rows = cursor.fetchall()
        
        if not rows:
            print("[ERRO] Nenhum time encontrado")
            return
        
        print(f"[INFO] Monitorando {len(rows)} times...\n")
        
        for row in rows:
            team_id = row[0]
            team_name = row[1]
            
            team = get_team(conn, team_id)
            if not team:
                continue
            
            access_token = team.get('access_token')
            refresh_token = team.get('refresh_token')
            id_token = team.get('id_token')
            
            if not all([access_token, refresh_token, id_token]):
                print(f"[ERRO] {team_name}: Tokens incompletos")
                continue
            
            # Verificar expiração
            access_exp, access_expired = check_token_expiration(access_token)
            refresh_exp, refresh_expired = check_token_expiration(refresh_token)
            id_exp, id_expired = check_token_expiration(id_token)
            
            print(f"[INFO] {team_name} (ID: {team_id}):")
            
            if refresh_expired:
                print(f"   [ERRO] Refresh Token EXPIRADO! Precisa de novo login.")
                print(f"   Refresh Token expirou em: {refresh_exp}")
                continue
            
            if id_expired:
                print(f"   [ATENCAO] ID Token EXPIRADO (expirou em: {id_exp})")
                print(f"   Tentando refresh mesmo assim...")
            else:
                time_until_id_expiry = id_exp - datetime.now()
                print(f"   ID Token expira em: {id_exp} (em {time_until_id_expiry})")
            
            # Tentar fazer refresh
            print(f"   Fazendo refresh...")
            new_access_token = refresh_access_token_by_team_id(conn, team_id)
            
            if new_access_token:
                # Verificar novos tokens
                team_updated = get_team(conn, team_id)
                if team_updated:
                    new_id_exp, new_id_expired = check_token_expiration(team_updated.get('id_token'))
                    if new_id_exp:
                        time_until_new_expiry = new_id_exp - datetime.now()
                        print(f"   [OK] Refresh realizado! Novo ID Token expira em: {new_id_exp} (em {time_until_new_expiry})")
                    else:
                        print(f"   [OK] Refresh realizado!")
            else:
                print(f"   [ERRO] Falha no refresh")
            
            print()
        
    except Exception as e:
        print(f"[ERRO] Erro: {e}")
        import traceback
        traceback.print_exc()
    finally:
        close_db_connection(conn)

if __name__ == "__main__":
    monitor_and_refresh_teams()

