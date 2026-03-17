"""Testes da regra R021 — PO válido: 5 dígitos e existente na tabela."""

from __future__ import annotations

import pandas as pd
import pytest

from ranking_msc.rules.r021 import R021


def _tabela_po_stub() -> pd.DataFrame:
    """Tabela PO reduzida para testes."""
    return pd.DataFrame({"codigo": ["10101", "10102", "20231"]})


def _df_com_po(conta: str, po: str) -> pd.DataFrame:
    return pd.DataFrame({"conta_contabil": [conta], "po": [po]})


class TestR021:
    def test_po_valido_nao_gera_pendencia(
        self,
        engine_context: object,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """PO com 5 dígitos e existente na tabela não gera pendência."""
        monkeypatch.setattr(
            "ranking_msc.rules.r021.load_tabela_po", lambda *a, **kw: _tabela_po_stub()
        )

        df = _df_com_po("111110200", "10101")
        result = R021().execute(df, engine_context)

        assert len(result) == 0

    def test_po_ausente_no_df_nao_gera_pendencia(
        self,
        engine_context: object,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Conta sem IC do tipo PO (po vazio) não gera pendência."""
        monkeypatch.setattr(
            "ranking_msc.rules.r021.load_tabela_po", lambda *a, **kw: _tabela_po_stub()
        )

        df = _df_com_po("111110200", "")
        result = R021().execute(df, engine_context)

        assert len(result) == 0

    def test_po_formato_invalido_gera_erro(
        self,
        engine_context: object,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """PO com número de dígitos diferente de 5 gera pendência ERRO."""
        monkeypatch.setattr(
            "ranking_msc.rules.r021.load_tabela_po", lambda *a, **kw: _tabela_po_stub()
        )

        df = _df_com_po("111110200", "101")  # apenas 3 dígitos
        result = R021().execute(df, engine_context)

        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ERRO"
        assert result.iloc[0]["regra_id"] == "R021"
        assert "formato" in result.iloc[0]["descricao"].lower()

    def test_po_inexistente_na_tabela_gera_erro(
        self,
        engine_context: object,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """PO com 5 dígitos mas ausente da tabela gera pendência ERRO."""
        monkeypatch.setattr(
            "ranking_msc.rules.r021.load_tabela_po", lambda *a, **kw: _tabela_po_stub()
        )

        df = _df_com_po("111110200", "99999")
        result = R021().execute(df, engine_context)

        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ERRO"
        assert result.iloc[0]["regra_id"] == "R021"
        assert "99999" in result.iloc[0]["descricao"]

    def test_multiplas_pendencias_uma_por_combinacao_conta_po(
        self,
        engine_context: object,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Contas distintas com PO inválido geram uma pendência cada."""
        monkeypatch.setattr(
            "ranking_msc.rules.r021.load_tabela_po", lambda *a, **kw: _tabela_po_stub()
        )

        df = pd.DataFrame({
            "conta_contabil": ["111110200", "211000000", "311000000"],
            "po": ["99999", "88888", "10101"],  # últimos dois inválidos/válido
        })
        result = R021().execute(df, engine_context)

        assert len(result) == 2
