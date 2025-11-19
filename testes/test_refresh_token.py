"""
Script de teste para verificar a funcionalidade de refresh_token
Especificamente para o time Aero-RBSV do usuário renaneunao
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
from api_cartola import refresh_access_token_by_team_id, fetch_team_data_by_team_id
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
        print(f"Erro ao decodificar JWT: {e}")
        return None

def check_token_expiration(token):
    """Verifica se um token está expirado"""
    payload = decode_jwt_payload(token)
    if not payload:
        return None, None
    
    exp = payload.get('exp')
    if not exp:
        return None, None
    
    exp_datetime = datetime.fromtimestamp(exp)
    now = datetime.now()
    is_expired = now > exp_datetime
    
    return exp_datetime, is_expired

def test_refresh_token_for_team(team_id):
    """Testa o refresh_token para um time específico"""
    print(f"\n{'='*80}")
    print(f"TESTE DE REFRESH TOKEN - Time ID: {team_id}")
    print(f"{'='*80}\n")
    
    conn = get_db_connection()
    if not conn:
        print("❌ Erro: Não foi possível conectar ao banco de dados")
        return False
    
    try:
        # Buscar o time
        team = get_team(conn, team_id)
        if not team:
            print(f"[ERRO] Time nao encontrado para ID {team_id}")
            return False
        
        print(f"[OK] Time encontrado: {team.get('team_name')}")
        print(f"   User ID: {team.get('user_id')}")
        print(f"   Criado em: {team.get('created_at')}")
        print(f"   Atualizado em: {team.get('updated_at')}\n")
        
        # Verificar tokens atuais
        access_token = team.get('access_token')
        refresh_token = team.get('refresh_token')
        id_token = team.get('id_token')
        
        print("[INFO] VERIFICACAO DOS TOKENS:")
        print(f"   Access Token: {'[OK] Presente' if access_token else '[ERRO] Ausente'}")
        print(f"   Refresh Token: {'[OK] Presente' if refresh_token else '[ERRO] Ausente'}")
        print(f"   ID Token: {'[OK] Presente' if id_token else '[ERRO] Ausente'}\n")
        
        # Verificar se os tokens são iguais (problema potencial)
        if access_token and refresh_token and access_token == refresh_token:
            print("[ATENCAO] Access Token e Refresh Token sao IGUAIS! Isso e um problema!")
        if access_token and id_token and access_token == id_token:
            print("[ATENCAO] Access Token e ID Token sao IGUAIS! Isso e um problema!")
        if refresh_token and id_token and refresh_token == id_token:
            print("[ATENCAO] Refresh Token e ID Token sao IGUAIS! Isso e um problema!")
        
        # Verificar expiração do access_token
        if access_token:
            exp_datetime, is_expired = check_token_expiration(access_token)
            if exp_datetime:
                print(f"\n[INFO] EXPIRACAO DO ACCESS TOKEN:")
                print(f"   Expira em: {exp_datetime}")
                print(f"   Status: {'[ERRO] EXPIRADO' if is_expired else '[OK] VALIDO'}")
                if is_expired:
                    time_diff = datetime.now() - exp_datetime
                    print(f"   Expirado há: {time_diff}")
                else:
                    time_diff = exp_datetime - datetime.now()
                    print(f"   Válido por mais: {time_diff}")
        
        # Verificar expiração do refresh_token
        if refresh_token:
            exp_datetime, is_expired = check_token_expiration(refresh_token)
            if exp_datetime:
                print(f"\n[INFO] EXPIRACAO DO REFRESH TOKEN:")
                print(f"   Expira em: {exp_datetime}")
                print(f"   Status: {'[ERRO] EXPIRADO' if is_expired else '[OK] VALIDO'}")
                if is_expired:
                    time_diff = datetime.now() - exp_datetime
                    print(f"   Expirado há: {time_diff}")
                else:
                    time_diff = exp_datetime - datetime.now()
                    print(f"   Válido por mais: {time_diff}")
        
        # Testar se o access_token atual funciona
        print(f"\n[TESTE] TESTANDO ACCESS TOKEN ATUAL:")
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        try:
            response = requests.get("https://api.cartola.globo.com/auth/time", headers=headers, timeout=10)
            if response.status_code == 200:
                print("   [OK] Access Token esta funcionando!")
                team_data = response.json()
                print(f"   Nome do time na API: {team_data.get('time', {}).get('nome', 'N/A')}")
            elif response.status_code == 401:
                print("   [ERRO] Access Token esta expirado ou invalido (401 Unauthorized)")
                print("   [INFO] Resposta:", response.text[:200])
            else:
                print(f"   [ATENCAO] Status inesperado: {response.status_code}")
                print(f"   Resposta: {response.text[:200]}")
        except Exception as e:
            print(f"   [ERRO] Erro ao testar token: {e}")
        
        # Tentar fazer refresh manualmente para ver detalhes
        print(f"\n[REFRESH] TENTANDO FAZER REFRESH DO TOKEN:")
        print(f"   URL: https://web-api.globoid.globo.com/v1/refresh-token")
        print(f"   Client ID: cartola-web@apps.globoid")
        
        # Fazer refresh manual para ver a resposta completa
        client_id = "cartola-web@apps.globoid"
        url = "https://web-api.globoid.globo.com/v1/refresh-token"
        headers_refresh = {
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
        
        try:
            print(f"   Enviando requisição...")
            response = requests.post(url, headers=headers_refresh, json=payload, timeout=30)
            print(f"   Status Code: {response.status_code}")
            
            if response.status_code == 200:
                tokens = response.json()
                new_access_token = tokens.get("access_token")
                new_refresh_token = tokens.get("refresh_token")
                new_id_token = tokens.get("id_token")
                
                print("   [OK] Refresh realizado com sucesso!")
                print(f"   Novo Access Token recebido: {'Sim' if new_access_token else 'Não'}")
                print(f"   Novo Refresh Token recebido: {'Sim' if new_refresh_token else 'Não'}")
                print(f"   Novo ID Token recebido: {'Sim' if new_id_token else 'Não'}")
                
                if new_access_token:
                    print(f"   Novo Access Token: {new_access_token[:50]}...")
                    
                    # Atualizar no banco usando a função da API
                    from models.teams import update_team_tokens
                    update_team_tokens(conn, team_id, 
                                     access_token=new_access_token, 
                                     refresh_token=new_refresh_token, 
                                     id_token=new_id_token)
                    print("   [OK] Tokens atualizados no banco de dados")
            else:
                print(f"   [ERRO] Falha no refresh: {response.status_code}")
                print(f"   Resposta: {response.text[:500]}")
                try:
                    error_data = response.json()
                    print(f"   Erro JSON: {json.dumps(error_data, indent=2)}")
                except:
                    pass
                new_access_token = None
        except requests.exceptions.RequestException as e:
            print(f"   [ERRO] Erro de rede: {e}")
            new_access_token = None
        except Exception as e:
            print(f"   [ERRO] Erro inesperado: {e}")
            import traceback
            traceback.print_exc()
            new_access_token = None
        
        # Também tentar usando a função da API
        print(f"\n[REFRESH] TENTANDO REFRESH USANDO FUNCAO DA API:")
        new_access_token_api = refresh_access_token_by_team_id(conn, team_id)
        
        if new_access_token_api:
            print("   [OK] Refresh via funcao da API realizado com sucesso!")
            if new_access_token and new_access_token != new_access_token_api:
                print("   [ATENCAO] Tokens diferentes entre refresh manual e funcao da API")
            new_access_token = new_access_token_api
        else:
            print("   [ERRO] Falha no refresh via funcao da API")
        
        if new_access_token:
            
            # Verificar se o novo token funciona
            print(f"\n[TESTE] TESTANDO NOVO ACCESS TOKEN:")
            headers["Authorization"] = f"Bearer {new_access_token}"
            try:
                response = requests.get("https://api.cartola.globo.com/auth/time", headers=headers, timeout=10)
                if response.status_code == 200:
                    print("   [OK] Novo Access Token esta funcionando!")
                    team_data = response.json()
                    print(f"   Nome do time na API: {team_data.get('time', {}).get('nome', 'N/A')}")
                else:
                    print(f"   [ERRO] Novo token nao funcionou: {response.status_code}")
                    print(f"   Resposta: {response.text[:200]}")
            except Exception as e:
                print(f"   [ERRO] Erro ao testar novo token: {e}")
            
            # Verificar expiração do novo token
            exp_datetime, is_expired = check_token_expiration(new_access_token)
            if exp_datetime:
                print(f"\n[INFO] EXPIRACAO DO NOVO ACCESS TOKEN:")
                print(f"   Expira em: {exp_datetime}")
                print(f"   Status: {'[ERRO] EXPIRADO' if is_expired else '[OK] VALIDO'}")
                if not is_expired:
                    time_diff = exp_datetime - datetime.now()
                    print(f"   Válido por mais: {time_diff}")
        else:
            print("   [ERRO] Falha ao fazer refresh do token")
            print("   Verifique os logs acima para mais detalhes")
        
        # Buscar dados atualizados do time no banco
        print(f"\n[INFO] DADOS ATUALIZADOS DO TIME NO BANCO:")
        team_updated = get_team(conn, team_id)
        if team_updated:
            print(f"   Atualizado em: {team_updated.get('updated_at')}")
            if new_access_token:
                new_exp_datetime, new_is_expired = check_token_expiration(team_updated.get('access_token'))
                if new_exp_datetime:
                    print(f"   Novo Access Token expira em: {new_exp_datetime}")
        
        print(f"\n{'='*80}\n")
        return True
        
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
    print("TESTE DE REFRESH TOKEN - Aero-RBSV")
    print("="*80)
    
    # Buscar o time Aero-RBSV do usuário renaneunao
    conn = get_db_connection()
    if not conn:
        print("❌ Erro: Não foi possível conectar ao banco de dados")
        return
    
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT t.id, t.team_name, u.username
            FROM acw_teams t
            JOIN acw_users u ON t.user_id = u.id
            WHERE u.username = 'renaneunao' AND t.team_name = 'Aero-RBSV'
        ''')
        row = cursor.fetchone()
        
        if not row:
            print("[ERRO] Time 'Aero-RBSV' nao encontrado para o usuario 'renaneunao'")
            return
        
        team_id = row[0]
        team_name = row[1]
        username = row[2]
        
        print(f"\n[OK] Time encontrado:")
        print(f"   ID: {team_id}")
        print(f"   Nome: {team_name}")
        print(f"   Usuário: {username}\n")
        
        # Executar o teste
        test_refresh_token_for_team(team_id)
        
    except Exception as e:
        print(f"[ERRO] Erro: {e}")
        import traceback
        traceback.print_exc()
    finally:
        close_db_connection(conn)

if __name__ == "__main__":
    main()

