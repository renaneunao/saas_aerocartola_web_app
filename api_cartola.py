import requests
import os
from pathlib import Path
from utils.utilidades import printdbg
from database import get_db_connection, close_db_connection
from models.credenciais import get_credencial_by_env_key, update_tokens_by_env_key
from models.teams import get_team, update_team_tokens

# Tokens agora são obtidos do banco de dados (tabela 'credenciais').

API_URL_MERCADO = "https://api.cartola.globo.com/atletas/mercado"
API_URL_STATUS = "https://api.cartola.globo.com/mercado/status"
API_URL_PONTUADOS = "https://api.cartola.globo.com/atletas/pontuados/{}"
API_URL_PARTIDAS = "https://api.cartola.globo.com/partidas/{}"
API_URL_ESQUEMAS = "https://api.cartolafc.globo.com/esquemas"
API_URL_DESTAQUES = "https://api.cartola.globo.com/auth/mercado/destaques"
API_URL_GATO_MESTRE = "https://api.cartola.globo.com/auth/gatomestre/atletas"
API_URL_REFRESH = "https://api.cartola.globo.com/refresh"
API_URL_TEAM_DATA = "https://api.cartola.globo.com/auth/time"
API_URL_TEAM_INFO = "https://api.cartola.globo.com/auth/time/info"
API_URL_SALVAR_TIME = "https://api.cartola.globo.com/auth/time/salvar"

# Cache para a temporada
_TEMPORADA_CACHE = None
_TEMPORADA_CACHE_TIMESTAMP = None
_CACHE_DURATION = 3600 # 1 hora in seconds

def update_env_with_new_key(new_key, env_key="ACCESS_TOKEN_TIME1"):
    """[DEPRECATED] Mantido por compatibilidade; não grava mais em .env."""
    return new_key

def refresh_access_token(current_token, env_key="ACCESS_TOKEN_TIME1"):
    """Atualiza os tokens de acesso via API usando o refresh token."""
    # Buscar credencial no banco
    conn = get_db_connection()
    cred = None
    try:
        cred = get_credencial_by_env_key(conn, env_key)
    finally:
        close_db_connection(conn)

    if not cred:
        printdbg(f"Erro: Credencial não encontrada para {env_key}")
        return None

    refresh_token = cred.get("refresh_token")
    id_token = cred.get("id_token")
    if not current_token:
        current_token = cred.get("access_token")
    if not current_token:
        printdbg(f"Erro: Nenhum access token disponível para refresh em {env_key}")
        return None
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
        "Sec-Ch-Ua": "\"Not)A;Brand\";v=\"8\", \"Chromium\";v=\"138\", \"Microsoft Edge\";v=\"138\"",
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": "\"Windows\"",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-site"
    }
    payload = {
        "client_id": client_id,
        "refresh_token": refresh_token,
        "access_token": current_token,
        "id_token": id_token
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code == 200:
            tokens = response.json()
            new_access_token = tokens.get("access_token")
            new_refresh_token = tokens.get("refresh_token")
            new_id_token = tokens.get("id_token")

            # Persistir no banco
            conn2 = get_db_connection()
            try:
                update_tokens_by_env_key(conn2, env_key, access_token=new_access_token, refresh_token=new_refresh_token, id_token=new_id_token)
            finally:
                close_db_connection(conn2)
            return new_access_token
        else:
            print(f"Falha no refresh ({response.status_code}) para {env_key}.")
            try:
                error_data = response.json()
                print(f"Resposta de erro: {error_data}")
            except:
                print(f"Resposta de erro (texto): {response.text[:500]}")
            return None
    except requests.exceptions.JSONDecodeError as e:
        print(f"Erro ao parsear resposta do refresh para {env_key}: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Resposta recebida: {e.response.text[:500]}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Erro de rede no refresh para {env_key}: {e}")
        return None

def fetch_cartola_data():
    """Obtém dados do mercado (não requer autenticação)."""
    try:
        response = requests.get(API_URL_MERCADO)
        response.raise_for_status()
        data = response.json()
        if 'atletas' in data:
            printdbg(f"Total de atletas obtidos da API: {len(data['atletas'])}")
        return data
    except requests.exceptions.RequestException as e:
        print(f"Erro ao consultar a API Cartola (mercado): {e}")
        return None

def fetch_status_data():
    """Obtém o status do mercado (não requer autenticação)."""
    try:
        response = requests.get(API_URL_STATUS)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Erro ao consultar a API Cartola (status): {e}")
        return None

def get_temporada_atual() -> int:
    """
    Retorna a temporada atual buscando da API de status do Cartola.
    Usa cache de 1 hora para evitar múltiplas requisições.
    Fallback para ano atual caso a API falhe.
    """
    import time
    from datetime import datetime
    
    global _TEMPORADA_CACHE, _TEMPORADA_CACHE_TIMESTAMP
    
    # Verificar cache
    current_time = time.time()
    if _TEMPORADA_CACHE is not None and _TEMPORADA_CACHE_TIMESTAMP is not None:
        if current_time - _TEMPORADA_CACHE_TIMESTAMP < _CACHE_DURATION:
            return _TEMPORADA_CACHE
    
    # Buscar da API
    try:
        status_data = fetch_status_data()
        
        if status_data and 'temporada' in status_data:
            temporada = int(status_data['temporada'])
            # Atualizar cache
            _TEMPORADA_CACHE = temporada
            _TEMPORADA_CACHE_TIMESTAMP = current_time
            return temporada
    except Exception as e:
        printdbg(f"Erro ao buscar temporada da API: {e}. Usando fallback (ano atual)")
    
    # Fallback para o ano atual do sistema
    return datetime.now().year

def fetch_pontuados_data(rodada):
    """Obtém dados de atletas pontuados para a rodada especificada (não requer autenticação)."""
    try:
        response = requests.get(API_URL_PONTUADOS.format(rodada))
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Erro ao consultar a API Cartola (pontuados, rodada {rodada}): {e}")
        return None

def fetch_partidas_data(rodada):
    """Obtém dados das partidas da rodada especificada (não requer autenticação)."""
    try:
        response = requests.get(API_URL_PARTIDAS.format(rodada))
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Erro ao consultar a API Cartola (partidas, rodada {rodada}): {e}")
        return None

def fetch_esquemas_data():
    """Obtém dados dos esquemas disponíveis (não requer autenticação)."""
    try:
        response = requests.get(API_URL_ESQUEMAS)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Erro ao consultar a API Cartola (esquemas): {e}")
        return None

def fetch_destaques_data(access_token=None, env_key="ACCESS_TOKEN_TIME1"):
    """Obtém dados de destaques do mercado."""
    token = access_token
    if not token:
        conn = get_db_connection()
        try:
            cred = get_credencial_by_env_key(conn, env_key)
            token = cred.get("access_token") if cred else None
        finally:
            close_db_connection(conn)
    if not token:
        printdbg(f"Erro: Access token não encontrado para {env_key}")
        return None

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
    }

    try:
        response = requests.get(API_URL_DESTAQUES, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        if hasattr(e.response, 'status_code') and e.response.status_code == 401:
            printdbg(f"Token expirado ({env_key}). Atualizando...")
            new_token = refresh_access_token(token, env_key)
            if new_token:
                headers["Authorization"] = f"Bearer {new_token}"
                try:
                    response = requests.get(API_URL_DESTAQUES, headers=headers)
                    response.raise_for_status()
                    return response.json()
                except requests.exceptions.RequestException as e:
                    printdbg(f"Falha pós-refresh em destaques ({env_key}): {e}")
                    return None
            else:
                printdbg(f"Refresh de token falhou ({env_key}).")
                return None
        else:
            printdbg(f"Erro em destaques ({env_key}): {e}")
            return None

def fetch_gato_mestre_data(access_token=None, env_key="ACCESS_TOKEN_TIME1"):
    """Obtém dados do Gato Mestre."""
    token = access_token
    if not token:
        conn = get_db_connection()
        try:
            cred = get_credencial_by_env_key(conn, env_key)
            token = cred.get("access_token") if cred else None
        finally:
            close_db_connection(conn)
    if not token:
        printdbg(f"Erro: Access token não encontrado para {env_key}")
        return None

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
    }

    try:
        response = requests.get(API_URL_GATO_MESTRE, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        if hasattr(e.response, 'status_code') and e.response.status_code == 401:
            printdbg(f"Token expirado para {env_key}. Tentando atualizar o token...")
            new_token = refresh_access_token(token, env_key)
            if new_token:
                headers["Authorization"] = f"Bearer {new_token}"
                try:
                    response = requests.get(API_URL_GATO_MESTRE, headers=headers)
                    response.raise_for_status()
                    return response.json()
                except requests.exceptions.RequestException as e:
                    printdbg(f"Falha pós-refresh em gato_mestre ({env_key}): {e}")
                    return None
            else:
                printdbg(f"Falha ao atualizar o token para {env_key}.")
                return None
        else:
            printdbg(f"Erro em gato_mestre ({env_key}): {e}")
            return None

def refresh_access_token_by_team_id(conn, team_id: int):
    """Atualiza os tokens de acesso via API usando o refresh token, baseado em team_id."""
    team = get_team(conn, team_id)
    
    if not team:
        printdbg(f"Erro: Time não encontrado para ID {team_id}")
        return None
    
    current_token = team.get('access_token')
    refresh_token = team.get('refresh_token')
    id_token = team.get('id_token')
    
    if not refresh_token or not current_token:
        printdbg(f"Erro: Tokens não disponíveis para ID {team_id}")
        return None
    
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
        "access_token": current_token,
        "id_token": id_token
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code == 200:
            tokens = response.json()
            new_access_token = tokens.get("access_token")
            new_refresh_token = tokens.get("refresh_token")
            new_id_token = tokens.get("id_token")

            # Atualizar no banco
            update_team_tokens(conn, team_id, access_token=new_access_token, refresh_token=new_refresh_token, id_token=new_id_token)
            return new_access_token
        else:
            printdbg(f"Falha no refresh ({response.status_code}) para ID {team_id}.")
            try:
                error_data = response.json()
                printdbg(f"Resposta de erro: {error_data}")
            except:
                printdbg(f"Resposta de erro (texto): {response.text[:500]}")
            return None
    except requests.exceptions.RequestException as e:
        printdbg(f"Erro de rede ao atualizar token para ID {team_id}: {e}")
        return None
    except Exception as e:
        printdbg(f"Erro ao atualizar token para ID {team_id}: {e}")
        import traceback
        printdbg(traceback.format_exc())
        return None

def fetch_team_data(access_token=None, env_key="ACCESS_TOKEN_TIME1"):
    """Obtém os dados do time do usuário, incluindo o patrimônio."""
    printdbg(f"Buscando dados do time ({env_key})")
    token = access_token
    if not token:
        conn = get_db_connection()
        try:
            cred = get_credencial_by_env_key(conn, env_key)
            token = cred.get("access_token") if cred else None
        finally:
            close_db_connection(conn)
    if not token:
        printdbg(f"Erro: Access token não encontrado para {env_key}")
        return None, None

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
    }

    try:
        response = requests.get(API_URL_TEAM_DATA, headers=headers)
        response.raise_for_status()
        return response.json(), token
    except requests.exceptions.RequestException as e:
        if hasattr(e.response, 'status_code') and e.response.status_code == 401:
            printdbg(f"Token expirado para {env_key}. Tentando atualizar o token...")
            new_token = refresh_access_token(token, env_key)
            if new_token:
                headers["Authorization"] = f"Bearer {new_token}"
                try:
                    response = requests.get(API_URL_TEAM_DATA, headers=headers)
                    response.raise_for_status()
                    return response.json(), new_token
                except requests.exceptions.RequestException as e:
                    printdbg(f"Falha pós-refresh em time ({env_key}): {e}")
                    return None, None
            else:
                printdbg(f"Falha ao atualizar o token para {env_key}.")
                return None, None
        else:
            printdbg(f"Erro em time ({env_key}): {e}")
            return None, None

def fetch_team_info_by_team_id(conn, team_id: int):
    """Obtém as informações do time (nome, escudo, etc.) usando team_id via /auth/time/info."""
    printdbg(f"Buscando informações do time (ID: {team_id})")
    
    team = get_team(conn, team_id)
    
    if not team:
        printdbg(f"Erro: Time não encontrado para ID {team_id}")
        return None
    
    token = team.get('access_token')
    
    if not token:
        printdbg(f"Erro: Access token não encontrado para ID {team_id}")
        return None

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
    }

    try:
        response = requests.get(API_URL_TEAM_INFO, headers=headers)
        response.raise_for_status()
        team_info = response.json()
        printdbg(f"Sucesso ao buscar informações do time (ID: {team_id})")
        return team_info
    except requests.exceptions.RequestException as e:
        if hasattr(e.response, 'status_code') and e.response.status_code == 401:
            printdbg(f"Token expirado para ID {team_id}. Tentando atualizar o token...")
            new_token = refresh_access_token_by_team_id(conn, team_id)
            if new_token:
                headers["Authorization"] = f"Bearer {new_token}"
                try:
                    response = requests.get(API_URL_TEAM_INFO, headers=headers)
                    response.raise_for_status()
                    team_info = response.json()
                    printdbg(f"Sucesso ao buscar informações do time após refresh (ID: {team_id})")
                    return team_info
                except requests.exceptions.RequestException as e2:
                    printdbg(f"Falha pós-refresh em info do time (ID: {team_id}): {e2}")
                    return None
            else:
                printdbg(f"Falha ao atualizar o token para ID {team_id}.")
                return None
        else:
            printdbg(f"Erro em info do time (ID: {team_id}): {e}")
            return None

def fetch_team_data_by_team_id(conn, team_id: int):
    """Obtém os dados do time do usuário usando team_id, incluindo o patrimônio."""
    printdbg(f"Buscando dados do time (ID: {team_id})")
    
    team = get_team(conn, team_id)
    
    if not team:
        printdbg(f"Erro: Time não encontrado para ID {team_id}")
        return None, None
    
    token = team.get('access_token')
    refresh_token = team.get('refresh_token')
    id_token = team.get('id_token')
    
    if not token:
        printdbg(f"Erro: Access token não encontrado para ID {team_id}")
        return None, None

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
    }

    try:
        response = requests.get(API_URL_TEAM_DATA, headers=headers)
        response.raise_for_status()
        team_data = response.json()
        printdbg(f"Sucesso ao buscar dados do time (ID: {team_id})")
        return team_data, token
    except requests.exceptions.RequestException as e:
        if hasattr(e.response, 'status_code') and e.response.status_code == 401:
            printdbg(f"Token expirado para ID {team_id}. Tentando atualizar o token...")
            new_token = refresh_access_token_by_team_id(conn, team_id)
            if new_token:
                headers["Authorization"] = f"Bearer {new_token}"
                try:
                    response = requests.get(API_URL_TEAM_DATA, headers=headers)
                    response.raise_for_status()
                    team_data = response.json()
                    printdbg(f"Sucesso ao buscar dados do time após refresh (ID: {team_id})")
                    return team_data, new_token
                except requests.exceptions.RequestException as e2:
                    printdbg(f"Falha pós-refresh em time (ID: {team_id}): {e2}")
                    return None, None
            else:
                printdbg(f"Falha ao atualizar o token para ID {team_id}.")
                return None, None
        else:
            printdbg(f"Erro em time (ID: {team_id}): {e}")
            return None, None

def salvar_time_no_cartola(time_para_escalacao, access_token=None, env_key="ACCESS_TOKEN_TIME1"):
    """Envia a escalação para a API do Cartola FC."""
    printdbg(f"Enviando escalação ({env_key})")
    token = access_token
    if not token:
        conn = get_db_connection()
        try:
            cred = get_credencial_by_env_key(conn, env_key)
            token = cred.get("access_token") if cred else None
        finally:
            close_db_connection(conn)
    if not token:
        printdbg(f"Erro: Access token não encontrado para {env_key}")
        return False

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json;charset=UTF-8",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36 Edg/139.0.0.0",
        "Origin": "https://cartola.globo.com",
        "Referer": "https://cartola.globo.com/",
        "x-glb-app": "cartola_web",
        "x-glb-auth": "oidc",
    }

    try:
        response = requests.post(API_URL_SALVAR_TIME, json=time_para_escalacao, headers=headers)
        status = response.status_code
        # Tentar JSON; se falhar, manter texto cru
        try:
            data = response.json()
        except Exception:
            data = None
        body_preview = (response.text[:500] + ('...' if len(response.text) > 500 else '')) if response.text else ''

        if status == 401:
            # Tratar como erro de token e fazer refresh abaixo
            raise requests.exceptions.HTTPError(response=response)

        if 200 <= status < 300:
            if isinstance(data, dict) and data.get("mensagem") == "Time Escalado! Boa Sorte!":
                printdbg("Escalação bem-sucedida:", data["mensagem"]) 
                return True
            else:
                # 2xx mas conteúdo inesperado
                printdbg("Erro na escalação:", (data.get("mensagem") if isinstance(data, dict) else None) or "Resposta inesperada")
                if isinstance(data, dict):
                    if "erros" in data:
                        printdbg("Detalhes de erro:", data["erros"])
                    printdbg(f"Resposta API (resumo): {data}")
                else:
                    printdbg(f"Resposta não-JSON (preview): {body_preview}")
                printdbg(f"HTTP {status}")
                printdbg(f"Payload enviado: {time_para_escalacao}")
                return False
        else:
            # 4xx/5xx
            printdbg(f"Falha HTTP ao escalar: {status}")
            if isinstance(data, dict):
                # Mensagens de erro apenas em debug
                printdbg("Erro na escalação:", data.get("mensagem", ""))
                if "erros" in data:
                    printdbg("Detalhes de erro:", data["erros"])
                printdbg(f"Resposta JSON (resumo): {data}")
            else:
                # Não-JSON: apenas em debug
                printdbg(f"Erro HTTP {status} corpo (preview): {body_preview}")
            printdbg(f"Payload enviado: {time_para_escalacao}")
            if status == 409:
                printdbg("Erro 409: Conflito na escalação. Possíveis causas: time já escalado, rodada fechada ou escalação inválida.")
            return False
    except requests.exceptions.RequestException as e:
        if hasattr(e.response, 'status_code') and e.response.status_code == 401:
            printdbg(f"Token expirado para {env_key}. Tentando atualizar o token...")
            new_token = refresh_access_token(token, env_key)
            if new_token:
                headers["Authorization"] = f"Bearer {new_token}"
                try:
                    response = requests.post(API_URL_SALVAR_TIME, json=time_para_escalacao, headers=headers)
                    status = response.status_code
                    try:
                        data = response.json()
                    except Exception:
                        data = None
                    body_preview = (response.text[:500] + ('...' if len(response.text) > 500 else '')) if response.text else ''
                    if 200 <= status < 300 and isinstance(data, dict) and data.get("mensagem") == "Time Escalado! Boa Sorte!":
                        printdbg("Escalação bem-sucedida:", data["mensagem"]) 
                        return True
                    else:
                        printdbg("Erro na escalação após refresh:", (data.get("mensagem") if isinstance(data, dict) else None) or "Resposta inesperada")
                        printdbg(f"HTTP {status}")
                        if isinstance(data, dict):
                            if "erros" in data:
                                printdbg("Detalhes de erro:", data["erros"]) 
                            printdbg(f"Resposta API (resumo): {data}")
                        else:
                            printdbg(f"Erro HTTP {status} corpo (preview): {body_preview}")
                        printdbg(f"Payload enviado: {time_para_escalacao}")
                        return False
                except requests.exceptions.RequestException as e:
                    printdbg(f"Falha pós-refresh em salvar_time ({env_key}): {e}")
                    return False
            else:
                printdbg(f"Falha ao atualizar o token para {env_key}.")
                return False
        else:
            printdbg(f"Erro ao escalar ({env_key}): {e}")
            if hasattr(e, 'response') and e.response is not None:
                printdbg(f"HTTP {e.response.status_code} corpo: {(e.response.text[:500] + '...') if e.response.text and len(e.response.text) > 500 else e.response.text}")
            printdbg(f"Payload enviado: {time_para_escalacao}")
            return False