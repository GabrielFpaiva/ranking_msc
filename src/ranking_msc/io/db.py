"""Conexão com o Postgres (Supabase) e aplicação das migrações SQL.

As migrações são arquivos ``NNNN_descricao.sql`` em ``io/migrations/``,
aplicados em ordem, cada um na sua transação, e registrados em
``schema_migrations``. Rodar de novo só aplica os que faltam.
"""

from __future__ import annotations

import logging
from pathlib import Path

import psycopg

from ranking_msc.exceptions import ConfigError, DatabaseError

logger = logging.getLogger("ranking_msc")

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


def connect(url: str) -> psycopg.Connection:
    """Abre conexão com o Postgres.

    ``prepare_threshold=None`` desliga prepared statements, que o pooler do
    Supabase em modo transação (porta 6543) não suporta.

    Raises:
        ConfigError: se a URL estiver vazia.
        DatabaseError: se a conexão falhar.
    """
    if not url:
        raise ConfigError(
            "URL do banco não configurada. Defina DATABASE_URL ou database.url no settings.yaml."
        )
    try:
        return psycopg.connect(url, prepare_threshold=None, connect_timeout=15)
    except psycopg.Error as exc:
        raise DatabaseError(f"Falha ao conectar no banco: {exc}") from exc


def apply_migrations(conn: psycopg.Connection, migrations_dir: Path = MIGRATIONS_DIR) -> list[str]:
    """Aplica as migrações ainda não registradas em ``schema_migrations``.

    Args:
        conn: conexão aberta (o search_path define o schema de destino).
        migrations_dir: pasta com os arquivos ``.sql``.

    Returns:
        Versões aplicadas nesta chamada, em ordem (vazia se nada faltava).

    Raises:
        DatabaseError: se alguma migração falhar (a dela é desfeita; as
            anteriores desta chamada ficam aplicadas).
    """
    with conn.transaction():
        conn.execute(
            "create table if not exists schema_migrations ("
            " versao text primary key, aplicada_em timestamptz not null default now())"
        )
        # Mesmo motivo das tabelas da 0001: o Supabase expõe o schema pela API REST.
        conn.execute("alter table schema_migrations enable row level security")
        aplicadas = {row[0] for row in conn.execute("select versao from schema_migrations")}

    novas: list[str] = []
    for arquivo in sorted(migrations_dir.glob("*.sql")):
        versao = arquivo.stem
        if versao in aplicadas:
            continue
        try:
            with conn.transaction():
                conn.execute(arquivo.read_text(encoding="utf-8"))  # type: ignore[arg-type]
                conn.execute("insert into schema_migrations (versao) values (%s)", (versao,))
        except psycopg.Error as exc:
            raise DatabaseError(f"Falha na migração {versao}: {exc}") from exc
        logger.info("Migração aplicada: %s", versao, extra={"modulo": "db"})
        novas.append(versao)
    return novas
