from __future__ import annotations

import json
from typing import Dict, Any
from database import get_db_connection, close_db_connection


def load_weights_from_db(posicao: str, user_id: int = None, team_id: int = None) -> Dict[str, Any]:
    """Carrega o JSON de weights da tabela acw_posicao_weights para a posicao fornecida.
    Retorna dicionário vazio se não houver registro.
    Se user_id e team_id forem fornecidos, busca os pesos específicos do time.
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        if user_id and team_id:
            cur.execute('''
                SELECT weights_json FROM acw_posicao_weights 
                WHERE posicao = %s AND user_id = %s AND team_id = %s
            ''', (posicao, user_id, team_id))
        else:
            cur.execute('SELECT weights_json FROM acw_posicao_weights WHERE posicao = %s LIMIT 1', (posicao,))
        row = cur.fetchone()
        close_db_connection(conn)
        if not row or not row[0]:
            return {}
        weights_data = row[0]
        # Se já for dict (JSONB), retorna direto; se for string, faz parse
        if isinstance(weights_data, dict):
            return weights_data
        try:
            return json.loads(weights_data) if isinstance(weights_data, str) else {}
        except Exception:
            return {}
    except Exception:
        # Se houver erro (tabela não existe, etc.), retorna dicionário vazio
        return {}


def get_weight(posicao: str, key: str, default=None):
    weights = load_weights_from_db(posicao)
    return weights.get(key, default)
