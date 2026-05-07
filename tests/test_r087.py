"""Testes da regra R087 — Passivo (classe 2, exceto PL) com saldo devedor invertido (SIGEF V9)."""

from __future__ import annotations

from unittest.mock import patch

import pandas as pd
import pytest

from ranking_msc.rules.r087 import R087

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PCASP_MOCK = pd.DataFrame({
    "conta_contabil": [
        "211000000",  # Passivo Credora (saldo C esperado)
        "219000000",  # Passivo Credora/Devedora (aceita ambos — sem violação)
        "212000000",  # Passivo Devedora (não viola por R087 — seria R032)
        "231000000",  # PL Credora (fora do escopo de R087 — grupo 23)
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
    """DataFrame mínimo com uma linha para testes de R087."""
    return pd.DataFrame({
        "conta_contabil": [conta],
        "saldo_final_debito": [saldo_debito],
        "saldo_final_credito": [saldo_credito],
    })


@pytest.fixture(autouse=True)
def mock_pcasp():
    """Substitui load_pcasp por tabela controlada para todos os testes."""
    with patch(
        "ranking_msc.rules.r087.load_pcasp",
        return_value=_PCASP_MOCK.copy(),
    ):
        yield


# ---------------------------------------------------------------------------
# Testes de violação — deve gerar ALERTA
# ---------------------------------------------------------------------------


class TestR087Violacoes:
    def test_passivo_credora_com_saldo_devedor_gera_alerta(
        self, engine_context: object
    ) -> None:
        """Conta de Passivo NAT_SALDO=Credora com saldo devedor deve gerar ALERTA."""
        df = _df("211000000", saldo_debito=750.0, saldo_credito=0)
        result = R087().execute(df, engine_context)

        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ALERTA"
        assert result.iloc[0]["regra_id"] == "R087"
        assert "211000000" in result.iloc[0]["descricao"]
        assert "devedor" in result.iloc[0]["descricao"]
        assert "SIGEF V9" in result.iloc[0]["descricao"]
        assert result.iloc[0]["competencia"] == "2024-01"

    def test_multiplas_contas_violadas(self, engine_context: object) -> None:
        """Múltiplas contas de Passivo com saldo devedor geram pendências distintas."""
        df = pd.DataFrame({
            "conta_contabil": ["211000000", "211000000"],
            "saldo_final_debito": [100.0, 200.0],
            "saldo_final_credito": [0, 0],
        })
        result = R087().execute(df, engine_context)

        assert len(result) == 2
        assert set(result["severidade"].tolist()) == {"ALERTA"}

    def test_saldo_devedor_string_convertido(self, engine_context: object) -> None:
        """Saldo devedor recebido como string é convertido antes da comparação."""
        df = _df("211000000", saldo_debito="450.75", saldo_credito="0")
        result = R087().execute(df, engine_context)

        assert len(result) == 1
        assert "450.75" in result.iloc[0]["valor_encontrado"]


# ---------------------------------------------------------------------------
# Testes sem violação — não deve gerar pendência
# ---------------------------------------------------------------------------


class TestR087SemViolacao:
    def test_passivo_credora_com_saldo_credito_sem_pendencia(
        self, engine_context: object
    ) -> None:
        """Conta de Passivo NAT_SALDO=Credora com saldo credor é compatível."""
        df = _df("211000000", saldo_debito=0, saldo_credito=2000.0)
        result = R087().execute(df, engine_context)
        assert len(result) == 0

    def test_passivo_credora_saldo_devedor_zero_sem_pendencia(
        self, engine_context: object
    ) -> None:
        """Conta de Passivo Credora com saldo_final_debito=0 não é violação."""
        df = _df("211000000", saldo_debito=0.0, saldo_credito=500.0)
        result = R087().execute(df, engine_context)
        assert len(result) == 0

    def test_passivo_credora_devedora_com_saldo_devedor_sem_pendencia(
        self, engine_context: object
    ) -> None:
        """Conta de Passivo Credora/Devedora aceita saldo devedor — sem pendência."""
        df = _df("219000000", saldo_debito=100.0, saldo_credito=0)
        result = R087().execute(df, engine_context)
        assert len(result) == 0

    def test_passivo_devedora_com_saldo_devedor_sem_pendencia_r087(
        self, engine_context: object
    ) -> None:
        """Passivo NAT_SALDO=Devedora: R087 ignora (seria violação só de R032)."""
        df = _df("212000000", saldo_debito=500.0, saldo_credito=0)
        result = R087().execute(df, engine_context)
        assert len(result) == 0

    def test_conta_pl_excluida_do_escopo(self, engine_context: object) -> None:
        """Conta de PL (grupo 23) é excluída — tratada por R088."""
        df = _df("231000000", saldo_debito=300.0, saldo_credito=0)
        result = R087().execute(df, engine_context)
        assert len(result) == 0

    def test_conta_ativo_nao_avaliada(self, engine_context: object) -> None:
        """Conta de Ativo (classe 1) é ignorada — fora do escopo de R087."""
        df = _df("111110200", saldo_debito=0, saldo_credito=500.0)
        result = R087().execute(df, engine_context)
        assert len(result) == 0

    def test_conta_ausente_no_pcasp_ignorada(self, engine_context: object) -> None:
        """Conta não existente no PCASP é ignorada — R010 trata essa violação."""
        df = _df("200000000", saldo_debito=999.0, saldo_credito=0)
        result = R087().execute(df, engine_context)
        assert len(result) == 0

    def test_df_vazio_retorna_sem_pendencia(self, engine_context: object) -> None:
        """DataFrame vazio não gera pendências."""
        df = pd.DataFrame({
            "conta_contabil": [],
            "saldo_final_debito": [],
            "saldo_final_credito": [],
        })
        result = R087().execute(df, engine_context)
        assert len(result) == 0

    def test_pcasp_sem_nat_saldo_retorna_sem_pendencia(
        self, engine_context: object
    ) -> None:
        """PCASP sem coluna nat_saldo desativa a regra silenciosamente."""
        pcasp_sem_nat = pd.DataFrame({"conta_contabil": ["211000000"]})
        df = _df("211000000", saldo_debito=750.0, saldo_credito=0)

        with patch("ranking_msc.rules.r087.load_pcasp", return_value=pcasp_sem_nat):
            result = R087().execute(df, engine_context)
        assert len(result) == 0
