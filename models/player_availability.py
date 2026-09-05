"""Regras de disponibilidade de jogadores por usuário, time e rodada.

Este módulo não conhece a aplicação Flask. Ele concentra a tabela, as operações
de persistência e os helpers que podem ser usados pelos cálculos e pela
escalação ideal.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import psycopg2


PLAYER_AVAILABILITY_TABLE = "acw_player_availability"
RULE_SAVE = "poupar"
RULE_LOCK_IN = "cravado"
VALID_RULES = frozenset((RULE_SAVE, RULE_LOCK_IN))


def create_player_availability_table(conn: psycopg2.extensions.connection) -> None:
    """Cria a tabela nova e seus índices sem alterar tabelas existentes.

    A função é segura para ser chamada mais de uma vez. A FK de ``team_id``
    garante que a regra só aponte para um time existente; ``athlete_id`` não
    possui FK porque a fonte de jogadores do Cartola não é uma tabela local
    estável neste projeto.
    """

    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS acw_player_availability (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                team_id INTEGER NOT NULL,
                season INTEGER NOT NULL,
                round_number INTEGER NOT NULL,
                athlete_id INTEGER NOT NULL,
                rule VARCHAR(20) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES acw_users(id) ON DELETE CASCADE,
                FOREIGN KEY (team_id) REFERENCES acw_teams(id) ON DELETE CASCADE,
                CONSTRAINT ck_acw_player_availability_rule
                    CHECK (rule IN ('poupar', 'cravado')),
                CONSTRAINT ck_acw_player_availability_context
                    CHECK (season > 0 AND round_number > 0 AND athlete_id > 0),
                CONSTRAINT uq_acw_player_availability_context
                    UNIQUE (user_id, team_id, season, round_number, athlete_id)
            )
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_acw_player_availability_context
            ON acw_player_availability (user_id, team_id, season, round_number)
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_acw_player_availability_athlete
            ON acw_player_availability (athlete_id)
            """
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()


# Nome curto para inicializadores que preferem uma função explícita de garantia.
ensure_player_availability_table = create_player_availability_table


def normalize_rule(rule: Any) -> str:
    """Normaliza os nomes aceitos pela API e rejeita estados ambíguos."""

    if not isinstance(rule, str):
        raise ValueError("rule deve ser 'poupar' ou 'cravado'")

    normalized = rule.strip().lower()
    aliases = {
        "poupar": RULE_SAVE,
        "save": RULE_SAVE,
        "cravado": RULE_LOCK_IN,
        "cravar": RULE_LOCK_IN,
        "cravar_que_joga": RULE_LOCK_IN,
        "cravar que joga": RULE_LOCK_IN,
        "lock_in": RULE_LOCK_IN,
    }
    normalized = aliases.get(normalized, normalized)
    if normalized not in VALID_RULES:
        raise ValueError("rule deve ser 'poupar' ou 'cravado'")
    return normalized


def _positive_int(value: Any, field_name: str) -> int:
    # bool é int em Python, mas não é um identificador/contexto válido.
    if isinstance(value, bool):
        raise ValueError(f"{field_name} deve ser um inteiro positivo")
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} deve ser um inteiro positivo")
    if parsed <= 0:
        raise ValueError(f"{field_name} deve ser um inteiro positivo")
    return parsed


def validate_context(
    user_id: Any,
    team_id: Any,
    season: Any,
    round_number: Any,
    athlete_id: Any,
) -> Tuple[int, int, int, int, int]:
    """Valida e converte os cinco identificadores do contexto da regra."""

    return (
        _positive_int(user_id, "user_id"),
        _positive_int(team_id, "team_id"),
        _positive_int(season, "season"),
        _positive_int(round_number, "round_number"),
        _positive_int(athlete_id, "athlete_id"),
    )


def build_player_availability_filters(
    *,
    user_id: Optional[int] = None,
    team_id: Optional[int] = None,
    season: Optional[int] = None,
    round_number: Optional[int] = None,
    athlete_id: Optional[int] = None,
    table_alias: Optional[str] = None,
) -> Tuple[str, Tuple[int, ...]]:
    """Monta filtros SQL parametrizados para atleta e contexto da rodada.

    Retorna ``(where_sql, params)``. O SQL nunca contém valores fornecidos pelo
    cliente; ``table_alias`` só aceita um identificador simples para permitir
    reutilização em queries com JOIN.
    """

    if table_alias is not None:
        if not table_alias.replace("_", "").isalnum() or table_alias[0].isdigit():
            raise ValueError("table_alias inválido")
        prefix = f"{table_alias}."
    else:
        prefix = ""

    fields = (
        ("user_id", user_id),
        ("team_id", team_id),
        ("season", season),
        ("round_number", round_number),
        ("athlete_id", athlete_id),
    )
    clauses: List[str] = []
    params: List[int] = []
    for field_name, value in fields:
        if value is not None:
            clauses.append(f"{prefix}{field_name} = %s")
            params.append(_positive_int(value, field_name))

    return (" AND ".join(clauses) if clauses else "TRUE", tuple(params))


def _row_to_dict(row: Sequence[Any]) -> Dict[str, Any]:
    return {
        "id": row[0],
        "user_id": row[1],
        "team_id": row[2],
        "season": row[3],
        "round_number": row[4],
        "athlete_id": row[5],
        "rule": row[6],
        # Aliases facilitam o consumo por clientes em português sem duplicar
        # a coluna persistida.
        "temporada": row[3],
        "rodada": row[4],
        "atleta_id": row[5],
        "status": row[6],
        "created_at": row[7],
        "updated_at": row[8],
    }


_SELECT_COLUMNS = """
    id, user_id, team_id, season, round_number, athlete_id, rule,
    created_at, updated_at
"""


def list_player_availability(
    conn: psycopg2.extensions.connection,
    *,
    user_id: int,
    team_id: Optional[int] = None,
    season: Optional[int] = None,
    round_number: Optional[int] = None,
    athlete_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Lista regras do usuário, opcionalmente filtradas por contexto/atleta."""

    user_id = _positive_int(user_id, "user_id")
    where_sql, params = build_player_availability_filters(
        user_id=user_id,
        team_id=team_id,
        season=season,
        round_number=round_number,
        athlete_id=athlete_id,
    )
    cursor = conn.cursor()
    cursor.execute(
        f"""
        SELECT {_SELECT_COLUMNS}
        FROM acw_player_availability
        WHERE {where_sql}
        ORDER BY season DESC, round_number DESC, athlete_id ASC
        """,
        params,
    )
    try:
        return [_row_to_dict(row) for row in cursor.fetchall()]
    finally:
        cursor.close()


def upsert_player_availability(
    conn: psycopg2.extensions.connection,
    *,
    user_id: int,
    team_id: int,
    season: int,
    round_number: int,
    athlete_id: int,
    rule: str,
) -> Dict[str, Any]:
    """Cria ou substitui a regra do mesmo atleta no mesmo contexto."""

    user_id, team_id, season, round_number, athlete_id = validate_context(
        user_id, team_id, season, round_number, athlete_id
    )
    rule = normalize_rule(rule)
    cursor = conn.cursor()
    try:
        cursor.execute(
            f"""
            INSERT INTO {PLAYER_AVAILABILITY_TABLE}
                (user_id, team_id, season, round_number, athlete_id, rule)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (user_id, team_id, season, round_number, athlete_id)
            DO UPDATE SET rule = EXCLUDED.rule, updated_at = CURRENT_TIMESTAMP
            RETURNING {_SELECT_COLUMNS}
            """,
            (user_id, team_id, season, round_number, athlete_id, rule),
        )
        row = cursor.fetchone()
        conn.commit()
        return _row_to_dict(row)
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()


def delete_player_availability(
    conn: psycopg2.extensions.connection,
    *,
    user_id: int,
    team_id: int,
    season: int,
    round_number: int,
    athlete_id: int,
) -> bool:
    """Remove uma regra exata e retorna se algum registro foi removido."""

    user_id, team_id, season, round_number, athlete_id = validate_context(
        user_id, team_id, season, round_number, athlete_id
    )
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            DELETE FROM acw_player_availability
            WHERE user_id = %s AND team_id = %s AND season = %s
              AND round_number = %s AND athlete_id = %s
            """,
            (user_id, team_id, season, round_number, athlete_id),
        )
        removed = cursor.rowcount > 0
        conn.commit()
        return removed
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()


def resolve_availability_rule(
    rule: Optional[str],
    source_available: Optional[bool] = None,
) -> Dict[str, Any]:
    """Resolve a regra sem alterar uma disponibilidade de origem nula.

    ``poupar`` sempre exclui o atleta dos cálculos/escalão. ``cravado`` permite
    incluí-lo, mas ``source_available`` permanece exatamente como veio: em
    particular, ``None`` continua ``None`` e nunca vira ``True``.
    """

    normalized = normalize_rule(rule) if rule is not None else None
    if normalized == RULE_SAVE:
        return {
            "rule": normalized,
            "excluded_from_calculations": True,
            "include_in_lineup": False,
            "available": source_available,
        }
    if normalized == RULE_LOCK_IN:
        return {
            "rule": normalized,
            "excluded_from_calculations": False,
            "include_in_lineup": True,
            "available": source_available,
        }
    return {
        "rule": None,
        "excluded_from_calculations": False,
        "include_in_lineup": source_available is True,
        "available": source_available,
    }


def filter_players_for_availability(
    players: Iterable[Mapping[str, Any]],
    rules_by_athlete: Mapping[int, Any],
) -> List[Mapping[str, Any]]:
    """Remove da coleção os atletas marcados como ``poupar``.

    Este helper não injeta ``is_playing=True`` em nenhum item. Assim, uma
    disponibilidade nula ou negativa da fonte não é sobrescrita por ``cravado``.
    """

    filtered: List[Mapping[str, Any]] = []
    for player in players:
        athlete_id = player.get("athlete_id", player.get("atleta_id"))
        # Um item sem atleta nunca pode receber uma regra de inclusão.
        if athlete_id is None:
            filtered.append(player)
            continue
        rule_value = rules_by_athlete.get(athlete_id)
        normalized = normalize_rule(rule_value) if rule_value is not None else None
        if normalized != RULE_SAVE:
            filtered.append(player)
    return filtered
