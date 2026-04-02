"""Testes para a regra R025 — CO válido — 4 dígitos + tabela."""

from __future__ import annotations

from unittest.mock import patch

import pandas as pd

from ranking_msc.rules.r025 import R025

_TABELA_CO_MOCK = pd.DataFrame({
    "codigo": ["1001", "1002", "1010", "1070"],
})

_PATCH = "ranking_msc.rules.r025.load_tabela_co"


def _df(co: str, conta: str = "1.1.1.1.1.01.00") -> pd.DataFrame:
    """Cria DataFrame mínimo para testes de R025."""
    return pd.DataFrame({"conta_contabil": [conta], "co": [co]})


class TestR025:
    def test_co_valido_sem_pendencia(self, engine_context):
        """CO existente na tabela → nenhuma pendência."""
        with patch(_PATCH, return_value=_TABELA_CO_MOCK):
            result = R025().execute(_df("1001"), engine_context)
        assert len(result) == 0

    def test_co_1070_valido_sem_pendencia(self, engine_context):
        """CO 1070 existente na tabela → nenhuma pendência."""
        with patch(_PATCH, return_value=_TABELA_CO_MOCK):
            result = R025().execute(_df("1070"), engine_context)
        assert len(result) == 0

    def test_co_inexistente_gera_erro(self, engine_context):
        """CO ausente da tabela → pendência ERRO."""
        with patch(_PATCH, return_value=_TABELA_CO_MOCK):
            result = R025().execute(_df("9999"), engine_context)
        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ERRO"
        assert result.iloc[0]["regra_id"] == "R025"

    def test_co_formato_curto_gera_erro(self, engine_context):
        """CO com menos de 4 dígitos → pendência ERRO de formato."""
        with patch(_PATCH, return_value=_TABELA_CO_MOCK):
            result = R025().execute(_df("12"), engine_context)
        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ERRO"
        assert "4 dígitos" in result.iloc[0]["descricao"]

    def test_co_nao_informado_sem_pendencia(self, engine_context):
        """CO zero → nenhuma pendência."""
        with patch(_PATCH, return_value=_TABELA_CO_MOCK):
            result = R025().execute(_df("0"), engine_context)
        assert len(result) == 0

    def test_co_string_vazia_sem_pendencia(self, engine_context):
        """CO string vazia → nenhuma pendência."""
        with patch(_PATCH, return_value=_TABELA_CO_MOCK):
            result = R025().execute(_df(""), engine_context)
        assert len(result) == 0

    def test_coluna_co_ausente_sem_pendencia(self, engine_context):
        """DataFrame sem coluna 'co' → nenhuma pendência."""
        df = pd.DataFrame({"conta_contabil": ["1.1.1.1.1.01.00"], "po": ["00101"]})
        with patch(_PATCH, return_value=_TABELA_CO_MOCK):
            result = R025().execute(df, engine_context)
        assert len(result) == 0

    def test_duplicatas_contam_uma_vez(self, engine_context):
        """Mesma combinação conta/CO duplicada → apenas 1 pendência."""
        df = pd.DataFrame({
            "conta_contabil": ["1.1.1.1.1.01.00", "1.1.1.1.1.01.00"],
            "co": ["9999", "9999"],
        })
        with patch(_PATCH, return_value=_TABELA_CO_MOCK):
            result = R025().execute(df, engine_context)
        assert len(result) == 1

    def test_multiplas_contas_invalidas(self, engine_context):
        """Duas contas com CO inválido → 2 pendências."""
        df = pd.DataFrame({
            "conta_contabil": ["1.1.1.1.1.01.00", "2.1.1.1.1.01.00"],
            "co": ["9999", "8888"],
        })
        with patch(_PATCH, return_value=_TABELA_CO_MOCK):
            result = R025().execute(df, engine_context)
        assert len(result) == 2
