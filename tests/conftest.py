"""
tests/conftest.py
~~~~~~~~~~~~~~~~~

Fixtures compartilhadas entre todos os módulos de teste.
"""

from __future__ import annotations

import io
from collections.abc import Callable
from pathlib import Path

import pytest

from ranking_msc.config.settings import Settings
from ranking_msc.engine.executor import EngineContext


@pytest.fixture
def settings() -> Settings:
    """Settings padrão para testes."""
    return Settings()


@pytest.fixture
def engine_context(settings: Settings) -> EngineContext:
    """EngineContext padrão para testes de regra."""
    return EngineContext(
        competencia="2024-01",
        siconfi="250400",
        settings=settings,
        usuario="teste",
    )


def _build_msc_csv_bytes(
    siconfi: str = "2507507EX",
    competencia: str = "2025-11",
    rows: list[list[str]] | None = None,
    header: str = "CONTA;IC1;TIPO1;IC2;TIPO2;IC3;TIPO3;IC4;TIPO4;IC5;TIPO5;IC6;TIPO6"
                  ";Valor;Tipo_valor;Natureza_valor",
    line_terminator: str = "\r",
) -> bytes:
    """Gera bytes de um CSV MSC sintético para testes.

    Args:
        siconfi: código SICONFI na linha de metadata.
        competencia: competência na linha de metadata.
        rows: linhas de dados (cada uma é uma lista de strings com 16 campos).
        header: header CSV.
        line_terminator: terminador de linha (padrão \\r como no CSV real).

    Returns:
        Bytes do CSV com line terminator adequado.
    """
    if rows is None:
        # Dados mínimos: 1 conta com 4 linhas (beginning D, period D, period C, ending D)
        # IC sequence: PO, FP, DC → IC_MAP[3] (válido para R082)
        rows = [
            ["111110200", "10131", "PO", "1", "FP", "1500", "DC", "", "", "", "", "", "",
             "1000.00", "beginning_balance", "D"],
            ["111110200", "10131", "PO", "1", "FP", "1500", "DC", "", "", "", "", "", "",
             "500.00", "beginning_balance", "C"],
            ["111110200", "10131", "PO", "1", "FP", "1500", "DC", "", "", "", "", "", "",
             "200.50", "period_change", "D"],
            ["111110200", "10131", "PO", "1", "FP", "1500", "DC", "", "", "", "", "", "",
             "100.25", "period_change", "C"],
            ["111110200", "10131", "PO", "1", "FP", "1500", "DC", "", "", "", "", "", "",
             "1100.25", "ending_balance", "D"],
            ["111110200", "10131", "PO", "1", "FP", "1500", "DC", "", "", "", "", "", "",
             "600.25", "ending_balance", "C"],
        ]

    metadata = f"{siconfi};{competencia}"
    data_lines = [";".join(row) for row in rows]
    all_lines = [metadata, header] + data_lines
    text = line_terminator.join(all_lines)
    return text.encode("ascii")


@pytest.fixture
def msc_csv_bytes() -> bytes:
    """Bytes de um CSV MSC sintético válido."""
    return _build_msc_csv_bytes()


@pytest.fixture
def msc_csv_path(tmp_path: Path, msc_csv_bytes: bytes) -> Path:
    """Caminho para um arquivo CSV MSC sintético válido."""
    path = tmp_path / "MSC_2507507EX_2025-11.csv"
    path.write_bytes(msc_csv_bytes)
    return path


@pytest.fixture
def msc_csv_bytesio(msc_csv_bytes: bytes) -> io.BytesIO:
    """BytesIO com CSV MSC sintético válido."""
    return io.BytesIO(msc_csv_bytes)


@pytest.fixture
def build_msc_csv() -> Callable[..., bytes]:
    """Retorna a função _build_msc_csv_bytes para uso em testes."""
    return _build_msc_csv_bytes
