"""Testes da regra R030 — Débito = Crédito por conta (fechamento patrimonial)."""

from __future__ import annotations

import pandas as pd

from ranking_msc.rules.r030 import R030


def _df(conta: str, mov_d: float, mov_c: float) -> pd.DataFrame:
    return pd.DataFrame({
        "conta_contabil": [conta],
        "movimento_debito": [mov_d],
        "movimento_credito": [mov_c],
    })


class TestR030:
    def test_debito_igual_credito_nao_gera_pendencia(self, engine_context: object) -> None:
        """Conta patrimonial com D=C exato não gera pendência."""
        df = _df("111110200", 1000.00, 1000.00)
        result = R030().execute(df, engine_context)

        assert len(result) == 0

    def test_diferenca_dentro_tolerancia_nao_gera_pendencia(
        self, engine_context: object
    ) -> None:
        """Diferença D-C dentro da tolerância de 0.01 não gera pendência."""
        df = _df("111110200", 1000.00, 999.995)
        result = R030().execute(df, engine_context)

        assert len(result) == 0

    def test_debito_diferente_credito_gera_erro(self, engine_context: object) -> None:
        """Conta patrimonial com D≠C gera pendência ERRO."""
        df = _df("111110200", 1000.00, 500.00)
        result = R030().execute(df, engine_context)

        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ERRO"
        assert result.iloc[0]["regra_id"] == "R030"
        assert "111110200" in result.iloc[0]["descricao"]

    def test_conta_nao_patrimonial_ignorada(self, engine_context: object) -> None:
        """Contas das classes 5-9 (resultado, controle) não são verificadas."""
        df = pd.DataFrame({
            "conta_contabil": ["511000000", "611000000", "711000000"],
            "movimento_debito": [1000.00, 2000.00, 3000.00],
            "movimento_credito": [0.00, 0.00, 0.00],
        })
        result = R030().execute(df, engine_context)

        assert len(result) == 0

    def test_soma_por_conta_agrega_multiplas_linhas(
        self, engine_context: object
    ) -> None:
        """Movimentos de múltiplas ICs são somados antes da comparação."""
        df = pd.DataFrame({
            "conta_contabil": ["111110200", "111110200"],
            "movimento_debito": [600.00, 400.00],   # total D = 1000.00
            "movimento_credito": [500.00, 500.00],  # total C = 1000.00
        })
        result = R030().execute(df, engine_context)

        assert len(result) == 0

    def test_multiplas_contas_com_violacao(self, engine_context: object) -> None:
        """Várias contas patrimoniais com D≠C geram uma pendência cada."""
        df = pd.DataFrame({
            "conta_contabil": ["111110200", "211000000", "311000000"],
            "movimento_debito": [1000.00, 2000.00, 500.00],
            "movimento_credito": [1000.00, 100.00, 500.00],  # 211 diverge
        })
        result = R030().execute(df, engine_context)

        assert len(result) == 1
        assert result.iloc[0]["conta_contabil"] == "211000000"
