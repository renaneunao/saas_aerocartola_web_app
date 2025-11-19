"""
Script para verificar se o time foi enviado com os tokens corretos
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
        return None, None, None
    payload = decode_jwt_payload(token)
    if not payload:
        return None, None, None
    exp = payload.get('exp')
    iat = payload.get('iat')
    if not exp:
        return None, None, None
    exp_datetime = datetime.fromtimestamp(exp)
    iat_datetime = datetime.fromtimestamp(iat) if iat else None
    is_expired = datetime.now() > exp_datetime
    return exp_datetime, is_expired, iat_datetime

def verify_team_tokens(team_id, team_name):
    """Verifica se os tokens do time estão corretos"""
    print(f"\n{'='*80}")
    print(f"VERIFICACAO: {team_name} (ID: {team_id})")
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
        
        print("[1] Verificando se os tokens existem:")
        print(f"   Access Token: {'[OK] Presente' if access_token else '[ERRO] Ausente'}")
        print(f"   Refresh Token: {'[OK] Presente' if refresh_token else '[ERRO] Ausente'}")
        print(f"   ID Token: {'[OK] Presente' if id_token else '[ERRO] Ausente'}")
        
        if not all([access_token, refresh_token, id_token]):
            print("\n[ERRO] Nem todos os tokens estao presentes!")
            return False
        
        print("\n[2] Verificando se os tokens sao diferentes entre si:")
        tokens_are_same = (
            access_token == refresh_token or 
            access_token == id_token or 
            refresh_token == id_token
        )
        if tokens_are_same:
            print("   [ERRO] Os tokens sao IGUAIS! Isso indica um problema na hora de salvar.")
            if access_token == refresh_token:
                print("   [ERRO] Access Token e Refresh Token sao iguais!")
            if access_token == id_token:
                print("   [ERRO] Access Token e ID Token sao iguais!")
            if refresh_token == id_token:
                print("   [ERRO] Refresh Token e ID Token sao iguais!")
            return False
        else:
            print("   [OK] Os tokens sao diferentes entre si")
        
        print("\n[3] Verificando expiracao dos tokens:")
        
        access_exp, access_expired, access_iat = check_token_expiration(access_token)
        refresh_exp, refresh_expired, refresh_iat = check_token_expiration(refresh_token)
        id_exp, id_expired, id_iat = check_token_expiration(id_token)
        
        print(f"   Access Token:")
        if access_exp:
            print(f"      Emitido em: {access_iat}")
            print(f"      Expira em: {access_exp}")
            print(f"      Status: {'[ERRO] EXPIRADO' if access_expired else '[OK] VALIDO'}")
            if not access_expired:
                time_until_expiry = access_exp - datetime.now()
                print(f"      Valido por mais: {time_until_expiry}")
            else:
                time_expired = datetime.now() - access_exp
                print(f"      Expirado ha: {time_expired}")
        
        print(f"\n   Refresh Token:")
        if refresh_exp:
            print(f"      Emitido em: {refresh_iat}")
            print(f"      Expira em: {refresh_exp}")
            print(f"      Status: {'[ERRO] EXPIRADO' if refresh_expired else '[OK] VALIDO'}")
            if not refresh_expired:
                time_until_expiry = refresh_exp - datetime.now()
                print(f"      Valido por mais: {time_until_expiry}")
            else:
                time_expired = datetime.now() - refresh_exp
                print(f"      Expirado ha: {time_expired}")
        
        print(f"\n   ID Token:")
        if id_exp:
            print(f"      Emitido em: {id_iat}")
            print(f"      Expira em: {id_exp}")
            print(f"      Status: {'[ERRO] EXPIRADO' if id_expired else '[OK] VALIDO'}")
            if not id_expired:
                time_until_expiry = id_exp - datetime.now()
                print(f"      Valido por mais: {time_until_expiry}")
            else:
                time_expired = datetime.now() - id_exp
                print(f"      Expirado ha: {time_expired}")
        
        print("\n[4] Verificando session_state (sid) nos tokens:")
        access_payload = decode_jwt_payload(access_token)
        refresh_payload = decode_jwt_payload(refresh_token)
        id_payload = decode_jwt_payload(id_token)
        
        access_sid = access_payload.get('sid') if access_payload else None
        refresh_sid = refresh_payload.get('sid') if refresh_payload else None
        id_sid = id_payload.get('sid') if id_payload else None
        
        print(f"   Access Token SID: {access_sid}")
        print(f"   Refresh Token SID: {refresh_sid}")
        print(f"   ID Token SID: {id_sid}")
        
        if access_sid and refresh_sid and id_sid:
            if access_sid == refresh_sid == id_sid:
                print("   [OK] Todos os tokens tem o mesmo session_state (sid)")
            else:
                print("   [ATENCAO] Os tokens tem session_state diferentes!")
                print("   Isso pode indicar que foram gerados em momentos diferentes")
        
        print("\n[5] Testando se o Access Token funciona:")
        test_headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        try:
            test_response = requests.get("https://api.cartola.globo.com/auth/time", headers=test_headers, timeout=10)
            if test_response.status_code == 200:
                print("   [OK] Access Token esta funcionando!")
                team_data = test_response.json()
                api_team_name = team_data.get('time', {}).get('nome', 'N/A')
                print(f"   Nome do time na API: {api_team_name}")
                return True
            else:
                print(f"   [ERRO] Access Token nao funcionou: {test_response.status_code}")
                print(f"   Resposta: {test_response.text[:200]}")
                return False
        except Exception as e:
            print(f"   [ERRO] Erro ao testar token: {e}")
            return False
        
    except Exception as e:
        print(f"[ERRO] Erro durante a verificacao: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        close_db_connection(conn)

def main():
    """Função principal"""
    print("\n" + "="*80)
    print("VERIFICACAO: TIME ENVIADO RECENTEMENTE")
    print("Verificando se os tokens foram salvos corretamente")
    print("="*80)
    
    conn = get_db_connection()
    if not conn:
        print("[ERRO] Nao foi possivel conectar ao banco de dados")
        return
    
    try:
        cursor = conn.cursor()
        # Buscar o time Aero-RBSV (ID 7) que foi enviado recentemente
        cursor.execute('''
            SELECT t.id, t.team_name, t.created_at, t.updated_at
            FROM acw_teams t
            JOIN acw_users u ON t.user_id = u.id
            WHERE u.username = 'renaneunao' AND t.team_name = 'Aero-RBSV'
            ORDER BY t.updated_at DESC
            LIMIT 1
        ''')
        row = cursor.fetchone()
        
        if not row:
            print("[ERRO] Time Aero-RBSV nao encontrado")
            # Listar todos os times para ver qual foi atualizado recentemente
            cursor.execute('''
                SELECT t.id, t.team_name, t.created_at, t.updated_at
                FROM acw_teams t
                JOIN acw_users u ON t.user_id = u.id
                WHERE u.username = 'renaneunao'
                ORDER BY t.updated_at DESC
            ''')
            rows = cursor.fetchall()
            print("\n[INFO] Times encontrados (ordenados por atualizacao mais recente):")
            for r in rows:
                print(f"   ID: {r[0]}, Nome: {r[1]}, Criado: {r[2]}, Atualizado: {r[3]}")
            return
        
        team_id = row[0]
        team_name = row[1]
        created_at = row[2]
        updated_at = row[3]
        
        print(f"\n[INFO] Time encontrado:")
        print(f"   ID: {team_id}")
        print(f"   Nome: {team_name}")
        print(f"   Criado em: {created_at}")
        print(f"   Atualizado em: {updated_at}")
        
        # Verificar tokens
        result = verify_team_tokens(team_id, team_name)
        
        if result:
            print(f"\n{'='*80}")
            print("[OK] VERIFICACAO CONCLUIDA: Tokens estao corretos e funcionando!")
            print(f"{'='*80}\n")
        else:
            print(f"\n{'='*80}")
            print("[ERRO] VERIFICACAO FALHOU: Ha problemas com os tokens!")
            print(f"{'='*80}\n")
        
    except Exception as e:
        print(f"[ERRO] Erro: {e}")
        import traceback
        traceback.print_exc()
    finally:
        close_db_connection(conn)

if __name__ == "__main__":
    main()

