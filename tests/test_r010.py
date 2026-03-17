"""Testes da regra R010 — Conta existe no PCASP Estendido 2026."""

from __future__ import annotations

import pandas as pd
import pytest

from ranking_msc.rules.r010 import R010


def _pcasp_stub() -> pd.DataFrame:
    """PCASP reduzido para testes."""
    return pd.DataFrame({"conta_contabil": ["111110200", "211000000", "311000000"]})


class TestR010:
    def test_conta_valida_nao_gera_pendencia(
        self,
        engine_context: object,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Conta existente no PCASP não gera pendência."""
        monkeypatch.setattr("ranking_msc.rules.r010.load_pcasp", lambda *a, **kw: _pcasp_stub())

        df = pd.DataFrame({"conta_contabil": ["111110200", "211000000"]})
        result = R010().execute(df, engine_context)

        assert len(result) == 0

    def test_conta_invalida_gera_erro(
        self,
        engine_context: object,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Conta ausente no PCASP gera pendência ERRO."""
        monkeypatch.setattr("ranking_msc.rules.r010.load_pcasp", lambda *a, **kw: _pcasp_stub())

        df = pd.DataFrame({"conta_contabil": ["999999999"]})
        result = R010().execute(df, engine_context)

        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ERRO"
        assert result.iloc[0]["regra_id"] == "R010"
        assert "999999999" in result.iloc[0]["descricao"]

    def test_multiplas_contas_invalidas_gera_uma_pendencia_por_conta(
        self,
        engine_context: object,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Cada conta inválida única gera uma pendência separada."""
        monkeypatch.setattr("ranking_msc.rules.r010.load_pcasp", lambda *a, **kw: _pcasp_stub())

        df = pd.DataFrame({"conta_contabil": ["999999991", "999999992", "111110200"]})
        result = R010().execute(df, engine_context)

        assert len(result) == 2
        contas_pendentes = set(result["conta_contabil"])
        assert "999999991" in contas_pendentes
        assert "999999992" in contas_pendentes
        assert "111110200" not in contas_pendentes

    def test_conta_duplicada_no_df_gera_uma_unica_pendencia(
        self,
        engine_context: object,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Conta inválida repetida no DataFrame gera apenas uma pendência."""
        monkeypatch.setattr("ranking_msc.rules.r010.load_pcasp", lambda *a, **kw: _pcasp_stub())

        df = pd.DataFrame({"conta_contabil": ["999999999", "999999999"]})
        result = R010().execute(df, engine_context)

        assert len(result) == 1
