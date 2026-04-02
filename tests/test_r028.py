"""Testes para a regra R028 — FS válida — 5 dígitos (2 função + 3 subfunção)."""

from __future__ import annotations

from unittest.mock import patch

import pandas as pd

from ranking_msc.rules.r028 import R028

_TABELA_FS_MOCK = pd.DataFrame({
    "funcao": ["01", "01", "04", "04"],
    "subfuncao": ["031", "032", "122", "131"],
})

_PATCH = "ranking_msc.rules.r028.load_tabela_fs"


def _df(fs: str, conta: str = "3.3.1.1.1.01.00") -> pd.DataFrame:
    """Cria DataFrame mínimo para testes de R028."""
    return pd.DataFrame({"conta_contabil": [conta], "fs": [fs]})


class TestR028:
    def test_fs_valida_sem_pendencia(self, engine_context):
        """FS com função e subfunção válidas → nenhuma pendência."""
        with patch(_PATCH, return_value=_TABELA_FS_MOCK):
            result = R028().execute(_df("01031"), engine_context)
        assert len(result) == 0

    def test_fs_funcao_04_valida_sem_pendencia(self, engine_context):
        """FS com função 04 e subfunção 122 válidas → nenhuma pendência."""
        with patch(_PATCH, return_value=_TABELA_FS_MOCK):
            result = R028().execute(_df("04122"), engine_context)
        assert len(result) == 0

    def test_fs_formato_curto_gera_erro(self, engine_context):
        """FS com menos de 5 dígitos → pendência ERRO de formato."""
        with patch(_PATCH, return_value=_TABELA_FS_MOCK):
            result = R028().execute(_df("012"), engine_context)
        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ERRO"
        assert result.iloc[0]["regra_id"] == "R028"
        assert "5 dígitos" in result.iloc[0]["descricao"]

    def test_fs_funcao_invalida_gera_erro(self, engine_context):
        """FS com função inexistente na tabela → pendência ERRO."""
        with patch(_PATCH, return_value=_TABELA_FS_MOCK):
            result = R028().execute(_df("99031"), engine_context)
        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ERRO"
        assert "99" in result.iloc[0]["descricao"]

    def test_fs_subfuncao_invalida_gera_alerta(self, engine_context):
        """FS com função válida mas subfunção inexistente → pendência ALERTA."""
        with patch(_PATCH, return_value=_TABELA_FS_MOCK):
            result = R028().execute(_df("01999"), engine_context)
        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ALERTA"
        assert result.iloc[0]["regra_id"] == "R028"

    def test_fs_nao_informada_sem_pendencia(self, engine_context):
        """FS zero → nenhuma pendência."""
        with patch(_PATCH, return_value=_TABELA_FS_MOCK):
            result = R028().execute(_df("0"), engine_context)
        assert len(result) == 0

    def test_fs_string_vazia_sem_pendencia(self, engine_context):
        """FS string vazia → nenhuma pendência."""
        with patch(_PATCH, return_value=_TABELA_FS_MOCK):
            result = R028().execute(_df(""), engine_context)
        assert len(result) == 0

    def test_coluna_fs_ausente_sem_pendencia(self, engine_context):
        """DataFrame sem coluna 'fs' → nenhuma pendência."""
        df = pd.DataFrame({"conta_contabil": ["3.3.1.1.1.01.00"], "fr": ["1500"]})
        with patch(_PATCH, return_value=_TABELA_FS_MOCK):
            result = R028().execute(df, engine_context)
        assert len(result) == 0

    def test_duplicatas_contam_uma_vez(self, engine_context):
        """Mesma combinação conta/FS duplicada → apenas 1 pendência."""
        df = pd.DataFrame({
            "conta_contabil": ["3.3.1.1.1.01.00", "3.3.1.1.1.01.00"],
            "fs": ["99031", "99031"],
        })
        with patch(_PATCH, return_value=_TABELA_FS_MOCK):
            result = R028().execute(df, engine_context)
        assert len(result) == 1
