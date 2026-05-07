"""Testes da regra R088 — PL (grupo 2.3) com saldo devedor invertido (SIGEF V10)."""

from __future__ import annotations

from unittest.mock import patch

import pandas as pd
import pytest

from ranking_msc.rules.r088 import R088

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PCASP_MOCK = pd.DataFrame({
    "conta_contabil": [
        "231000000",  # PL Credora (saldo C esperado)
        "232000000",  # PL Credora/Devedora (aceita ambos — ex: Ajustes de Avaliação)
        "233000000",  # PL Devedora (não viola por R088 — seria R032)
        "211000000",  # Passivo Credora (fora do escopo — grupo 21)
        "111110200",  # Ativo Devedora (fora do escopo — classe 1)
    ],
    "nat_saldo": [
        "Credora",
        "Credora/Devedora",
        "Devedora",
        "Credora",
        "Devedora",
    ],
})


def _df(
    conta: str,
    saldo_debito: object = 0,
    saldo_credito: object = 0,
) -> pd.DataFrame:
    """DataFrame mínimo com uma linha para testes de R088."""
    return pd.DataFrame({
        "conta_contabil": [conta],
        "saldo_final_debito": [saldo_debito],
        "saldo_final_credito": [saldo_credito],
    })


@pytest.fixture(autouse=True)
def mock_pcasp():
    """Substitui load_pcasp por tabela controlada para todos os testes."""
    with patch(
        "ranking_msc.rules.r088.load_pcasp",
        return_value=_PCASP_MOCK.copy(),
    ):
        yield


# ---------------------------------------------------------------------------
# Testes de violação — deve gerar ALERTA
# ---------------------------------------------------------------------------


class TestR088Violacoes:
    def test_pl_credora_com_saldo_devedor_gera_alerta(
        self, engine_context: object
    ) -> None:
        """Conta de PL NAT_SALDO=Credora com saldo devedor deve gerar ALERTA."""
        df = _df("231000000", saldo_debito=300.0, saldo_credito=0)
        result = R088().execute(df, engine_context)

        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ALERTA"
        assert result.iloc[0]["regra_id"] == "R088"
        assert "231000000" in result.iloc[0]["descricao"]
        assert "devedor" in result.iloc[0]["descricao"]
        assert "SIGEF V10" in result.iloc[0]["descricao"]
        assert result.iloc[0]["competencia"] == "2024-01"

    def test_multiplas_contas_pl_violadas(self, engine_context: object) -> None:
        """Múltiplas contas de PL com saldo devedor geram pendências distintas."""
        df = pd.DataFrame({
            "conta_contabil": ["231000000", "231000000"],
            "saldo_final_debito": [100.0, 200.0],
            "saldo_final_credito": [0, 0],
        })
        result = R088().execute(df, engine_context)

        assert len(result) == 2
        assert set(result["severidade"].tolist()) == {"ALERTA"}

    def test_saldo_devedor_string_convertido(self, engine_context: object) -> None:
        """Saldo devedor recebido como string é convertido antes da comparação."""
        df = _df("231000000", saldo_debito="1250.00", saldo_credito="0")
        result = R088().execute(df, engine_context)

        assert len(result) == 1
        assert "1250.00" in result.iloc[0]["valor_encontrado"]


# ---------------------------------------------------------------------------
# Testes sem violação — não deve gerar pendência
# ---------------------------------------------------------------------------


class TestR088SemViolacao:
    def test_pl_credora_com_saldo_credito_sem_pendencia(
        self, engine_context: object
    ) -> None:
        """Conta de PL NAT_SALDO=Credora com saldo credor é compatível."""
        df = _df("231000000", saldo_debito=0, saldo_credito=5000.0)
        result = R088().execute(df, engine_context)
        assert len(result) == 0

    def test_pl_credora_saldo_devedor_zero_sem_pendencia(
        self, engine_context: object
    ) -> None:
        """Conta de PL Credora com saldo_final_debito=0 não é violação."""
        df = _df("231000000", saldo_debito=0.0, saldo_credito=100.0)
        result = R088().execute(df, engine_context)
        assert len(result) == 0

    def test_pl_credora_devedora_com_saldo_devedor_sem_pendencia(
        self, engine_context: object
    ) -> None:
        """Conta de PL Credora/Devedora (ex: Ajustes) aceita saldo devedor — sem pendência."""
        df = _df("232000000", saldo_debito=1000.0, saldo_credito=0)
        result = R088().execute(df, engine_context)
        assert len(result) == 0

    def test_pl_devedora_com_saldo_devedor_sem_pendencia_r088(
        self, engine_context: object
    ) -> None:
        """PL NAT_SALDO=Devedora: R088 ignora (seria violação de R032)."""
        df = _df("233000000", saldo_debito=500.0, saldo_credito=0)
        result = R088().execute(df, engine_context)
        assert len(result) == 0

    def test_conta_passivo_sem_pl_excluida(self, engine_context: object) -> None:
        """Conta de Passivo comum (grupo ≠ 23) é ignorada — tratada por R087."""
        df = _df("211000000", saldo_debito=750.0, saldo_credito=0)
        result = R088().execute(df, engine_context)
        assert len(result) == 0

    def test_conta_ativo_nao_avaliada(self, engine_context: object) -> None:
        """Conta de Ativo (classe 1) é ignorada — fora do escopo de R088."""
        df = _df("111110200", saldo_debito=0, saldo_credito=500.0)
        result = R088().execute(df, engine_context)
        assert len(result) == 0

    def test_conta_ausente_no_pcasp_ignorada(self, engine_context: object) -> None:
        """Conta não existente no PCASP é ignorada — R010 trata essa violação."""
        df = _df("230000000", saldo_debito=999.0, saldo_credito=0)
        result = R088().execute(df, engine_context)
        assert len(result) == 0

    def test_df_vazio_retorna_sem_pendencia(self, engine_context: object) -> None:
        """DataFrame vazio não gera pendências."""
        df = pd.DataFrame({
            "conta_contabil": [],
            "saldo_final_debito": [],
            "saldo_final_credito": [],
        })
        result = R088().execute(df, engine_context)
        assert len(result) == 0

    def test_pcasp_sem_nat_saldo_retorna_sem_pendencia(
        self, engine_context: object
    ) -> None:
        """PCASP sem coluna nat_saldo desativa a regra silenciosamente."""
        pcasp_sem_nat = pd.DataFrame({"conta_contabil": ["231000000"]})
        df = _df("231000000", saldo_debito=300.0, saldo_credito=0)

        with patch("ranking_msc.rules.r088.load_pcasp", return_value=pcasp_sem_nat):
            result = R088().execute(df, engine_context)
        assert len(result) == 0
