"""Testes da regra R029 — AI: Ano Inscrição RP válido."""

from __future__ import annotations

import datetime

import pandas as pd

from ranking_msc.rules.r029 import R029


def _df_ai(conta: str, ai: object) -> pd.DataFrame:
    """DataFrame mínimo com uma linha e colunas conta_contabil + ai."""
    return pd.DataFrame({"conta_contabil": [conta], "ai": [ai]})


class TestR029:
    def test_ai_ausente_nao_gera_pendencia(self, engine_context: object) -> None:
        """Linha sem AI (coluna vazia) não gera pendência."""
        df = _df_ai("111110200", "")
        result = R029().execute(df, engine_context)
        assert len(result) == 0

    def test_ai_ausente_nan_nao_gera_pendencia(self, engine_context: object) -> None:
        """Linha com AI None/NaN não gera pendência."""
        df = _df_ai("111110200", None)
        result = R029().execute(df, engine_context)
        assert len(result) == 0

    def test_ai_4_digitos_ano_plausivel_nao_gera_pendencia(
        self, engine_context: object
    ) -> None:
        """AI com 4 dígitos e ano plausível (ex: 2023) não gera pendência."""
        df = _df_ai("111110200", "2023")
        result = R029().execute(df, engine_context)
        assert len(result) == 0

    def test_ai_formato_invalido_3_digitos_gera_erro(
        self, engine_context: object
    ) -> None:
        """AI com 3 dígitos gera pendência ERRO."""
        df = _df_ai("111110200", "202")
        result = R029().execute(df, engine_context)

        assert len(result) == 1
        assert result.iloc[0]["regra_id"] == "R029"
        assert result.iloc[0]["severidade"] == "ERRO"
        assert "202" in result.iloc[0]["descricao"]
        assert "111110200" in result.iloc[0]["descricao"]
        assert result.iloc[0]["competencia"] == "2024-01"

    def test_ai_formato_nao_numerico_gera_erro(self, engine_context: object) -> None:
        """AI com 4 caracteres não numéricos gera pendência ERRO."""
        df = _df_ai("111110200", "ABCD")
        result = R029().execute(df, engine_context)

        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ERRO"
        assert result.iloc[0]["regra_id"] == "R029"
        assert "ABCD" in result.iloc[0]["descricao"]
        assert "111110200" in result.iloc[0]["descricao"]
        assert result.iloc[0]["competencia"] == "2024-01"

    def test_ai_ano_abaixo_de_2000_gera_alerta(self, engine_context: object) -> None:
        """AI com ano < 2000 (ex: '1999') gera pendência ALERTA."""
        df = _df_ai("111110200", "1999")
        result = R029().execute(df, engine_context)

        assert len(result) == 1
        assert result.iloc[0]["regra_id"] == "R029"
        assert result.iloc[0]["severidade"] == "ALERTA"
        assert "1999" in result.iloc[0]["descricao"]

    def test_ai_ano_acima_do_corrente_gera_alerta(
        self, engine_context: object
    ) -> None:
        """AI com ano > ano corrente gera pendência ALERTA."""
        ano_futuro = str(datetime.date.today().year + 1)
        df = _df_ai("111110200", ano_futuro)
        result = R029().execute(df, engine_context)

        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ALERTA"
        assert ano_futuro in result.iloc[0]["descricao"]
        assert result.iloc[0]["regra_id"] == "R029"

    def test_multiplas_linhas_cada_uma_com_ai_invalido(
        self, engine_context: object
    ) -> None:
        """Múltiplas linhas com AI inválido geram uma pendência por combinação conta/AI."""
        df = pd.DataFrame({
            "conta_contabil": ["111110200", "211000000", "311000000"],
            "ai": ["2023", "1999", "ABCD"],  # válido, implausível, formato errado
        })
        result = R029().execute(df, engine_context)

        assert len(result) == 2
        severidades = set(result["severidade"].tolist())
        assert severidades == {"ALERTA", "ERRO"}
