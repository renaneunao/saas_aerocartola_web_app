"""Persistência dos vínculos manuais entre fonte externa e Cartola oficial."""

from __future__ import annotations

from typing import Optional


SOURCE = "provaveisdocartola"


def create_provaveis_mapping_table(conn):
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS acw_provaveis_mapeamentos (
            id BIGSERIAL PRIMARY KEY,
            temporada INTEGER NOT NULL,
            rodada_id INTEGER NOT NULL,
            fonte VARCHAR(50) NOT NULL,
            atleta_externo_id TEXT NOT NULL,
            atleta_id INTEGER,
            atualizado_por INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT uq_acw_provaveis_mapeamento
                UNIQUE (temporada, rodada_id, fonte, atleta_externo_id)
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS acw_provaveis_clubes_mapeamentos (
            id BIGSERIAL PRIMARY KEY,
            temporada INTEGER NOT NULL,
            rodada_id INTEGER NOT NULL,
            fonte VARCHAR(50) NOT NULL,
            clube_slug_externo TEXT NOT NULL,
            clube_id INTEGER,
            atualizado_por INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT uq_acw_provaveis_clube_mapeamento
                UNIQUE (temporada, rodada_id, fonte, clube_slug_externo)
        )
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_acw_provaveis_clube_mapeamento_oficial
            ON acw_provaveis_clubes_mapeamentos (temporada, rodada_id, fonte, clube_id)
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_acw_provaveis_mapeamento_atleta
            ON acw_provaveis_mapeamentos (temporada, rodada_id, fonte, atleta_id)
        """
    )
    conn.commit()


def save_mapping(conn, temporada: int, rodada_id: int, external_id: str, athlete_id: Optional[int], user_id: int):
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO acw_provaveis_mapeamentos
            (temporada, rodada_id, fonte, atleta_externo_id, atleta_id, atualizado_por)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (temporada, rodada_id, fonte, atleta_externo_id) DO UPDATE SET
            atleta_id = EXCLUDED.atleta_id,
            atualizado_por = EXCLUDED.atualizado_por,
            updated_at = CURRENT_TIMESTAMP
        RETURNING id, atleta_id
        """,
        (temporada, rodada_id, SOURCE, str(external_id), athlete_id, user_id),
    )
    row = cursor.fetchone()
    conn.commit()
    cursor.close()
    return {"id": row[0], "atleta_id": row[1]} if row else None


def save_club_mapping(conn, temporada: int, rodada_id: int, external_slug: str, club_id: Optional[int], user_id: int):
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO acw_provaveis_clubes_mapeamentos
            (temporada, rodada_id, fonte, clube_slug_externo, clube_id, atualizado_por)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (temporada, rodada_id, fonte, clube_slug_externo) DO UPDATE SET
            clube_id = EXCLUDED.clube_id,
            atualizado_por = EXCLUDED.atualizado_por,
            updated_at = CURRENT_TIMESTAMP
        RETURNING id, clube_id
        """,
        (temporada, rodada_id, SOURCE, str(external_slug), club_id, user_id),
    )
    row = cursor.fetchone()
    conn.commit()
    cursor.close()
    return {"id": row[0], "clube_id": row[1]} if row else None
