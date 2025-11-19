"""
Script para verificar o session_state (sid) em todos os tokens de todos os times
"""
import os
import sys
import json
import base64
from datetime import datetime
from dotenv import load_dotenv

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
from models.teams import get_team

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

def verify_sid_in_tokens(team_id, team_name):
    """Verifica o SID em todos os tokens do time"""
    print(f"\n{'='*80}")
    print(f"VERIFICACAO SID: {team_name} (ID: {team_id})")
    print(f"{'='*80}\n")
    
    conn = get_db_connection()
    if not conn:
        print("[ERRO] Nao foi possivel conectar ao banco de dados")
        return None
    
    try:
        team = get_team(conn, team_id)
        if not team:
            print(f"[ERRO] Time nao encontrado")
            return None
        
        access_token = team.get('access_token')
        refresh_token = team.get('refresh_token')
        id_token = team.get('id_token')
        
        if not all([access_token, refresh_token, id_token]):
            print("[ERRO] Tokens incompletos")
            return None
        
        # Decodificar todos os tokens
        access_payload = decode_jwt_payload(access_token)
        refresh_payload = decode_jwt_payload(refresh_token)
        id_payload = decode_jwt_payload(id_token)
        
        print("[INFO] Campos nos tokens:")
        
        # Access Token
        print(f"\n   Access Token:")
        if access_payload:
            access_sid = access_payload.get('sid')
            access_session_state = access_payload.get('session_state')
            access_sub = access_payload.get('sub')
            access_exp = access_payload.get('exp')
            access_iat = access_payload.get('iat')
            
            print(f"      SID: {access_sid}")
            print(f"      session_state: {access_session_state}")
            print(f"      sub: {access_sub}")
            if access_exp:
                exp_dt = datetime.fromtimestamp(access_exp)
                print(f"      exp: {exp_dt}")
            if access_iat:
                iat_dt = datetime.fromtimestamp(access_iat)
                print(f"      iat: {iat_dt}")
            
            # Mostrar todos os campos para debug
            print(f"      Todos os campos: {list(access_payload.keys())}")
        else:
            print("      [ERRO] Nao foi possivel decodificar")
        
        # Refresh Token
        print(f"\n   Refresh Token:")
        if refresh_payload:
            refresh_sid = refresh_payload.get('sid')
            refresh_session_state = refresh_payload.get('session_state')
            refresh_sub = refresh_payload.get('sub')
            refresh_exp = refresh_payload.get('exp')
            refresh_iat = refresh_payload.get('iat')
            refresh_type = refresh_payload.get('typ')
            
            print(f"      SID: {refresh_sid}")
            print(f"      session_state: {refresh_session_state}")
            print(f"      sub: {refresh_sub}")
            print(f"      typ: {refresh_type}")
            if refresh_exp:
                exp_dt = datetime.fromtimestamp(refresh_exp)
                print(f"      exp: {exp_dt}")
            if refresh_iat:
                iat_dt = datetime.fromtimestamp(refresh_iat)
                print(f"      iat: {iat_dt}")
            
            # Mostrar todos os campos para debug
            print(f"      Todos os campos: {list(refresh_payload.keys())}")
        else:
            print("      [ERRO] Nao foi possivel decodificar")
        
        # ID Token
        print(f"\n   ID Token:")
        if id_payload:
            id_sid = id_payload.get('sid')
            id_session_state = id_payload.get('session_state')
            id_sub = id_payload.get('sub')
            id_exp = id_payload.get('exp')
            id_iat = id_payload.get('iat')
            
            print(f"      SID: {id_sid}")
            print(f"      session_state: {id_session_state}")
            print(f"      sub: {id_sub}")
            if id_exp:
                exp_dt = datetime.fromtimestamp(id_exp)
                print(f"      exp: {exp_dt}")
            if id_iat:
                iat_dt = datetime.fromtimestamp(id_iat)
                print(f"      iat: {iat_dt}")
            
            # Mostrar todos os campos para debug
            print(f"      Todos os campos: {list(id_payload.keys())}")
        else:
            print("      [ERRO] Nao foi possivel decodificar")
        
        # Comparação
        print(f"\n[COMPARACAO]")
        if access_payload and refresh_payload and id_payload:
            access_sid = access_payload.get('sid')
            refresh_sid = refresh_payload.get('sid')
            id_sid = id_payload.get('sid')
            
            access_session_state = access_payload.get('session_state')
            refresh_session_state = refresh_payload.get('session_state')
            id_session_state = id_payload.get('session_state')
            
            print(f"   Access Token SID: {access_sid}")
            print(f"   Refresh Token SID: {refresh_sid}")
            print(f"   ID Token SID: {id_sid}")
            
            print(f"\n   Access Token session_state: {access_session_state}")
            print(f"   Refresh Token session_state: {refresh_session_state}")
            print(f"   ID Token session_state: {id_session_state}")
            
            # Verificar se são iguais
            if access_sid and id_sid:
                if access_sid == id_sid:
                    print(f"\n   [OK] Access Token e ID Token tem o mesmo SID")
                else:
                    print(f"\n   [ATENCAO] Access Token e ID Token tem SIDs diferentes!")
            
            if refresh_sid:
                if access_sid and refresh_sid == access_sid:
                    print(f"   [OK] Refresh Token tem o mesmo SID que Access Token")
                elif id_sid and refresh_sid == id_sid:
                    print(f"   [OK] Refresh Token tem o mesmo SID que ID Token")
                else:
                    print(f"   [ATENCAO] Refresh Token tem SID diferente dos outros tokens")
            else:
                print(f"\n   [INFO] Refresh Token NAO tem campo SID (isso pode ser normal)")
                print(f"   O Refresh Token pode nao ter SID porque ele e usado apenas para refresh")
        
        return {
            'access_sid': access_payload.get('sid') if access_payload else None,
            'refresh_sid': refresh_payload.get('sid') if refresh_payload else None,
            'id_sid': id_payload.get('sid') if id_payload else None,
            'access_session_state': access_payload.get('session_state') if access_payload else None,
            'refresh_session_state': refresh_payload.get('session_state') if refresh_payload else None,
            'id_session_state': id_payload.get('session_state') if id_payload else None,
        }
        
    except Exception as e:
        print(f"[ERRO] Erro durante a verificacao: {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        close_db_connection(conn)

def main():
    """Função principal"""
    print("\n" + "="*80)
    print("VERIFICACAO: SESSION_STATE (SID) EM TODOS OS TIMES")
    print("Verificando se o Refresh Token tem SID em todos os times")
    print("="*80)
    
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
        
        print(f"\n[INFO] Total de times encontrados: {len(rows)}\n")
        
        results = []
        for row in rows:
            team_id = row[0]
            team_name = row[1]
            
            result = verify_sid_in_tokens(team_id, team_name)
            if result:
                results.append({
                    'team_id': team_id,
                    'team_name': team_name,
                    **result
                })
        
        # Resumo
        print("\n" + "="*80)
        print("RESUMO: SID NOS TOKENS")
        print("="*80)
        print(f"\n{'Time':<30} {'Access SID':<15} {'Refresh SID':<15} {'ID SID':<15}")
        print("-" * 80)
        for result in results:
            access_sid = "Sim" if result['access_sid'] else "Nao"
            refresh_sid = "Sim" if result['refresh_sid'] else "Nao"
            id_sid = "Sim" if result['id_sid'] else "Nao"
            print(f"{result['team_name']:<30} {access_sid:<15} {refresh_sid:<15} {id_sid:<15}")
        
        # Verificar se todos os refresh tokens não têm SID
        refresh_tokens_without_sid = [r for r in results if not r['refresh_sid']]
        refresh_tokens_with_sid = [r for r in results if r['refresh_sid']]
        
        print(f"\n[INFO] Refresh Tokens SEM SID: {len(refresh_tokens_without_sid)}/{len(results)}")
        print(f"[INFO] Refresh Tokens COM SID: {len(refresh_tokens_with_sid)}/{len(results)}")
        
        if len(refresh_tokens_without_sid) == len(results):
            print("\n[CONCLUSAO] Todos os Refresh Tokens NAO tem SID - isso e NORMAL!")
            print("O Refresh Token nao precisa ter SID porque ele e usado apenas para refresh.")
        elif len(refresh_tokens_with_sid) > 0:
            print("\n[ATENCAO] Alguns Refresh Tokens tem SID e outros nao.")
            print("Times com Refresh Token COM SID:")
            for r in refresh_tokens_with_sid:
                print(f"   - {r['team_name']} (ID: {r['team_id']})")
        
    except Exception as e:
        print(f"[ERRO] Erro: {e}")
        import traceback
        traceback.print_exc()
    finally:
        close_db_connection(conn)

if __name__ == "__main__":
    main()

