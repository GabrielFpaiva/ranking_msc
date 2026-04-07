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


from ranking_msc.rules.r051 import R051


def _df_r051(
    vpa_mov_c: float = 500.0,
    vpa_mov_d: float = 0.0,
    vpd_mov_d: float = 200.0,
    vpd_mov_c: float = 0.0,
    pl214_sf_c: float = 300.0,
    pl214_sf_d: float = 0.0,
    pl214_si_c: float = 0.0,
    pl214_si_d: float = 0.0,
    include_214: bool = True,
) -> pd.DataFrame:
    """Cria DataFrame mínimo para testes de R051.

    Por padrão: VPA=500, VPD=200, resultado=300, delta_PL(214)=300 → consistente.
    Conta 4 (VPA): créditos aumentam VPA. Conta 3 (VPD): débitos aumentam VPD.
    Conta 214 (Resultados Acumulados): credora — SF_C - SF_D indica variação positiva.
    """
    rows = [
        {
            "conta_contabil": "411110100",
            "movimento_debito": vpa_mov_d,
            "movimento_credito": vpa_mov_c,
            "saldo_inicial_debito": 0.0,
            "saldo_inicial_credito": 0.0,
            "saldo_final_debito": 0.0,
            "saldo_final_credito": 0.0,
        },
        {
            "conta_contabil": "311110100",
            "movimento_debito": vpd_mov_d,
            "movimento_credito": vpd_mov_c,
            "saldo_inicial_debito": 0.0,
            "saldo_inicial_credito": 0.0,
            "saldo_final_debito": 0.0,
            "saldo_final_credito": 0.0,
        },
    ]
    if include_214:
        rows.append({
            "conta_contabil": "214110100",
            "movimento_debito": 0.0,
            "movimento_credito": 0.0,
            "saldo_inicial_debito": pl214_si_d,
            "saldo_inicial_credito": pl214_si_c,
            "saldo_final_debito": pl214_sf_d,
            "saldo_final_credito": pl214_sf_c,
        })
    return pd.DataFrame(rows)


class TestR051:
    """Testes da regra R051 — VPA - VPD = Resultado."""

    def test_r051_consistente_sem_pendencia(self, engine_context: EngineContext) -> None:
        """VPA-VPD == delta_PL(2.1.4) → sem pendência."""
        # VPA_liq=500, VPD_liq=200, resultado=300, delta_PL=300-0=300
        df = _df_r051(
            vpa_mov_c=500.0, vpd_mov_d=200.0,
            pl214_sf_c=300.0, pl214_si_c=0.0,
        )
        result = R051().execute(df, engine_context)
        assert len(result) == 0

    def test_r051_divergencia_gera_alerta(self, engine_context: EngineContext) -> None:
        """VPA-VPD != delta_PL(2.1.4) → 1 pendência ALERTA."""
        # resultado=300, delta_PL=250 → divergência de 50
        df = _df_r051(
            vpa_mov_c=500.0, vpd_mov_d=200.0,
            pl214_sf_c=250.0, pl214_si_c=0.0,
        )
        result = R051().execute(df, engine_context)
        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ALERTA"
        assert result.iloc[0]["regra_id"] == "R051"
        assert result.iloc[0]["conta_contabil"] == ""

    def test_r051_sem_contas_214_sem_pendencia(self, engine_context: EngineContext) -> None:
        """Sem contas 214 no DF → sem pendência (validação ignorada)."""
        df = _df_r051(include_214=False)
        result = R051().execute(df, engine_context)
        assert len(result) == 0

    def test_r051_df_vazio_sem_pendencia(self, engine_context: EngineContext) -> None:
        """DF vazio → sem pendência."""
        df = pd.DataFrame()
        result = R051().execute(df, engine_context)
        assert len(result) == 0

    def test_r051_deficit_divergencia_gera_alerta(self, engine_context: EngineContext) -> None:
        """Déficit (VPD > VPA): resultado=-100, delta_PL=-80 → divergência de 20."""
        # VPA_liq=100, VPD_liq=200, resultado=-100, delta_PL(214): SF_C-SF_D=80 → delta=-80
        # Divergência = abs(-100 - (-80)) = 20 → ALERTA
        df = _df_r051(
            vpa_mov_c=100.0, vpd_mov_d=200.0,
            pl214_sf_c=0.0, pl214_sf_d=80.0,
            pl214_si_c=0.0, pl214_si_d=0.0,
        )
        result = R051().execute(df, engine_context)
        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ALERTA"
