"""Testes da regra R055 — Contas de resultado zeradas no mes 01."""

from __future__ import annotations

import pandas as pd
import pytest

from ranking_msc.config.settings import Settings
from ranking_msc.engine.executor import EngineContext
from ranking_msc.rules.r055 import R055


@pytest.fixture
def ctx_janeiro() -> EngineContext:
    """EngineContext com competencia janeiro."""
    return EngineContext(
        competencia="2025-01",
        siconfi="2507507EX",
        settings=Settings(),
        usuario="teste",
    )


@pytest.fixture
def ctx_fevereiro() -> EngineContext:
    """EngineContext com competencia fevereiro."""
    return EngineContext(
        competencia="2025-02",
        siconfi="2507507EX",
        settings=Settings(),
        usuario="teste",
    )


def _make_df(rows: list[dict[str, object]]) -> pd.DataFrame:
    """Cria DataFrame minimo para testes de R055."""
    return pd.DataFrame(rows)


class TestR055:
    """Testes da regra R055 — resultado zerado em janeiro."""

    def test_janeiro_resultado_zerado_sem_pendencia(self, ctx_janeiro: EngineContext) -> None:
        """Contas classe 3/4 com SI=0 em janeiro nao geram pendencia."""
        df = _make_df([
            {
                "conta_contabil": "311110100",
                "saldo_inicial_debito": 0.0,
                "saldo_inicial_credito": 0.0,
                "saldo_final_debito": 100.0,
                "saldo_final_credito": 0.0,
            },
            {
                "conta_contabil": "411110100",
                "saldo_inicial_debito": 0.0,
                "saldo_inicial_credito": 0.0,
                "saldo_final_debito": 0.0,
                "saldo_final_credito": 200.0,
            },
        ])
        result = R055().execute(df, ctx_janeiro)
        assert len(result) == 0

    def test_janeiro_resultado_nao_zerado_gera_alerta(self, ctx_janeiro: EngineContext) -> None:
        """Conta classe 3 com SI != 0 em janeiro gera ALERTA."""
        df = _make_df([
            {
                "conta_contabil": "311110100",
                "saldo_inicial_debito": 5000.0,
                "saldo_inicial_credito": 0.0,
                "saldo_final_debito": 6000.0,
                "saldo_final_credito": 0.0,
            },
        ])
        result = R055().execute(df, ctx_janeiro)
        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ALERTA"
        assert result.iloc[0]["regra_id"] == "R055"
        assert "311110100" in result.iloc[0]["descricao"]

    def test_janeiro_classe_1_2_ignoradas(self, ctx_janeiro: EngineContext) -> None:
        """Contas classe 1 e 2 com SI != 0 em janeiro nao geram pendencia."""
        df = _make_df([
            {
                "conta_contabil": "111110100",
                "saldo_inicial_debito": 9999.0,
                "saldo_inicial_credito": 0.0,
                "saldo_final_debito": 9999.0,
                "saldo_final_credito": 0.0,
            },
            {
                "conta_contabil": "211110100",
                "saldo_inicial_debito": 0.0,
                "saldo_inicial_credito": 5000.0,
                "saldo_final_debito": 0.0,
                "saldo_final_credito": 5000.0,
            },
        ])
        result = R055().execute(df, ctx_janeiro)
        assert len(result) == 0

    def test_mes_nao_janeiro_regra_nao_aplica(self, ctx_fevereiro: EngineContext) -> None:
        """Em meses diferentes de janeiro, a regra nao se aplica."""
        df = _make_df([
            {
                "conta_contabil": "311110100",
                "saldo_inicial_debito": 5000.0,
                "saldo_inicial_credito": 0.0,
                "saldo_final_debito": 6000.0,
                "saldo_final_credito": 0.0,
            },
        ])
        result = R055().execute(df, ctx_fevereiro)
        assert len(result) == 0

    def test_janeiro_multiplas_contas_resultado(self, ctx_janeiro: EngineContext) -> None:
        """Multiplas contas classe 3/4 com SI != 0 geram uma pendencia cada."""
        df = _make_df([
            {
                "conta_contabil": "311110100",
                "saldo_inicial_debito": 1000.0,
                "saldo_inicial_credito": 0.0,
                "saldo_final_debito": 1000.0,
                "saldo_final_credito": 0.0,
            },
            {
                "conta_contabil": "411110100",
                "saldo_inicial_debito": 0.0,
                "saldo_inicial_credito": 2000.0,
                "saldo_final_debito": 0.0,
                "saldo_final_credito": 2000.0,
            },
        ])
        result = R055().execute(df, ctx_janeiro)
        assert len(result) == 2
        contas = set(result["conta_contabil"])
        assert contas == {"311110100", "411110100"}

    def test_janeiro_df_vazio_sem_pendencia(self, ctx_janeiro: EngineContext) -> None:
        """DataFrame vazio retorna sem pendencias."""
        df = pd.DataFrame(columns=[
            "conta_contabil", "saldo_inicial_debito", "saldo_inicial_credito",
            "saldo_final_debito", "saldo_final_credito",
        ])
        result = R055().execute(df, ctx_janeiro)
        assert len(result) == 0

    def test_janeiro_agrega_linhas_mesma_conta(self, ctx_janeiro: EngineContext) -> None:
        """Linhas da mesma conta sao agregadas antes da verificacao."""
        df = _make_df([
            {
                "conta_contabil": "311110100",
                "saldo_inicial_debito": 500.0,
                "saldo_inicial_credito": 0.0,
                "saldo_final_debito": 500.0,
                "saldo_final_credito": 0.0,
            },
            {
                "conta_contabil": "311110100",
                "saldo_inicial_debito": 0.0,
                "saldo_inicial_credito": 500.0,
                "saldo_final_debito": 0.0,
                "saldo_final_credito": 500.0,
            },
        ])
        # SI_D=500, SI_C=500 → liquido=0 → sem pendencia
        result = R055().execute(df, ctx_janeiro)
        assert len(result) == 0
