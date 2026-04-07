"""tests/test_r060.py — Testes para R060 (FP coerente com IND_SF PCASP)."""

from __future__ import annotations

from unittest.mock import patch

import pandas as pd

from ranking_msc.rules.r060 import R060


def _pcasp(rows: list[dict]) -> pd.DataFrame:
    """Constrói DataFrame PCASP de teste."""
    return pd.DataFrame(rows)


def _msc(rows: list[dict]) -> pd.DataFrame:
    """Constrói DataFrame MSC mínimo de teste."""
    return pd.DataFrame(rows)


class TestR060:
    def test_fp_correto_financeiro_sem_pendencia(self, engine_context):
        """IND_SF=Financeiro, FP=1 → sem ALERTA."""
        pcasp = _pcasp([{"conta_contabil": "111110200", "ind_sf": "Financeiro"}])
        df = _msc([{"conta_contabil": "111110200", "fp": "1"}])
        with patch("ranking_msc.rules.r060.load_pcasp", return_value=pcasp):
            result = R060().execute(df, engine_context)
        assert len(result) == 0

    def test_fp_correto_permanente_sem_pendencia(self, engine_context):
        """IND_SF=Permanente, FP=2 → sem ALERTA."""
        pcasp = _pcasp([{"conta_contabil": "111110200", "ind_sf": "Permanente"}])
        df = _msc([{"conta_contabil": "111110200", "fp": "2"}])
        with patch("ranking_msc.rules.r060.load_pcasp", return_value=pcasp):
            result = R060().execute(df, engine_context)
        assert len(result) == 0

    def test_fp_financeiro_permanente_aceita_ambos_sem_pendencia(self, engine_context):
        """IND_SF=Financeiro/Permanente aceita FP=1 e FP=2 → sem ALERTA."""
        pcasp = _pcasp([
            {"conta_contabil": "111110200", "ind_sf": "Financeiro/Permanente"},
            {"conta_contabil": "111110201", "ind_sf": "Financeiro/Permanente"},
        ])
        df = _msc([
            {"conta_contabil": "111110200", "fp": "1"},
            {"conta_contabil": "111110201", "fp": "2"},
        ])
        with patch("ranking_msc.rules.r060.load_pcasp", return_value=pcasp):
            result = R060().execute(df, engine_context)
        assert len(result) == 0

    def test_fp_divergente_financeiro_gera_alerta(self, engine_context):
        """IND_SF=Financeiro mas FP=2 → 1 ALERTA com valor_esperado='1'."""
        pcasp = _pcasp([{"conta_contabil": "111110200", "ind_sf": "Financeiro"}])
        df = _msc([{"conta_contabil": "111110200", "fp": "2"}])
        with patch("ranking_msc.rules.r060.load_pcasp", return_value=pcasp):
            result = R060().execute(df, engine_context)
        assert len(result) == 1
        row = result.iloc[0]
        assert row["severidade"] == "ALERTA"
        assert row["regra_id"] == "R060"
        assert row["valor_esperado"] == "1"
        assert row["valor_encontrado"] == "2"

    def test_fp_divergente_permanente_gera_alerta(self, engine_context):
        """IND_SF=Permanente mas FP=1 → 1 ALERTA com valor_esperado='2'."""
        pcasp = _pcasp([{"conta_contabil": "111110200", "ind_sf": "Permanente"}])
        df = _msc([{"conta_contabil": "111110200", "fp": "1"}])
        with patch("ranking_msc.rules.r060.load_pcasp", return_value=pcasp):
            result = R060().execute(df, engine_context)
        assert len(result) == 1
        row = result.iloc[0]
        assert row["severidade"] == "ALERTA"
        assert row["valor_esperado"] == "2"
        assert row["valor_encontrado"] == "1"

    def test_fp_nao_informado_com_financeiro_gera_alerta(self, engine_context):
        """IND_SF=Financeiro, FP='' (não informado) → ALERTA (fp != '1')."""
        pcasp = _pcasp([{"conta_contabil": "111110200", "ind_sf": "Financeiro"}])
        df = _msc([{"conta_contabil": "111110200", "fp": ""}])
        with patch("ranking_msc.rules.r060.load_pcasp", return_value=pcasp):
            result = R060().execute(df, engine_context)
        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ALERTA"

    def test_conta_sem_match_pcasp_sem_pendencia(self, engine_context):
        """Conta não encontrada no PCASP → skip (R010 trata)."""
        pcasp = _pcasp([{"conta_contabil": "999999999", "ind_sf": "Financeiro"}])
        df = _msc([{"conta_contabil": "111110200", "fp": "2"}])
        with patch("ranking_msc.rules.r060.load_pcasp", return_value=pcasp):
            result = R060().execute(df, engine_context)
        assert len(result) == 0

    def test_ind_sf_ausente_no_pcasp_degradacao_gracosa(self, engine_context):
        """PCASP sem coluna 'ind_sf' → 0 issues, sem exceção."""
        pcasp = _pcasp([{"conta_contabil": "111110200"}])  # ind_sf ausente
        df = _msc([{"conta_contabil": "111110200", "fp": "2"}])
        with patch("ranking_msc.rules.r060.load_pcasp", return_value=pcasp):
            result = R060().execute(df, engine_context)
        assert len(result) == 0

    def test_ind_sf_com_espacos_no_pcasp_nao_gera_falso_positivo(self, engine_context):
        """ind_sf com espaços no PCASP deve ser normalizado — FP correto não gera ALERTA."""
        pcasp = _pcasp([{"conta_contabil": "111110200", "ind_sf": "  Financeiro  "}])
        df = _msc([{"conta_contabil": "111110200", "fp": "1"}])
        with patch("ranking_msc.rules.r060.load_pcasp", return_value=pcasp):
            result = R060().execute(df, engine_context)
        assert len(result) == 0

    def test_multiplas_violacoes_detectadas(self, engine_context):
        """Múltiplas contas com FP divergente → um ALERTA por conta."""
        pcasp = _pcasp([
            {"conta_contabil": "111110200", "ind_sf": "Financeiro"},
            {"conta_contabil": "111110201", "ind_sf": "Permanente"},
            {"conta_contabil": "111110202", "ind_sf": "Financeiro"},
        ])
        df = _msc([
            {"conta_contabil": "111110200", "fp": "2"},   # diverge
            {"conta_contabil": "111110201", "fp": "1"},   # diverge
            {"conta_contabil": "111110202", "fp": "1"},   # correto
        ])
        with patch("ranking_msc.rules.r060.load_pcasp", return_value=pcasp):
            result = R060().execute(df, engine_context)
        assert len(result) == 2
        assert all(result["severidade"] == "ALERTA")
