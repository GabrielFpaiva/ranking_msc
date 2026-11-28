"""Testes de io/db.py e da migração inicial do schema Postgres (F7-05).

Os testes que precisam de banco usam ``MCRA_TEST_DATABASE_URL`` e rodam num
schema descartável (criado e apagado por teste). Sem a variável, são pulados;
no CI ela aponta para um serviço Postgres.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Generator
from pathlib import Path

import psycopg
import pytest

from ranking_msc.config.settings import load_settings
from ranking_msc.exceptions import ConfigError, DatabaseError
from ranking_msc.io.db import MIGRATIONS_DIR, apply_migrations, connect

TEST_URL = os.environ.get("MCRA_TEST_DATABASE_URL", "")
precisa_banco = pytest.mark.skipif(not TEST_URL, reason="MCRA_TEST_DATABASE_URL não definida")

TABELAS = {
    "usuarios", "matrizes", "matriz_linhas", "execucoes", "pendencias",
    "dispensadas", "registros_envio", "historico_score", "uso", "schema_migrations",
}


@pytest.fixture
def conn() -> Generator[psycopg.Connection, None, None]:
    """Conexão com search_path num schema novo, apagado ao fim do teste."""
    schema = f"teste_{uuid.uuid4().hex[:12]}"
    with psycopg.connect(TEST_URL, autocommit=True) as admin:
        admin.execute(f"create schema {schema}")
    try:
        with psycopg.connect(TEST_URL, options=f"-c search_path={schema}") as c:
            yield c
    finally:
        with psycopg.connect(TEST_URL, autocommit=True) as admin:
            admin.execute(f"drop schema {schema} cascade")


def _nova_matriz(conn: psycopg.Connection, origem: str = "previa") -> int:
    """Insere uma matriz de 10/2026 e devolve o id."""
    row = conn.execute(
        "insert into matrizes (siconfi, competencia, origem, enviado_por)"
        " values ('2507507EX', '2026-10', %s, 'ana') returning id",
        (origem,),
    ).fetchone()
    assert row is not None
    return int(row[0])


def test_connect_sem_url_levanta_configerror() -> None:
    """URL vazia → ConfigError antes de tentar a rede."""
    with pytest.raises(ConfigError):
        connect("")


def test_connect_url_invalida_levanta_databaseerror() -> None:
    """Servidor inexistente → DatabaseError com mensagem em português."""
    with pytest.raises(DatabaseError, match="Falha ao conectar"):
        connect("postgresql://x:y@127.0.0.1:1/nada")


def test_load_settings_database_url_env_tem_precedencia(monkeypatch: pytest.MonkeyPatch) -> None:
    """DATABASE_URL no ambiente vence o database.url do YAML."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert load_settings().database.url == ""
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h/db")
    assert load_settings().database.url == "postgresql://u:p@h/db"


def test_migracoes_seguem_padrao_de_nome() -> None:
    """Arquivos NNNN_descricao.sql, com números sem repetição."""
    nomes = [p.stem for p in sorted(MIGRATIONS_DIR.glob("*.sql"))]
    assert nomes and nomes[0] == "0001_schema_inicial"
    numeros = [n.split("_", 1)[0] for n in nomes]
    assert all(len(n) == 4 and n.isdigit() for n in numeros)
    assert len(numeros) == len(set(numeros))


@precisa_banco
def test_apply_migrations_cria_tabelas_e_e_idempotente(conn: psycopg.Connection) -> None:
    """Primeira chamada cria tudo com RLS ligado; a segunda não aplica nada."""
    assert apply_migrations(conn) == ["0001_schema_inicial"]
    assert apply_migrations(conn) == []
    rows = conn.execute(
        "select relname, relrowsecurity from pg_class"
        " where relnamespace = current_schema()::regnamespace and relkind = 'r'"
    ).fetchall()
    assert {r[0] for r in rows} == TABELAS
    assert all(rls for _, rls in rows)


@precisa_banco
def test_apply_migrations_falha_desfaz_e_levanta(
    conn: psycopg.Connection, tmp_path: Path
) -> None:
    """SQL inválido → DatabaseError e a versão não fica registrada."""
    (tmp_path / "0001_ruim.sql").write_text("create table x (;", encoding="utf-8")
    with pytest.raises(DatabaseError, match="0001_ruim"):
        apply_migrations(conn, tmp_path)
    assert conn.execute("select count(*) from schema_migrations").fetchone() == (0,)


@precisa_banco
def test_matriz_unica_por_competencia_e_origem(conn: psycopg.Connection) -> None:
    """Segunda prévia do mesmo mês é recusada; homologada do mesmo mês convive."""
    apply_migrations(conn)
    _nova_matriz(conn, "previa")
    _nova_matriz(conn, "homologada")
    with pytest.raises(psycopg.errors.UniqueViolation):
        _nova_matriz(conn, "previa")


@precisa_banco
def test_matriz_competencia_invalida_recusada(conn: psycopg.Connection) -> None:
    """Competência fora de YYYY-MM (mês 01–13) viola o check."""
    apply_migrations(conn)
    with pytest.raises(psycopg.errors.CheckViolation):
        conn.execute(
            "insert into matrizes (siconfi, competencia, origem) values ('x', '2026-14', 'previa')"
        )


@precisa_banco
def test_apagar_matriz_leva_linhas_execucoes_e_pendencias(conn: psycopg.Connection) -> None:
    """Cascade: apagar a prévia limpa o que depende dela, mas não o histórico."""
    apply_migrations(conn)
    mid = _nova_matriz(conn)
    exec_id = uuid.uuid4()
    conn.execute(
        "insert into matriz_linhas (matriz_id, linha, conta_contabil, saldo_final_debito,"
        " has_saldo_inicial, has_saldo_final, has_period_change)"
        " values (%s, 0, '111110200', 0.1, true, true, true)",
        (mid,),
    )
    conn.execute(
        "insert into execucoes (id, matriz_id, usuario, inicio, status, regras_executadas)"
        " values (%s, %s, 'ana', now(), 'OK', %s)",
        (exec_id, mid, ["R001", "R082"]),
    )
    conn.execute(
        "insert into pendencias (execucao_id, regra_id, regra_nome, dimensao, severidade,"
        " descricao, competencia) values (%s, 'R082', 'x', 'Fechamento', 'ERRO', 'd', '2026-10')",
        (exec_id,),
    )
    conn.execute(
        "insert into historico_score (siconfi, competencia, origem, execucao_id, pontuacao, banda)"
        " values ('2507507EX', '2026-10', 'previa', %s, 87.5, 'B')",
        (exec_id,),
    )
    assert conn.execute("select saldo_final_debito from matriz_linhas").fetchone() == (0.1,)

    conn.execute("delete from matrizes where id = %s", (mid,))
    for tabela, esperado in (
        ("matriz_linhas", 0), ("execucoes", 0), ("pendencias", 0), ("historico_score", 1),
    ):
        assert conn.execute(f"select count(*) from {tabela}").fetchone() == (esperado,), tabela


@precisa_banco
def test_dispensada_exige_motivo_e_e_unica_por_regra_conta(conn: psycopg.Connection) -> None:
    """Motivo em branco viola o check; mesma regra + conta duas vezes viola a PK."""
    apply_migrations(conn)
    sql = (
        "insert into dispensadas (regra_id, conta_contabil, motivo, usuario)"
        " values (%s, %s, %s, 'ana')"
    )
    with pytest.raises(psycopg.errors.CheckViolation):
        with conn.transaction():
            conn.execute(sql, ("R082", "111110200", "   "))
    conn.execute(sql, ("R082", "111110200", "conta encerrada em 2024"))
    with pytest.raises(psycopg.errors.UniqueViolation):
        conn.execute(sql, ("R082", "111110200", "de novo"))
