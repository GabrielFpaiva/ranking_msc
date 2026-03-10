"""
tests/test_normalize.py
~~~~~~~~~~~~~~~~~~~~~~~

Testes de normalização IC/TIPO em ``ranking_msc.transform.ic_normalize``.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
import pytest

from ranking_msc.exceptions import InputFormatError
from ranking_msc.io.reader_msc import read_msc_csv
from ranking_msc.transform.ic_normalize import normalize_ic

_TYPE_TO_COL: dict[str, str] = {
    "PO": "po",
    "FP": "fp",
    "FS": "fs",
    "FR": "fr",
    "CO": "co",
    "NR": "nr",
    "ND": "nd",
    "AI": "ai",
}


def test_normalize_ic_expande_colunas_e_mantem_originais() -> None:
    """Expande colunas normalizadas e preserva colunas originais IC/TIPO."""
    df = pd.DataFrame(
        [
            {
                "competencia": "2024-01",
                "siconfi": "250400",
                "conta_contabil": "111110200",
                "ic1": "10131",
                "tipo1": "PO",
                "ic2": "001",
                "tipo2": "FP",
                "ic3": "1500",
                "tipo3": "FR",
                "ic4": "1001",
                "tipo4": "CO",
                "ic5": "33903099",
                "tipo5": "ND",
                "ic6": "2024",
                "tipo6": "AI",
            },
            {
                "competencia": "2024-01",
                "siconfi": "250400",
                "conta_contabil": "222220000",
                "ic1": "10132",
                "tipo1": "PO",
                "ic2": "F0001",
                "tipo2": "FS",
                "ic3": "1501",
                "tipo3": "FR",
                "ic4": "",
                "tipo4": "",
                "ic5": "44905200",
                "tipo5": "ND",
                "ic6": "",
                "tipo6": "",
            },
        ],
    )

    result = normalize_ic(df)

    for col in ("po", "fp", "fs", "fr", "co", "nr", "nd", "ai"):
        assert col in result.columns

    assert result.iloc[0]["po"] == "10131"
    assert result.iloc[0]["fp"] == "001"
    assert result.iloc[0]["fr"] == "1500"
    assert result.iloc[0]["co"] == "1001"
    assert result.iloc[0]["nd"] == "33903099"
    assert result.iloc[0]["ai"] == "2024"
    assert result.iloc[0]["fs"] == ""
    assert result.iloc[0]["nr"] == ""

    assert result.iloc[1]["po"] == "10132"
    assert result.iloc[1]["fs"] == "F0001"
    assert result.iloc[1]["fr"] == "1501"
    assert result.iloc[1]["nd"] == "44905200"
    assert result.iloc[1]["fp"] == ""
    assert result.iloc[1]["co"] == ""
    assert result.iloc[1]["nr"] == ""
    assert result.iloc[1]["ai"] == ""

    assert result.iloc[0]["tipo2"] == "FP"
    assert result.iloc[1]["tipo2"] == "FS"
    assert result.iloc[0]["ic2"] == "001"
    assert result.iloc[1]["ic2"] == "F0001"


def test_normalize_ic_combinacao_desconhecida_loga_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Loga warning para combinação TIPO não mapeada sem interromper execução."""
    df = pd.DataFrame(
        [
            {
                "ic1": "10131",
                "tipo1": "PO",
                "ic2": "abc",
                "tipo2": "ZZ",
                "ic3": "",
                "tipo3": "",
                "ic4": "",
                "tipo4": "",
                "ic5": "",
                "tipo5": "",
                "ic6": "",
                "tipo6": "",
            },
        ],
    )

    with caplog.at_level(logging.WARNING, logger="ranking_msc"):
        result = normalize_ic(df)

    assert result.iloc[0]["po"] == "10131"
    assert any("não mapeadas" in record.getMessage() for record in caplog.records)
    assert any("ZZ" in record.getMessage() for record in caplog.records)


def test_normalize_ic_csvs_reais_ref_com_colunas_corretas() -> None:
    """Valida normalização para todos os CSVs reais em ref/amostras."""
    amostras_dir = Path("ref/amostras")
    csvs = sorted(amostras_dir.glob("msc_*.csv"))
    if not csvs:
        pytest.skip("Nenhuma amostra em ref/amostras para validar normalize_ic")

    for csv_path in csvs:
        raw = read_msc_csv(csv_path)
        normalized = normalize_ic(raw.df)

        for col in _TYPE_TO_COL.values():
            assert col in normalized.columns, f"Coluna normalizada ausente: {col}"

        for i in range(1, 7):
            tipo_col = f"tipo{i}"
            ic_col = f"ic{i}"
            tipo_series = raw.df[tipo_col].fillna("").astype(str).str.strip().str.upper()
            ic_series = raw.df[ic_col].fillna("").astype(str).str.strip()

            for tipo_code, dest_col in _TYPE_TO_COL.items():
                mask = (tipo_series == tipo_code) & (ic_series != "")
                if not mask.any():
                    continue
                assert (normalized.loc[mask, dest_col].astype(str) == ic_series[mask]).all(), (
                    f"Falha de normalização em {csv_path.name} para {tipo_code}->{dest_col}"
                )


def test_normalize_ic_sem_colunas_tipo_levanta_inputformaterror() -> None:
    """Levanta InputFormatError quando faltam colunas IC/TIPO obrigatórias."""
    df = pd.DataFrame([{"ic1": "10131", "tipo1": "PO"}])
    with pytest.raises(InputFormatError, match="colunas obrigatórias"):
        normalize_ic(df)
