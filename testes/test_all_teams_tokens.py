"""
Script de teste para verificar a validade dos tokens de todos os times de um usuário
"""
import os
import sys
import json
import base64
from datetime import datetime
from dotenv import load_dotenv

# Configurar encoding para Windows e remover emojis
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
    """Decodifica o payload de um JWT sem verificar a assinatura"""
    try:
        # JWT tem formato: header.payload.signature
        parts = token.split('.')
        if len(parts) != 3:
            return None
        
        # Decodificar o payload (parte do meio)
        payload = parts[1]
        # Adicionar padding se necessário
        padding = 4 - len(payload) % 4
        if padding != 4:
            payload += '=' * padding
        
        decoded = base64.urlsafe_b64decode(payload)
        return json.loads(decoded)
    except Exception as e:
        print(f"   [ERRO] Erro ao decodificar JWT: {e}")
        return None

def check_token_expiration(token, token_name):
    """Verifica se um token está expirado e retorna informações detalhadas"""
    if not token:
        return None, None, None, None
    
    payload = decode_jwt_payload(token)
    if not payload:
        return None, None, None, None
    
    exp = payload.get('exp')
    iat = payload.get('iat')  # Issued at
    if not exp:
        return None, None, None, None
    
    exp_datetime = datetime.fromtimestamp(exp)
    iat_datetime = datetime.fromtimestamp(iat) if iat else None
    now = datetime.now()
    is_expired = now > exp_datetime
    
    # Calcular duração total do token
    if iat_datetime:
        total_duration = exp_datetime - iat_datetime
    else:
        total_duration = None
    
    return exp_datetime, is_expired, iat_datetime, total_duration

def test_team_tokens(team_id, team_name):
    """Testa os tokens de um time específico"""
    print(f"\n{'='*80}")
    print(f"TIME: {team_name} (ID: {team_id})")
    print(f"{'='*80}")
    
    conn = get_db_connection()
    if not conn:
        print("[ERRO] Nao foi possivel conectar ao banco de dados")
        return None
    
    try:
        team = get_team(conn, team_id)
        if not team:
            print(f"[ERRO] Time nao encontrado para ID {team_id}")
            return None
        
        access_token = team.get('access_token')
        refresh_token = team.get('refresh_token')
        id_token = team.get('id_token')
        
        print(f"\n[INFO] Tokens presentes:")
        print(f"   Access Token: {'[OK] Sim' if access_token else '[ERRO] Nao'}")
        print(f"   Refresh Token: {'[OK] Sim' if refresh_token else '[ERRO] Nao'}")
        print(f"   ID Token: {'[OK] Sim' if id_token else '[ERRO] Nao'}")
        
        # Verificar se os tokens são iguais
        if access_token and refresh_token and access_token == refresh_token:
            print(f"   [ATENCAO] Access Token e Refresh Token sao IGUAIS!")
        if access_token and id_token and access_token == id_token:
            print(f"   [ATENCAO] Access Token e ID Token sao IGUAIS!")
        if refresh_token and id_token and refresh_token == id_token:
            print(f"   [ATENCAO] Refresh Token e ID Token sao IGUAIS!")
        
        # Verificar expiração do Access Token
        print(f"\n[INFO] ACCESS TOKEN:")
        if access_token:
            exp_datetime, is_expired, iat_datetime, total_duration = check_token_expiration(access_token, "Access Token")
            if exp_datetime:
                print(f"   Emitido em: {iat_datetime if iat_datetime else 'N/A'}")
                print(f"   Expira em: {exp_datetime}")
                if total_duration:
                    print(f"   Duracao total: {total_duration}")
                print(f"   Status: {'[ERRO] EXPIRADO' if is_expired else '[OK] VALIDO'}")
                if is_expired:
                    time_diff = datetime.now() - exp_datetime
                    print(f"   Expirado ha: {time_diff}")
                else:
                    time_diff = exp_datetime - datetime.now()
                    print(f"   Valido por mais: {time_diff}")
        else:
            print(f"   [ERRO] Token nao disponivel")
        
        # Verificar expiração do Refresh Token
        print(f"\n[INFO] REFRESH TOKEN:")
        if refresh_token:
            exp_datetime, is_expired, iat_datetime, total_duration = check_token_expiration(refresh_token, "Refresh Token")
            if exp_datetime:
                print(f"   Emitido em: {iat_datetime if iat_datetime else 'N/A'}")
                print(f"   Expira em: {exp_datetime}")
                if total_duration:
                    print(f"   Duracao total: {total_duration}")
                print(f"   Status: {'[ERRO] EXPIRADO' if is_expired else '[OK] VALIDO'}")
                if is_expired:
                    time_diff = datetime.now() - exp_datetime
                    print(f"   Expirado ha: {time_diff}")
                else:
                    time_diff = exp_datetime - datetime.now()
                    print(f"   Valido por mais: {time_diff}")
        else:
            print(f"   [ERRO] Token nao disponivel")
        
        # Verificar expiração do ID Token
        print(f"\n[INFO] ID TOKEN:")
        if id_token:
            exp_datetime, is_expired, iat_datetime, total_duration = check_token_expiration(id_token, "ID Token")
            if exp_datetime:
                print(f"   Emitido em: {iat_datetime if iat_datetime else 'N/A'}")
                print(f"   Expira em: {exp_datetime}")
                if total_duration:
                    print(f"   Duracao total: {total_duration}")
                print(f"   Status: {'[ERRO] EXPIRADO' if is_expired else '[OK] VALIDO'}")
                if is_expired:
                    time_diff = datetime.now() - exp_datetime
                    print(f"   Expirado ha: {time_diff}")
                else:
                    time_diff = exp_datetime - datetime.now()
                    print(f"   Valido por mais: {time_diff}")
        else:
            print(f"   [ERRO] Token nao disponivel")
        
        # Testar se o access_token funciona
        print(f"\n[TESTE] Testando Access Token na API:")
        if access_token:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            try:
                response = requests.get("https://api.cartola.globo.com/auth/time", headers=headers, timeout=10)
                if response.status_code == 200:
                    print(f"   [OK] Access Token esta funcionando!")
                    team_data = response.json()
                    print(f"   Nome do time na API: {team_data.get('time', {}).get('nome', 'N/A')}")
                elif response.status_code == 401:
                    print(f"   [ERRO] Access Token expirado ou invalido (401)")
                    print(f"   Resposta: {response.text[:100]}")
                else:
                    print(f"   [ATENCAO] Status inesperado: {response.status_code}")
            except Exception as e:
                print(f"   [ERRO] Erro ao testar: {e}")
        else:
            print(f"   [ERRO] Access Token nao disponivel para teste")
        
        print(f"\n{'='*80}\n")
        
        return {
            'team_id': team_id,
            'team_name': team_name,
            'access_expired': is_expired if access_token else None,
            'refresh_expired': is_expired if refresh_token else None,
            'id_expired': is_expired if id_token else None,
            'access_exp_datetime': exp_datetime if access_token else None,
            'refresh_exp_datetime': exp_datetime if refresh_token else None,
            'id_exp_datetime': exp_datetime if id_token else None,
        }
        
    except Exception as e:
        print(f"[ERRO] Erro durante o teste: {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        close_db_connection(conn)

def main():
    """Função principal"""
    print("\n" + "="*80)
    print("VERIFICACAO DE TOKENS - TODOS OS TIMES DO USUARIO renaneunao")
    print("="*80)
    
    conn = get_db_connection()
    if not conn:
        print("[ERRO] Nao foi possivel conectar ao banco de dados")
        return
    
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT t.id, t.team_name, t.created_at, t.updated_at
            FROM acw_teams t
            JOIN acw_users u ON t.user_id = u.id
            WHERE u.username = 'renaneunao'
            ORDER BY t.id
        ''')
        rows = cursor.fetchall()
        
        if not rows:
            print("[ERRO] Nenhum time encontrado para o usuario 'renaneunao'")
            return
        
        print(f"\n[INFO] Total de times encontrados: {len(rows)}\n")
        
        results = []
        for row in rows:
            team_id = row[0]
            team_name = row[1]
            created_at = row[2]
            updated_at = row[3]
            
            print(f"[INFO] Processando time ID {team_id}: {team_name}")
            print(f"   Criado em: {created_at}")
            print(f"   Atualizado em: {updated_at}")
            
            result = test_team_tokens(team_id, team_name)
            if result:
                results.append(result)
        
        # Resumo final
        print("\n" + "="*80)
        print("RESUMO GERAL")
        print("="*80)
        print(f"\nTotal de times verificados: {len(results)}\n")
        
        for result in results:
            print(f"Time: {result['team_name']} (ID: {result['team_id']})")
            if result['access_exp_datetime']:
                print(f"   Access Token expira em: {result['access_exp_datetime']} ({'EXPIRADO' if result['access_expired'] else 'VALIDO'})")
            if result['refresh_exp_datetime']:
                print(f"   Refresh Token expira em: {result['refresh_exp_datetime']} ({'EXPIRADO' if result['refresh_expired'] else 'VALIDO'})")
            if result['id_exp_datetime']:
                print(f"   ID Token expira em: {result['id_exp_datetime']} ({'EXPIRADO' if result['id_expired'] else 'VALIDO'})")
            print()
        
    except Exception as e:
        print(f"[ERRO] Erro: {e}")
        import traceback
        traceback.print_exc()
    finally:
        close_db_connection(conn)

if __name__ == "__main__":
    main()

