"""Cruzamento de scouts por jogador, posição, rodada e adversário.

Este módulo é intencionalmente independente das rotas dos módulos de posição.
Ele usa somente as tabelas ACF já existentes e pode ser registrado no app com:

    from routes.scout_crossing import scout_crossing_bp
    app.register_blueprint(scout_crossing_bp)
"""

from collections import defaultdict
from functools import wraps

from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for
from dotenv import load_dotenv
from psycopg2.extras import RealDictCursor

load_dotenv()

from database import close_db_connection, get_db_connection
from utils.team_shields import get_team_shield
from utils.utilidades import get_temporada_atual


scout_crossing_bp = Blueprint("scout_crossing", __name__, url_prefix="/cruzamento-scouts")

POSITION_OPTIONS = (
    {"id": 1, "slug": "goleiro", "label": "Goleiro"},
    {"id": 2, "slug": "lateral", "label": "Lateral"},
    {"id": 3, "slug": "zagueiro", "label": "Zagueiro"},
    {"id": 4, "slug": "meia", "label": "Meia"},
    {"id": 5, "slug": "atacante", "label": "Atacante"},
    {"id": 6, "slug": "treinador", "label": "Treinador"},
)
POSITION_BY_ID = {item["id"]: item for item in POSITION_OPTIONS}

SCOUT_LABELS = {
    "a": "Assistências",
    "ca": "Cartões amarelos",
    "cv": "Cartões vermelhos",
    "de": "Defesas",
    "ds": "Desarmes",
    "fc": "Faltas cometidas",
    "fd": "Finalizações defendidas",
    "ff": "Finalizações para fora",
    "fs": "Faltas sofridas",
    "g": "Gols",
    "gs": "Gols sofridos",
    "i": "Impedimentos",
    "sg": "Saldo de gols",
}
POSITION_SCOUTS = {
    1: ("de", "gs", "sg", "ds"),
    2: ("ds", "fs", "ff", "a"),
    3: ("ds", "sg", "fs", "de"),
    4: ("fs", "a", "g", "ds"),
    5: ("g", "a", "ff", "fs"),
    6: (),
}
SCOUT_COLUMNS = tuple(SCOUT_LABELS)


def login_required(view):
    """Protege a página e as APIs sem depender do decorator do app.py."""

    @wraps(view)
    def decorated(*args, **kwargs):
        if not session.get("user_id"):
            if request.path.startswith(f"{scout_crossing_bp.url_prefix}/api/"):
                return jsonify({"error": "Autenticação necessária."}), 401
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return decorated


def _int_arg(name, default=None, minimum=None, maximum=None):
    value = request.args.get(name, default)
    if value in (None, ""):
        return default
    try:
        value = int(value)
    except (TypeError, ValueError):
        return default
    if minimum is not None and value < minimum:
        return default
    if maximum is not None and value > maximum:
        return default
    return value


def _json_number(value, digits=2):
    if value is None:
        return 0
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0
    return round(number, digits)


def _json_int(value):
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _position_id(value):
    value = _json_int(value)
    return value if value in POSITION_BY_ID else None


def _current_context(cursor):
    """Sempre trabalha com a temporada atual e a última rodada disponível."""
    temporada = get_temporada_atual()
    cursor.execute(
        """
        SELECT COALESCE(MAX(rodada_id), 1) AS rodada_atual
        FROM acf_partidas
        WHERE temporada = %s AND valida = TRUE
        """,
        (temporada,),
    )
    row = cursor.fetchone()
    rodada = _json_int(row["rodada_atual"] if hasattr(row, "keys") else row[0])
    return temporada, rodada


def _club_payload(clube_id, nome=None):
    clube_id = _json_int(clube_id)
    return {
        "id": clube_id,
        "nome": nome or "Clube não informado",
        "escudo": get_team_shield(clube_id, size="45x45") or "",
    }


def _team_options(cursor, temporada, rodada):
    cursor.execute(
        """
        SELECT DISTINCT c.id, c.nome, c.abreviacao
        FROM acf_partidas p
        JOIN acf_clubes c ON c.id IN (p.clube_casa_id, p.clube_visitante_id)
        WHERE p.temporada = %s AND p.rodada_id = %s AND p.valida = TRUE
        ORDER BY c.nome
        """,
        (temporada, rodada),
    )
    return [
        {
            **_club_payload(row["id"], row["nome"]),
            "abreviacao": row["abreviacao"] or row["nome"],
        }
        for row in cursor.fetchall()
    ]


def _match_options(cursor, clube_id, temporada, rodada):
    cursor.execute(
        """
        SELECT p.partida_id, p.clube_casa_id, p.clube_visitante_id,
               casa.nome AS casa_nome, visitante.nome AS visitante_nome,
               p.placar_oficial_mandante, p.placar_oficial_visitante,
               p.local, p.partida_data
        FROM acf_partidas p
        LEFT JOIN acf_clubes casa ON casa.id = p.clube_casa_id
        LEFT JOIN acf_clubes visitante ON visitante.id = p.clube_visitante_id
        WHERE p.temporada = %s AND p.rodada_id = %s
          AND p.valida = TRUE
          AND (%s IN (p.clube_casa_id, p.clube_visitante_id))
        ORDER BY p.partida_id
        """,
        (temporada, rodada, clube_id),
    )
    matches = []
    for row in cursor.fetchall():
        home = _club_payload(row["clube_casa_id"], row["casa_nome"])
        away = _club_payload(row["clube_visitante_id"], row["visitante_nome"])
        is_home = _json_int(clube_id) == home["id"]
        matches.append(
            {
                "id": _json_int(row["partida_id"]),
                "casa": home,
                "fora": away,
                "adversario": away if is_home else home,
                "mando": "casa" if is_home else "fora",
                "placar_casa": row["placar_oficial_mandante"],
                "placar_fora": row["placar_oficial_visitante"],
                "local": row["local"] or "",
            }
        )
    return matches


def _season_options(cursor):
    cursor.execute(
        """
        SELECT DISTINCT temporada
        FROM (
            SELECT temporada FROM acf_partidas WHERE temporada IS NOT NULL
            UNION ALL
            SELECT temporada FROM acf_pontuados WHERE temporada IS NOT NULL
        ) temporadas
        ORDER BY temporada DESC
        LIMIT 10
        """
    )
    return [_json_int(row["temporada"]) for row in cursor.fetchall()]


def _round_options(cursor, temporada):
    cursor.execute(
        """
        SELECT DISTINCT rodada_id
        FROM acf_partidas
        WHERE temporada = %s AND rodada_id IS NOT NULL
        ORDER BY rodada_id DESC
        """,
        (temporada,),
    )
    return [_json_int(row["rodada_id"]) for row in cursor.fetchall()]


def _player_options(cursor, temporada, posicao_id, clube_id=None):
    """Retorna atletas da temporada, com histórico como fallback para temporadas antigas."""
    cursor.execute(
        """
        WITH candidates AS (
            SELECT atleta_id, clube_id, posicao_id, apelido, nome, foto, rodada_id
            FROM acf_atletas_historico
            WHERE temporada = %s AND posicao_id = %s
              AND (%s IS NULL OR clube_id = %s)
            UNION ALL
            SELECT atleta_id, clube_id, posicao_id, apelido, nome,
                   COALESCE(foto_custom, foto) AS foto, rodada_id
            FROM acf_atletas
            WHERE temporada = %s AND posicao_id = %s
              AND (%s IS NULL OR clube_id = %s)
        ), latest AS (
            SELECT DISTINCT ON (atleta_id)
                atleta_id, clube_id, posicao_id, apelido, nome, foto
            FROM candidates
            ORDER BY atleta_id, rodada_id DESC NULLS LAST
        )
        SELECT l.atleta_id,
               COALESCE(l.apelido, l.nome, 'Atleta ' || l.atleta_id::text) AS nome,
               l.clube_id,
               COALESCE(c.nome, 'Clube não informado') AS clube_nome,
               l.foto
        FROM latest l
        LEFT JOIN acf_clubes c ON c.id = l.clube_id
        ORDER BY nome
        """,
        (temporada, posicao_id, clube_id, clube_id, temporada, posicao_id, clube_id, clube_id),
    )
    return [
        {
            "id": _json_int(row["atleta_id"]),
            "nome": row["nome"],
            "clube_id": _json_int(row["clube_id"]),
            "clube_nome": row["clube_nome"],
            "foto": row["foto"] or "",
        }
        for row in cursor.fetchall()
    ]


def _match_query(cursor, atleta_id, temporada, rodada_limite, adversario_id=None, rodada_exata=None):
    """Busca jogos do atleta já enriquecidos com mando e adversário."""
    rodada_clause = "p.rodada_id <= %s"
    params = [temporada, atleta_id, temporada, rodada_limite]
    if rodada_exata is not None:
        rodada_clause = "p.rodada_id = %s"
        params[-1] = rodada_exata

    opponent_clause = ""
    if adversario_id is not None:
        opponent_clause = """
          AND (
              (p.clube_id = partida.clube_casa_id AND partida.clube_visitante_id = %s)
              OR (p.clube_id = partida.clube_visitante_id AND partida.clube_casa_id = %s)
          )
        """
        params.extend([adversario_id, adversario_id])

    cursor.execute(
        f"""
        SELECT p.atleta_id, p.rodada_id, p.clube_id, p.posicao_id,
               p.pontuacao, p.entrou_em_campo, p.apelido, p.foto,
               p.scout_a, p.scout_ca, p.scout_cv, p.scout_de, p.scout_ds,
               p.scout_fc, p.scout_fd, p.scout_ff, p.scout_fs, p.scout_g,
               p.scout_gs, p.scout_i, p.scout_sg,
               partida.partida_id,
               partida.clube_casa_id, partida.clube_visitante_id,
               partida.placar_oficial_mandante, partida.placar_oficial_visitante,
               partida.local, partida.partida_data,
               casa.nome AS casa_nome, visitante.nome AS visitante_nome
        FROM acf_pontuados p
        LEFT JOIN acf_partidas partida
          ON partida.rodada_id = p.rodada_id
         AND partida.temporada = %s
         AND partida.valida = TRUE
         AND (p.clube_id = partida.clube_casa_id OR p.clube_id = partida.clube_visitante_id)
        LEFT JOIN acf_clubes casa ON casa.id = partida.clube_casa_id
        LEFT JOIN acf_clubes visitante ON visitante.id = partida.clube_visitante_id
        WHERE p.atleta_id = %s
          AND (p.temporada = %s OR p.temporada IS NULL)
          AND {rodada_clause}
          {opponent_clause}
        ORDER BY p.rodada_id DESC
        """,
        params,
    )
    return [_serialize_match(row) for row in cursor.fetchall()]


def _serialize_match(row):
    clube_id = _json_int(row["clube_id"])
    casa_id = _json_int(row["clube_casa_id"])
    visitante_id = _json_int(row["clube_visitante_id"])
    if clube_id and clube_id == casa_id:
        mando = "casa"
        adversario_id = visitante_id
        adversario_nome = row["visitante_nome"] or "Adversário não informado"
    elif clube_id and clube_id == visitante_id:
        mando = "fora"
        adversario_id = casa_id
        adversario_nome = row["casa_nome"] or "Adversário não informado"
    else:
        mando = "indefinido"
        adversario_id = 0
        adversario_nome = "Adversário não informado"

    scouts = {key: _json_int(row[f"scout_{key}"]) for key in SCOUT_COLUMNS}
    partida_data = row["partida_data"]
    if partida_data is not None and hasattr(partida_data, "isoformat"):
        partida_data = partida_data.isoformat()
    elif partida_data is not None:
        partida_data = str(partida_data)

    return {
        "atleta_id": _json_int(row["atleta_id"]),
        "posicao_id": _json_int(row["posicao_id"]),
        "rodada": _json_int(row["rodada_id"]),
        "pontuacao": _json_number(row["pontuacao"]),
        "entrou_em_campo": bool(row["entrou_em_campo"]),
        "clube_id": clube_id,
        "partida_id": _json_int(row["partida_id"]),
        "mando": mando,
        "mando_label": {"casa": "Casa", "fora": "Fora"}.get(mando, "Sem mando"),
        "adversario_id": adversario_id,
        "adversario_nome": adversario_nome,
        "adversario": _club_payload(adversario_id, adversario_nome),
        "casa_nome": row["casa_nome"] or "Casa",
        "visitante_nome": row["visitante_nome"] or "Visitante",
        "casa": _club_payload(casa_id, row["casa_nome"]),
        "fora": _club_payload(visitante_id, row["visitante_nome"]),
        "placar_casa": row["placar_oficial_mandante"],
        "placar_fora": row["placar_oficial_visitante"],
        "local": row["local"] or "",
        "partida_data": partida_data,
        "scouts": scouts,
    }


def _player_snapshot(cursor, atleta_id, temporada, posicao_id):
    cursor.execute(
        """
        WITH snapshots AS (
            SELECT atleta_id, clube_id, posicao_id, apelido, nome, foto, rodada_id
            FROM acf_atletas_historico
            WHERE atleta_id = %s AND temporada = %s AND posicao_id = %s
            UNION ALL
            SELECT atleta_id, clube_id, posicao_id, apelido, nome,
                   COALESCE(foto_custom, foto) AS foto, rodada_id
            FROM acf_atletas
            WHERE atleta_id = %s AND temporada = %s AND posicao_id = %s
            UNION ALL
            SELECT atleta_id, clube_id, posicao_id, apelido, NULL AS nome, foto, rodada_id
            FROM acf_pontuados
            WHERE atleta_id = %s AND (temporada = %s OR temporada IS NULL)
              AND posicao_id = %s
        )
        SELECT s.atleta_id, s.clube_id, s.posicao_id,
               COALESCE(s.apelido, s.nome, 'Atleta ' || s.atleta_id::text) AS nome,
               s.foto, c.nome AS clube_nome
        FROM snapshots s
        LEFT JOIN acf_clubes c ON c.id = s.clube_id
        ORDER BY (s.foto IS NOT NULL) DESC, s.rodada_id DESC NULLS LAST
        LIMIT 1
        """,
        (
            atleta_id,
            temporada,
            posicao_id,
            atleta_id,
            temporada,
            posicao_id,
            atleta_id,
            temporada,
            posicao_id,
        ),
    )
    row = cursor.fetchone()
    if not row:
        return None
    return {
        "id": _json_int(row["atleta_id"]),
        "nome": row["nome"],
        "clube_id": _json_int(row["clube_id"]),
        "clube_nome": row["clube_nome"] or "Clube não informado",
        "foto": row["foto"] or "",
        "posicao": POSITION_BY_ID.get(_json_int(row["posicao_id"]), {}).get("label", ""),
    }


def _position_scouts(cursor, posicao_id, temporada, rodada_limite):
    if not POSITION_SCOUTS.get(posicao_id):
        return []

    columns = ", ".join(
        f"AVG(COALESCE(p.scout_{key}, 0)) AS media_{key}, SUM(COALESCE(p.scout_{key}, 0)) AS total_{key}"
        for key in SCOUT_COLUMNS
    )
    cursor.execute(
        f"""
        SELECT COUNT(*) FILTER (WHERE p.entrou_em_campo = TRUE) AS jogos, {columns}
        FROM acf_pontuados p
        WHERE p.posicao_id = %s
          AND (p.temporada = %s OR p.temporada IS NULL)
          AND p.rodada_id <= %s
          AND p.entrou_em_campo = TRUE
        """,
        (posicao_id, temporada, rodada_limite),
    )
    row = cursor.fetchone()
    jogos = _json_int(row["jogos"] if row else 0)
    scouts = []
    for key in POSITION_SCOUTS[posicao_id]:
        media = _json_number(row[f"media_{key}"] if row else 0)
        total = _json_int(row[f"total_{key}"] if row else 0)
        scouts.append(
            {
                "codigo": key,
                "nome": SCOUT_LABELS[key],
                "media": media,
                "total": total,
                "jogos": jogos,
            }
        )
    return sorted(scouts, key=lambda item: (item["media"], item["total"]), reverse=True)


def _aggregate_matches(matches):
    valid_matches = [match for match in matches if match["entrou_em_campo"]]
    points = [match["pontuacao"] for match in valid_matches]

    opponents = defaultdict(lambda: {"jogos": 0, "pontos": []})
    mando = defaultdict(lambda: {"jogos": 0, "pontos": []})
    for match in valid_matches:
        if match["adversario_id"]:
            key = (match["adversario_id"], match["adversario_nome"])
            opponents[key]["jogos"] += 1
            opponents[key]["pontos"].append(match["pontuacao"])
        if match["mando"] in ("casa", "fora"):
            mando[match["mando"]]["jogos"] += 1
            mando[match["mando"]]["pontos"].append(match["pontuacao"])

    opponent_data = [
        {
            "id": key[0],
            "nome": key[1],
            "jogos": value["jogos"],
            "media": _json_number(sum(value["pontos"]) / value["jogos"]),
        }
        for key, value in opponents.items()
    ]
    opponent_data.sort(key=lambda item: (item["jogos"], item["media"]), reverse=True)

    mando_data = []
    for key, label in (("casa", "Casa"), ("fora", "Fora")):
        value = mando.get(key, {"jogos": 0, "pontos": []})
        mando_data.append(
            {
                "tipo": key,
                "label": label,
                "jogos": value["jogos"],
                "media": _json_number(sum(value["pontos"]) / value["jogos"])
                if value["jogos"]
                else 0,
            }
        )

    return {
        "jogos": len(valid_matches),
        "media": _json_number(sum(points) / len(points)) if points else 0,
        "maior_pontuacao": _json_number(max(points)) if points else 0,
        "menor_pontuacao": _json_number(min(points)) if points else 0,
        "adversarios": opponent_data,
        "mando": mando_data,
    }


def _ceded_scouts(cursor, partida_id, clube_id, posicao_id, temporada):
    """Scouts produzidos pelo time do atleta contra o adversário no jogo selecionado.

    Na prática, esse é o retrato do que o adversário cedeu à posição analisada
    naquela partida, sem misturar rodadas ou confrontos anteriores.
    """
    if not partida_id or not clube_id or not posicao_id or not POSITION_SCOUTS.get(posicao_id):
        return {"jogos": 0, "pontuacao": 0, "scouts": []}

    columns = ", ".join(
        f"SUM(COALESCE(p.scout_{key}, 0)) AS total_{key}" for key in POSITION_SCOUTS[posicao_id]
    )
    cursor.execute(
        f"""
        SELECT COUNT(*) FILTER (WHERE p.entrou_em_campo = TRUE) AS jogos,
               COALESCE(SUM(CASE WHEN p.entrou_em_campo = TRUE THEN p.pontuacao ELSE 0 END), 0) AS pontuacao,
               {columns}
        FROM acf_pontuados p
        JOIN acf_partidas partida
          ON partida.partida_id = %s
         AND partida.temporada = %s
         AND partida.rodada_id = p.rodada_id
         AND partida.valida = TRUE
        WHERE p.temporada = %s
          AND p.clube_id = %s
          AND p.posicao_id = %s
          AND p.entrou_em_campo = TRUE
        """,
        (partida_id, temporada, temporada, clube_id, posicao_id),
    )
    row = cursor.fetchone()
    return {
        "jogos": _json_int(row["jogos"] if row else 0),
        "pontuacao": _json_number(row["pontuacao"] if row else 0),
        "scouts": [
            {
                "codigo": key,
                "nome": SCOUT_LABELS[key],
                "total": _json_int(row[f"total_{key}"] if row else 0),
            }
            for key in POSITION_SCOUTS[posicao_id]
        ],
    }


def _attach_conceded_scouts(cursor, matches, posicao_id, temporada):
    """Enriquece cada jogo com os scouts cedidos pelo adversário.

    O recorte usa os jogadores da mesma posição que enfrentaram aquele
    adversário no mesmo campeonato e rodada. Assim o modal mostra a
    referência do confronto sem alterar os cálculos ou os dados históricos.
    """
    main_scouts = POSITION_SCOUTS.get(posicao_id, ())
    if not main_scouts:
        return matches

    for match in matches:
        opponent_id = match.get("adversario_id")
        club_id = match.get("clube_id")
        round_id = match.get("rodada")
        if not opponent_id or not club_id or not round_id:
            match["cedidos_adversario"] = {"jogos": 0, "scouts": {}}
            continue

        select_columns = ", ".join(
            f"AVG(COALESCE(p.scout_{key}, 0)) AS {key}" for key in main_scouts
        )
        cursor.execute(
            f"""
            SELECT COUNT(*) AS jogos, {select_columns}
            FROM acf_pontuados p
            WHERE p.clube_id = %s
              AND p.posicao_id = %s
              AND p.rodada_id = %s
              AND (p.temporada = %s OR p.temporada IS NULL)
              AND p.entrou_em_campo = TRUE
              AND EXISTS (
                  SELECT 1
                  FROM acf_partidas partida
                  WHERE partida.temporada = %s
                    AND partida.rodada_id = p.rodada_id
                    AND partida.valida = TRUE
                    AND (
                        (partida.clube_casa_id = %s AND partida.clube_visitante_id = %s)
                        OR (partida.clube_casa_id = %s AND partida.clube_visitante_id = %s)
                    )
              )
            """,
            (opponent_id, posicao_id, round_id, temporada, temporada, club_id, opponent_id, opponent_id, club_id),
        )
        row = cursor.fetchone()
        match["cedidos_adversario"] = {
            "adversario_id": opponent_id,
            "adversario_nome": match.get("adversario_nome"),
            "jogos": _json_int(row["jogos"] if row else 0),
            "scouts": {
                key: _json_number(row[key] if row else 0) for key in main_scouts
            },
        }
    return matches


def _api_error(message, status=400):
    return jsonify({"error": message}), status


@scout_crossing_bp.route("/")
@login_required
def index():
    conn = get_db_connection()
    if not conn:
        return render_template(
            "scout_crossing.html",
            current_season=get_temporada_atual(),
            current_round=1,
            team_options=[],
            position_options=POSITION_OPTIONS,
            selected_position=5,
            selected_player=None,
            database_error="Não foi possível conectar ao banco de dados.",
        ), 503

    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        current_season, current_round = _current_context(cursor)
        selected_position = _position_id(request.args.get("posicao_id")) or 5
        selected_player = _int_arg("atleta_id", None, 1)
        return render_template(
            "scout_crossing.html",
            current_season=current_season,
            current_round=current_round,
            team_options=_team_options(cursor, current_season, current_round),
            selected_position=selected_position,
            selected_player=selected_player,
            position_options=POSITION_OPTIONS,
            database_error=None,
        )
    except Exception as exc:
        print(f"[SCOUT CROSSING] Erro ao renderizar página: {exc}")
        return render_template(
            "scout_crossing.html",
            current_season=get_temporada_atual(),
            current_round=1,
            team_options=[],
            selected_position=5,
            selected_player=None,
            position_options=POSITION_OPTIONS,
            database_error="Não foi possível carregar os filtros.",
        ), 500
    finally:
        close_db_connection(conn)


@scout_crossing_bp.route("/api/opcoes")
@login_required
def options():
    clube_id = _int_arg("clube_id", None, 1)
    posicao_id = _position_id(request.args.get("posicao_id"))

    conn = get_db_connection()
    if not conn:
        return _api_error("Banco de dados indisponível.", 503)
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        temporada, rodada = _current_context(cursor)
        teams = _team_options(cursor, temporada, rodada)
        if clube_id and clube_id not in {team["id"] for team in teams}:
            clube_id = None
        players = _player_options(cursor, temporada, posicao_id, clube_id) if posicao_id else []
        atleta_id = _int_arg("atleta_id", None, 1)
        matches = _match_options(cursor, clube_id, temporada, rodada) if clube_id else []
        return jsonify(
            {
                "temporada": temporada,
                "rodada": rodada,
                "times": teams,
                "jogadores": players,
                "confrontos": matches,
            }
        )
    except Exception as exc:
        print(f"[SCOUT CROSSING] Erro ao carregar opções: {exc}")
        return _api_error("Não foi possível carregar as opções.", 500)
    finally:
        close_db_connection(conn)


@scout_crossing_bp.route("/api/contexto")
@login_required
def context():
    """Retorna temporada/rodada padrão para abrir o cruzamento num modal."""

    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Banco de dados indisponível."}), 503
    try:
        cursor = conn.cursor()
        temporada, rodada = _current_context(cursor)
        return jsonify({"temporada": temporada, "rodada": rodada})
    finally:
        close_db_connection(conn)


@scout_crossing_bp.route("/api/cruzar")
@login_required
def crossing():
    atleta_id = _int_arg("atleta_id", None, 1)
    posicao_id = _position_id(request.args.get("posicao_id"))
    adversario_id = _int_arg("adversario_id", None, 1)
    if not atleta_id or not posicao_id:
        return _api_error("Jogador e posição são obrigatórios.")

    conn = get_db_connection()
    if not conn:
        return _api_error("Banco de dados indisponível.", 503)
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        temporada, rodada = _current_context(cursor)
        player = _player_snapshot(cursor, atleta_id, temporada, posicao_id)
        if not player:
            return _api_error("Jogador não encontrado para a temporada e posição informadas.", 404)

        matches = _match_query(
            cursor,
            atleta_id,
            temporada,
            rodada,
            adversario_id=adversario_id,
            rodada_exata=rodada if adversario_id else None,
        )
        _attach_conceded_scouts(cursor, matches, posicao_id, temporada)
        summary = _aggregate_matches(matches)
        recent = matches[:8]
        confronto = matches[0] if adversario_id and matches else None
        return jsonify(
            {
                "filtros": {
                    "atleta_id": atleta_id,
                    "posicao_id": posicao_id,
                    "temporada": temporada,
                    "rodada": rodada,
                    "adversario_id": adversario_id,
                },
                "jogador": player,
                "resumo": summary,
                "ultimas_pontuacoes": recent,
                "scouts_da_posicao": _position_scouts(cursor, posicao_id, temporada, rodada),
                "confronto": confronto,
                "cedidos_adversario": (confronto or {}).get("cedidos_adversario", {"jogos": 0, "scouts": {}}),
            }
        )
    except Exception as exc:
        print(f"[SCOUT CROSSING] Erro no cruzamento: {exc}")
        return _api_error("Não foi possível executar o cruzamento.", 500)
    finally:
        close_db_connection(conn)


@scout_crossing_bp.route("/api/detalhe/<int:atleta_id>/<int:rodada>")
@login_required
def detail(atleta_id, rodada):
    conn = get_db_connection()
    if not conn:
        return _api_error("Banco de dados indisponível.", 503)
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        temporada, _ = _current_context(cursor)
        matches = _match_query(cursor, atleta_id, temporada, rodada, rodada_exata=rodada)
        if not matches:
            return _api_error("Detalhe da rodada não encontrado.", 404)
        _attach_conceded_scouts(cursor, matches, matches[0].get("posicao_id"), temporada)
        return jsonify(matches[0])
    except Exception as exc:
        print(f"[SCOUT CROSSING] Erro no detalhe: {exc}")
        return _api_error("Não foi possível carregar o detalhe.", 500)
    finally:
        close_db_connection(conn)
