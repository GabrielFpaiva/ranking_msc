"""
tests/test_r080.py
~~~~~~~~~~~~~~~~~~

Testes para a regra R080 — CONTA tem 9 dígitos numéricos.
"""

from __future__ import annotations

import pandas as pd

from ranking_msc.engine.executor import EngineContext
from ranking_msc.rules.r080 import R080


def _make_df(conta_contabil: str | None) -> pd.DataFrame:
    """Cria DataFrame mínimo com a conta informada para testar R080.

    Args:
        conta_contabil: valor do campo conta_contabil.

    Returns:
        DataFrame com uma linha e as colunas mínimas esperadas.
    """
    return pd.DataFrame({
        "conta_contabil": [conta_contabil],
        "competencia": ["2024-01"],
        "siconfi": ["250400"],
    })


class TestR080:
    """Testes para R080 — validação de formato da conta contábil."""

    def test_conta_valida_sem_pendencia(self, engine_context: EngineContext) -> None:
        """Conta com 9 dígitos numéricos não gera pendência."""
        df = _make_df("111110200")
        rule = R080()
        result = rule.execute(df, engine_context)
        assert len(result) == 0

    def test_conta_curta_gera_erro(self, engine_context: EngineContext) -> None:
        """Conta com menos de 9 dígitos gera ERRO."""
        df = _make_df("11111020")  # 8 dígitos
        rule = R080()
        result = rule.execute(df, engine_context)
        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ERRO"
        assert result.iloc[0]["regra_id"] == "R080"
        assert "8 caractere(s)" in result.iloc[0]["descricao"]

    def test_conta_com_pontos_gera_erro(self, engine_context: EngineContext) -> None:
        """Conta com pontos/letras gera ERRO."""
        df = _make_df("1.1111.02")
        rule = R080()
        result = rule.execute(df, engine_context)
        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ERRO"
        assert result.iloc[0]["regra_id"] == "R080"

    def test_conta_com_letras_gera_erro(self, engine_context: EngineContext) -> None:
        """Conta com letras gera ERRO."""
        df = _make_df("11111020A")  # 9 chars mas não numérico
        rule = R080()
        result = rule.execute(df, engine_context)
        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ERRO"

    def test_conta_longa_gera_erro(self, engine_context: EngineContext) -> None:
        """Conta com mais de 9 dígitos gera ERRO."""
        df = _make_df("1111102000")  # 10 dígitos
        rule = R080()
        result = rule.execute(df, engine_context)
        assert len(result) == 1
        assert result.iloc[0]["valor_esperado"] == "9 dígitos numéricos (ex: 111110200)"

    def test_conta_nula_nao_gera_pendencia(self, engine_context: EngineContext) -> None:
        """Conta nula/NaN não gera pendência."""
        df = _make_df(None)
        rule = R080()
        result = rule.execute(df, engine_context)
        assert len(result) == 0

    def test_sem_coluna_conta_retorna_vazio(self, engine_context: EngineContext) -> None:
        """DataFrame sem coluna conta_contabil retorna resultado vazio."""
        df = pd.DataFrame({"competencia": ["2024-01"]})
        rule = R080()
        result = rule.execute(df, engine_context)
        assert len(result) == 0

    def test_multiplas_contas_invalidas_gera_uma_pendencia_por_conta(
        self, engine_context: EngineContext
    ) -> None:
        """Várias contas inválidas distintas geram uma pendência por conta."""
        df = pd.DataFrame({
            "conta_contabil": ["11111020", "1.1111.02", "11111020"],  # 2 distintas
            "competencia": ["2024-01", "2024-01", "2024-01"],
            "siconfi": ["250400", "250400", "250400"],
        })
        rule = R080()
        result = rule.execute(df, engine_context)
        assert len(result) == 2

    def test_competencia_preenchida_na_pendencia(self, engine_context: EngineContext) -> None:
        """Pendência gerada deve conter a competência do contexto."""
        df = _make_df("11111020")
        rule = R080()
        result = rule.execute(df, engine_context)
        assert result.iloc[0]["competencia"] == "2024-01"
