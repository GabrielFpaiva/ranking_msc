"""Testes de io/store.py — armazenamento de matrizes e resultados (F7-06).

Os testes de ``PostgresStore`` usam ``MCRA_TEST_DATABASE_URL`` e rodam num
schema descartável com a migração aplicada; sem a variável, são pulados.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Generator
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

import pandas as pd
import psycopg
import pytest

import ranking_msc.rules  # noqa: F401  -- popular RULE_REGISTRY
from ranking_msc.config.settings import DatabaseSettings, Settings, load_settings
from ranking_msc.engine.executor import EngineContext, run_engine
from ranking_msc.exceptions import SnapshotError, SnapshotNotFoundError
from ranking_msc.io.db import apply_migrations
from ranking_msc.io.reader_msc import read_msc_csv
from ranking_msc.io.store import (
    ExecucaoRegistro,
    MatrizRef,
    ParquetStore,
    PostgresStore,
    SnapshotStore,
    make_store,
)
from ranking_msc.schemas import FACT_RESULTADO_REGRAS_COLUMNS
from ranking_msc.transform.ic_normalize import normalize_ic

TEST_URL = os.environ.get("MCRA_TEST_DATABASE_URL", "")
precisa_banco = pytest.mark.skipif(not TEST_URL, reason="MCRA_TEST_DATABASE_URL não definida")

_AMOSTRAS = Path(__file__).resolve().parents[1] / "ref" / "amostras"
SICONFI = "2507507EX"


def _execucao(regras: list[str]) -> ExecucaoRegistro:
    """Registro de execução mínimo."""
    return ExecucaoRegistro(
        execucao_id=str(uuid.uuid4()), usuario="ana", inicio=datetime.now(), status="OK",
        regras_executadas=regras, pontuacao=90.0, banda="A", dimensoes={"Fechamento": {"s": 1}},
    )


def _pendencias(n: int, competencia: str = "2025-12") -> pd.DataFrame:
    """N pendências no formato de FACT_RESULTADO_REGRAS_COLUMNS (a última, global)."""
    linhas = [
        {
            "regra_id": "R082", "regra_nome": "D=C", "dimensao": "Fechamento",
            "severidade": "ERRO", "conta_contabil": "" if i == n - 1 else f"11111020{i}",
            "descricao": f"d{i}", "valor_esperado": "0", "valor_encontrado": "1",
            "competencia": competencia,
        }
        for i in range(n)
    ]
    return pd.DataFrame(linhas, columns=FACT_RESULTADO_REGRAS_COLUMNS)


@pytest.fixture(scope="module")
def msc_real() -> pd.DataFrame:
    """Matriz real de 12/2025 normalizada (~29 mil linhas)."""
    raw = read_msc_csv(_AMOSTRAS / "2507507EX-2025-12-001.csv")
    return normalize_ic(raw.df)


@pytest.fixture
def pg_url() -> Generator[str, None, None]:
    """URL do banco de teste num schema novo, já migrado e apagado ao fim."""
    schema = f"teste_{uuid.uuid4().hex[:12]}"
    with psycopg.connect(TEST_URL, autocommit=True) as admin:
        admin.execute(f"create schema {schema}")
    sep = "&" if "?" in TEST_URL else "?"
    url = f"{TEST_URL}{sep}options={quote(f'-c search_path={schema}')}"
    try:
        with psycopg.connect(url) as conn:
            apply_migrations(conn)
        yield url
    finally:
        with psycopg.connect(TEST_URL, autocommit=True) as admin:
            admin.execute(f"drop schema {schema} cascade")


# ---------------------------------------------------------------------------
# Sem banco
# ---------------------------------------------------------------------------


def test_matrizref_origem_invalida_levanta_snapshoterror() -> None:
    """Origem fora de previa/homologada é recusada na criação do endereço."""
    with pytest.raises(SnapshotError, match="Origem inválida"):
        MatrizRef(SICONFI, "2025-12", "rascunho")


def test_make_store_escolhe_postgres_com_url_e_parquet_sem(tmp_path: Path) -> None:
    """Com database.url → PostgresStore; sem → ParquetStore na pasta dada."""
    assert isinstance(make_store(Settings(), tmp_path), ParquetStore)
    com_url = Settings(database=DatabaseSettings(url="postgresql://u:p@h/db"))
    assert isinstance(make_store(com_url, tmp_path), PostgresStore)


def test_engine_context_sem_store_usa_o_da_configuracao(tmp_path: Path) -> None:
    """get_store() monta um ParquetStore em snapshots_dir e o reaproveita."""
    ctx = EngineContext(competencia="2025-12", siconfi=SICONFI, settings=load_settings(),
                        snapshots_dir=tmp_path)
    store = ctx.get_store()
    assert isinstance(store, ParquetStore) and store.base_dir == tmp_path
    assert ctx.get_store() is store
    assert ctx.ref("2025-11") == MatrizRef(SICONFI, "2025-11", "previa")


def test_parquet_store_separa_previa_e_homologada(tmp_path: Path) -> None:
    """Prévia fica no caminho antigo; homologada em subpasta; list_refs vê as duas."""
    store = ParquetStore(tmp_path)
    previa, homologada = MatrizRef(SICONFI, "2025-12"), MatrizRef(SICONFI, "2025-12", "homologada")
    store.save_resultado(previa, _pendencias(2), _execucao(["R082"]))
    store.save_resultado(homologada, _pendencias(5), _execucao(["R001", "R082"]))

    assert (tmp_path / SICONFI / "2025-12" / "resultado_regras.parquet").exists()
    assert len(store.load_resultado(previa)) == 2
    assert len(store.load_resultado(homologada)) == 5
    assert store.load_rule_ids(homologada) == ["R001", "R082"]
    assert store.list_refs() == [homologada, previa]  # ordem: ente, competência, origem
    assert store.list_refs(origem="homologada") == [homologada]
    assert store.list_refs(siconfi="outro") == []


def test_parquet_store_sem_raiz_lista_vazio(tmp_path: Path) -> None:
    """Raiz inexistente → nenhuma matriz e load levanta SnapshotNotFoundError."""
    store = ParquetStore(tmp_path / "nada")
    assert store.list_refs() == []
    with pytest.raises(SnapshotNotFoundError):
        store.load_msc(MatrizRef(SICONFI, "2025-12"))


# ---------------------------------------------------------------------------
# Postgres
# ---------------------------------------------------------------------------


@precisa_banco
def test_postgres_msc_ida_e_volta_identica(pg_url: str, msc_real: pd.DataFrame) -> None:
    """A matriz real sai do banco igual ao que entrou: colunas, ordem, valores e tipos lógicos."""
    store = PostgresStore(pg_url)
    ref = MatrizRef(SICONFI, "2025-12")
    store.save_msc(ref, msc_real, usuario="ana")
    lida = store.load_msc(ref)
    assert list(lida.columns) == list(msc_real.columns)
    pd.testing.assert_frame_equal(lida, msc_real, check_dtype=False)


@precisa_banco
def test_postgres_regras_dao_o_mesmo_resultado_que_parquet(
    pg_url: str, tmp_path: Path, msc_real: pd.DataFrame
) -> None:
    """Rodar o motor com a matriz anterior lida do banco ou do Parquet dá as mesmas pendências."""
    settings = load_settings()
    anterior = normalize_ic(read_msc_csv(_AMOSTRAS / "msc_2025-11.csv").df)

    resultados = []
    for store in (PostgresStore(pg_url), ParquetStore(tmp_path)):
        store.save_msc(MatrizRef(SICONFI, "2025-11"), anterior, usuario="ana")
        ctx = EngineContext(competencia="2025-12", siconfi=SICONFI, settings=settings, store=store)
        result = run_engine(msc_real, ctx)
        assert {"R054", "R083"} <= set(result.executed_rule_ids)
        assert result.regras_com_erro == 0
        resultados.append(result.pendencias.reset_index(drop=True))
    pd.testing.assert_frame_equal(resultados[0], resultados[1])


@precisa_banco
def test_postgres_resultado_rule_ids_historico_e_listagem(pg_url: str) -> None:
    """Grava resultado, lê de volta, registra o score e lista só matrizes com execução."""
    store: SnapshotStore = PostgresStore(pg_url)
    ref = MatrizRef(SICONFI, "2025-12")
    with pytest.raises(SnapshotError, match="Grave a matriz"):
        store.save_resultado(ref, _pendencias(1), _execucao(["R082"]))
    store.save_msc(ref, pd.DataFrame(columns=["conta_contabil"]), usuario="ana")
    assert store.list_refs() == []
    with pytest.raises(SnapshotNotFoundError):
        store.load_resultado(ref)
    assert store.load_rule_ids(ref) is None

    pend = _pendencias(3)
    store.save_resultado(ref, pend, _execucao(["R082", "R001"]))
    pd.testing.assert_frame_equal(
        store.load_resultado(ref).sort_values("descricao").reset_index(drop=True), pend,
        check_dtype=False,
    )
    assert store.load_rule_ids(ref) == ["R001", "R082"]
    assert store.list_refs() == [ref]

    store.save_resultado(ref, _pendencias(1), _execucao(["R082"]))  # nova execução troca a anterior
    assert len(store.load_resultado(ref)) == 1
    with psycopg.connect(pg_url) as conn:
        assert conn.execute("select count(*) from execucoes").fetchone() == (1,)
        assert conn.execute("select count(*) from historico_score").fetchone() == (2,)


@precisa_banco
def test_postgres_substituir_previa_apaga_execucao_e_competencia_invalida(pg_url: str) -> None:
    """Regravar a prévia do mês limpa a execução antiga; competência inválida é recusada."""
    store = PostgresStore(pg_url)
    ref = MatrizRef(SICONFI, "2025-12")
    sem_linhas = pd.DataFrame(columns=["conta_contabil"])
    store.save_msc(ref, sem_linhas, usuario="ana")
    store.save_resultado(ref, _pendencias(2), _execucao(["R082"]))
    store.save_msc(ref, sem_linhas, usuario="bia")
    with pytest.raises(SnapshotNotFoundError):
        store.load_resultado(ref)
    assert store.load_msc(ref).empty
    with pytest.raises(SnapshotError, match="Competência inválida"):
        store.save_msc(MatrizRef(SICONFI, "2025-14"), sem_linhas, usuario="ana")
