"""Testes para a regra R026 — NR válida — 8 dígitos + tabela."""

from __future__ import annotations

from unittest.mock import patch

import pandas as pd

from ranking_msc.rules.r026 import R026

_TABELA_NR_MOCK = pd.DataFrame({
    "codigo": ["11110101", "11110102", "11110200"],
    "valorizavel": ["SIM", "SIM", "NÃO"],
})

_PATCH = "ranking_msc.rules.r026.load_tabela_nr"


def _df(nr: str, conta: str = "1.1.1.1.1.01.00") -> pd.DataFrame:
    """Cria DataFrame mínimo para testes de R026."""
    return pd.DataFrame({"conta_contabil": [conta], "nr": [nr]})


class TestR026:
    def test_nr_valida_sem_pendencia(self, engine_context):
        """NR existente na tabela → nenhuma pendência."""
        with patch(_PATCH, return_value=_TABELA_NR_MOCK):
            result = R026().execute(_df("11110101"), engine_context)
        assert len(result) == 0

    def test_nr_formato_curto_gera_erro(self, engine_context):
        """NR com menos de 8 dígitos → pendência ERRO."""
        with patch(_PATCH, return_value=_TABELA_NR_MOCK):
            result = R026().execute(_df("1234"), engine_context)
        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ERRO"
        assert result.iloc[0]["regra_id"] == "R026"
        assert "8 dígitos" in result.iloc[0]["descricao"]

    def test_nr_alfanumerico_gera_erro(self, engine_context):
        """NR com caractere não-dígito (ex: '12AB5678') → ERRO de formato, não ALERTA."""
        with patch(_PATCH, return_value=_TABELA_NR_MOCK):
            result = R026().execute(_df("12AB5678"), engine_context)
        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ERRO"
        assert result.iloc[0]["regra_id"] == "R026"
        assert "dígitos" in result.iloc[0]["descricao"]

    def test_nr_inexistente_gera_alerta(self, engine_context):
        """NR com 8 dígitos mas ausente da tabela → pendência ALERTA."""
        with patch(_PATCH, return_value=_TABELA_NR_MOCK):
            result = R026().execute(_df("99999999"), engine_context)
        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ALERTA"
        assert result.iloc[0]["regra_id"] == "R026"

    def test_nr_nao_informada_sem_pendencia(self, engine_context):
        """NR zero ou vazia → nenhuma pendência."""
        with patch(_PATCH, return_value=_TABELA_NR_MOCK):
            result = R026().execute(_df("0"), engine_context)
        assert len(result) == 0

    def test_nr_string_vazia_sem_pendencia(self, engine_context):
        """NR string vazia → nenhuma pendência."""
        with patch(_PATCH, return_value=_TABELA_NR_MOCK):
            result = R026().execute(_df(""), engine_context)
        assert len(result) == 0

    def test_coluna_nr_ausente_sem_pendencia(self, engine_context):
        """DataFrame sem coluna 'nr' → nenhuma pendência."""
        df = pd.DataFrame({"conta_contabil": ["1.1.1.1.1.01.00"], "fr": ["1500"]})
        with patch(_PATCH, return_value=_TABELA_NR_MOCK):
            result = R026().execute(df, engine_context)
        assert len(result) == 0

    def test_duplicatas_contam_uma_vez(self, engine_context):
        """Mesma combinação conta/NR duplicada → apenas 1 pendência."""
        df = pd.DataFrame({
            "conta_contabil": ["1.1.1.1.1.01.00", "1.1.1.1.1.01.00"],
            "nr": ["99999999", "99999999"],
        })
        with patch(_PATCH, return_value=_TABELA_NR_MOCK):
            result = R026().execute(df, engine_context)
        assert len(result) == 1
