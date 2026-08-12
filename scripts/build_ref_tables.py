"""Regenera as tabelas de domínio de ``ref/`` a partir do workbook oficial da STN.

O workbook (Anexo do leiaute MSC, publicado em thot-arquivos.tesouro.gov.br) é a
fonte das tabelas ND e NR. Rodar este script sempre que a STN publicar uma versão
nova, junto com a atualização de ``ANO_TABELAS_REF`` em ``io/ref_loader.py``.

Uso:
    python scripts/build_ref_tables.py [--workbook CAMINHO] [--ref-dir CAMINHO]
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import openpyxl
import pandas as pd

logger = logging.getLogger("ranking_msc")

_WORKBOOK_PADRAO = Path("ref/2026_Leiaute_MSC_STN_anexo_28661.xlsx")
_REF_DIR_PADRAO = Path("ref")

# Linha em que começam os dados de cada aba (o cabeçalho fica na linha anterior).
_PRIMEIRA_LINHA_ND = 8
_PRIMEIRA_LINHA_NR = 6


def extrair_nd(workbook: Path) -> pd.DataFrame:
    """Lê a aba "ND 2026" e devolve as colunas codigo, nivel e nome.

    Args:
        workbook: caminho do xlsx oficial da STN.

    Returns:
        DataFrame ordenado por código, sem duplicatas.
    """
    wb = openpyxl.load_workbook(workbook, read_only=True, data_only=True)
    linhas: list[dict[str, str]] = []
    for row in wb["ND 2026"].iter_rows(min_row=_PRIMEIRA_LINHA_ND, values_only=True):
        # A maioria das células de código vem como número; ao menos uma linha do
        # workbook oficial guarda o código como texto pontuado (ex.: "3.1.90.46.00").
        codigo = str(row[5]).strip().replace(".", "") if row[5] is not None else ""
        if not codigo.isdigit():
            continue
        linhas.append({
            "codigo": codigo.zfill(8),
            "nivel": str(row[7]).strip() if row[7] is not None else "",
            "nome": str(row[6]).strip() if row[6] is not None else "",
        })
    return (
        pd.DataFrame(linhas)
        .drop_duplicates(subset=["codigo"])
        .sort_values("codigo")
        .reset_index(drop=True)
    )


def extrair_nr(workbook: Path) -> pd.DataFrame:
    """Lê a aba "NR 2026" e devolve as colunas codigo e valorizavel.

    Args:
        workbook: caminho do xlsx oficial da STN.

    Returns:
        DataFrame ordenado por código, sem duplicatas.
    """
    wb = openpyxl.load_workbook(workbook, read_only=True, data_only=True)
    linhas: list[dict[str, str]] = []
    for row in wb["NR 2026"].iter_rows(min_row=_PRIMEIRA_LINHA_NR, values_only=True):
        codigo = str(row[7]).strip() if row[7] is not None else ""
        if not codigo.isdigit():
            continue
        linhas.append({
            "codigo": codigo.zfill(8),
            "valorizavel": str(row[10]).strip() if row[10] is not None else "",
        })
    return (
        pd.DataFrame(linhas)
        .drop_duplicates(subset=["codigo"])
        .sort_values("codigo")
        .reset_index(drop=True)
    )


def main() -> None:
    """Regenera ``tabela_nd.csv`` e ``tabela_nr.csv`` a partir do workbook."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workbook", type=Path, default=_WORKBOOK_PADRAO)
    parser.add_argument("--ref-dir", type=Path, default=_REF_DIR_PADRAO)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    # CRLF para manter o mesmo terminador de linha dos CSVs já versionados em ref/.
    nd = extrair_nd(args.workbook)
    nd.to_csv(
        args.ref_dir / "tabela_nd.csv",
        sep=";",
        index=False,
        encoding="utf-8",
        lineterminator="\r\n",
    )
    logger.info("tabela_nd.csv: %d códigos", len(nd))

    nr = extrair_nr(args.workbook)
    nr.to_csv(
        args.ref_dir / "tabela_nr.csv",
        sep=";",
        index=False,
        encoding="utf-8",
        lineterminator="\r\n",
    )
    logger.info("tabela_nr.csv: %d códigos", len(nr))


if __name__ == "__main__":
    main()
