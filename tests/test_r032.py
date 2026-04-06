"""Testes da regra R032 — Natureza do saldo compatível com conta."""

from __future__ import annotations

from unittest.mock import patch

import pandas as pd
import pytest

from ranking_msc.exceptions import ConfigError
from ranking_msc.rules.r032 import R032

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PCASP_MOCK = pd.DataFrame({
    "conta_contabil": ["111110200", "211000000", "311000000", "999999999"],
    "nat_saldo": ["Devedora", "Credora", "Credora/Devedora", "Devedora"],
})


def _df(conta: str, saldo_debito: object = 0, saldo_credito: object = 0) -> pd.DataFrame:
    """DataFrame mínimo com uma linha para testes de R032."""
    return pd.DataFrame({
        "conta_contabil": [conta],
        "saldo_final_debito": [saldo_debito],
        "saldo_final_credito": [saldo_credito],
    })


@pytest.fixture(autouse=True)
def mock_pcasp():
    """Substitui load_pcasp por tabela controlada para todos os testes."""
    with patch(
        "ranking_msc.rules.r032.load_pcasp",
        return_value=_PCASP_MOCK.copy(),
    ):
        yield


# ---------------------------------------------------------------------------
# Testes de violação — deve gerar ALERTA
# ---------------------------------------------------------------------------


class TestR032Violacoes:
    def test_devedora_com_saldo_credito_gera_alerta(
        self, engine_context: object
    ) -> None:
        """Conta Devedora com saldo credor deve gerar ALERTA."""
        df = _df("111110200", saldo_debito=0, saldo_credito=100.0)
        result = R032().execute(df, engine_context)

        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ALERTA"
        assert result.iloc[0]["regra_id"] == "R032"
        assert "Devedora" in result.iloc[0]["descricao"]
        assert "111110200" in result.iloc[0]["descricao"]
        assert result.iloc[0]["competencia"] == "2024-01"

    def test_credora_com_saldo_devedor_gera_alerta(
        self, engine_context: object
    ) -> None:
        """Conta Credora com saldo devedor deve gerar ALERTA."""
        df = _df("211000000", saldo_debito=50.0, saldo_credito=0)
        result = R032().execute(df, engine_context)

        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ALERTA"
        assert result.iloc[0]["regra_id"] == "R032"
        assert "Credora" in result.iloc[0]["descricao"]
        assert "211000000" in result.iloc[0]["descricao"]
        assert result.iloc[0]["competencia"] == "2024-01"

    def test_multiplas_linhas_violadas_geram_pendencias_distintas(
        self, engine_context: object
    ) -> None:
        """Múltiplas linhas com natureza invertida geram uma pendência por linha."""
        df = pd.DataFrame({
            "conta_contabil": ["111110200", "211000000"],
            "saldo_final_debito": [0, 30.0],
            "saldo_final_credito": [200.0, 0],
        })
        result = R032().execute(df, engine_context)

        assert len(result) == 2
        assert set(result["severidade"].tolist()) == {"ALERTA"}

    def test_devedora_com_ambos_saldos_gera_alerta_pelo_credito(
        self, engine_context: object
    ) -> None:
        """Conta Devedora com ambos os saldos: o credor é a violação."""
        df = _df("111110200", saldo_debito=100.0, saldo_credito=50.0)
        result = R032().execute(df, engine_context)

        assert len(result) == 1
        assert "saldo credor" in result.iloc[0]["descricao"]


# ---------------------------------------------------------------------------
# Testes sem violação — não deve gerar pendência
# ---------------------------------------------------------------------------


class TestR032SemViolacao:
    def test_devedora_com_saldo_devedor_sem_pendencia(
        self, engine_context: object
    ) -> None:
        """Conta Devedora com saldo devedor é compatível — sem pendência."""
        df = _df("111110200", saldo_debito=200.0, saldo_credito=0)
        result = R032().execute(df, engine_context)
        assert len(result) == 0

    def test_credora_com_saldo_credito_sem_pendencia(
        self, engine_context: object
    ) -> None:
        """Conta Credora com saldo credor é compatível — sem pendência."""
        df = _df("211000000", saldo_debito=0, saldo_credito=300.0)
        result = R032().execute(df, engine_context)
        assert len(result) == 0

    def test_credora_devedora_com_qualquer_saldo_sem_pendencia(
        self, engine_context: object
    ) -> None:
        """Conta Credora/Devedora aceita qualquer natureza — sem pendência."""
        df = _df("311000000", saldo_debito=50.0, saldo_credito=80.0)
        result = R032().execute(df, engine_context)
        assert len(result) == 0

    def test_saldo_zero_nao_gera_alerta(self, engine_context: object) -> None:
        """Conta Devedora com saldo credor zero não gera pendência."""
        df = _df("111110200", saldo_debito=100.0, saldo_credito=0.0)
        result = R032().execute(df, engine_context)
        assert len(result) == 0

    def test_conta_ausente_no_pcasp_ignorada(self, engine_context: object) -> None:
        """Conta não existente no PCASP é ignorada — R010 trata essa violação."""
        df = _df("000000000", saldo_debito=0, saldo_credito=999.0)
        result = R032().execute(df, engine_context)
        assert len(result) == 0

    def test_df_vazio_retorna_sem_pendencia(self, engine_context: object) -> None:
        """DataFrame vazio não gera pendências."""
        df = pd.DataFrame({
            "conta_contabil": [],
            "saldo_final_debito": [],
            "saldo_final_credito": [],
        })
        result = R032().execute(df, engine_context)
        assert len(result) == 0

    def test_saldo_string_convertido_corretamente(
        self, engine_context: object
    ) -> None:
        """Saldos recebidos como string são convertidos antes da comparação."""
        df = _df("111110200", saldo_debito="150.0", saldo_credito="0")
        result = R032().execute(df, engine_context)
        assert len(result) == 0

    def test_pcasp_sem_coluna_nat_saldo_levanta_config_error(
        self, engine_context: object
    ) -> None:
        """PCASP sem nat_saldo deve levantar ConfigError — não retornar 0 issues (falso negativo)."""
        pcasp_sem_nat_saldo = pd.DataFrame({"conta_contabil": ["111110200", "211000000"]})
        df = _df("111110200", saldo_debito=0, saldo_credito=100.0)

        with patch("ranking_msc.rules.r032.load_pcasp", return_value=pcasp_sem_nat_saldo):
            with pytest.raises(ConfigError, match="nat_saldo"):
                R032().execute(df, engine_context)
