"""Testes para as regras R050, R051 e R052.

Dimensão: Interconta
- R050: Ativo (classe 1) = Passivo + PL (classe 2)
- R051: VPA (classe 4) - VPD (classe 3) = Resultado (delta grupo 2.1.4)
- R052: Controles devedores (classe 7) = Controles credores (classe 8)
"""

from __future__ import annotations

import pandas as pd

from ranking_msc.engine.executor import EngineContext
from ranking_msc.rules.r050 import R050

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _df_r050(
    conta1: str = "111110200",
    sf_d_1: float = 1000.0,
    sf_c_1: float = 0.0,
    conta2: str = "211110100",
    sf_d_2: float = 0.0,
    sf_c_2: float = 1000.0,
) -> pd.DataFrame:
    """Cria DataFrame mínimo para testes de R050 (classes 1 e 2)."""
    return pd.DataFrame([
        {
            "conta_contabil": conta1,
            "saldo_final_debito": sf_d_1,
            "saldo_final_credito": sf_c_1,
        },
        {
            "conta_contabil": conta2,
            "saldo_final_debito": sf_d_2,
            "saldo_final_credito": sf_c_2,
        },
    ])


# ---------------------------------------------------------------------------
# R050 — Ativo = Passivo + PL
# ---------------------------------------------------------------------------

class TestR050:
    """Testes da regra R050 — equação patrimonial."""

    def test_r050_balanceado_sem_pendencia(self, engine_context: EngineContext) -> None:
        """Ativo == Passivo+PL → sem pendência."""
        df = _df_r050(sf_d_1=1000.0, sf_c_2=1000.0)
        result = R050().execute(df, engine_context)
        assert len(result) == 0

    def test_r050_desequilibrio_gera_erro(self, engine_context: EngineContext) -> None:
        """Ativo != Passivo+PL → 1 pendência ERRO."""
        df = _df_r050(sf_d_1=1000.0, sf_c_2=999.0)
        result = R050().execute(df, engine_context)
        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ERRO"
        assert result.iloc[0]["regra_id"] == "R050"
        assert result.iloc[0]["conta_contabil"] == ""

    def test_r050_df_vazio_sem_pendencia(self, engine_context: EngineContext) -> None:
        """DF vazio → sem pendência."""
        df = pd.DataFrame(columns=["conta_contabil", "saldo_final_debito", "saldo_final_credito"])
        result = R050().execute(df, engine_context)
        assert len(result) == 0

    def test_r050_multiplas_contas_soma_correta(self, engine_context: EngineContext) -> None:
        """Múltiplas contas nas classes 1 e 2 somadas corretamente → sem pendência."""
        df = pd.DataFrame({
            "conta_contabil": ["111110200", "112110100", "211110100", "212110100"],
            "saldo_final_debito": [600.0, 400.0, 0.0, 0.0],
            "saldo_final_credito": [0.0, 0.0, 700.0, 300.0],
        })
        result = R050().execute(df, engine_context)
        assert len(result) == 0
