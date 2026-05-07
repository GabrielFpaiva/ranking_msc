"""Testes da regra R086 — Ativo (classe 1) com saldo credor invertido (SIGEF V5)."""

from __future__ import annotations

from unittest.mock import patch

import pandas as pd
import pytest

from ranking_msc.rules.r086 import R086

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PCASP_MOCK = pd.DataFrame({
    "conta_contabil": [
        "111110200",  # Ativo Devedora (saldo D esperado)
        "119000000",  # Ativo retificadora Credora (saldo C esperado — sem violação)
        "118000000",  # Ativo Credora/Devedora (aceita ambos — sem violação)
        "211000000",  # Passivo Credora (fora do escopo — classe 2)
        "231000000",  # PL Credora (fora do escopo — classe 2, grupo 23)
    ],
    "nat_saldo": [
        "Devedora",
        "Credora",
        "Credora/Devedora",
        "Credora",
        "Credora",
    ],
})


def _df(
    conta: str,
    saldo_debito: object = 0,
    saldo_credito: object = 0,
) -> pd.DataFrame:
    """DataFrame mínimo com uma linha para testes de R086."""
    return pd.DataFrame({
        "conta_contabil": [conta],
        "saldo_final_debito": [saldo_debito],
        "saldo_final_credito": [saldo_credito],
    })


@pytest.fixture(autouse=True)
def mock_pcasp():
    """Substitui load_pcasp por tabela controlada para todos os testes."""
    with patch(
        "ranking_msc.rules.r086.load_pcasp",
        return_value=_PCASP_MOCK.copy(),
    ):
        yield


# ---------------------------------------------------------------------------
# Testes de violação — deve gerar ALERTA
# ---------------------------------------------------------------------------


class TestR086Violacoes:
    def test_ativo_devedora_com_saldo_credito_gera_alerta(
        self, engine_context: object
    ) -> None:
        """Conta de Ativo NAT_SALDO=Devedora com saldo credor deve gerar ALERTA."""
        df = _df("111110200", saldo_debito=0, saldo_credito=500.0)
        result = R086().execute(df, engine_context)

        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ALERTA"
        assert result.iloc[0]["regra_id"] == "R086"
        assert "111110200" in result.iloc[0]["descricao"]
        assert "credor" in result.iloc[0]["descricao"]
        assert "SIGEF V5" in result.iloc[0]["descricao"]
        assert result.iloc[0]["competencia"] == "2024-01"

    def test_multiplas_contas_violadas(self, engine_context: object) -> None:
        """Múltiplas contas de Ativo com saldo credor geram pendências distintas."""
        df = pd.DataFrame({
            "conta_contabil": ["111110200", "111110200"],
            "saldo_final_debito": [0, 0],
            "saldo_final_credito": [100.0, 200.0],
        })
        result = R086().execute(df, engine_context)

        assert len(result) == 2
        assert set(result["severidade"].tolist()) == {"ALERTA"}

    def test_saldo_credito_string_convertido(self, engine_context: object) -> None:
        """Saldo credor recebido como string é convertido antes da comparação."""
        df = _df("111110200", saldo_debito="0", saldo_credito="300.50")
        result = R086().execute(df, engine_context)

        assert len(result) == 1
        assert "300.50" in result.iloc[0]["valor_encontrado"]


# ---------------------------------------------------------------------------
# Testes sem violação — não deve gerar pendência
# ---------------------------------------------------------------------------


class TestR086SemViolacao:
    def test_ativo_devedora_com_saldo_devedor_sem_pendencia(
        self, engine_context: object
    ) -> None:
        """Conta de Ativo NAT_SALDO=Devedora com saldo devedor é compatível."""
        df = _df("111110200", saldo_debito=1000.0, saldo_credito=0)
        result = R086().execute(df, engine_context)
        assert len(result) == 0

    def test_ativo_devedora_saldo_credito_zero_sem_pendencia(
        self, engine_context: object
    ) -> None:
        """Conta de Ativo Devedora com saldo_final_credito=0 não é violação."""
        df = _df("111110200", saldo_debito=500.0, saldo_credito=0.0)
        result = R086().execute(df, engine_context)
        assert len(result) == 0

    def test_ativo_retificadora_credora_com_saldo_credito_sem_pendencia(
        self, engine_context: object
    ) -> None:
        """Conta de Ativo retificadora NAT_SALDO=Credora com saldo credor é esperado."""
        df = _df("119000000", saldo_debito=0, saldo_credito=800.0)
        result = R086().execute(df, engine_context)
        assert len(result) == 0

    def test_ativo_credora_devedora_com_saldo_credito_sem_pendencia(
        self, engine_context: object
    ) -> None:
        """Conta de Ativo Credora/Devedora aceita saldo credor — sem pendência."""
        df = _df("118000000", saldo_debito=0, saldo_credito=200.0)
        result = R086().execute(df, engine_context)
        assert len(result) == 0

    def test_conta_passivo_nao_avaliada(self, engine_context: object) -> None:
        """Conta de Passivo (classe 2) é ignorada — fora do escopo de R086."""
        df = _df("211000000", saldo_debito=0, saldo_credito=999.0)
        result = R086().execute(df, engine_context)
        assert len(result) == 0

    def test_conta_pl_nao_avaliada(self, engine_context: object) -> None:
        """Conta de PL (grupo 23) é ignorada — tratada por R088."""
        df = _df("231000000", saldo_debito=100.0, saldo_credito=0)
        result = R086().execute(df, engine_context)
        assert len(result) == 0

    def test_conta_ausente_no_pcasp_ignorada(self, engine_context: object) -> None:
        """Conta não existente no PCASP é ignorada — R010 trata essa violação."""
        df = _df("100000000", saldo_debito=0, saldo_credito=999.0)
        result = R086().execute(df, engine_context)
        assert len(result) == 0

    def test_df_vazio_retorna_sem_pendencia(self, engine_context: object) -> None:
        """DataFrame vazio não gera pendências."""
        df = pd.DataFrame({
            "conta_contabil": [],
            "saldo_final_debito": [],
            "saldo_final_credito": [],
        })
        result = R086().execute(df, engine_context)
        assert len(result) == 0

    def test_pcasp_sem_nat_saldo_retorna_sem_pendencia(
        self, engine_context: object
    ) -> None:
        """PCASP sem coluna nat_saldo desativa a regra silenciosamente."""
        pcasp_sem_nat = pd.DataFrame({"conta_contabil": ["111110200"]})
        df = _df("111110200", saldo_debito=0, saldo_credito=500.0)

        with patch("ranking_msc.rules.r086.load_pcasp", return_value=pcasp_sem_nat):
            result = R086().execute(df, engine_context)
        assert len(result) == 0
