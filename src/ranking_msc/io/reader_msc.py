"""
ranking_msc.io.reader_msc
~~~~~~~~~~~~~~~~~~~~~~~~~~

Leitura e parse inicial do CSV MSC (Matriz de Saldos Contábeis).

O CSV MSC é o arquivo mensal enviado ao SICONFI. Cada arquivo contém:
    - Metadados: código SICONFI do ente e competência (YYYY-MM).
    - Dados: saldos contábeis por conta PCASP.

Este módulo NÃO aplica regras de validação de negócio. Ele apenas:
    1. Lê o CSV.
    2. Extrai competência e siconfi (do nome do arquivo ou cabeçalho).
    3. Valida o layout mínimo (colunas obrigatórias presentes?).
    4. Retorna um ``RawMSC`` com o DataFrame + metadados.

Validações de conteúdo (domínios, PCASP, etc.) ficam nas regras.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

import pandas as pd

from ranking_msc.exceptions import InputFormatError


@dataclass
class RawMSC:
    """Resultado da leitura de um CSV MSC.

    Attributes:
        competencia: mês de referência no formato "YYYY-MM".
        siconfi: código SICONFI do ente (ex: "250400").
        df: DataFrame bruto (sem normalização de IC).
        source: caminho ou nome do arquivo de origem.
    """
    competencia: str
    siconfi: str
    df: pd.DataFrame
    source: str = ""


def read_msc_csv(
    file: str | Path | BinaryIO,
    *,
    encoding: str = "latin-1",
    separator: str = ";",
) -> RawMSC:
    """Lê o CSV MSC e devolve um ``RawMSC``.

    Args:
        file: caminho do arquivo ou objeto file-like (ex: upload do Panel).
        encoding: encoding do CSV (padrão latin-1, comum em arquivos brasileiros).
        separator: separador de colunas.

    Returns:
        ``RawMSC`` com metadados e DataFrame.

    Raises:
        InputFormatError: se o arquivo estiver vazio, ilegível ou sem
                          as colunas mínimas esperadas.

    TODO (implementar):
        - Detectar competência: pode vir do nome do arquivo (ex: MSC_250400_2024-01.csv)
          ou de um campo no cabeçalho. Definir padrão com a equipe.
        - Detectar siconfi: idem.
        - Mapear nomes de colunas do CSV original para os nomes padronizados
          de ``FACT_MSC_COLUMNS``.
        - Tratar colunas numéricas (vírgula → ponto, etc.).
    """
    # --- STUB ---
    raise NotImplementedError(
        "read_msc_csv() ainda não implementado. "
        "Consulte os comentários para o fluxo esperado."
    )


def _extract_metadata(filename: str) -> tuple[str, str]:
    """Extrai competência e siconfi a partir do nome do arquivo.

    Padrão esperado: MSC_<SICONFI>_<YYYY-MM>.csv
    Exemplo: MSC_250400_2024-01.csv → ("2024-01", "250400")

    TODO: ajustar regex conforme padrão real dos arquivos.
    """
    raise NotImplementedError("_extract_metadata() — definir padrão de nomes.")
