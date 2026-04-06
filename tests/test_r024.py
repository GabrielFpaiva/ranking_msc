"""Testes para a regra R024 — FR válida — 4 dígitos + tabela."""

from __future__ import annotations

from unittest.mock import patch

import pandas as pd

from ranking_msc.rules.r024 import R024

_TABELA_FR_MOCK = pd.DataFrame({
    "codigo_base": ["500", "501", "502"],
    "nome": ["Recursos não Vinculados de Impostos", "Outros Recursos", "Compensação"],
})

_PATCH = "ranking_msc.rules.r024.load_tabela_fr"


def _df(fr: str, conta: str = "1.1.1.1.1.01.00") -> pd.DataFrame:
    """Cria DataFrame mínimo para testes de R024."""
    return pd.DataFrame({"conta_contabil": [conta], "fr": [fr]})


class TestR024:
    def test_fr_valida_sem_pendencia(self, engine_context):
        """FR com prefixo válido e código-raiz na tabela → nenhuma pendência."""
        with patch(_PATCH, return_value=_TABELA_FR_MOCK):
            result = R024().execute(_df("1500"), engine_context)
        assert len(result) == 0

    def test_fr_prefixo_2_valido_sem_pendencia(self, engine_context):
        """FR com prefixo 2 (exercício anterior) → nenhuma pendência."""
        with patch(_PATCH, return_value=_TABELA_FR_MOCK):
            result = R024().execute(_df("2501"), engine_context)
        assert len(result) == 0

    def test_fr_prefixo_9_valido_sem_pendencia(self, engine_context):
        """FR com prefixo 9 (condicionado) → nenhuma pendência."""
        with patch(_PATCH, return_value=_TABELA_FR_MOCK):
            result = R024().execute(_df("9502"), engine_context)
        assert len(result) == 0

    def test_fr_formato_curto_gera_erro(self, engine_context):
        """FR com menos de 4 dígitos → pendência ERRO de comprimento."""
        with patch(_PATCH, return_value=_TABELA_FR_MOCK):
            result = R024().execute(_df("15"), engine_context)
        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ERRO"
        assert result.iloc[0]["regra_id"] == "R024"
        assert "4 dígitos" in result.iloc[0]["descricao"]

    def test_fr_alfanumerico_gera_erro(self, engine_context):
        """FR com caractere não-dígito (ex: '1A00') → pendência ERRO de formato, não ALERTA."""
        with patch(_PATCH, return_value=_TABELA_FR_MOCK):
            result = R024().execute(_df("1A00"), engine_context)
        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ERRO"
        assert result.iloc[0]["regra_id"] == "R024"
        assert "dígitos" in result.iloc[0]["descricao"]

    def test_fr_alfanumerico_prefixo_invalido_gera_erro(self, engine_context):
        """FR alfanumérico com prefixo inválido → ERRO de formato (não chega ao prefixo)."""
        with patch(_PATCH, return_value=_TABELA_FR_MOCK):
            result = R024().execute(_df("A500"), engine_context)
        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ERRO"
        assert "dígitos" in result.iloc[0]["descricao"]

    def test_fr_prefixo_invalido_gera_erro(self, engine_context):
        """FR com 1º dígito fora de {1, 2, 9} → pendência ERRO."""
        with patch(_PATCH, return_value=_TABELA_FR_MOCK):
            result = R024().execute(_df("3500"), engine_context)
        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ERRO"
        assert "3" in result.iloc[0]["descricao"]

    def test_fr_raiz_desconhecida_gera_alerta(self, engine_context):
        """FR com código-raiz ausente na tabela → pendência ALERTA."""
        with patch(_PATCH, return_value=_TABELA_FR_MOCK):
            result = R024().execute(_df("1999"), engine_context)
        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ALERTA"
        assert result.iloc[0]["regra_id"] == "R024"

    def test_fr_nao_informada_sem_pendencia(self, engine_context):
        """FR vazia/zero → nenhuma pendência."""
        with patch(_PATCH, return_value=_TABELA_FR_MOCK):
            result = R024().execute(_df("0"), engine_context)
        assert len(result) == 0

    def test_fr_string_vazia_sem_pendencia(self, engine_context):
        """FR string vazia → nenhuma pendência."""
        with patch(_PATCH, return_value=_TABELA_FR_MOCK):
            result = R024().execute(_df(""), engine_context)
        assert len(result) == 0

    def test_coluna_fr_ausente_sem_pendencia(self, engine_context):
        """DataFrame sem coluna 'fr' → nenhuma pendência."""
        df = pd.DataFrame({"conta_contabil": ["1.1.1.1.1.01.00"], "po": ["00101"]})
        with patch(_PATCH, return_value=_TABELA_FR_MOCK):
            result = R024().execute(df, engine_context)
        assert len(result) == 0

    def test_duplicatas_contam_uma_vez(self, engine_context):
        """Mesma combinação conta/FR duplicada → apenas 1 pendência."""
        df = pd.DataFrame({
            "conta_contabil": ["1.1.1.1.1.01.00", "1.1.1.1.1.01.00"],
            "fr": ["3500", "3500"],
        })
        with patch(_PATCH, return_value=_TABELA_FR_MOCK):
            result = R024().execute(df, engine_context)
        assert len(result) == 1
