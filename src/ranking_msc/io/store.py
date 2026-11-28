"""Armazenamento das matrizes e dos resultados do motor (F7-06).

Todo leitor e gravador de snapshot passa por um ``SnapshotStore``, endereçado
por ``MatrizRef`` (ente × competência × origem). Duas implementações:

- ``PostgresStore``: o banco do Supabase (tabelas da migração 0001).
- ``ParquetStore``: arquivos em disco, para rodar sem banco (testes, CLI local).

``make_store()`` escolhe: Postgres quando há ``database.url``/``DATABASE_URL``.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

import pandas as pd

from ranking_msc.config.settings import Settings
from ranking_msc.exceptions import SnapshotError, SnapshotNotFoundError
from ranking_msc.io.db import connect
from ranking_msc.outputs.snapshot import (
    read_scoring_metadata,
    read_snapshot,
    write_scoring_metadata,
    write_snapshot_atomic,
)
from ranking_msc.schemas import (
    FACT_MSC_COLUMNS,
    FACT_RESULTADO_REGRAS_COLUMNS,
    RAW_MSC_COLUMNS,
)

ORIGENS = ("previa", "homologada")

# Ordem das colunas do msc_normalizado: o bruto (com ic1..tipo6) + as ICs mapeadas.
MSC_COLUMNS: list[str] = RAW_MSC_COLUMNS + [c for c in FACT_MSC_COLUMNS if c not in RAW_MSC_COLUMNS]
_LINHA_COLUMNS = [c for c in MSC_COLUMNS if c not in ("competencia", "siconfi")]
_COMPETENCIA_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-3])$")


@dataclass(frozen=True)
class MatrizRef:
    """Endereço de uma matriz: ente, competência (YYYY-MM, mês 13 = encerramento) e origem."""

    siconfi: str
    competencia: str
    origem: str = "previa"

    def __post_init__(self) -> None:
        """Recusa origem desconhecida (o banco também recusaria, mas tarde demais)."""
        if self.origem not in ORIGENS:
            raise SnapshotError(f"Origem inválida: {self.origem!r}. Use uma de {ORIGENS}.")


@dataclass(frozen=True)
class ExecucaoRegistro:
    """Metadados de uma execução do motor gravados junto com as pendências."""

    execucao_id: str
    usuario: str
    inicio: datetime
    status: str
    regras_executadas: list[str]
    pontuacao: float
    banda: str
    dimensoes: dict[str, Any] = field(default_factory=dict)


class SnapshotStore(Protocol):
    """Contrato de leitura e gravação de matrizes e resultados."""

    def save_msc(self, ref: MatrizRef, df: pd.DataFrame, *, usuario: str) -> None:
        """Grava (ou substitui) a matriz normalizada."""

    def load_msc(self, ref: MatrizRef) -> pd.DataFrame:
        """Lê a matriz normalizada. Levanta SnapshotNotFoundError se não existir."""

    def save_resultado(
        self, ref: MatrizRef, pendencias: pd.DataFrame, execucao: ExecucaoRegistro
    ) -> None:
        """Grava as pendências e as regras executadas de uma execução sobre a matriz."""

    def load_resultado(self, ref: MatrizRef) -> pd.DataFrame:
        """Lê as pendências da última execução. Levanta SnapshotNotFoundError se não houver."""

    def load_rule_ids(self, ref: MatrizRef) -> list[str] | None:
        """Regras executadas na última execução, ou None se não houver registro."""

    def list_refs(self, siconfi: str | None = None, origem: str | None = None) -> list[MatrizRef]:
        """Matrizes que já têm resultado, ordenadas por ente e competência."""


def make_store(settings: Settings, snapshots_dir: str | Path) -> SnapshotStore:
    """Escolhe o armazenamento: Postgres se houver URL do banco, senão Parquet em disco."""
    if settings.database.url:
        return PostgresStore(settings.database.url)
    return ParquetStore(snapshots_dir)


# ---------------------------------------------------------------------------
# Parquet
# ---------------------------------------------------------------------------


class ParquetStore:
    """Snapshots em ``<raiz>/<siconfi>/<competencia>/`` (prévia) e
    ``<raiz>/<siconfi>/homologada/<competencia>/`` (homologada)."""

    def __init__(self, base_dir: str | Path) -> None:
        """Guarda a raiz dos snapshots."""
        self.base_dir = Path(base_dir)

    def _dir_origem(self, siconfi: str, origem: str) -> Path:
        """Diretório-pai das competências de um ente × origem."""
        base = self.base_dir / siconfi
        return base if origem == "previa" else base / origem

    def _dir(self, ref: MatrizRef) -> Path:
        """Diretório-pai da competência do endereço (as funções de snapshot a acrescentam)."""
        return self._dir_origem(ref.siconfi, ref.origem)

    def save_msc(self, ref: MatrizRef, df: pd.DataFrame, *, usuario: str) -> None:
        """Grava o msc_normalizado.parquet."""
        write_snapshot_atomic(df, ref.competencia, base_dir=self._dir(ref), label="msc_normalizado")

    def load_msc(self, ref: MatrizRef) -> pd.DataFrame:
        """Lê o msc_normalizado.parquet."""
        return read_snapshot(ref.competencia, base_dir=self._dir(ref), label="msc_normalizado")

    def save_resultado(
        self, ref: MatrizRef, pendencias: pd.DataFrame, execucao: ExecucaoRegistro
    ) -> None:
        """Grava resultado_regras.parquet e scoring_metadata.json."""
        base = self._dir(ref)
        write_snapshot_atomic(pendencias, ref.competencia, base_dir=base, label="resultado_regras")
        write_scoring_metadata(execucao.regras_executadas, ref.competencia, base_dir=base)

    def load_resultado(self, ref: MatrizRef) -> pd.DataFrame:
        """Lê resultado_regras.parquet."""
        return read_snapshot(ref.competencia, base_dir=self._dir(ref), label="resultado_regras")

    def load_rule_ids(self, ref: MatrizRef) -> list[str] | None:
        """Lê scoring_metadata.json."""
        return read_scoring_metadata(ref.competencia, base_dir=self._dir(ref))

    def list_refs(self, siconfi: str | None = None, origem: str | None = None) -> list[MatrizRef]:
        """Varre os diretórios atrás de resultado_regras.parquet."""
        if not self.base_dir.is_dir():
            return []
        refs: list[MatrizRef] = []
        for sic_dir in self.base_dir.iterdir():
            if not sic_dir.is_dir() or (siconfi and sic_dir.name != siconfi):
                continue
            for org in ORIGENS:
                if origem and org != origem:
                    continue
                refs.extend(
                    MatrizRef(sic_dir.name, p.parent.name, org)
                    for p in self._dir_origem(sic_dir.name, org).glob("*/resultado_regras.parquet")
                    if _COMPETENCIA_RE.match(p.parent.name)
                )
        return sorted(refs, key=lambda r: (r.siconfi, r.competencia, r.origem))


# ---------------------------------------------------------------------------
# Postgres
# ---------------------------------------------------------------------------


def _sem_nan(df: pd.DataFrame, columns: list[str]) -> list[tuple[Any, ...]]:
    """Linhas do DataFrame como tuplas, com NaN/NA trocados por None (texto 'nan' no banco não)."""
    sub = df.reindex(columns=columns).astype(object)
    return list(sub.where(sub.notna(), None).itertuples(index=False, name=None))


class PostgresStore:
    """Matrizes, execuções e pendências nas tabelas do Supabase.

    shortcut: uma conexão nova por operação (sem pool); trocar por psycopg_pool se a
    latência por chamada pesar nas telas.
    """

    def __init__(self, url: str) -> None:
        """Guarda a URL de conexão."""
        self._url = url

    @staticmethod
    def _matriz_id(conn: Any, ref: MatrizRef) -> int | None:
        """Id da matriz do endereço, ou None."""
        row = conn.execute(
            "select id from matrizes where siconfi = %s and competencia = %s and origem = %s",
            (ref.siconfi, ref.competencia, ref.origem),
        ).fetchone()
        return int(row[0]) if row else None

    def save_msc(self, ref: MatrizRef, df: pd.DataFrame, *, usuario: str) -> None:
        """Substitui a matriz do endereço (o cascade apaga linhas, execuções e pendências)."""
        if not _COMPETENCIA_RE.match(ref.competencia):
            raise SnapshotError(f"Competência inválida: {ref.competencia!r}.")
        colunas = [c.lstrip("_") for c in _LINHA_COLUMNS]
        with connect(self._url) as conn, conn.transaction():
            conn.execute(
                "delete from matrizes where siconfi = %s and competencia = %s and origem = %s",
                (ref.siconfi, ref.competencia, ref.origem),
            )
            row = conn.execute(
                "insert into matrizes (siconfi, competencia, origem, enviado_por)"
                " values (%s, %s, %s, %s) returning id",
                (ref.siconfi, ref.competencia, ref.origem, usuario),
            ).fetchone()
            assert row is not None
            sql = f"copy matriz_linhas (matriz_id, linha, {', '.join(colunas)}) from stdin"
            with conn.cursor().copy(sql) as copy:  # type: ignore[arg-type]
                for i, linha in enumerate(_sem_nan(df, _LINHA_COLUMNS)):
                    copy.write_row((row[0], i, *linha))

    def load_msc(self, ref: MatrizRef) -> pd.DataFrame:
        """Lê a matriz na ordem em que foi gravada, com as colunas do msc_normalizado."""
        colunas = [c.lstrip("_") for c in _LINHA_COLUMNS]
        with connect(self._url) as conn:
            matriz_id = self._matriz_id(conn, ref)
            if matriz_id is None:
                raise SnapshotNotFoundError(f"Matriz não encontrada: {ref}")
            rows = conn.execute(
                f"select {', '.join(colunas)} from matriz_linhas"  # type: ignore[arg-type]
                " where matriz_id = %s order by linha",
                (matriz_id,),
            ).fetchall()
        df = pd.DataFrame(rows, columns=_LINHA_COLUMNS)
        df.insert(0, "siconfi", ref.siconfi)
        df.insert(0, "competencia", ref.competencia)
        return df

    def save_resultado(
        self, ref: MatrizRef, pendencias: pd.DataFrame, execucao: ExecucaoRegistro
    ) -> None:
        """Troca a execução anterior da matriz pela nova e registra o score no histórico."""
        cols = FACT_RESULTADO_REGRAS_COLUMNS
        with connect(self._url) as conn, conn.transaction():
            matriz_id = self._matriz_id(conn, ref)
            if matriz_id is None:
                raise SnapshotError(f"Grave a matriz antes do resultado: {ref}")
            conn.execute("delete from execucoes where matriz_id = %s", (matriz_id,))
            conn.execute(
                "insert into execucoes (id, matriz_id, usuario, inicio, fim, status,"
                " regras_executadas) values (%s, %s, %s, %s, now(), %s, %s)",
                (
                    execucao.execucao_id, matriz_id, execucao.usuario, execucao.inicio,
                    execucao.status, sorted(execucao.regras_executadas),
                ),
            )
            with conn.cursor().copy(
                f"copy pendencias (execucao_id, {', '.join(cols)}) from stdin"  # type: ignore[arg-type]
            ) as copy:
                for linha in _sem_nan(pendencias, cols):
                    valores = dict(zip(cols, linha, strict=True))
                    valores["conta_contabil"] = valores["conta_contabil"] or ""
                    copy.write_row((execucao.execucao_id, *valores.values()))
            conn.execute(
                "insert into historico_score (siconfi, competencia, origem, execucao_id,"
                " pontuacao, banda, dimensoes) values (%s, %s, %s, %s, %s, %s, %s)",
                (
                    ref.siconfi, ref.competencia, ref.origem, execucao.execucao_id,
                    execucao.pontuacao, execucao.banda, json.dumps(execucao.dimensoes),
                ),
            )

    def load_resultado(self, ref: MatrizRef) -> pd.DataFrame:
        """Pendências da execução da matriz."""
        cols = FACT_RESULTADO_REGRAS_COLUMNS
        with connect(self._url) as conn:
            ultima = self._ultima_execucao(conn, ref)
            if ultima is None:
                raise SnapshotNotFoundError(f"Resultado não encontrado: {ref}")
            rows = conn.execute(
                f"select {', '.join(cols)} from pendencias where execucao_id = %s",  # type: ignore[arg-type]
                (ultima[0],),
            ).fetchall()
        return pd.DataFrame(rows, columns=cols)

    def load_rule_ids(self, ref: MatrizRef) -> list[str] | None:
        """Regras executadas na execução da matriz."""
        with connect(self._url) as conn:
            ultima = self._ultima_execucao(conn, ref)
        return list(ultima[1]) if ultima else None

    def list_refs(self, siconfi: str | None = None, origem: str | None = None) -> list[MatrizRef]:
        """Matrizes com pelo menos uma execução."""
        with connect(self._url) as conn:
            rows = conn.execute(
                "select distinct m.siconfi, m.competencia, m.origem from matrizes m"
                " join execucoes e on e.matriz_id = m.id"
                " where (%s::text is null or m.siconfi = %s)"
                " and (%s::text is null or m.origem = %s)"
                " order by 1, 2, 3",
                (siconfi, siconfi, origem, origem),
            ).fetchall()
        return [MatrizRef(*r) for r in rows]

    @staticmethod
    def _ultima_execucao(conn: Any, ref: MatrizRef) -> tuple[Any, list[str]] | None:
        """(id, regras executadas) da execução mais recente da matriz, ou None."""
        row = conn.execute(
            "select e.id, e.regras_executadas from execucoes e"
            " join matrizes m on m.id = e.matriz_id"
            " where m.siconfi = %s and m.competencia = %s and m.origem = %s"
            " order by e.inicio desc limit 1",
            (ref.siconfi, ref.competencia, ref.origem),
        ).fetchone()
        return (row[0], row[1]) if row else None
