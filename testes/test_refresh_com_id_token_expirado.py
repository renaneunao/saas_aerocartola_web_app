"""
Script para testar refresh token mesmo quando id_token está expirado
Verifica quando os id_tokens dos outros times vencem e tenta fazer refresh
"""
import os
import sys
import json
import base64
from datetime import datetime, timedelta
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
from models.teams import get_team, update_team_tokens
import requests

def decode_jwt_payload(token):
    """Decodifica o payload de um JWT sem verificar a assinatura"""
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
    except Exception as e:
        print(f"   [ERRO] Erro ao decodificar JWT: {e}")
        return None

def check_token_expiration(token):
    """Verifica se um token está expirado e retorna informações"""
    if not token:
        return None, None, None, None
    
    payload = decode_jwt_payload(token)
    if not payload:
        return None, None, None, None
    
    exp = payload.get('exp')
    iat = payload.get('iat')
    if not exp:
        return None, None, None, None
    
    exp_datetime = datetime.fromtimestamp(exp)
    iat_datetime = datetime.fromtimestamp(iat) if iat else None
    now = datetime.now()
    is_expired = now > exp_datetime
    
    if iat_datetime:
        total_duration = exp_datetime - iat_datetime
    else:
        total_duration = None
    
    return exp_datetime, is_expired, iat_datetime, total_duration

def test_refresh_with_expired_id_token(team_id, team_name):
    """Testa fazer refresh mesmo quando id_token está expirado"""
    print(f"\n{'='*80}")
    print(f"TESTE: {team_name} (ID: {team_id})")
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
        
        # Verificar expiração dos tokens
        print("[INFO] Verificando expiracao dos tokens:")
        
        access_exp, access_expired, access_iat, access_duration = check_token_expiration(access_token)
        refresh_exp, refresh_expired, refresh_iat, refresh_duration = check_token_expiration(refresh_token)
        id_exp, id_expired, id_iat, id_duration = check_token_expiration(id_token)
        
        print(f"   Access Token:")
        if access_exp:
            print(f"      Emitido em: {access_iat}")
            print(f"      Expira em: {access_exp}")
            print(f"      Duracao: {access_duration}")
            print(f"      Status: {'[ERRO] EXPIRADO' if access_expired else '[OK] VALIDO'}")
            if access_expired:
                print(f"      Expirado ha: {datetime.now() - access_exp}")
            else:
                print(f"      Valido por mais: {access_exp - datetime.now()}")
        
        print(f"\n   Refresh Token:")
        if refresh_exp:
            print(f"      Emitido em: {refresh_iat}")
            print(f"      Expira em: {refresh_exp}")
            print(f"      Duracao: {refresh_duration}")
            print(f"      Status: {'[ERRO] EXPIRADO' if refresh_expired else '[OK] VALIDO'}")
            if refresh_expired:
                print(f"      Expirado ha: {datetime.now() - refresh_exp}")
            else:
                print(f"      Valido por mais: {refresh_exp - datetime.now()}")
        
        print(f"\n   ID Token:")
        if id_exp:
            print(f"      Emitido em: {id_iat}")
            print(f"      Expira em: {id_exp}")
            print(f"      Duracao: {id_duration}")
            print(f"      Status: {'[ERRO] EXPIRADO' if id_expired else '[OK] VALIDO'}")
            if id_expired:
                time_expired = datetime.now() - id_exp
                print(f"      Expirado ha: {time_expired}")
                print(f"      [ATENCAO] ID Token esta EXPIRADO! Vamos tentar refresh mesmo assim...")
            else:
                print(f"      Valido por mais: {id_exp - datetime.now()}")
        
        # Tentar fazer refresh mesmo com id_token expirado
        print(f"\n[TESTE] Tentando fazer refresh (mesmo com ID Token expirado):")
        
        client_id = "cartola-web@apps.globoid"
        url = "https://web-api.globoid.globo.com/v1/refresh-token"
        headers = {
            "Content-Type": "application/json",
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
            "Origin": "https://cartola.globo.com",
            "Referer": "https://cartola.globo.com/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36 Edg/138.0.0.0",
        }
        payload = {
            "client_id": client_id,
            "refresh_token": refresh_token,
            "access_token": access_token,
            "id_token": id_token
        }
        
        print(f"   Enviando requisição para: {url}")
        print(f"   Payload: client_id, refresh_token, access_token, id_token (todos presentes)")
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            print(f"   Status Code: {response.status_code}")
            
            if response.status_code == 200:
                tokens = response.json()
                new_access_token = tokens.get("access_token")
                new_refresh_token = tokens.get("refresh_token")
                new_id_token = tokens.get("id_token")
                
                print("   [OK] Refresh realizado com sucesso!")
                print(f"   Novo Access Token recebido: {'Sim' if new_access_token else 'Nao'}")
                print(f"   Novo Refresh Token recebido: {'Sim' if new_refresh_token else 'Nao'}")
                print(f"   Novo ID Token recebido: {'Sim' if new_id_token else 'Nao'}")
                
                if new_access_token and new_refresh_token and new_id_token:
                    # Verificar expiração dos novos tokens
                    new_access_exp, new_access_expired, _, _ = check_token_expiration(new_access_token)
                    new_refresh_exp, new_refresh_expired, _, _ = check_token_expiration(new_refresh_token)
                    new_id_exp, new_id_expired, _, _ = check_token_expiration(new_id_token)
                    
                    print(f"\n   [INFO] Novos tokens:")
                    if new_access_exp:
                        print(f"      Novo Access Token expira em: {new_access_exp} ({'EXPIRADO' if new_access_expired else 'VALIDO'})")
                    if new_refresh_exp:
                        print(f"      Novo Refresh Token expira em: {new_refresh_exp} ({'EXPIRADO' if new_refresh_expired else 'VALIDO'})")
                    if new_id_exp:
                        print(f"      Novo ID Token expira em: {new_id_exp} ({'EXPIRADO' if new_id_expired else 'VALIDO'})")
                    
                    # Atualizar no banco
                    update_team_tokens(conn, team_id, 
                                     access_token=new_access_token, 
                                     refresh_token=new_refresh_token, 
                                     id_token=new_id_token)
                    print("   [OK] Tokens atualizados no banco de dados")
                    
                    # Testar se o novo access_token funciona
                    print(f"\n   [TESTE] Testando novo Access Token:")
                    test_headers = {
                        "Authorization": f"Bearer {new_access_token}",
                        "Accept": "application/json",
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                    }
                    try:
                        test_response = requests.get("https://api.cartola.globo.com/auth/time", headers=test_headers, timeout=10)
                        if test_response.status_code == 200:
                            print("      [OK] Novo Access Token esta funcionando!")
                            team_data = test_response.json()
                            print(f"      Nome do time na API: {team_data.get('time', {}).get('nome', 'N/A')}")
                        else:
                            print(f"      [ERRO] Novo token nao funcionou: {test_response.status_code}")
                            print(f"      Resposta: {test_response.text[:200]}")
                    except Exception as e:
                        print(f"      [ERRO] Erro ao testar novo token: {e}")
                    
                    return True
                else:
                    print("   [ERRO] Nem todos os tokens foram recebidos na resposta")
                    return False
            else:
                print(f"   [ERRO] Falha no refresh: {response.status_code}")
                print(f"   Resposta: {response.text[:500]}")
                try:
                    error_data = response.json()
                    print(f"   Erro JSON: {json.dumps(error_data, indent=2)}")
                    
                    if error_data.get('error') == 'session_terminated':
                        print(f"\n   [ATENCAO] Sessao encerrada no servidor!")
                        print(f"   Isso significa que mesmo com refresh_token valido, a sessao foi encerrada.")
                        print(f"   E necessario fazer um novo login para obter novos tokens.")
                except:
                    pass
                return False
        except requests.exceptions.RequestException as e:
            print(f"   [ERRO] Erro de rede: {e}")
            return False
        except Exception as e:
            print(f"   [ERRO] Erro inesperado: {e}")
            import traceback
            traceback.print_exc()
            return False
        
    except Exception as e:
        print(f"[ERRO] Erro durante o teste: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        close_db_connection(conn)

def main():
    """Função principal"""
    print("\n" + "="*80)
    print("TESTE: REFRESH COM ID TOKEN EXPIRADO")
    print("Verificando quando os id_tokens vencem e testando refresh")
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
            print("[ERRO] Nenhum time encontrado")
            return
        
        print(f"\n[INFO] Total de times encontrados: {len(rows)}\n")
        
        results = []
        for row in rows:
            team_id = row[0]
            team_name = row[1]
            
            # Verificar quando o id_token expira
            team = get_team(conn, team_id)
            if team:
                id_token = team.get('id_token')
                if id_token:
                    id_exp, id_expired, id_iat, _ = check_token_expiration(id_token)
                    if id_exp:
                        print(f"[INFO] {team_name} (ID: {team_id})")
                        print(f"   ID Token expira em: {id_exp}")
                        print(f"   Status: {'EXPIRADO' if id_expired else 'VALIDO'}")
                        if not id_expired:
                            time_until_expiry = id_exp - datetime.now()
                            print(f"   Vai expirar em: {time_until_expiry}")
                        print()
        
        # Testar refresh em cada time
        for row in rows:
            team_id = row[0]
            team_name = row[1]
            
            result = test_refresh_with_expired_id_token(team_id, team_name)
            results.append({
                'team_id': team_id,
                'team_name': team_name,
                'success': result
            })
        
        # Resumo
        print("\n" + "="*80)
        print("RESUMO DOS TESTES")
        print("="*80)
        for result in results:
            status = "[OK] Sucesso" if result['success'] else "[ERRO] Falhou"
            print(f"{result['team_name']} (ID: {result['team_id']}): {status}")
        
    except Exception as e:
        print(f"[ERRO] Erro: {e}")
        import traceback
        traceback.print_exc()
    finally:
        close_db_connection(conn)

if __name__ == "__main__":
    main()

