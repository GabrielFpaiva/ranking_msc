"""Testes para as regras R040, R041, R042 e R043.

Dimensão: Completude
- R040: contas patrimoniais devem ter saldo inicial
- R041: contas patrimoniais devem ter saldo final
- R042: contas de resultado não devem ter saldo (apenas movimentos)
- R043: nenhuma conta deve estar totalmente zerada
"""

from __future__ import annotations

import pandas as pd

from ranking_msc.engine.executor import EngineContext
from ranking_msc.rules.r040 import R040
from ranking_msc.rules.r041 import R041
from ranking_msc.rules.r042 import R042
from ranking_msc.rules.r043 import R043

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_df(**kwargs: object) -> pd.DataFrame:
    """Cria DataFrame mínimo com colunas de valor, presença e conta_contabil."""
    defaults: dict[str, object] = {
        "conta_contabil": "1.1.1.1.1.01.00",
        "saldo_inicial_debito": 0.0,
        "saldo_inicial_credito": 0.0,
        "movimento_debito": 0.0,
        "movimento_credito": 0.0,
        "saldo_final_debito": 0.0,
        "saldo_final_credito": 0.0,
        "_has_saldo_inicial": False,
        "_has_saldo_final": False,
    }
    defaults.update(kwargs)
    return pd.DataFrame([defaults])


# ---------------------------------------------------------------------------
# R040 — Contas patrimoniais têm saldo inicial
# ---------------------------------------------------------------------------

class TestR040:
    """Testes da regra R040 — saldo inicial de contas patrimoniais."""

    def test_conta_patrimonial_com_saldo_inicial_sem_pendencia(
        self, engine_context: EngineContext
    ) -> None:
        """Conta patrimonial com entrada beginning_balance presente → sem pendência."""
        df = _make_df(
            conta_contabil="1.1.1.1.1.01.00",
            saldo_inicial_debito=1000.0,
            _has_saldo_inicial=True,
        )
        result = R040().execute(df, engine_context)
        assert len(result) == 0

    def test_conta_patrimonial_si_credito_sem_pendencia(
        self, engine_context: EngineContext
    ) -> None:
        """Conta patrimonial com entrada beginning_balance credito presente → sem pendência."""
        df = _make_df(
            conta_contabil="2.1.1.1.1.01.00",
            saldo_inicial_credito=500.0,
            _has_saldo_inicial=True,
        )
        result = R040().execute(df, engine_context)
        assert len(result) == 0

    def test_conta_patrimonial_si_zerado_gera_alerta(
        self, engine_context: EngineContext
    ) -> None:
        """Conta patrimonial sem entrada beginning_balance no CSV → ALERTA."""
        df = _make_df(
            conta_contabil="1.1.1.1.1.01.00",
            saldo_final_debito=500.0,
            _has_saldo_inicial=False,  # nenhuma entrada beginning_balance
        )
        result = R040().execute(df, engine_context)
        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ALERTA"
        assert result.iloc[0]["regra_id"] == "R040"
        assert result.iloc[0]["conta_contabil"] == "1.1.1.1.1.01.00"

    def test_conta_resultado_ignorada(self, engine_context: EngineContext) -> None:
        """Conta de resultado (classe 3) zerada → R040 não reporta."""
        df = _make_df(
            conta_contabil="3.1.1.1.1.01.00",
            saldo_inicial_debito=0.0,
            saldo_inicial_credito=0.0,
        )
        result = R040().execute(df, engine_context)
        assert len(result) == 0

    def test_multiplas_linhas_mesma_conta_agrega_antes_de_validar(
        self, engine_context: EngineContext
    ) -> None:
        """Conta com SI em uma IC, outra IC sem SI → any(_has_saldo_inicial)=True → sem ALERTA."""
        df = pd.DataFrame([
            {
                "conta_contabil": "1.1.1.1.1.01.00",
                "saldo_inicial_debito": 500.0,
                "saldo_inicial_credito": 0.0,
                "movimento_debito": 0.0,
                "movimento_credito": 0.0,
                "saldo_final_debito": 500.0,
                "saldo_final_credito": 0.0,
                "_has_saldo_inicial": True,
                "_has_saldo_final": True,
            },
            {
                "conta_contabil": "1.1.1.1.1.01.00",
                "saldo_inicial_debito": 0.0,
                "saldo_inicial_credito": 0.0,
                "movimento_debito": 100.0,
                "movimento_credito": 100.0,
                "saldo_final_debito": 0.0,
                "saldo_final_credito": 0.0,
                "_has_saldo_inicial": False,
                "_has_saldo_final": False,
            },
        ])
        result = R040().execute(df, engine_context)
        assert len(result) == 0

    def test_df_vazio_retorna_sem_pendencia(self, engine_context: EngineContext) -> None:
        """DataFrame vazio → sem pendência."""
        df = pd.DataFrame(
            columns=["conta_contabil", "_has_saldo_inicial", "_has_saldo_final"]
        )
        result = R040().execute(df, engine_context)
        assert len(result) == 0

    def test_conta_patrimonial_si_zero_mas_presente_nao_gera_alerta(
        self, engine_context: EngineContext
    ) -> None:
        """Conta patrimonial com beginning_balance=0 mas entrada presente → sem ALERTA."""
        df = _make_df(
            conta_contabil="1.1.1.1.1.01.00",
            saldo_inicial_debito=0.0,   # valor zero (legítimo)
            _has_saldo_inicial=True,    # mas a entrada existe no CSV
        )
        result = R040().execute(df, engine_context)
        assert len(result) == 0

    def test_classes_5_e_6_sao_patrimoniais(
        self, engine_context: EngineContext
    ) -> None:
        """Contas das classes 5 e 6 (controle) também são patrimoniais para R040."""
        df_5 = _make_df(conta_contabil="5.1.1.1.1.01.00")
        df_6 = _make_df(conta_contabil="6.1.1.1.1.01.00")
        result_5 = R040().execute(df_5, engine_context)
        result_6 = R040().execute(df_6, engine_context)
        assert len(result_5) == 1
        assert len(result_6) == 1


# ---------------------------------------------------------------------------
# R041 — Contas patrimoniais têm saldo final
# ---------------------------------------------------------------------------

class TestR041:
    """Testes da regra R041 — saldo final de contas patrimoniais."""

    def test_conta_patrimonial_com_saldo_final_sem_pendencia(
        self, engine_context: EngineContext
    ) -> None:
        """Conta patrimonial com entrada ending_balance presente → sem pendência."""
        df = _make_df(
            conta_contabil="1.1.1.1.1.01.00",
            saldo_final_debito=2000.0,
            _has_saldo_final=True,
        )
        result = R041().execute(df, engine_context)
        assert len(result) == 0

    def test_conta_patrimonial_sf_credito_sem_pendencia(
        self, engine_context: EngineContext
    ) -> None:
        """Conta patrimonial com entrada ending_balance crédito presente → sem pendência."""
        df = _make_df(
            conta_contabil="2.1.1.1.1.01.00",
            saldo_final_credito=750.0,
            _has_saldo_final=True,
        )
        result = R041().execute(df, engine_context)
        assert len(result) == 0

    def test_conta_patrimonial_sf_zerado_gera_alerta(
        self, engine_context: EngineContext
    ) -> None:
        """Conta patrimonial sem entrada ending_balance no CSV → ALERTA."""
        df = _make_df(
            conta_contabil="1.1.1.1.1.01.00",
            saldo_inicial_debito=1000.0,
            _has_saldo_inicial=True,
            _has_saldo_final=False,  # nenhuma entrada ending_balance
        )
        result = R041().execute(df, engine_context)
        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ALERTA"
        assert result.iloc[0]["regra_id"] == "R041"
        assert result.iloc[0]["conta_contabil"] == "1.1.1.1.1.01.00"

    def test_conta_resultado_ignorada(self, engine_context: EngineContext) -> None:
        """Conta de resultado (classe 4) zerada → R041 não reporta."""
        df = _make_df(
            conta_contabil="4.1.1.1.1.01.00",
            saldo_final_debito=0.0,
            saldo_final_credito=0.0,
        )
        result = R041().execute(df, engine_context)
        assert len(result) == 0

    def test_multiplas_linhas_mesma_conta_agrega_antes_de_validar(
        self, engine_context: EngineContext
    ) -> None:
        """SF em uma IC, outra IC sem SF → any(_has_saldo_final)=True → sem ALERTA."""
        df = pd.DataFrame([
            {
                "conta_contabil": "2.1.1.1.1.01.00",
                "saldo_inicial_debito": 0.0,
                "saldo_inicial_credito": 300.0,
                "movimento_debito": 0.0,
                "movimento_credito": 0.0,
                "saldo_final_debito": 0.0,
                "saldo_final_credito": 300.0,
                "_has_saldo_inicial": True,
                "_has_saldo_final": True,
            },
            {
                "conta_contabil": "2.1.1.1.1.01.00",
                "saldo_inicial_debito": 0.0,
                "saldo_inicial_credito": 0.0,
                "movimento_debito": 50.0,
                "movimento_credito": 0.0,
                "saldo_final_debito": 0.0,
                "saldo_final_credito": 0.0,
                "_has_saldo_inicial": False,
                "_has_saldo_final": False,
            },
        ])
        result = R041().execute(df, engine_context)
        assert len(result) == 0

    def test_df_vazio_retorna_sem_pendencia(self, engine_context: EngineContext) -> None:
        """DataFrame vazio → sem pendência."""
        df = pd.DataFrame(
            columns=["conta_contabil", "_has_saldo_inicial", "_has_saldo_final"]
        )
        result = R041().execute(df, engine_context)
        assert len(result) == 0

    def test_conta_patrimonial_sf_zero_mas_presente_nao_gera_alerta(
        self, engine_context: EngineContext
    ) -> None:
        """Conta patrimonial com ending_balance=0 mas entrada presente → sem ALERTA."""
        df = _make_df(
            conta_contabil="2.1.1.1.1.01.00",
            saldo_final_credito=0.0,    # valor zero (legítimo)
            _has_saldo_final=True,      # mas a entrada existe no CSV
        )
        result = R041().execute(df, engine_context)
        assert len(result) == 0

    def test_multiplas_contas_apenas_sem_entrada_sf_reportadas(
        self, engine_context: EngineContext
    ) -> None:
        """Duas contas patrimoniais: uma com ending_balance, outra sem → só a ausente reportada."""
        df = pd.DataFrame([
            {
                "conta_contabil": "1.1.1.1.1.01.00",
                "saldo_inicial_debito": 1000.0,
                "saldo_inicial_credito": 0.0,
                "movimento_debito": 0.0,
                "movimento_credito": 0.0,
                "saldo_final_debito": 1000.0,
                "saldo_final_credito": 0.0,
                "_has_saldo_inicial": True,
                "_has_saldo_final": True,
            },
            {
                "conta_contabil": "1.1.1.1.1.02.00",
                "saldo_inicial_debito": 500.0,
                "saldo_inicial_credito": 0.0,
                "movimento_debito": 0.0,
                "movimento_credito": 0.0,
                "saldo_final_debito": 0.0,
                "saldo_final_credito": 0.0,
                "_has_saldo_inicial": True,
                "_has_saldo_final": False,  # sem entrada ending_balance
            },
        ])
        result = R041().execute(df, engine_context)
        assert len(result) == 1
        assert result.iloc[0]["conta_contabil"] == "1.1.1.1.1.02.00"


# ---------------------------------------------------------------------------
# R042 — Contas de resultado sem saldo (apenas movimentos)
# ---------------------------------------------------------------------------

class TestR042:
    """Testes da regra R042 — contas de resultado sem saldo."""

    def test_conta_resultado_apenas_movimentos_sem_pendencia(
        self, engine_context: EngineContext
    ) -> None:
        """Conta de resultado sem entradas beginning/ending_balance → sem pendência."""
        df = _make_df(
            conta_contabil="3.1.1.1.1.01.00",
            movimento_debito=1000.0,
            movimento_credito=800.0,
            _has_saldo_inicial=False,
            _has_saldo_final=False,
        )
        result = R042().execute(df, engine_context)
        assert len(result) == 0

    def test_conta_resultado_com_si_gera_alerta(
        self, engine_context: EngineContext
    ) -> None:
        """Conta de resultado com entrada beginning_balance presente → ALERTA."""
        df = _make_df(
            conta_contabil="3.1.1.1.1.01.00",
            saldo_inicial_debito=500.0,
            movimento_debito=1000.0,
            movimento_credito=800.0,
            _has_saldo_inicial=True,
        )
        result = R042().execute(df, engine_context)
        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ALERTA"
        assert result.iloc[0]["regra_id"] == "R042"
        assert result.iloc[0]["valor_encontrado"] == "saldo inicial"

    def test_conta_resultado_com_sf_gera_alerta(
        self, engine_context: EngineContext
    ) -> None:
        """Conta de resultado com entrada ending_balance presente → ALERTA."""
        df = _make_df(
            conta_contabil="4.1.1.1.1.01.00",
            movimento_debito=800.0,
            movimento_credito=1000.0,
            saldo_final_credito=200.0,
            _has_saldo_final=True,
        )
        result = R042().execute(df, engine_context)
        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ALERTA"
        assert result.iloc[0]["regra_id"] == "R042"

    def test_conta_resultado_si_zero_mas_presente_gera_alerta(
        self, engine_context: EngineContext
    ) -> None:
        """Conta de resultado com beginning_balance=0 mas entrada presente → ALERTA."""
        df = _make_df(
            conta_contabil="3.1.1.1.1.01.00",
            saldo_inicial_debito=0.0,   # valor zero
            movimento_debito=500.0,
            _has_saldo_inicial=True,    # mas a entrada existe no CSV
        )
        result = R042().execute(df, engine_context)
        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ALERTA"
        assert result.iloc[0]["regra_id"] == "R042"

    def test_conta_patrimonial_ignorada(self, engine_context: EngineContext) -> None:
        """Conta patrimonial (classe 1) com saldo → R042 não reporta."""
        df = _make_df(
            conta_contabil="1.1.1.1.1.01.00",
            saldo_inicial_debito=1000.0,
            saldo_final_debito=1000.0,
            _has_saldo_inicial=True,
            _has_saldo_final=True,
        )
        result = R042().execute(df, engine_context)
        assert len(result) == 0

    def test_conta_resultado_totalmente_zerada_sem_pendencia(
        self, engine_context: EngineContext
    ) -> None:
        """Conta de resultado sem nenhuma entrada de saldo → R042 não reporta."""
        df = _make_df(
            conta_contabil="3.1.1.1.1.01.00",
            _has_saldo_inicial=False,
            _has_saldo_final=False,
        )
        result = R042().execute(df, engine_context)
        assert len(result) == 0

    def test_multiplas_linhas_mesma_conta_agrupa_antes_de_validar(
        self, engine_context: EngineContext
    ) -> None:
        """Uma IC com beginning_balance, outra sem → any(_has_saldo_inicial)=True → ALERTA."""
        df = pd.DataFrame([
            {
                "conta_contabil": "3.1.1.1.1.01.00",
                "saldo_inicial_debito": 100.0,
                "saldo_inicial_credito": 0.0,
                "movimento_debito": 500.0,
                "movimento_credito": 0.0,
                "saldo_final_debito": 0.0,
                "saldo_final_credito": 0.0,
                "_has_saldo_inicial": True,
                "_has_saldo_final": False,
            },
            {
                "conta_contabil": "3.1.1.1.1.01.00",
                "saldo_inicial_debito": 0.0,
                "saldo_inicial_credito": 0.0,
                "movimento_debito": 0.0,
                "movimento_credito": 500.0,
                "saldo_final_debito": 0.0,
                "saldo_final_credito": 0.0,
                "_has_saldo_inicial": False,
                "_has_saldo_final": False,
            },
        ])
        result = R042().execute(df, engine_context)
        assert len(result) == 1

    def test_df_vazio_retorna_sem_pendencia(self, engine_context: EngineContext) -> None:
        """DataFrame vazio → sem pendência."""
        df = pd.DataFrame(
            columns=[
                "conta_contabil", "_has_saldo_inicial", "_has_saldo_final",
                "saldo_inicial_debito", "saldo_inicial_credito",
                "saldo_final_debito", "saldo_final_credito",
            ]
        )
        result = R042().execute(df, engine_context)
        assert len(result) == 0

    def test_df_sem_colunas_saldo_nao_crasha(self, engine_context: EngineContext) -> None:
        """DataFrame sem colunas de saldo (apenas presença) → R042 não crasha."""
        df = pd.DataFrame([{
            "conta_contabil": "3.1.1.1.1.01.00",
            "_has_saldo_inicial": True,
            "_has_saldo_final": False,
        }])
        result = R042().execute(df, engine_context)
        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ALERTA"


# ---------------------------------------------------------------------------
# R043 — Conta totalmente zerada
# ---------------------------------------------------------------------------

class TestR043:
    """Testes da regra R043 — conta totalmente zerada."""

    def test_conta_com_algum_valor_sem_pendencia(
        self, engine_context: EngineContext
    ) -> None:
        """Conta com pelo menos um valor ≠ 0 → sem pendência."""
        df = _make_df(conta_contabil="1.1.1.1.1.01.00", movimento_debito=500.0)
        result = R043().execute(df, engine_context)
        assert len(result) == 0

    def test_conta_totalmente_zerada_gera_info(
        self, engine_context: EngineContext
    ) -> None:
        """Conta com todos os valores zerados → INFO."""
        df = _make_df(conta_contabil="1.1.1.1.1.01.00")
        result = R043().execute(df, engine_context)
        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "INFO"
        assert result.iloc[0]["regra_id"] == "R043"
        assert result.iloc[0]["conta_contabil"] == "1.1.1.1.1.01.00"

    def test_conta_resultado_zerada_gera_info(
        self, engine_context: EngineContext
    ) -> None:
        """Conta de resultado zerada também gera INFO (qualquer classe)."""
        df = _make_df(conta_contabil="3.1.1.1.1.01.00")
        result = R043().execute(df, engine_context)
        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "INFO"

    def test_multiplas_contas_apenas_zeradas_reportadas(
        self, engine_context: EngineContext
    ) -> None:
        """Duas contas: uma zerada, outra com valor → apenas a zerada reportada."""
        df = pd.DataFrame([
            {
                "conta_contabil": "1.1.1.1.1.01.00",
                "saldo_inicial_debito": 1000.0,
                "saldo_inicial_credito": 0.0,
                "movimento_debito": 0.0,
                "movimento_credito": 0.0,
                "saldo_final_debito": 1000.0,
                "saldo_final_credito": 0.0,
            },
            {
                "conta_contabil": "1.1.1.1.1.02.00",
                "saldo_inicial_debito": 0.0,
                "saldo_inicial_credito": 0.0,
                "movimento_debito": 0.0,
                "movimento_credito": 0.0,
                "saldo_final_debito": 0.0,
                "saldo_final_credito": 0.0,
            },
        ])
        result = R043().execute(df, engine_context)
        assert len(result) == 1
        assert result.iloc[0]["conta_contabil"] == "1.1.1.1.1.02.00"

    def test_multiplas_linhas_mesma_conta_soma_antes_de_validar(
        self, engine_context: EngineContext
    ) -> None:
        """Conta com ICs distintos: uma linha zerada, outra com valor → não reporta."""
        df = pd.DataFrame([
            {
                "conta_contabil": "1.1.1.1.1.01.00",
                "saldo_inicial_debito": 0.0,
                "saldo_inicial_credito": 0.0,
                "movimento_debito": 0.0,
                "movimento_credito": 0.0,
                "saldo_final_debito": 0.0,
                "saldo_final_credito": 0.0,
            },
            {
                "conta_contabil": "1.1.1.1.1.01.00",
                "saldo_inicial_debito": 200.0,
                "saldo_inicial_credito": 0.0,
                "movimento_debito": 0.0,
                "movimento_credito": 0.0,
                "saldo_final_debito": 200.0,
                "saldo_final_credito": 0.0,
            },
        ])
        result = R043().execute(df, engine_context)
        assert len(result) == 0

    def test_df_sem_colunas_de_valor_retorna_info(
        self, engine_context: EngineContext
    ) -> None:
        """DataFrame sem colunas de valor → robustez: conta zerada reportada."""
        df = pd.DataFrame([{"conta_contabil": "1.1.1.1.1.01.00"}])
        result = R043().execute(df, engine_context)
        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "INFO"

    def test_df_vazio_retorna_sem_pendencia(self, engine_context: EngineContext) -> None:
        """DataFrame vazio → sem pendência."""
        df = pd.DataFrame(columns=["conta_contabil"])
        result = R043().execute(df, engine_context)
        assert len(result) == 0
