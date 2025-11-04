import requests
import json
from functools import lru_cache

# Cache para armazenar os dados dos clubes
_clubes_cache = None

@lru_cache(maxsize=1)
def get_clubes_data():
    """
    Busca dados dos clubes da API do Cartola
    """
    global _clubes_cache
    
    if _clubes_cache is None:
        try:
            response = requests.get('https://api.cartola.globo.com/clubes', timeout=10)
            if response.status_code == 200:
                _clubes_cache = response.json()
            else:
                print(f"Erro ao buscar dados dos clubes: {response.status_code}")
                _clubes_cache = {}
        except Exception as e:
            print(f"Erro ao conectar com API dos clubes: {e}")
            _clubes_cache = {}
    
    return _clubes_cache

def get_team_shield(clube_id, size='30x30'):
    """
    Retorna o URL do escudo do time
    
    Args:
        clube_id: ID do clube
        size: Tamanho do escudo ('30x30', '45x45', '60x60')
    
    Returns:
        URL do escudo ou None se não encontrado
    """
    clubes = get_clubes_data()
    
    if str(clube_id) in clubes:
        clube = clubes[str(clube_id)]
        return clube.get('escudos', {}).get(size)
    
    return None

def get_team_info(clube_id):
    """
    Retorna informações completas do time
    
    Args:
        clube_id: ID do clube
    
    Returns:
        Dict com informações do clube ou None se não encontrado
    """
    clubes = get_clubes_data()
    
    if str(clube_id) in clubes:
        return clubes[str(clube_id)]
    
    return None

def clear_cache():
    """
    Limpa o cache dos clubes (útil para testes)
    """
    global _clubes_cache
    _clubes_cache = None
    get_clubes_data.cache_clear()
