"""Testes de cobertura do mapeamento IC × TIPO.

Valida que ref/mapeamento_ic_tipo.csv cobre 100% das combinações
de TIPO1–TIPO6 encontradas nos CSVs reais de amostra.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from ranking_msc.io.reader_msc import read_msc_csv

_REF_DIR = Path(__file__).resolve().parent.parent / "ref"
_AMOSTRAS_DIR = _REF_DIR / "amostras"
_MAPEAMENTO_PATH = _REF_DIR / "mapeamento_ic_tipo.csv"

_TIPO_COLS = ["tipo1", "tipo2", "tipo3", "tipo4", "tipo5", "tipo6"]


@pytest.fixture(scope="module")
def mapeamento_df() -> pd.DataFrame:
    """Carrega ref/mapeamento_ic_tipo.csv."""
    assert _MAPEAMENTO_PATH.exists(), (
        f"Arquivo de mapeamento não encontrado: {_MAPEAMENTO_PATH}"
    )
    df = pd.read_csv(_MAPEAMENTO_PATH, sep=";", dtype=str, keep_default_na=False)
    return df


@pytest.fixture(scope="module")
def combinacoes_reais() -> set[tuple[str, ...]]:
    """Extrai todas as combinações únicas de TIPO dos CSVs reais."""
    csvs = sorted(_AMOSTRAS_DIR.glob("msc_*.csv"))
    assert len(csvs) > 0, f"Nenhum CSV de amostra encontrado em {_AMOSTRAS_DIR}"

    all_combos: set[tuple[str, ...]] = set()
    for csv_path in csvs:
        raw = read_msc_csv(csv_path)
        combos = raw.df[_TIPO_COLS].drop_duplicates()
        for _, row in combos.iterrows():
            all_combos.add(tuple(row[c] for c in _TIPO_COLS))

    return all_combos


@pytest.fixture(scope="module")
def combinacoes_mapeamento(mapeamento_df: pd.DataFrame) -> set[tuple[str, ...]]:
    """Extrai as combinações de TIPO do mapeamento."""
    combos: set[tuple[str, ...]] = set()
    for _, row in mapeamento_df.iterrows():
        combos.add(tuple(row[c] for c in _TIPO_COLS))
    return combos


class TestMapeamentoIcTipo:
    """Testes do arquivo ref/mapeamento_ic_tipo.csv."""

    def test_mapeamento_tem_colunas_esperadas(
        self, mapeamento_df: pd.DataFrame,
    ) -> None:
        """Mapeamento possui todas as colunas obrigatórias."""
        expected = [*_TIPO_COLS, "colunas_aplicaveis", "descricao"]
        missing = set(expected) - set(mapeamento_df.columns)
        assert not missing, f"Colunas ausentes no mapeamento: {missing}"

    def test_mapeamento_nao_vazio(self, mapeamento_df: pd.DataFrame) -> None:
        """Mapeamento tem pelo menos uma linha."""
        assert len(mapeamento_df) > 0

    def test_mapeamento_sem_duplicatas(self, mapeamento_df: pd.DataFrame) -> None:
        """Mapeamento não tem combinações duplicadas."""
        dupes = mapeamento_df[_TIPO_COLS].duplicated()
        assert not dupes.any(), (
            f"Combinações duplicadas: {mapeamento_df[dupes][_TIPO_COLS].to_dict('records')}"
        )

    def test_cobertura_100_csvs_reais(
        self,
        combinacoes_reais: set[tuple[str, ...]],
        combinacoes_mapeamento: set[tuple[str, ...]],
    ) -> None:
        """Todas as combinações dos CSVs reais estão no mapeamento."""
        missing = combinacoes_reais - combinacoes_mapeamento
        assert not missing, (
            f"{len(missing)} combinação(ões) dos CSVs reais ausente(s) no mapeamento:\n"
            + "\n".join(str(m) for m in sorted(missing))
        )

    def test_colunas_aplicaveis_consistentes(
        self, mapeamento_df: pd.DataFrame,
    ) -> None:
        """Campo colunas_aplicaveis é consistente com os TIPOs preenchidos."""
        tipo_to_col = {
            "PO": "po", "FP": "fp", "FS": "fs", "FR": "fr",
            "CO": "co", "NR": "nr", "ND": "nd", "AI": "ai",
        }
        for idx, row in mapeamento_df.iterrows():
            cols_declaradas = set(row["colunas_aplicaveis"].split(","))
            cols_esperadas = set()
            for tc in _TIPO_COLS:
                tipo_val = row[tc]
                if tipo_val and tipo_val in tipo_to_col:
                    cols_esperadas.add(tipo_to_col[tipo_val])

            assert cols_declaradas == cols_esperadas, (
                f"Linha {idx}: colunas_aplicaveis={cols_declaradas} "
                f"mas TIPOs indicam={cols_esperadas}"
            )

    def test_tipos_validos(self, mapeamento_df: pd.DataFrame) -> None:
        """Todos os valores de TIPO são válidos ou vazios."""
        valid_tipos = {"PO", "FP", "FS", "FR", "CO", "NR", "ND", "AI", ""}
        for tc in _TIPO_COLS:
            found = set(mapeamento_df[tc].unique())
            invalid = found - valid_tipos
            assert not invalid, f"Valores inválidos em {tc}: {invalid}"
