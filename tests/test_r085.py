"""Testes para R085 — Depreciação/amortização/exaustão sem movimentação."""

from __future__ import annotations

from unittest.mock import patch

import pandas as pd

from ranking_msc.rules.r085 import R085


def _make_pcasp_com_titulo(
    titulo: str = "DEPRECIACAO ACUMULADA", nat: str = "Credora"
) -> pd.DataFrame:
    """PCASP com titulo_desc e nat_saldo."""
    return pd.DataFrame({
        "conta_contabil": ["199990100"],
        "titulo_desc": [titulo],
        "nat_saldo": [nat],
    })


def _make_pcasp_sem_titulo() -> pd.DataFrame:
    """PCASP sem coluna titulo_desc (situação atual do projeto)."""
    return pd.DataFrame({
        "conta_contabil": ["199990100"],
        "nat_saldo": ["Credora"],
    })


class TestR085:
    def test_titulo_desc_ausente_retorna_vazio(self, engine_context):
        """PCASP sem 'titulo_desc' → graceful degradation, sem crash."""
        rule = R085()
        df = pd.DataFrame({
            "conta_contabil": ["199990100"],
            "_has_period_change": [False],
        })
        with patch("ranking_msc.rules.r085.load_pcasp", return_value=_make_pcasp_sem_titulo()):
            result = rule.execute(df, engine_context)
        assert len(result) == 0

    def test_conta_deprec_sem_pc_gera_alerta(self, engine_context):
        """Conta de depreciação sem period_change → ALERTA."""
        rule = R085()
        df = pd.DataFrame({
            "conta_contabil": ["199990100"],
            "_has_period_change": [False],
        })
        pcasp = _make_pcasp_com_titulo("DEPRECIACAO ACUMULADA", "Credora")
        with patch("ranking_msc.rules.r085.load_pcasp", return_value=pcasp):
            result = rule.execute(df, engine_context)
        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ALERTA"
        assert result.iloc[0]["regra_id"] == "R085"

    def test_conta_deprec_com_pc_sem_pendencia(self, engine_context):
        """Conta de depreciação com period_change → sem pendências."""
        rule = R085()
        df = pd.DataFrame({
            "conta_contabil": ["199990100"],
            "_has_period_change": [True],
        })
        pcasp = _make_pcasp_com_titulo("DEPRECIACAO ACUMULADA", "Credora")
        with patch("ranking_msc.rules.r085.load_pcasp", return_value=pcasp):
            result = rule.execute(df, engine_context)
        assert len(result) == 0

    def test_conta_devedora_nao_verificada(self, engine_context):
        """Conta com título de depreciação mas NAT_SALDO=Devedora → ignorada."""
        rule = R085()
        df = pd.DataFrame({
            "conta_contabil": ["199990100"],
            "_has_period_change": [False],
        })
        pcasp = _make_pcasp_com_titulo("DEPRECIACAO ACUMULADA", "Devedora")
        with patch("ranking_msc.rules.r085.load_pcasp", return_value=pcasp):
            result = rule.execute(df, engine_context)
        assert len(result) == 0

    def test_amortizacao_sem_pc_gera_alerta(self, engine_context):
        """Padrão AMORTIZA no título também detectado."""
        rule = R085()
        df = pd.DataFrame({
            "conta_contabil": ["199990200"],
            "_has_period_change": [False],
        })
        pcasp = pd.DataFrame({
            "conta_contabil": ["199990200"],
            "titulo_desc": ["AMORTIZACAO ACUMULADA"],
            "nat_saldo": ["Credora"],
        })
        with patch("ranking_msc.rules.r085.load_pcasp", return_value=pcasp):
            result = rule.execute(df, engine_context)
        assert len(result) == 1

    def test_exaustao_sem_pc_gera_alerta(self, engine_context):
        """Padrão EXAUST no título também detectado."""
        rule = R085()
        df = pd.DataFrame({
            "conta_contabil": ["199990300"],
            "_has_period_change": [False],
        })
        pcasp = pd.DataFrame({
            "conta_contabil": ["199990300"],
            "titulo_desc": ["EXAUSTAO ACUMULADA"],
            "nat_saldo": ["Credora"],
        })
        with patch("ranking_msc.rules.r085.load_pcasp", return_value=pcasp):
            result = rule.execute(df, engine_context)
        assert len(result) == 1

    def test_conta_deprec_ausente_no_df_gera_alerta(self, engine_context):
        """Conta de depreciação ausente do df → sem period_change → ALERTA."""
        rule = R085()
        df = pd.DataFrame({
            "conta_contabil": ["111110100"],  # conta diferente, não de depreciação
            "_has_period_change": [True],
        })
        pcasp = _make_pcasp_com_titulo("DEPRECIACAO ACUMULADA", "Credora")
        with patch("ranking_msc.rules.r085.load_pcasp", return_value=pcasp):
            result = rule.execute(df, engine_context)
        assert len(result) == 1

    def test_flag_string_true_aceito(self, engine_context):
        """Flag '_has_period_change' como string 'True' é aceito corretamente."""
        rule = R085()
        df = pd.DataFrame({
            "conta_contabil": ["199990100"],
            "_has_period_change": ["True"],
        })
        pcasp = _make_pcasp_com_titulo("DEPRECIACAO ACUMULADA", "Credora")
        with patch("ranking_msc.rules.r085.load_pcasp", return_value=pcasp):
            result = rule.execute(df, engine_context)
        assert len(result) == 0
