"""Testes da regra R031 — SF = SI + Movimentos."""

from __future__ import annotations

import pandas as pd

from ranking_msc.rules.r031 import R031


def _df(
    conta: str,
    si_d: float,
    si_c: float,
    mov_d: float,
    mov_c: float,
    sf_d: float,
    sf_c: float,
) -> pd.DataFrame:
    """Cria DataFrame mínimo para teste de R031."""
    return pd.DataFrame({
        "conta_contabil": [conta],
        "saldo_inicial_debito": [si_d],
        "saldo_inicial_credito": [si_c],
        "movimento_debito": [mov_d],
        "movimento_credito": [mov_c],
        "saldo_final_debito": [sf_d],
        "saldo_final_credito": [sf_c],
    })


class TestR031:
    def test_conta_devedora_sf_correto_nao_gera_pendencia(
        self, engine_context: object
    ) -> None:
        """Conta devedora com SF = SI + mov_D − mov_C exato não gera pendência."""
        # SI_net = 1000-0 = 1000; mov_net = 200-50 = 150; SF_net = 1150-0 = 1150
        df = _df("111110200", si_d=1000.0, si_c=0.0, mov_d=200.0, mov_c=50.0,
                 sf_d=1150.0, sf_c=0.0)
        result = R031().execute(df, engine_context)

        assert len(result) == 0

    def test_conta_credora_sf_correto_nao_gera_pendencia(
        self, engine_context: object
    ) -> None:
        """Conta credora com SF = SI + mov_C − mov_D exato não gera pendência."""
        # SI_net = 0-500 = -500; mov_net = 100-300 = -200; SF_net = 0-700 = -700
        df = _df("211000000", si_d=0.0, si_c=500.0, mov_d=100.0, mov_c=300.0,
                 sf_d=0.0, sf_c=700.0)
        result = R031().execute(df, engine_context)

        assert len(result) == 0

    def test_sf_incorreto_gera_erro(self, engine_context: object) -> None:
        """SF divergente de SI + movimentos gera pendência ERRO."""
        # SI_net = 1000; mov_net = +150; expected SF_net = 1150; actual SF_net = 2000 → diverge
        df = _df("111110200", si_d=1000.0, si_c=0.0, mov_d=200.0, mov_c=50.0,
                 sf_d=2000.0, sf_c=0.0)
        result = R031().execute(df, engine_context)

        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ERRO"
        assert result.iloc[0]["regra_id"] == "R031"
        assert "111110200" in result.iloc[0]["descricao"]

    def test_diferenca_dentro_tolerancia_nao_gera_pendencia(
        self, engine_context: object
    ) -> None:
        """Diferença residual ≤ 0.01 não gera pendência (tolerância de centavo)."""
        # SI=1000, mov=+150, SF=1150.005 → residual = 0.005 < 0.01
        df = _df("111110200", si_d=1000.0, si_c=0.0, mov_d=200.0, mov_c=50.0,
                 sf_d=1150.005, sf_c=0.0)
        result = R031().execute(df, engine_context)

        assert len(result) == 0

    def test_diferenca_acima_tolerancia_gera_erro(self, engine_context: object) -> None:
        """Diferença residual > 0.01 gera pendência ERRO."""
        # SI=1000, mov=+150, SF=1150.02 → residual = 0.02 > 0.01
        df = _df("111110200", si_d=1000.0, si_c=0.0, mov_d=200.0, mov_c=50.0,
                 sf_d=1150.02, sf_c=0.0)
        result = R031().execute(df, engine_context)

        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ERRO"

    def test_sf_zero_si_zero_mov_zero_nao_gera_pendencia(
        self, engine_context: object
    ) -> None:
        """Conta com todos os saldos zerados não gera pendência."""
        df = _df("111110200", si_d=0.0, si_c=0.0, mov_d=0.0, mov_c=0.0,
                 sf_d=0.0, sf_c=0.0)
        result = R031().execute(df, engine_context)

        assert len(result) == 0

    def test_multiplas_contas_apenas_a_incorreta_retorna(
        self, engine_context: object
    ) -> None:
        """Apenas a conta com SF errado aparece nas pendências."""
        df = pd.DataFrame({
            "conta_contabil": ["111110200", "211000000", "311000000"],
            "saldo_inicial_debito": [1000.0, 0.0, 500.0],
            "saldo_inicial_credito": [0.0, 800.0, 0.0],
            "movimento_debito": [200.0, 100.0, 50.0],
            "movimento_credito": [50.0, 50.0, 50.0],
            "saldo_final_debito": [1150.0, 0.0, 999.0],   # 311: expected 500, got 999 → ERRO
            "saldo_final_credito": [0.0, 750.0, 0.0],
        })
        result = R031().execute(df, engine_context)

        assert len(result) == 1
        assert result.iloc[0]["conta_contabil"] == "311000000"

    def test_dataframe_vazio_retorna_vazio(self, engine_context: object) -> None:
        """DataFrame sem linhas retorna DataFrame de pendências vazio."""
        df = pd.DataFrame(columns=[
            "conta_contabil",
            "saldo_inicial_debito", "saldo_inicial_credito",
            "movimento_debito", "movimento_credito",
            "saldo_final_debito", "saldo_final_credito",
        ])
        result = R031().execute(df, engine_context)

        assert len(result) == 0

    def test_valores_string_nao_numericos_sao_tratados_como_zero(
        self, engine_context: object
    ) -> None:
        """Valores não numéricos (ex: strings vazias) são convertidos para 0.0."""
        # SI_net=0, mov_net=0, SF_net=0 → sem pendência
        df = pd.DataFrame({
            "conta_contabil": ["111110200"],
            "saldo_inicial_debito": [""],
            "saldo_inicial_credito": [""],
            "movimento_debito": [""],
            "movimento_credito": [""],
            "saldo_final_debito": [""],
            "saldo_final_credito": [""],
        })
        result = R031().execute(df, engine_context)

        assert len(result) == 0

    def test_mesmo_combo_conta_ic_em_multiplas_linhas_agrega_antes_de_validar(
        self, engine_context: object
    ) -> None:
        """Mesmo combo CONTA+IC dividido em 2 linhas não gera falso ERRO.

        O pipeline pode representar um combo (ex: PO;FR vs PO;;FR) como linhas
        separadas após normalize_ic. A regra deve agregar antes de validar.
        SI_total=1000, mov_total=+150, SF_total=1150 → sem pendência.
        """
        df = pd.DataFrame({
            "conta_contabil": ["111110200", "111110200"],
            "po": ["10131", "10131"],
            "fr": ["1500", "1500"],
            "saldo_inicial_debito":  [600.0,  400.0],   # total SI_D = 1000
            "saldo_inicial_credito": [0.0,    0.0],
            "movimento_debito":      [120.0,  80.0],    # total mov_D = 200
            "movimento_credito":     [30.0,   20.0],    # total mov_C = 50  → mov_net = 150
            "saldo_final_debito":    [690.0,  460.0],   # total SF_D = 1150
            "saldo_final_credito":   [0.0,    0.0],
        })
        result = R031().execute(df, engine_context)

        assert len(result) == 0

    def test_resultado_contem_valores_esperado_e_encontrado(
        self, engine_context: object
    ) -> None:
        """Pendência deve conter valor_esperado (SF_net esperado) e valor_encontrado."""
        df = _df("111110200", si_d=1000.0, si_c=0.0, mov_d=200.0, mov_c=50.0,
                 sf_d=2000.0, sf_c=0.0)
        result = R031().execute(df, engine_context)

        assert len(result) == 1
        assert result.iloc[0]["valor_esperado"] is not None
        assert result.iloc[0]["valor_encontrado"] is not None
        assert result.iloc[0]["competencia"] == "2024-01"
