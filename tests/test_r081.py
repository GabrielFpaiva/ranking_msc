"""
tests/test_r081.py
~~~~~~~~~~~~~~~~~~

Testes para a regra R081 — IC tem dígitos no formato correto.
"""

from __future__ import annotations

import pandas as pd

from ranking_msc.engine.executor import EngineContext
from ranking_msc.rules.r081 import R081


def _make_df(**kwargs: str | None) -> pd.DataFrame:
    """Cria DataFrame mínimo com colunas IC informadas para testar R081.

    Args:
        **kwargs: pares coluna=valor para as colunas IC (po, fp, fr, etc.).

    Returns:
        DataFrame com uma linha incluindo conta_contabil e as ICs fornecidas.
    """
    data: dict[str, list[str | None]] = {
        "conta_contabil": ["111110200"],
        "competencia": ["2024-01"],
        "siconfi": ["250400"],
    }
    for col, val in kwargs.items():
        data[col] = [val]
    return pd.DataFrame(data)


class TestR081:
    """Testes para R081 — validação de formato dos campos IC."""

    def test_ics_corretas_sem_pendencia(self, engine_context: EngineContext) -> None:
        """ICs com dígitos corretos não geram pendência."""
        df = _make_df(po="10131", fp="1", fr="1700")
        rule = R081()
        result = rule.execute(df, engine_context)
        assert len(result) == 0

    def test_po_com_digitos_errados_gera_erro(self, engine_context: EngineContext) -> None:
        """PO com 4 dígitos (esperado 5) gera ERRO."""
        df = _make_df(po="1013")  # 4 dígitos, esperado 5
        rule = R081()
        result = rule.execute(df, engine_context)
        assert len(result) == 1
        assert result.iloc[0]["regra_id"] == "R081"
        assert result.iloc[0]["severidade"] == "ERRO"
        assert "PO" in result.iloc[0]["descricao"]

    def test_ic_nao_numerica_gera_erro(self, engine_context: EngineContext) -> None:
        """IC com letras gera ERRO."""
        df = _make_df(fr="17XX")  # 4 chars mas não numérico
        rule = R081()
        result = rule.execute(df, engine_context)
        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ERRO"
        assert "FR" in result.iloc[0]["descricao"]

    def test_ic_vazia_nao_gera_pendencia(self, engine_context: EngineContext) -> None:
        """IC vazia/NaN não deve gerar pendência."""
        df = _make_df(fr=None)
        rule = R081()
        result = rule.execute(df, engine_context)
        assert len(result) == 0

    def test_ic_zero_nao_gera_pendencia(self, engine_context: EngineContext) -> None:
        """IC com valor '0' não deve gerar pendência (considerada não informada)."""
        df = _make_df(fp="0")
        rule = R081()
        result = rule.execute(df, engine_context)
        assert len(result) == 0

    def test_fp_valido_sem_pendencia(self, engine_context: EngineContext) -> None:
        """FP com 1 dígito numérico não gera pendência."""
        df = _make_df(fp="1")
        rule = R081()
        result = rule.execute(df, engine_context)
        assert len(result) == 0

    def test_fp_com_dois_digitos_gera_erro(self, engine_context: EngineContext) -> None:
        """FP com 2 dígitos (esperado 1) gera ERRO."""
        df = _make_df(fp="12")
        rule = R081()
        result = rule.execute(df, engine_context)
        assert len(result) == 1
        assert "FP" in result.iloc[0]["descricao"]

    def test_nr_valido_sem_pendencia(self, engine_context: EngineContext) -> None:
        """NR com 8 dígitos numéricos não gera pendência."""
        df = _make_df(nr="17210000")
        rule = R081()
        result = rule.execute(df, engine_context)
        assert len(result) == 0

    def test_nd_curto_gera_erro(self, engine_context: EngineContext) -> None:
        """ND com menos de 8 dígitos gera ERRO."""
        df = _make_df(nd="339030")  # 6 dígitos, esperado 8
        rule = R081()
        result = rule.execute(df, engine_context)
        assert len(result) == 1
        assert "ND" in result.iloc[0]["descricao"]
        assert result.iloc[0]["valor_esperado"] == "8 dígito(s) numérico(s)"

    def test_multiplas_ics_invalidas_geram_multiplas_pendencias(
        self, engine_context: EngineContext
    ) -> None:
        """Múltiplas ICs inválidas geram uma pendência cada."""
        df = _make_df(po="1013", fr="17XX")  # po muito curto, fr não numérico
        rule = R081()
        result = rule.execute(df, engine_context)
        assert len(result) == 2

    def test_coluna_ic_ausente_nao_gera_pendencia(
        self, engine_context: EngineContext
    ) -> None:
        """Coluna IC ausente no DataFrame não gera pendência (skip silencioso)."""
        df = pd.DataFrame({
            "conta_contabil": ["111110200"],
            "competencia": ["2024-01"],
            # sem nenhuma coluna IC
        })
        rule = R081()
        result = rule.execute(df, engine_context)
        assert len(result) == 0

    def test_competencia_preenchida_na_pendencia(self, engine_context: EngineContext) -> None:
        """Pendência gerada deve conter a competência do contexto."""
        df = _make_df(po="1013")
        rule = R081()
        result = rule.execute(df, engine_context)
        assert result.iloc[0]["competencia"] == "2024-01"

    def test_conta_contabil_preenchida_na_pendencia(
        self, engine_context: EngineContext
    ) -> None:
        """Pendência deve conter a conta contábil da linha com IC inválida."""
        df = _make_df(po="1013")
        rule = R081()
        result = rule.execute(df, engine_context)
        assert result.iloc[0]["conta_contabil"] == "111110200"
