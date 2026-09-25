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


def _club_payload(clube_id, nome=None, abreviacao=None):
    clube_id = _json_int(clube_id)
    return {
        "id": clube_id,
        "nome": nome or "Clube não informado",
        "abreviacao": abreviacao or nome or "---",
        "escudo": get_team_shield(clube_id, size="45x45") or "",
    }


def _team_options(cursor, temporada, rodada):
    cursor.execute(
        """
        WITH round_clubs AS (
            SELECT DISTINCT v.clube_id
            FROM acf_partidas p
            CROSS JOIN LATERAL (VALUES (p.clube_casa_id), (p.clube_visitante_id)) v(clube_id)
            WHERE p.temporada = %s AND p.rodada_id = %s
        )
        SELECT c.id, c.nome, c.abreviacao,
               EXISTS (
                   SELECT 1
                   FROM acf_partidas p
                   WHERE p.temporada = %s
                     AND p.rodada_id = %s
                     AND p.valida = TRUE
                     AND c.id IN (p.clube_casa_id, p.clube_visitante_id)
               ) AS valido
        FROM round_clubs r
        JOIN acf_clubes c ON c.id = r.clube_id
        ORDER BY c.nome
        """,
        (temporada, rodada, temporada, rodada),
    )
    return [
        {
            **_club_payload(row["id"], row["nome"]),
            "abreviacao": row["abreviacao"] or row["nome"],
            "valido": bool(row["valido"]),
        }
        for row in cursor.fetchall()
    ]


def _round_fixture_options(cursor, temporada, rodada):
    """Retorna os confrontos da rodada para a seleção visual da página.

    A tela precisa apresentar o campeonato como pares de adversários, e não
    como uma lista solta de clubes. Mantemos os mesmos dados de escudo,
    mando e placar usados no histórico para evitar duas fontes visuais
    diferentes.
    """
    cursor.execute(
        """
        SELECT p.partida_id, p.clube_casa_id, p.clube_visitante_id,
               casa.nome AS casa_nome, visitante.nome AS visitante_nome,
               casa.abreviacao AS casa_abreviacao,
               visitante.abreviacao AS visitante_abreviacao,
               p.placar_oficial_mandante, p.placar_oficial_visitante,
               p.local, p.valida
        FROM acf_partidas p
        LEFT JOIN acf_clubes casa ON casa.id = p.clube_casa_id
        LEFT JOIN acf_clubes visitante ON visitante.id = p.clube_visitante_id
        WHERE p.temporada = %s
          AND p.rodada_id = %s
        ORDER BY p.partida_id
        """,
        (temporada, rodada),
    )
    fixtures = []
    for row in cursor.fetchall():
        fixtures.append(
            {
                "id": _json_int(row["partida_id"]),
                "casa": _club_payload(row["clube_casa_id"], row["casa_nome"], row["casa_abreviacao"]),
                "fora": _club_payload(row["clube_visitante_id"], row["visitante_nome"], row["visitante_abreviacao"]),
                "placar_casa": row["placar_oficial_mandante"],
                "placar_fora": row["placar_oficial_visitante"],
                "local": row["local"] or "",
                "valido": bool(row["valida"]),
            }
        )
    return fixtures


def _match_options(cursor, clube_id, temporada, rodada):
    cursor.execute(
        """
        SELECT p.partida_id, p.clube_casa_id, p.clube_visitante_id,
               casa.nome AS casa_nome, visitante.nome AS visitante_nome,
               casa.abreviacao AS casa_abreviacao, visitante.abreviacao AS visitante_abreviacao,
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
        home = _club_payload(row["clube_casa_id"], row["casa_nome"], row["casa_abreviacao"])
        away = _club_payload(row["clube_visitante_id"], row["visitante_nome"], row["visitante_abreviacao"])
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


def _current_fixture(cursor, clube_id, temporada, rodada):
    """Resolve o único confronto do clube na rodada atual sem ação do usuário."""
    matches = _match_options(cursor, clube_id, temporada, rodada)
    if not matches:
        return None
    fixture = matches[0]
    _attach_fixture_indices(cursor, fixture, temporada, rodada)
    fixture["mando_label"] = "Casa" if fixture["mando"] == "casa" else "Fora"
    fixture["casa_nome"] = fixture["casa"]["nome"]
    fixture["visitante_nome"] = fixture["fora"]["nome"]
    return fixture


def _attach_fixture_indices(cursor, fixture, temporada, rodada):
    """Anexa favoritismo e SG dos perfis escolhidos pelo usuário ao jogo."""
    if not fixture:
        return fixture

    peso_jogo = {}
    peso_sg = {}
    try:
        # Os pesos de favoritismo/SG ficam em acw_weight_configurations.
        # acw_escalacao_config guarda formação, capitão e prováveis, mas não
        # possui os IDs dos perfis de pesos. Usar a tabela de escalação aqui
        # fazia o confronto chegar ao frontend sempre com F/SG zerados.
        from models.user_configurations import get_user_default_configuration

        user_id = session.get("user_id")
        team_id = session.get("selected_team_id")
        config = (
            get_user_default_configuration(cursor.connection, int(user_id), team_id)
            if user_id
            else None
        ) or {}
        # Mantém uma recuperação segura para sessões antigas que ainda não
        # carregaram selected_team_id, sem misturar perfis de outro usuário.
        if not config and user_id:
            config = get_user_default_configuration(cursor.connection, int(user_id)) or {}
        perfil_jogo = config.get("perfil_peso_jogo")
        perfil_sg = config.get("perfil_peso_sg")
        if perfil_jogo:
            cursor.execute(
                """
                SELECT clube_id, peso_jogo
                FROM acp_peso_jogo_perfis
                WHERE perfil_id = %s AND rodada_atual = %s
                """,
                (perfil_jogo, rodada),
            )
            peso_jogo = {_json_int(row["clube_id"]): float(row["peso_jogo"] or 0) for row in cursor.fetchall()}
        if perfil_sg:
            cursor.execute(
                """
                SELECT clube_id, peso_sg
                FROM acp_peso_sg_perfis
                WHERE perfil_id = %s AND rodada_atual = %s
                """,
                (perfil_sg, rodada),
            )
            peso_sg = {_json_int(row["clube_id"]): float(row["peso_sg"] or 0) for row in cursor.fetchall()}
    except Exception as exc:
        print(f"[SCOUT CROSSING] Índices do confronto indisponíveis: {exc}")

    # A régua é comum à rodada inteira. Assim o maior favoritismo da rodada
    # representa 100% em todos os confrontos, permitindo comparar as barras
    # entre jogos sem que cada duelo crie uma escala própria.
    max_jogo = max((abs(value) for value in peso_jogo.values()), default=1.0) or 1.0
    for side in ("casa", "fora"):
        club = fixture.get(side) or {}
        club_id = _json_int(club.get("id"))
        favoritismo = peso_jogo.get(club_id, 0.0)
        saldo = peso_sg.get(club_id, 0.0)
        saldo_percent = saldo * 100 if abs(saldo) <= 1 else saldo
        club["favoritismo"] = round(favoritismo, 2)
        club["saldo"] = round(saldo, 2)
        club["saldo_percent"] = round(max(0.0, min(100.0, saldo_percent)), 1)
    for side in ("casa", "fora"):
        club = fixture.get(side) or {}
        club["favoritismo_percent"] = round(
            min(100.0, abs(float(club.get("favoritismo") or 0)) / max_jogo * 100),
            1,
        )
    fixture["favoritismo_maximo"] = round(max_jogo, 2)
    return fixture


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


def _player_options(cursor, temporada, posicao_id, clube_id=None, rodada=None, availability=None):
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
               l.posicao_id,
               COALESCE(l.apelido, l.nome, 'Atleta ' || l.atleta_id::text) AS nome,
               l.clube_id,
               COALESCE(c.nome, 'Clube não informado') AS clube_nome,
               COALESCE(c.abreviacao, '') AS clube_abrev,
               COALESCE(a.foto, l.foto) AS foto,
               COALESCE(a.status_id, 0) AS status_id,
               COALESCE(a.pontos_num, 0) AS pontos_num,
               COALESCE(a.media_num, 0) AS media_num,
               COALESCE(a.preco_num, 0) AS preco_num,
               COALESCE(a.jogos_num, 0) AS jogos_num
        FROM latest l
        LEFT JOIN acf_clubes c ON c.id = l.clube_id
        LEFT JOIN LATERAL (
            SELECT status_id, pontos_num, media_num, preco_num, jogos_num,
                   COALESCE(NULLIF(BTRIM(foto_custom), ''), foto) AS foto
            FROM acf_atletas current_atleta
            WHERE current_atleta.atleta_id = l.atleta_id
              AND current_atleta.temporada = %s
            ORDER BY current_atleta.rodada_id DESC NULLS LAST
            LIMIT 1
        ) a ON TRUE
        ORDER BY nome
        """,
        (temporada, posicao_id, clube_id, clube_id, temporada, posicao_id, clube_id, clube_id, temporada),
    )
    players = []
    rows = cursor.fetchall()
    ids = [_json_int(row["atleta_id"]) for row in rows]
    scout_by_player = {}
    if ids:
        placeholders = ",".join(["%s"] * len(ids))
        cursor.execute(
            f"""
            SELECT atleta_id,
                   AVG(COALESCE(pontuacao, 0)) AS media_pontuacao,
                   AVG(COALESCE(scout_ds, 0)) AS media_ds,
                   AVG(COALESCE(scout_fs, 0)) AS media_fs,
                   AVG(COALESCE(scout_ff, 0)) AS media_ff,
                   AVG(COALESCE(scout_fd, 0)) AS media_fd,
                   AVG(COALESCE(scout_g, 0)) AS media_g,
                   AVG(COALESCE(scout_a, 0)) AS media_a,
                   AVG(COALESCE(scout_sg, 0)) AS media_sg,
                   COUNT(*) FILTER (WHERE entrou_em_campo = TRUE) AS jogos
            FROM acf_pontuados
            WHERE atleta_id IN ({placeholders})
              AND (temporada = %s OR temporada IS NULL)
              AND (%s IS NULL OR rodada_id <= %s)
              AND entrou_em_campo = TRUE
            GROUP BY atleta_id
            """,
            ids + [temporada, rodada, rodada],
        )
        scout_by_player = {
            _json_int(row["atleta_id"]): {
                "media_pontuacao": _json_number(row["media_pontuacao"]),
                "media_ds": _json_number(row["media_ds"]),
                "media_fs": _json_number(row["media_fs"]),
                "media_ff": _json_number(row["media_ff"]),
                "media_fd": _json_number(row["media_fd"]),
                "media_g": _json_number(row["media_g"]),
                "media_a": _json_number(row["media_a"]),
                "media_sg": _json_number(row["media_sg"]),
                "jogos": _json_int(row["jogos"]),
            }
            for row in cursor.fetchall()
        }

    status_names = {2: "Dúvida", 3: "Improvável", 5: "Suspenso", 6: "Nulo", 7: "Provável"}
    external_status = {}
    probable_source = "globo"
    try:
        from models.user_escalacao_config import create_user_escalacao_config_table, get_user_escalacao_config
        create_user_escalacao_config_table(cursor.connection)
        config = get_user_escalacao_config(cursor.connection, int(session.get("user_id")), session.get("selected_team_id"))
        probable_source = (config or {}).get("fonte_provaveis", "globo")
        cursor.execute("SELECT to_regclass('public.acf_provaveis_fontes')")
        table_exists = cursor.fetchone()[0] is not None
        if probable_source == "provaveisdocartola" and table_exists:
            cursor.execute(
                """
                SELECT pm.atleta_id, pf.status
                FROM acf_provaveis_fontes pf
                JOIN LATERAL (
                    SELECT pm.atleta_id
                    FROM acw_provaveis_mapeamentos pm
                    WHERE pm.temporada = pf.temporada AND pm.fonte = pf.fonte
                      AND pm.atleta_externo_id = pf.atleta_externo_id
                      AND pm.rodada_id <= pf.rodada_id
                    ORDER BY pm.rodada_id DESC LIMIT 1
                ) pm ON TRUE
                JOIN LATERAL (
                    SELECT cm.clube_id FROM acw_provaveis_clubes_mapeamentos cm
                    WHERE cm.temporada = pf.temporada AND cm.fonte = pf.fonte
                      AND cm.clube_slug_externo = pf.clube_slug_externo
                      AND cm.rodada_id <= pf.rodada_id
                    ORDER BY cm.rodada_id DESC LIMIT 1
                ) tm ON TRUE
                JOIN acf_atletas live ON live.atleta_id = pm.atleta_id
                  AND live.temporada = pf.temporada AND live.status_id <> 6
                  AND live.clube_id = tm.clube_id
                WHERE pf.temporada = %s AND pf.rodada_id = %s AND pf.fonte = %s
                  AND pf.ativo = TRUE AND pm.atleta_id IS NOT NULL
                """,
                (temporada, rodada or 1, "provaveisdocartola"),
            )
            external_status = {int(row[0]): str(row[1] or "duvida") for row in cursor.fetchall()}
    except Exception as source_error:
        print(f"[SCOUT CROSSING] Fonte externa não carregada: {source_error}")
    for row in rows:
        athlete_id = _json_int(row["atleta_id"])
        status_id = _json_int(row["status_id"])
        source_status = external_status.get(athlete_id)
        source_status_id = {"provavel": 7, "duvida": 2, "improvavel": 3, "suspenso": 5, "lesionado": 5, "fora": 6}.get(source_status)
        scouts = scout_by_player.get(athlete_id, {})
        players.append(
            {
                "id": athlete_id,
                "nome": row["nome"],
                "posicao_id": _json_int(row["posicao_id"]),
                "clube_id": _json_int(row["clube_id"]),
                "clube_nome": row["clube_nome"],
                "clube_abrev": row["clube_abrev"] or row["clube_nome"],
                "foto": row["foto"] or "",
                "status_id": status_id,
                "source_status_id": source_status_id,
                "probables_source": probable_source,
                "status_nome": status_names.get(source_status_id if source_status_id is not None else status_id, "Desconhecido"),
                "pontos_num": _json_number(row["pontos_num"]),
                "media_num": _json_number(row["media_num"]),
                "preco_num": _json_number(row["preco_num"]),
                "jogos_num": _json_int(row["jogos_num"]),
                "scouts": scouts,
                "availability_rule": (availability or {}).get(athlete_id),
            }
        )
    return players


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
               casa.nome AS casa_nome, visitante.nome AS visitante_nome,
               casa.abreviacao AS casa_abreviacao, visitante.abreviacao AS visitante_abreviacao
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
        "casa": _club_payload(casa_id, row["casa_nome"], row["casa_abreviacao"]),
        "fora": _club_payload(visitante_id, row["visitante_nome"], row["visitante_abreviacao"]),
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
        ORDER BY (NULLIF(BTRIM(s.foto), '') IS NOT NULL) DESC, s.rodada_id DESC NULLS LAST
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
    current_stats = {}
    try:
        cursor.execute(
            """
            SELECT pontos_num, media_num, preco_num, jogos_num,
                   COALESCE(foto_custom, foto) AS foto
            FROM acf_atletas
            WHERE atleta_id = %s AND temporada = %s
            ORDER BY rodada_id DESC NULLS LAST
            LIMIT 1
            """,
            (atleta_id, temporada),
        )
        stats_row = cursor.fetchone()
        if stats_row:
            current_stats = {
                "pontos_num": _json_number(stats_row["pontos_num"]),
                "media_num": _json_number(stats_row["media_num"]),
                "preco_num": _json_number(stats_row["preco_num"]),
                "jogos_num": _json_int(stats_row["jogos_num"]),
                "foto": stats_row["foto"] or "",
            }
    except Exception:
        # Bases antigas podem não possuir todos os campos de snapshot.
        current_stats = {}
    return {
        "id": _json_int(row["atleta_id"]),
        "nome": row["nome"],
        "clube_id": _json_int(row["clube_id"]),
        "clube_nome": row["clube_nome"] or "Clube não informado",
        "foto": current_stats.get("foto") or row["foto"] or "",
        "posicao": POSITION_BY_ID.get(_json_int(row["posicao_id"]), {}).get("label", ""),
        "pontos_num": current_stats.get("pontos_num", 0),
        "media_num": current_stats.get("media_num", 0),
        "preco_num": current_stats.get("preco_num", 0),
        "jogos_num": current_stats.get("jogos_num", 0),
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
        "ultima_pontuacao": _json_number(points[0]) if points else 0,
        "pontos_total": _json_number(sum(points)) if points else 0,
        "adversarios": opponent_data,
        "mando": mando_data,
    }


def _empty_conceded_summary(main_scouts):
    return {
        "jogos": 0,
        "jogos_com_dados": 0,
        "atletas_analisados": 0,
        "pontuacao": 0,
        "pontuacao_por_jogo": 0,
        "pontuacao_por_atleta": 0,
        "pico": 0,
        "scouts": {key: 0 for key in main_scouts},
        "scouts_detalhados": [],
        "recorrencia": {"5": 0, "8": 0, "12": 0},
        "historico": [],
    }


def _summarize_conceded_games(games, main_scouts):
    """Resume o cedimento por partida, sem misturar atletas ou rodadas.

    O indicador principal é a média por jogo da posição adversária. Também
    mantemos a média por atleta, o pico individual e a recorrência dos scouts
    para que o usuário consiga distinguir volume de consistência.
    """
    summary = _empty_conceded_summary(main_scouts)
    summary["jogos"] = len(games)
    data_games = [game for game in games if game["jogadores"]]
    summary["jogos_com_dados"] = len(data_games)
    summary["atletas_analisados"] = sum(len(game["jogadores"]) for game in data_games)
    if not data_games:
        return summary

    denominator = float(len(data_games))
    points = [player["pontuacao"] for game in data_games for player in game["jogadores"]]
    summary["pontuacao_por_jogo"] = _json_number(
        sum(game["pontuacao"] for game in data_games) / denominator
    )
    summary["pontuacao"] = summary["pontuacao_por_jogo"]
    summary["pontuacao_por_atleta"] = _json_number(sum(points) / max(1, len(points)))
    summary["pico"] = _json_number(max(points) if points else 0)

    for key in main_scouts:
        total = sum(game["scouts"].get(key, 0) for game in data_games)
        occurrences = sum(1 for game in data_games if game["scouts"].get(key, 0) > 0)
        summary["scouts"][key] = _json_number(total / denominator)
        summary["scouts_detalhados"].append(
            {
                "codigo": key,
                "nome": SCOUT_LABELS[key],
                "media_por_jogo": _json_number(total / denominator),
                "total": _json_int(total),
                "recorrencia": round(occurrences / denominator * 100),
            }
        )

    for threshold in (5, 8, 12):
        count = sum(
            1
            for game in data_games
            if any(player["pontuacao"] >= threshold for player in game["jogadores"])
        )
        summary["recorrencia"][str(threshold)] = round(count / denominator * 100)
    summary["scouts_detalhados"].sort(
        key=lambda item: (item["media_por_jogo"], item["recorrencia"]), reverse=True
    )
    return summary


def _opponent_conceded_scouts(
    cursor, adversario_id, posicao_id, temporada, rodada_limite, mando_jogador=None
):
    """Monta um perfil de cedimento real do adversário.

    Cada linha histórica é uma partida do adversário-alvo. Os números são
    agregados somente pelos atletas da posição que enfrentaram aquele clube e
    entraram em campo. O recorte recomendado inverte o mando do jogador:
    se o atleta joga em casa, o adversário é analisado nos jogos fora, e
    vice-versa.
    """
    main_scouts = POSITION_SCOUTS.get(posicao_id, ())
    empty = {
        "adversario_id": _json_int(adversario_id),
        "jogos": 0,
        "pontuacao": 0,
        "scouts": {},
        "mando_relevante": "",
        "por_mando": {"casa": _empty_conceded_summary(main_scouts), "fora": _empty_conceded_summary(main_scouts)},
        "historico": [],
    }
    if not adversario_id or not main_scouts:
        return empty

    cursor.execute(
        f"""
        WITH jogos AS (
            SELECT p.partida_id, p.rodada_id,
                   p.clube_casa_id, p.clube_visitante_id,
                   CASE WHEN p.clube_casa_id = %s THEN 'casa' ELSE 'fora' END AS mando_alvo,
                   CASE WHEN p.clube_casa_id = %s THEN p.clube_visitante_id ELSE p.clube_casa_id END AS rival_id,
                   p.placar_oficial_mandante, p.placar_oficial_visitante,
                   p.partida_data, p.local,
                   casa.nome AS casa_nome, casa.abreviacao AS casa_abreviacao,
                   visitante.nome AS visitante_nome, visitante.abreviacao AS visitante_abreviacao
            FROM acf_partidas p
            LEFT JOIN acf_clubes casa ON casa.id = p.clube_casa_id
            LEFT JOIN acf_clubes visitante ON visitante.id = p.clube_visitante_id
            WHERE p.temporada = %s
              AND p.valida = TRUE
              AND p.rodada_id < %s
              AND %s IN (p.clube_casa_id, p.clube_visitante_id)
        ), pontos AS (
            SELECT DISTINCT ON (p.atleta_id, p.rodada_id, p.clube_id)
                   p.atleta_id, p.rodada_id, p.clube_id,
                   p.apelido,
                   COALESCE(NULLIF(BTRIM(a.foto_custom), ''), NULLIF(BTRIM(p.foto), ''), a.foto) AS foto,
                   p.pontuacao,
                   p.scout_a, p.scout_ca, p.scout_cv, p.scout_de, p.scout_ds,
                   p.scout_fc, p.scout_fd, p.scout_ff, p.scout_fs, p.scout_g,
                   p.scout_gs, p.scout_i, p.scout_sg
            FROM acf_pontuados p
            LEFT JOIN LATERAL (
                SELECT foto_custom, foto
                FROM acf_atletas atual
                WHERE atual.atleta_id = p.atleta_id
                  AND atual.temporada = %s
                ORDER BY atual.rodada_id DESC NULLS LAST
                LIMIT 1
            ) a ON TRUE
            WHERE p.posicao_id = %s
              AND p.entrou_em_campo = TRUE
              AND (p.temporada = %s OR p.temporada IS NULL)
            ORDER BY p.atleta_id, p.rodada_id, p.clube_id,
                     CASE WHEN p.temporada = %s THEN 0 ELSE 1 END
        )
        SELECT j.*, p.atleta_id, p.apelido, p.foto, p.pontuacao,
               p.scout_a, p.scout_ca, p.scout_cv, p.scout_de, p.scout_ds,
               p.scout_fc, p.scout_fd, p.scout_ff, p.scout_fs, p.scout_g,
               p.scout_gs, p.scout_i, p.scout_sg
        FROM jogos j
        LEFT JOIN pontos p
          ON p.rodada_id = j.rodada_id
         AND p.clube_id = j.rival_id
        ORDER BY j.rodada_id DESC, p.pontuacao DESC NULLS LAST
        """,
        (adversario_id, adversario_id, temporada, rodada_limite, adversario_id, temporada, posicao_id, temporada, temporada),
    )

    grouped = {}
    for row in cursor.fetchall():
        partida_id = _json_int(row["partida_id"])
        game = grouped.setdefault(
            partida_id,
            {
                "partida_id": partida_id,
                "rodada": _json_int(row["rodada_id"]),
                "mando_adversario": row["mando_alvo"],
                "mando_label": "Casa" if row["mando_alvo"] == "casa" else "Fora",
                "pontuacao": 0,
                "pico": 0,
                "scouts": {key: 0 for key in main_scouts},
                "jogadores": [],
                "casa": _club_payload(row["clube_casa_id"], row["casa_nome"], row["casa_abreviacao"]),
                "fora": _club_payload(row["clube_visitante_id"], row["visitante_nome"], row["visitante_abreviacao"]),
                "clube_id": _json_int(adversario_id),
                "placar_casa": row["placar_oficial_mandante"],
                "placar_fora": row["placar_oficial_visitante"],
                "local": row["local"] or "",
                "partida_data": row["partida_data"] or "",
            },
        )
        if row["atleta_id"] is None:
            continue
        player_scouts = {
            key: _json_int(row[f"scout_{key}"]) for key in main_scouts
        }
        player = {
            "id": _json_int(row["atleta_id"]),
            "nome": row["apelido"] or f"Atleta {_json_int(row['atleta_id'])}",
            "foto": row["foto"] or "",
            "pontuacao": _json_number(row["pontuacao"]),
            "scouts": player_scouts,
        }
        game["jogadores"].append(player)
        game["pontuacao"] += _json_number(row["pontuacao"])
        game["pico"] = max(game["pico"], _json_number(row["pontuacao"]))
        for key, value in player_scouts.items():
            game["scouts"][key] += value

    games = list(grouped.values())
    for game in games:
        game["pontuacao"] = _json_number(game["pontuacao"])
        game["pico"] = _json_number(game["pico"])
        game["jogadores"].sort(key=lambda item: item["pontuacao"], reverse=True)
        game["scouts"] = {key: _json_int(value) for key, value in game["scouts"].items()}
    games.sort(key=lambda item: item["rodada"], reverse=True)

    by_mando = {
        "casa": [game for game in games if game["mando_adversario"] == "casa"],
        "fora": [game for game in games if game["mando_adversario"] == "fora"],
    }
    summaries = {
        mando: _summarize_conceded_games(items, main_scouts)
        for mando, items in by_mando.items()
    }
    for mando, items in by_mando.items():
        summaries[mando]["historico"] = items[:8]

    mando_relevante = ""
    if mando_jogador == "casa":
        mando_relevante = "fora"
    elif mando_jogador == "fora":
        mando_relevante = "casa"
    selected = summaries.get(mando_relevante) or _empty_conceded_summary(main_scouts)
    return {
        "adversario_id": _json_int(adversario_id),
        "jogos": selected["jogos_com_dados"],
        "jogos_com_dados": selected["jogos_com_dados"],
        "pontuacao": selected["pontuacao_por_jogo"],
        "scouts": selected["scouts"],
        "scouts_detalhados": selected["scouts_detalhados"],
        "recorrencia": selected["recorrencia"],
        "mando_relevante": mando_relevante,
        "por_mando": summaries,
        "historico": selected["historico"],
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
    atleta_id = _int_arg("atleta_id", None, 1)

    conn = get_db_connection()
    if not conn:
        return _api_error("Banco de dados indisponível.", 503)
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        temporada, rodada = _current_context(cursor)
        teams = _team_options(cursor, temporada, rodada)
        fixtures = _round_fixture_options(cursor, temporada, rodada)
        if atleta_id and posicao_id and not clube_id:
            selected_player = _player_snapshot(cursor, atleta_id, temporada, posicao_id)
            clube_id = selected_player["clube_id"] if selected_player else None
        if clube_id and clube_id not in {team["id"] for team in teams}:
            clube_id = None
        availability_rules = {}
        try:
            from models.player_availability import create_player_availability_table, list_player_availability

            create_player_availability_table(conn)
            records = list_player_availability(
                conn,
                user_id=session["user_id"],
                team_id=session.get("selected_team_id"),
                season=temporada,
                round_number=rodada,
            )
            availability_rules = {
                _json_int(record.get("athlete_id")): record.get("rule")
                for record in records
            }
        except Exception as availability_error:
            # A tela continua disponível mesmo em instalações legadas que
            # ainda não tenham inicializado a tabela de regras do usuário.
            print(f"[SCOUT CROSSING] Disponibilidade não carregada: {availability_error}")
        players = _player_options(
            cursor,
            temporada,
            posicao_id,
            clube_id,
            rodada=rodada,
            availability=availability_rules,
        ) if posicao_id else []
        return jsonify(
            {
                "temporada": temporada,
                "rodada": rodada,
                "clube_id": clube_id,
                "times": teams,
                "confrontos": fixtures,
                "jogadores": players,
                "regras_disponibilidade": availability_rules,
                "confronto": _current_fixture(cursor, clube_id, temporada, rodada) if clube_id else None,
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

        # A rodada corrente ainda não tem pontuação histórica. O confronto
        # atual continua sendo carregado separadamente abaixo.
        matches = _match_query(cursor, atleta_id, temporada, max(0, rodada - 1))
        _attach_conceded_scouts(cursor, matches, posicao_id, temporada)
        summary = _aggregate_matches(matches)
        confronto = _current_fixture(cursor, player["clube_id"], temporada, rodada)
        adversario_id = confronto["adversario"]["id"] if confronto else None
        cedidos = _opponent_conceded_scouts(
            cursor,
            adversario_id,
            posicao_id,
            temporada,
            rodada,
            confronto.get("mando") if confronto else None,
        )
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
                "ultimas_pontuacoes": matches,
                "scouts_da_posicao": _position_scouts(cursor, posicao_id, temporada, rodada),
                "confronto": confronto,
                "cedidos_adversario": cedidos,
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
