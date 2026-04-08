"""Testes da regra R069 — MSC encerramento (mes 13) com resultado zerado."""

from __future__ import annotations

import pandas as pd
import pytest

from ranking_msc.config.settings import Settings
from ranking_msc.engine.executor import EngineContext
from ranking_msc.rules.r069 import R069


@pytest.fixture
def ctx_encerramento() -> EngineContext:
    """EngineContext com competencia de encerramento (mes 13)."""
    return EngineContext(
        competencia="2025-13",
        siconfi="2507507EX",
        settings=Settings(),
        usuario="teste",
    )


@pytest.fixture
def ctx_normal() -> EngineContext:
    """EngineContext com competencia normal (nao encerramento)."""
    return EngineContext(
        competencia="2025-12",
        siconfi="2507507EX",
        settings=Settings(),
        usuario="teste",
    )


def _make_df(rows: list[dict[str, object]]) -> pd.DataFrame:
    """Cria DataFrame minimo para testes de R069."""
    return pd.DataFrame(rows)


class TestR069:
    """Testes da regra R069 — resultado zerado no encerramento."""

    def test_encerramento_resultado_zerado_sem_pendencia(
        self, ctx_encerramento: EngineContext
    ) -> None:
        """Contas classe 3/4 com SF=0 no encerramento nao geram pendencia."""
        df = _make_df([
            {
                "conta_contabil": "311110100",
                "saldo_final_debito": 0.0,
                "saldo_final_credito": 0.0,
                "saldo_inicial_debito": 100.0,
                "saldo_inicial_credito": 0.0,
            },
            {
                "conta_contabil": "411110100",
                "saldo_final_debito": 0.0,
                "saldo_final_credito": 0.0,
                "saldo_inicial_debito": 0.0,
                "saldo_inicial_credito": 200.0,
            },
        ])
        result = R069().execute(df, ctx_encerramento)
        assert len(result) == 0

    def test_encerramento_resultado_nao_zerado_gera_alerta(
        self, ctx_encerramento: EngineContext
    ) -> None:
        """Conta classe 4 com SF != 0 no encerramento gera ALERTA."""
        df = _make_df([
            {
                "conta_contabil": "411110100",
                "saldo_final_debito": 0.0,
                "saldo_final_credito": 3000.0,
                "saldo_inicial_debito": 0.0,
                "saldo_inicial_credito": 5000.0,
            },
        ])
        result = R069().execute(df, ctx_encerramento)
        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ALERTA"
        assert result.iloc[0]["regra_id"] == "R069"
        assert "411110100" in result.iloc[0]["descricao"]

    def test_encerramento_classe_1_2_ignoradas(self, ctx_encerramento: EngineContext) -> None:
        """Contas classe 1 e 2 com SF != 0 no encerramento nao geram pendencia."""
        df = _make_df([
            {
                "conta_contabil": "111110100",
                "saldo_final_debito": 9999.0,
                "saldo_final_credito": 0.0,
                "saldo_inicial_debito": 9999.0,
                "saldo_inicial_credito": 0.0,
            },
            {
                "conta_contabil": "211110100",
                "saldo_final_debito": 0.0,
                "saldo_final_credito": 5000.0,
                "saldo_inicial_debito": 0.0,
                "saldo_inicial_credito": 5000.0,
            },
        ])
        result = R069().execute(df, ctx_encerramento)
        assert len(result) == 0

    def test_mes_nao_13_regra_nao_aplica(self, ctx_normal: EngineContext) -> None:
        """Em meses diferentes de 13, a regra nao se aplica."""
        df = _make_df([
            {
                "conta_contabil": "311110100",
                "saldo_final_debito": 5000.0,
                "saldo_final_credito": 0.0,
                "saldo_inicial_debito": 5000.0,
                "saldo_inicial_credito": 0.0,
            },
        ])
        result = R069().execute(df, ctx_normal)
        assert len(result) == 0

    def test_encerramento_multiplas_contas_resultado(
        self, ctx_encerramento: EngineContext
    ) -> None:
        """Multiplas contas classe 3/4 com SF != 0 geram uma pendencia cada."""
        df = _make_df([
            {
                "conta_contabil": "311110100",
                "saldo_final_debito": 1000.0,
                "saldo_final_credito": 0.0,
                "saldo_inicial_debito": 1000.0,
                "saldo_inicial_credito": 0.0,
            },
            {
                "conta_contabil": "411110100",
                "saldo_final_debito": 0.0,
                "saldo_final_credito": 2000.0,
                "saldo_inicial_debito": 0.0,
                "saldo_inicial_credito": 2000.0,
            },
        ])
        result = R069().execute(df, ctx_encerramento)
        assert len(result) == 2
        contas = set(result["conta_contabil"])
        assert contas == {"311110100", "411110100"}

    def test_encerramento_df_vazio_sem_pendencia(self, ctx_encerramento: EngineContext) -> None:
        """DataFrame vazio retorna sem pendencias."""
        df = pd.DataFrame(columns=[
            "conta_contabil", "saldo_final_debito", "saldo_final_credito",
            "saldo_inicial_debito", "saldo_inicial_credito",
        ])
        result = R069().execute(df, ctx_encerramento)
        assert len(result) == 0

    def test_encerramento_agrega_linhas_mesma_conta(
        self, ctx_encerramento: EngineContext
    ) -> None:
        """Linhas da mesma conta sao agregadas antes da verificacao."""
        df = _make_df([
            {
                "conta_contabil": "311110100",
                "saldo_final_debito": 700.0,
                "saldo_final_credito": 0.0,
                "saldo_inicial_debito": 700.0,
                "saldo_inicial_credito": 0.0,
            },
            {
                "conta_contabil": "311110100",
                "saldo_final_debito": 0.0,
                "saldo_final_credito": 700.0,
                "saldo_inicial_debito": 0.0,
                "saldo_inicial_credito": 700.0,
            },
        ])
        # SF_D=700, SF_C=700 → liquido=0 → sem pendencia
        result = R069().execute(df, ctx_encerramento)
        assert len(result) == 0
