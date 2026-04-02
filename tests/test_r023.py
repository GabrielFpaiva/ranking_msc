"""Testes da regra R023 — DC válido: domínio "1"."""

from __future__ import annotations

import math

import pandas as pd

from ranking_msc.rules.r023 import R023


def _df_com_dc(conta: str, dc: object) -> pd.DataFrame:
    """Cria DataFrame mínimo com uma conta e um valor de DC."""
    return pd.DataFrame({"conta_contabil": [conta], "dc": [dc]})


class TestR023:
    def test_dc_valor_1_sem_pendencia(self, engine_context: object) -> None:
        """DC="1" é válido → nenhuma pendência."""
        df = _df_com_dc("111110200", "1")
        result = R023().execute(df, engine_context)

        assert len(result) == 0

    def test_dc_vazio_sem_pendencia(self, engine_context: object) -> None:
        """DC="" (vazio) é tratado como não informado → nenhuma pendência."""
        df = _df_com_dc("111110200", "")
        result = R023().execute(df, engine_context)

        assert len(result) == 0

    def test_dc_zero_sem_pendencia(self, engine_context: object) -> None:
        """DC="0" é tratado como não informado (convenção IC vazia) → nenhuma pendência."""
        df = _df_com_dc("111110200", "0")
        result = R023().execute(df, engine_context)

        assert len(result) == 0

    def test_dc_nan_sem_pendencia(self, engine_context: object) -> None:
        """DC=NaN é tratado como não informado → nenhuma pendência."""
        df = _df_com_dc("111110200", math.nan)
        result = R023().execute(df, engine_context)

        assert len(result) == 0

    def test_dc_none_sem_pendencia(self, engine_context: object) -> None:
        """DC=None é tratado como não informado → nenhuma pendência."""
        df = _df_com_dc("111110200", None)
        result = R023().execute(df, engine_context)

        assert len(result) == 0

    def test_dc_valor_2_gera_erro(self, engine_context: object) -> None:
        """DC="2" está fora do domínio → ERRO."""
        df = _df_com_dc("111110200", "2")
        result = R023().execute(df, engine_context)

        assert len(result) == 1
        row = result.iloc[0]
        assert row["severidade"] == "ERRO"
        assert row["regra_id"] == "R023"
        assert row["conta_contabil"] == "111110200"

    def test_dc_valor_invalido_gera_erro(self, engine_context: object) -> None:
        """DC="X" está fora do domínio → ERRO."""
        df = _df_com_dc("111110200", "X")
        result = R023().execute(df, engine_context)

        assert len(result) == 1
        row = result.iloc[0]
        assert row["severidade"] == "ERRO"
        assert row["regra_id"] == "R023"

    def test_valor_esperado_e_encontrado(self, engine_context: object) -> None:
        """Pendência deve ter valor_esperado='1' e valor_encontrado com o valor inválido."""
        dc_invalido = "9"
        df = _df_com_dc("111110200", dc_invalido)
        result = R023().execute(df, engine_context)

        assert len(result) == 1
        row = result.iloc[0]
        assert row["valor_esperado"] == "1"
        assert row["valor_encontrado"] == dc_invalido
        assert dc_invalido in row["descricao"]

    def test_df_sem_coluna_dc_sem_pendencia(self, engine_context: object) -> None:
        """DataFrame sem coluna dc → nenhuma pendência (regra inaplicável)."""
        df = pd.DataFrame({"conta_contabil": ["111110200"]})
        result = R023().execute(df, engine_context)

        assert len(result) == 0

    def test_multiplas_contas_deduplicado(self, engine_context: object) -> None:
        """Mesma combinação conta+dc repetida → uma única pendência por par único."""
        df = pd.DataFrame({
            "conta_contabil": ["111110200", "111110200", "211000000"],
            "dc": ["2", "2", "3"],  # conta 1 repetida, conta 2 diferente
        })
        result = R023().execute(df, engine_context)

        assert len(result) == 2

    def test_misto_valido_invalido(self, engine_context: object) -> None:
        """Contas com DC válido e inválido na mesma entrada → apenas as inválidas geram erro."""
        df = pd.DataFrame({
            "conta_contabil": ["111110200", "211000000", "311000000"],
            "dc": ["1", "2", "X"],
        })
        result = R023().execute(df, engine_context)

        assert len(result) == 2
        contas_com_erro = set(result["conta_contabil"].tolist())
        assert contas_com_erro == {"211000000", "311000000"}
