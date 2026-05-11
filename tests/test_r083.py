"""Testes para R083 — Dados executivo idênticos entre meses."""

from __future__ import annotations

from unittest.mock import patch

import pandas as pd
import pytest

from ranking_msc.exceptions import SnapshotError, SnapshotNotFoundError
from ranking_msc.rules.r083 import R083


def _make_exec_df(sf_deb: float = 100.0, sf_cred: float = 0.0) -> pd.DataFrame:
    """DataFrame mínimo com registros do Poder Executivo."""
    return pd.DataFrame({
        "conta_contabil": ["111110100"],
        "po": ["10131"],
        "fp": ["1"],
        "fr": ["0100"],
        "saldo_final_debito": [sf_deb],
        "saldo_final_credito": [sf_cred],
    })


def _make_exec_df_multi() -> pd.DataFrame:
    """DataFrame com duas contas do executivo."""
    return pd.DataFrame({
        "conta_contabil": ["111110100", "211110100"],
        "po": ["10131", "10131"],
        "fp": ["1", "2"],
        "saldo_final_debito": [100.0, 200.0],
        "saldo_final_credito": [0.0, 0.0],
    })


class TestR083:
    def test_snapshot_ausente_retorna_vazio(self, engine_context):
        """SnapshotNotFoundError → skip silencioso, sem pendências."""
        rule = R083()
        df = _make_exec_df()
        with patch(
            "ranking_msc.rules.r083.read_snapshot",
            side_effect=SnapshotNotFoundError("not found"),
        ):
            result = rule.execute(df, engine_context)
        assert len(result) == 0

    def test_sf_identico_gera_alerta(self, engine_context):
        """SF 100% idêntico ao mês anterior → 1 ALERTA global."""
        rule = R083()
        df = _make_exec_df(sf_deb=100.0, sf_cred=0.0)
        prev_df = _make_exec_df(sf_deb=100.0, sf_cred=0.0)
        with patch("ranking_msc.rules.r083.read_snapshot", return_value=prev_df):
            result = rule.execute(df, engine_context)
        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ALERTA"
        assert result.iloc[0]["regra_id"] == "R083"
        assert "idênticos" in result.iloc[0]["descricao"].lower()

    def test_sf_diferente_sem_pendencia(self, engine_context):
        """SF diferente entre meses → sem pendências."""
        rule = R083()
        df = _make_exec_df(sf_deb=200.0, sf_cred=0.0)
        prev_df = _make_exec_df(sf_deb=100.0, sf_cred=0.0)
        with patch("ranking_msc.rules.r083.read_snapshot", return_value=prev_df):
            result = rule.execute(df, engine_context)
        assert len(result) == 0

    def test_snapshot_error_propaga(self, engine_context):
        """SnapshotError (I/O) deve propagar — não engolir."""
        rule = R083()
        df = _make_exec_df()
        with patch(
            "ranking_msc.rules.r083.read_snapshot",
            side_effect=SnapshotError("io error"),
        ):
            with pytest.raises(SnapshotError):
                rule.execute(df, engine_context)

    def test_sem_coluna_po_retorna_vazio(self, engine_context):
        """DataFrame sem coluna 'po' → regra desativada silenciosamente."""
        rule = R083()
        df = pd.DataFrame({
            "conta_contabil": ["111110100"],
            "saldo_final_debito": [100.0],
            "saldo_final_credito": [0.0],
        })
        result = rule.execute(df, engine_context)
        assert len(result) == 0

    def test_sem_registros_executivo_retorna_vazio(self, engine_context):
        """DF sem PO=10131 → skip (nenhum registro do executivo)."""
        rule = R083()
        df = pd.DataFrame({
            "conta_contabil": ["111110100"],
            "po": ["20231"],  # Legislativo municipal
            "saldo_final_debito": [100.0],
            "saldo_final_credito": [0.0],
        })
        prev_df = df.copy()
        with patch("ranking_msc.rules.r083.read_snapshot", return_value=prev_df):
            result = rule.execute(df, engine_context)
        assert len(result) == 0

    def test_snapshot_anterior_vazio_retorna_vazio(self, engine_context):
        """Snapshot anterior vazio → skip, sem pendências."""
        rule = R083()
        df = _make_exec_df()
        with patch("ranking_msc.rules.r083.read_snapshot", return_value=pd.DataFrame()):
            result = rule.execute(df, engine_context)
        assert len(result) == 0

    def test_conta_nova_no_atual_nao_gera_alerta(self, engine_context):
        """Conta nova no atual → key-sets diferentes → sem ALERTA mesmo SF igual na interseção."""
        rule = R083()
        # Conta A idêntica nos dois meses + conta C nova apenas no atual
        df = pd.DataFrame({
            "conta_contabil": ["111110100", "333330100"],
            "po": ["10131", "10131"],
            "saldo_final_debito": [100.0, 500.0],
            "saldo_final_credito": [0.0, 0.0],
        })
        prev_df = pd.DataFrame({
            "conta_contabil": ["111110100"],
            "po": ["10131"],
            "saldo_final_debito": [100.0],
            "saldo_final_credito": [0.0],
        })
        with patch("ranking_msc.rules.r083.read_snapshot", return_value=prev_df):
            result = rule.execute(df, engine_context)
        assert len(result) == 0

    def test_conta_removida_no_atual_nao_gera_alerta(self, engine_context):
        """Conta removida no atual → key-sets diferem → sem ALERTA mesmo SF igual na interseção."""
        rule = R083()
        df = pd.DataFrame({
            "conta_contabil": ["111110100"],
            "po": ["10131"],
            "saldo_final_debito": [100.0],
            "saldo_final_credito": [0.0],
        })
        prev_df = pd.DataFrame({
            "conta_contabil": ["111110100", "211110100"],
            "po": ["10131", "10131"],
            "saldo_final_debito": [100.0, 200.0],
            "saldo_final_credito": [0.0, 0.0],
        })
        with patch("ranking_msc.rules.r083.read_snapshot", return_value=prev_df):
            result = rule.execute(df, engine_context)
        assert len(result) == 0

    def test_multicontas_uma_diferente_sem_alerta(self, engine_context):
        """Mesmo uma conta diferente entre meses → sem ALERTA (não é 100% idêntico)."""
        rule = R083()
        df = pd.DataFrame({
            "conta_contabil": ["111110100", "211110100"],
            "po": ["10131", "10131"],
            "saldo_final_debito": [100.0, 999.0],  # 999 diferente do anterior
            "saldo_final_credito": [0.0, 0.0],
        })
        prev_df = pd.DataFrame({
            "conta_contabil": ["111110100", "211110100"],
            "po": ["10131", "10131"],
            "saldo_final_debito": [100.0, 200.0],
            "saldo_final_credito": [0.0, 0.0],
        })
        with patch("ranking_msc.rules.r083.read_snapshot", return_value=prev_df):
            result = rule.execute(df, engine_context)
        assert len(result) == 0
