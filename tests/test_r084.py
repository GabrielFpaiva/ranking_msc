"""Testes para R084 — Conta Financeira (FP=1) sem FR detalhada."""

from __future__ import annotations

from unittest.mock import patch

import pandas as pd
import pytest

from ranking_msc.rules.r084 import R084


def _make_pcasp(id_ic: str = "4") -> pd.DataFrame:
    """PCASP mínimo com conta_contabil e id_ic."""
    return pd.DataFrame({
        "conta_contabil": ["111110100"],
        "id_ic": [id_ic],
    })


def _make_df(fp: str = "1", fr: str = "") -> pd.DataFrame:
    """DataFrame MSC mínimo."""
    return pd.DataFrame({
        "conta_contabil": ["111110100"],
        "fp": [fp],
        "fr": [fr],
    })


class TestR084:
    def test_fp1_com_fr_sem_pendencia(self, engine_context):
        """FP=1 com FR preenchida → sem pendências."""
        rule = R084()
        df = _make_df(fp="1", fr="0100")
        pcasp = _make_pcasp(id_ic="4")
        with patch("ranking_msc.rules.r084.load_pcasp", return_value=pcasp):
            result = rule.execute(df, engine_context)
        assert len(result) == 0

    def test_fp1_sem_fr_id_ic_obrigatorio_gera_erro(self, engine_context):
        """FP=1 sem FR e ID_IC=4 (obriga FR) → ERRO."""
        rule = R084()
        df = _make_df(fp="1", fr="")
        pcasp = _make_pcasp(id_ic="4")
        with patch("ranking_msc.rules.r084.load_pcasp", return_value=pcasp):
            result = rule.execute(df, engine_context)
        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ERRO"
        assert result.iloc[0]["regra_id"] == "R084"

    def test_fp2_sem_fr_nao_gera_pendencia(self, engine_context):
        """FP=2 (Permanente) sem FR → não é verificado por R084."""
        rule = R084()
        df = _make_df(fp="2", fr="")
        pcasp = _make_pcasp(id_ic="4")
        with patch("ranking_msc.rules.r084.load_pcasp", return_value=pcasp):
            result = rule.execute(df, engine_context)
        assert len(result) == 0

    def test_fp1_sem_fr_id_ic_sem_fr_sem_pendencia(self, engine_context):
        """FP=1 sem FR mas ID_IC=1 (não obriga FR) → sem pendências."""
        rule = R084()
        df = _make_df(fp="1", fr="")
        pcasp = _make_pcasp(id_ic="1")
        with patch("ranking_msc.rules.r084.load_pcasp", return_value=pcasp):
            result = rule.execute(df, engine_context)
        assert len(result) == 0

    def test_id_ic_ausente_pcasp_retorna_vazio(self, engine_context):
        """PCASP sem coluna 'id_ic' → graceful degradation."""
        rule = R084()
        df = _make_df(fp="1", fr="")
        pcasp_sem_id_ic = pd.DataFrame({"conta_contabil": ["111110100"]})
        with patch("ranking_msc.rules.r084.load_pcasp", return_value=pcasp_sem_id_ic):
            result = rule.execute(df, engine_context)
        assert len(result) == 0

    @pytest.mark.parametrize("id_ic", ["4", "5", "6", "7", "8", "9"])
    def test_todos_id_ic_com_fr_obrigatorio(self, id_ic, engine_context):
        """Todos os ID_IC que obrigam FR geram ERRO quando FR ausente."""
        rule = R084()
        df = _make_df(fp="1", fr="0")  # "0" é vazio semanticamente
        pcasp = _make_pcasp(id_ic=id_ic)
        with patch("ranking_msc.rules.r084.load_pcasp", return_value=pcasp):
            result = rule.execute(df, engine_context)
        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ERRO"

    def test_fr_zero_considerado_vazio(self, engine_context):
        """FR='0' é considerado vazio (ic_mask_informada) → ALERTA se id_ic obriga."""
        rule = R084()
        df = _make_df(fp="1", fr="0")
        pcasp = _make_pcasp(id_ic="7")
        with patch("ranking_msc.rules.r084.load_pcasp", return_value=pcasp):
            result = rule.execute(df, engine_context)
        assert len(result) == 1

    def test_sem_coluna_fp_retorna_vazio(self, engine_context):
        """DataFrame sem coluna 'fp' → regra desativada."""
        rule = R084()
        df = pd.DataFrame({"conta_contabil": ["111110100"], "fr": [""]})
        pcasp = _make_pcasp()
        with patch("ranking_msc.rules.r084.load_pcasp", return_value=pcasp):
            result = rule.execute(df, engine_context)
        assert len(result) == 0
