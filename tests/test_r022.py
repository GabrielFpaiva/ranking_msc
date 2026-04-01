"""Testes da regra R022 — FP válido: domínio "1" ou "2"."""

from __future__ import annotations

import math

import pandas as pd

from ranking_msc.rules.r022 import R022


def _df_com_fp(conta: str, fp: object) -> pd.DataFrame:
    """Cria DataFrame mínimo com uma conta e um valor de FP."""
    return pd.DataFrame({"conta_contabil": [conta], "fp": [fp]})


class TestR022:
    def test_fp_valor_1_sem_pendencia(self, engine_context: object) -> None:
        """FP="1" (Financeiro) é válido → nenhuma pendência."""
        df = _df_com_fp("111110200", "1")
        result = R022().execute(df, engine_context)

        assert len(result) == 0

    def test_fp_valor_2_sem_pendencia(self, engine_context: object) -> None:
        """FP="2" (Permanente) é válido → nenhuma pendência."""
        df = _df_com_fp("111110200", "2")
        result = R022().execute(df, engine_context)

        assert len(result) == 0

    def test_fp_vazio_sem_pendencia(self, engine_context: object) -> None:
        """FP="" (vazio) é tratado como não informado → nenhuma pendência."""
        df = _df_com_fp("111110200", "")
        result = R022().execute(df, engine_context)

        assert len(result) == 0

    def test_fp_ausente_nan_sem_pendencia(self, engine_context: object) -> None:
        """FP=NaN é tratado como não informado → nenhuma pendência."""
        df = _df_com_fp("111110200", math.nan)
        result = R022().execute(df, engine_context)

        assert len(result) == 0

    def test_fp_zero_sem_pendencia(self, engine_context: object) -> None:
        """FP="0" é tratado como não informado (convencão IC vazia) → nenhuma pendência."""
        df = _df_com_fp("111110200", "0")
        result = R022().execute(df, engine_context)

        assert len(result) == 0

    def test_fp_invalido_gera_erro(self, engine_context: object) -> None:
        """FP="3" está fora do domínio → ERRO."""
        df = _df_com_fp("111110200", "3")
        result = R022().execute(df, engine_context)

        assert len(result) == 1
        row = result.iloc[0]
        assert row["severidade"] == "ERRO"
        assert row["regra_id"] == "R022"
        assert row["conta_contabil"] == "111110200"

    def test_fp_letra_gera_erro(self, engine_context: object) -> None:
        """FP="A" está fora do domínio → ERRO."""
        df = _df_com_fp("111110200", "A")
        result = R022().execute(df, engine_context)

        assert len(result) == 1
        row = result.iloc[0]
        assert row["severidade"] == "ERRO"
        assert row["regra_id"] == "R022"

    def test_valor_esperado_e_encontrado(self, engine_context: object) -> None:
        """Pendência deve ter valor_esperado='1 ou 2' e valor_encontrado com o valor inválido."""
        fp_invalido = "X"
        df = _df_com_fp("111110200", fp_invalido)
        result = R022().execute(df, engine_context)

        assert len(result) == 1
        row = result.iloc[0]
        assert row["valor_esperado"] == "1 ou 2"
        assert row["valor_encontrado"] == fp_invalido
        assert fp_invalido in row["descricao"]

    def test_fp_none_sem_pendencia(self, engine_context: object) -> None:
        """FP=None é tratado como não informado → nenhuma pendência."""
        df = _df_com_fp("111110200", None)
        result = R022().execute(df, engine_context)

        assert len(result) == 0

    def test_df_sem_coluna_fp_sem_pendencia(self, engine_context: object) -> None:
        """DataFrame sem coluna fp → nenhuma pendência (regra inaplicável)."""
        df = pd.DataFrame({"conta_contabil": ["111110200"]})
        result = R022().execute(df, engine_context)

        assert len(result) == 0

    def test_multiplas_contas_deduplicado(self, engine_context: object) -> None:
        """Mesma combinação conta+fp repetida → uma única pendência por par único."""
        df = pd.DataFrame({
            "conta_contabil": ["111110200", "111110200", "211000000"],
            "fp": ["3", "3", "5"],  # conta 1 repetida, conta 2 diferente
        })
        result = R022().execute(df, engine_context)

        assert len(result) == 2

    def test_misto_valido_invalido(self, engine_context: object) -> None:
        """Contas com FP válido e inválido na mesma entrada → apenas as inválidas geram erro."""
        df = pd.DataFrame({
            "conta_contabil": ["111110200", "211000000", "311000000"],
            "fp": ["1", "2", "9"],
        })
        result = R022().execute(df, engine_context)

        assert len(result) == 1
        assert result.iloc[0]["conta_contabil"] == "311000000"
