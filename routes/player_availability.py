"""API isolada para regras de disponibilidade de jogadores."""

from __future__ import annotations

from functools import wraps
from typing import Any, Dict, Optional, Tuple

from flask import Blueprint, jsonify, request, session

from models.player_availability import (
    create_player_availability_table,
    delete_player_availability,
    list_player_availability,
    upsert_player_availability,
    RULE_LOCK_IN,
    normalize_rule,
)
from utils.utilidades import get_temporada_atual


player_availability_bp = Blueprint(
    "player_availability",
    __name__,
    url_prefix="/api/player-availability",
)


def get_db_connection():
    """Importa a conexão sob demanda para manter este blueprint isolado."""

    from database import get_db_connection as _get_db_connection

    return _get_db_connection()


def close_db_connection(conn):
    """Fecha a conexão sob demanda (também facilita testes do blueprint)."""

    from database import close_db_connection as _close_db_connection

    return _close_db_connection(conn)


def _login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            return jsonify({"error": "Autenticação necessária"}), 401
        return view(*args, **kwargs)

    return wrapped


def _payload() -> Dict[str, Any]:
    body = request.get_json(silent=True)
    if body is None:
        body = request.form.to_dict()
    if not isinstance(body, dict):
        raise ValueError("o corpo deve ser um objeto JSON")
    return body


def _value(data: Dict[str, Any], *names: str) -> Any:
    for name in names:
        if name in data:
            return data[name]
    return None


def _context(data: Dict[str, Any], *, athlete_from_path: Optional[int] = None) -> Tuple[Any, ...]:
    return (
        _value(data, "team_id", "time_id"),
        _value(data, "season", "temporada"),
        _value(data, "round_number", "round", "rodada"),
        athlete_from_path
        if athlete_from_path is not None
        else _value(data, "athlete_id", "atleta_id"),
    )


def _team_belongs_to_user(conn, team_id: int, user_id: int) -> bool:
    """Evita que a regra de um usuário seja gravada em time de outro usuário."""

    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT 1 FROM acw_teams WHERE id = %s AND user_id = %s LIMIT 1",
            (team_id, user_id),
        )
        return cursor.fetchone() is not None
    finally:
        cursor.close()


@player_availability_bp.route("/page", methods=["GET"])
@_login_required
def player_availability_page():
    """Página para marcar jogadores poupados ou cravados na rodada."""

    from flask import render_template

    return render_template("player_availability.html")


@player_availability_bp.route("/candidates", methods=["GET"])
@_login_required
def player_availability_candidates():
    """Lista atletas/status da temporada para a tela de regras."""

    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Banco de dados indisponível"}), 503
    try:
        season = _value(request.args, "season", "temporada") or get_temporada_atual()
        round_number = _value(request.args, "round_number", "round", "rodada")
        position_id = _value(request.args, "position_id", "posicao_id")
        team_id = _value(request.args, "team_id", "time_id") or session.get("selected_team_id")
        if not team_id:
            return jsonify({"error": "Nenhum time selecionado"}), 400

        season = int(season)
        team_id = int(team_id)
        if not _team_belongs_to_user(conn, team_id, int(session["user_id"])):
            return jsonify({"error": "Time não encontrado ou não pertence ao usuário"}), 404

        if round_number in (None, ""):
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "SELECT COALESCE(MAX(rodada_id), 1) FROM acf_partidas WHERE temporada = %s",
                    (season,),
                )
                round_number = cursor.fetchone()[0] or 1
            finally:
                cursor.close()
        round_number = int(round_number)

        create_player_availability_table(conn)
        rules = list_player_availability(
            conn,
            user_id=session["user_id"],
            team_id=team_id,
            season=season,
            round_number=round_number,
        )
        rules_by_athlete = {int(item["athlete_id"]): item["rule"] for item in rules}

        cursor = conn.cursor()
        params = [season]
        position_clause = ""
        if position_id not in (None, ""):
            position_clause = " AND a.posicao_id = %s"
            params.append(int(position_id))
        cursor.execute(
            f"""
            SELECT a.atleta_id, a.apelido, a.nome, a.clube_id, a.posicao_id,
                   a.status_id, COALESCE(c.nome, 'Clube não informado'),
                   COALESCE(c.abreviacao, ''), COALESCE(a.foto_custom, a.foto)
            FROM acf_atletas a
            LEFT JOIN acf_clubes c ON c.id = a.clube_id
            WHERE a.temporada = %s{position_clause}
            ORDER BY a.posicao_id, a.apelido NULLS LAST, a.nome
            """,
            params,
        )
        items = []
        for row in cursor.fetchall():
            athlete_id = int(row[0])
            items.append(
                {
                    "atleta_id": athlete_id,
                    "apelido": row[1] or row[2] or f"Atleta {athlete_id}",
                    "nome": row[2] or row[1] or "",
                    "clube_id": row[3],
                    "posicao_id": row[4],
                    "status_id": row[5],
                    "clube_nome": row[6],
                    "clube_abrev": row[7],
                    "status_nome": {
                        2: "Dúvida",
                        3: "Improvável",
                        5: "Suspenso",
                        6: "Nulo",
                        7: "Provável",
                    }.get(int(row[5] or 0), "Desconhecido"),
                    "foto": row[8] or "",
                    "rule": rules_by_athlete.get(athlete_id),
                }
            )
        return jsonify(
            {
                "season": season,
                "round_number": round_number,
                "team_id": team_id,
                "items": items,
            }
        )
    except (TypeError, ValueError) as exc:
        return jsonify({"error": f"Filtro inválido: {exc}"}), 400
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    finally:
        close_db_connection(conn)


def _ensure_context(data: Dict[str, Any], *, athlete_from_path: Optional[int] = None):
    team_id, season, round_number, athlete_id = _context(
        data, athlete_from_path=athlete_from_path
    )
    if None in (team_id, season, round_number, athlete_id):
        raise ValueError("team_id, temporada, rodada e atleta_id são obrigatórios")
    return team_id, season, round_number, athlete_id


@player_availability_bp.route("", methods=["GET"])
@player_availability_bp.route("/", methods=["GET"])
@_login_required
def get_player_availability():
    """Lista regras; todos os filtros, exceto user_id, são opcionais."""

    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Banco de dados indisponível"}), 503
    try:
        create_player_availability_table(conn)
        rules = list_player_availability(
            conn,
            user_id=session["user_id"],
            team_id=_value(request.args, "team_id", "time_id"),
            season=_value(request.args, "season", "temporada"),
            round_number=_value(request.args, "round_number", "round", "rodada"),
            athlete_id=_value(request.args, "athlete_id", "atleta_id"),
        )
        return jsonify({"items": rules, "rules": rules, "count": len(rules)})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    finally:
        close_db_connection(conn)


@player_availability_bp.route("", methods=["POST"])
@player_availability_bp.route("/", methods=["POST"])
@_login_required
def save_player_availability():
    """Cria ou atualiza uma regra para o atleta/contexto informado."""

    conn = None
    try:
        data = _payload()
        team_id, season, round_number, athlete_id = _ensure_context(data)
        rule = _value(data, "rule", "status", "acao", "action")
        if rule is None:
            raise ValueError("rule é obrigatório e deve ser 'poupar' ou 'cravado'")

        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Banco de dados indisponível"}), 503
        create_player_availability_table(conn)
        if not _team_belongs_to_user(conn, int(team_id), int(session["user_id"])):
            return jsonify({"error": "Time não encontrado ou não pertence ao usuário"}), 404

        # Status nulo representa um atleta que não joga na rodada. A regra
        # "cravado" nunca pode transformá-lo artificialmente em disponível.
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT status_id FROM acf_atletas
                WHERE atleta_id = %s AND temporada = %s
                LIMIT 1
                """,
                (int(athlete_id), int(season)),
            )
            athlete_row = cursor.fetchone()
        finally:
            cursor.close()
        if not athlete_row:
            return jsonify({"error": "Atleta não encontrado na temporada informada"}), 404
        if normalize_rule(rule) == RULE_LOCK_IN and int(athlete_row[0] or 0) == 6:
            return jsonify({"error": "Jogador nulo não pode ser cravado como titular"}), 400

        saved = upsert_player_availability(
            conn,
            user_id=session["user_id"],
            team_id=team_id,
            season=season,
            round_number=round_number,
            athlete_id=athlete_id,
            rule=rule,
        )
        return jsonify({"item": saved, "rule": saved}), 200
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    finally:
        if conn:
            close_db_connection(conn)


@player_availability_bp.route("/<int:athlete_id>", methods=["DELETE"])
@player_availability_bp.route("", methods=["DELETE"])
@player_availability_bp.route("/", methods=["DELETE"])
@_login_required
def remove_player_availability(athlete_id: Optional[int] = None):
    """Remove uma regra exata; o atleta pode vir no path ou no JSON/query."""

    conn = None
    try:
        data = _payload() if request.data else {}
        if athlete_id is None:
            athlete_id = _value(data, "athlete_id", "atleta_id") or _value(
                request.args, "athlete_id", "atleta_id"
            )
        merged = dict(data)
        for key in ("team_id", "time_id", "season", "temporada", "round_number", "round", "rodada"):
            if key not in merged and request.args.get(key) is not None:
                merged[key] = request.args.get(key)
        merged["athlete_id"] = athlete_id
        team_id, season, round_number, athlete_id = _ensure_context(merged)

        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Banco de dados indisponível"}), 503
        create_player_availability_table(conn)
        if not _team_belongs_to_user(conn, int(team_id), int(session["user_id"])):
            return jsonify({"error": "Time não encontrado ou não pertence ao usuário"}), 404

        removed = delete_player_availability(
            conn,
            user_id=session["user_id"],
            team_id=team_id,
            season=season,
            round_number=round_number,
            athlete_id=athlete_id,
        )
        if not removed:
            return jsonify({"error": "Regra não encontrada"}), 404
        return jsonify({"success": True, "removed": True})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    finally:
        if conn:
            close_db_connection(conn)
