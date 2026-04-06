"""Testes para a regra R027 — ND válida — 8 dígitos + tabela."""

from __future__ import annotations

from unittest.mock import patch

import pandas as pd

from ranking_msc.rules.r027 import R027

_TABELA_ND_MOCK = pd.DataFrame({
    "codigo": ["31200000", "31220000", "33903600"],
    "nivel": [
        "Último 3º Nível - Modalidade",
        "Último 3º Nível - Modalidade",
        "Último 4º Nível - Elemento",
    ],
    "nome": [
        "TRANSFERÊNCIAS À UNIÃO",
        "EXEC. ORÇAMENTÁRIA DELEGADA",
        "OUTROS SERVIÇOS DE TERCEIROS",
    ],
})

_PATCH = "ranking_msc.rules.r027.load_tabela_nd"


def _df(nd: str, conta: str = "3.3.1.1.1.01.00") -> pd.DataFrame:
    """Cria DataFrame mínimo para testes de R027."""
    return pd.DataFrame({"conta_contabil": [conta], "nd": [nd]})


class TestR027:
    def test_nd_valida_sem_pendencia(self, engine_context):
        """ND existente na tabela → nenhuma pendência."""
        with patch(_PATCH, return_value=_TABELA_ND_MOCK):
            result = R027().execute(_df("33903600"), engine_context)
        assert len(result) == 0

    def test_nd_formato_curto_gera_erro(self, engine_context):
        """ND com menos de 8 dígitos → pendência ERRO."""
        with patch(_PATCH, return_value=_TABELA_ND_MOCK):
            result = R027().execute(_df("3390"), engine_context)
        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ERRO"
        assert result.iloc[0]["regra_id"] == "R027"
        assert "8 dígitos" in result.iloc[0]["descricao"]

    def test_nd_alfanumerico_gera_erro(self, engine_context):
        """ND com caractere não-dígito (ex: '33A0B600') → ERRO de formato, não ALERTA."""
        with patch(_PATCH, return_value=_TABELA_ND_MOCK):
            result = R027().execute(_df("33A0B600"), engine_context)
        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ERRO"
        assert result.iloc[0]["regra_id"] == "R027"
        assert "dígitos" in result.iloc[0]["descricao"]

    def test_nd_inexistente_gera_alerta(self, engine_context):
        """ND com 8 dígitos mas ausente da tabela → pendência ALERTA."""
        with patch(_PATCH, return_value=_TABELA_ND_MOCK):
            result = R027().execute(_df("99999999"), engine_context)
        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ALERTA"
        assert result.iloc[0]["regra_id"] == "R027"

    def test_nd_nao_informada_sem_pendencia(self, engine_context):
        """ND zero → nenhuma pendência."""
        with patch(_PATCH, return_value=_TABELA_ND_MOCK):
            result = R027().execute(_df("0"), engine_context)
        assert len(result) == 0

    def test_nd_string_vazia_sem_pendencia(self, engine_context):
        """ND string vazia → nenhuma pendência."""
        with patch(_PATCH, return_value=_TABELA_ND_MOCK):
            result = R027().execute(_df(""), engine_context)
        assert len(result) == 0

    def test_coluna_nd_ausente_sem_pendencia(self, engine_context):
        """DataFrame sem coluna 'nd' → nenhuma pendência."""
        df = pd.DataFrame({"conta_contabil": ["3.3.1.1.1.01.00"], "fr": ["1500"]})
        with patch(_PATCH, return_value=_TABELA_ND_MOCK):
            result = R027().execute(df, engine_context)
        assert len(result) == 0

    def test_duplicatas_contam_uma_vez(self, engine_context):
        """Mesma combinação conta/ND duplicada → apenas 1 pendência."""
        df = pd.DataFrame({
            "conta_contabil": ["3.3.1.1.1.01.00", "3.3.1.1.1.01.00"],
            "nd": ["99999999", "99999999"],
        })
        with patch(_PATCH, return_value=_TABELA_ND_MOCK):
            result = R027().execute(df, engine_context)
        assert len(result) == 1

    def test_multiplas_contas_invalidas(self, engine_context):
        """Duas contas com ND inválido → 2 pendências."""
        df = pd.DataFrame({
            "conta_contabil": ["3.3.1.1.1.01.00", "4.1.1.1.1.01.00"],
            "nd": ["99999999", "88888888"],
        })
        with patch(_PATCH, return_value=_TABELA_ND_MOCK):
            result = R027().execute(df, engine_context)
        assert len(result) == 2
