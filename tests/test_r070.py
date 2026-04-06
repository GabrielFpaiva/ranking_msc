"""
tests/test_r070.py
~~~~~~~~~~~~~~~~~~

Testes para a regra R070 — Sem registros duplicados.
"""

from __future__ import annotations

import pandas as pd

from ranking_msc.engine.executor import EngineContext
from ranking_msc.rules.r070 import R070


def _make_df(**overrides: object) -> pd.DataFrame:
    """Cria DataFrame mínimo com as colunas-chave de R070.

    Gera uma única linha válida (sem duplicatas). Use overrides para
    sobrescrever valores ou adicione linhas extras nos testes.

    Args:
        **overrides: valores a sobrescrever nas colunas da linha-base.

    Returns:
        DataFrame com as colunas de chave R070.
    """
    base: dict[str, object] = {
        "conta_contabil": "111110200",
        "po": "10131",
        "fp": "1",
        "dc": "",
        "fs": "",
        "fr": "1500",
        "co": "",
        "nr": "",
        "nd": "",
        "ai": "",
        "competencia": "2024-01",
        "siconfi": "250400",
    }
    base.update(overrides)
    return pd.DataFrame([base])


def _make_dup_df(conta: str = "111110200", n: int = 2) -> pd.DataFrame:
    """Cria DataFrame com N linhas idênticas na chave (duplicatas).

    Args:
        conta: valor de conta_contabil para todas as linhas.
        n: número de linhas duplicadas.

    Returns:
        DataFrame com n linhas com a mesma chave composta.
    """
    row = {
        "conta_contabil": conta,
        "po": "10131",
        "fp": "1",
        "dc": "",
        "fs": "",
        "fr": "1500",
        "co": "",
        "nr": "",
        "nd": "",
        "ai": "",
        "competencia": "2024-01",
        "siconfi": "250400",
    }
    return pd.DataFrame([row] * n)


class TestR070:
    """Testes para R070 — detecção de registros duplicados por chave composta."""

    def test_sem_duplicatas_sem_pendencia(self, engine_context: EngineContext) -> None:
        """DataFrame sem duplicatas não gera pendência."""
        df = _make_df()
        rule = R070()
        result = rule.execute(df, engine_context)
        assert len(result) == 0

    def test_duas_linhas_mesma_chave_gera_erro(self, engine_context: EngineContext) -> None:
        """Duas linhas com mesma chave composta geram um ERRO."""
        df = _make_dup_df(n=2)
        rule = R070()
        result = rule.execute(df, engine_context)
        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ERRO"
        assert result.iloc[0]["regra_id"] == "R070"

    def test_tres_linhas_mesma_chave_reporta_contagem(self, engine_context: EngineContext) -> None:
        """Três linhas com mesma chave → issue com '3 ocorrências'."""
        df = _make_dup_df(n=3)
        rule = R070()
        result = rule.execute(df, engine_context)
        assert len(result) == 1
        assert "3 ocorrências" in result.iloc[0]["valor_encontrado"]

    def test_conta_diferente_nao_e_duplicata(self, engine_context: EngineContext) -> None:
        """Linhas com conta_contabil diferente mas mesmas ICs não são duplicatas."""
        df = pd.concat([
            _make_df(conta_contabil="111110200"),
            _make_df(conta_contabil="111110300"),
        ], ignore_index=True)
        rule = R070()
        result = rule.execute(df, engine_context)
        assert len(result) == 0

    def test_ic_diferente_nao_e_duplicata(self, engine_context: EngineContext) -> None:
        """Linhas com mesma conta mas IC diferente não são duplicatas."""
        df = pd.concat([
            _make_df(fr="1500"),
            _make_df(fr="1600"),
        ], ignore_index=True)
        rule = R070()
        result = rule.execute(df, engine_context)
        assert len(result) == 0

    def test_dois_grupos_duplicados_geram_dois_erros(self, engine_context: EngineContext) -> None:
        """Dois grupos de duplicatas distintos geram dois ERROs."""
        df = pd.concat([
            _make_dup_df(conta="111110200", n=2),
            _make_dup_df(conta="111110300", n=2),
        ], ignore_index=True)
        rule = R070()
        result = rule.execute(df, engine_context)
        assert len(result) == 2
        assert all(result["severidade"] == "ERRO")
        assert all(result["regra_id"] == "R070")

    def test_ic_swap_detectado_como_duplicata(self, engine_context: EngineContext) -> None:
        """IC-position-swap: ICs em posições diferentes → mesma chave após normalize_ic."""
        # Simula o resultado pós-normalize_ic: ambas as linhas mapearam para
        # mesma chave (conta_contabil + po + fr idênticos), apesar de terem
        # vindo de posições IC diferentes no CSV original.
        row_base = {
            "conta_contabil": "111110200",
            "po": "10131",
            "fp": "1",
            "dc": "",
            "fs": "",
            "fr": "1500",
            "co": "",
            "nr": "",
            "nd": "",
            "ai": "",
            "competencia": "2024-01",
            "siconfi": "250400",
        }
        df = pd.DataFrame([row_base, row_base])  # Idênticas após normalize_ic
        rule = R070()
        result = rule.execute(df, engine_context)
        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ERRO"

    def test_nan_em_ic_tratado_consistentemente(self, engine_context: EngineContext) -> None:
        """Colunas IC com NaN são normalizadas para '' — NaN == NaN na chave."""
        import numpy as np

        row = {
            "conta_contabil": "111110200",
            "po": "10131",
            "fp": np.nan,  # NaN deve virar "" antes do groupby
            "dc": "",
            "fs": "",
            "fr": "1500",
            "co": "",
            "nr": "",
            "nd": "",
            "ai": "",
            "competencia": "2024-01",
            "siconfi": "250400",
        }
        df = pd.DataFrame([row, row])
        rule = R070()
        result = rule.execute(df, engine_context)
        # NaN deve ser tratado como igual ao NaN → detecta duplicata
        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ERRO"

    def test_df_sem_colunas_chave_retorna_vazio(self, engine_context: EngineContext) -> None:
        """DataFrame sem nenhuma coluna-chave retorna resultado vazio sem exceção."""
        df = pd.DataFrame({"competencia": ["2024-01"]})
        rule = R070()
        result = rule.execute(df, engine_context)
        assert len(result) == 0

    def test_descricao_contem_conta_afetada(self, engine_context: EngineContext) -> None:
        """Descrição da pendência deve conter a conta_contabil para diagnóstico."""
        df = _make_dup_df(conta="999990001", n=2)
        rule = R070()
        result = rule.execute(df, engine_context)
        assert "999990001" in result.iloc[0]["descricao"]

    def test_conta_contabil_preenchida_na_pendencia(self, engine_context: EngineContext) -> None:
        """Campo conta_contabil da pendência corresponde à conta duplicada."""
        df = _make_dup_df(conta="111110200", n=2)
        rule = R070()
        result = rule.execute(df, engine_context)
        assert result.iloc[0]["conta_contabil"] == "111110200"

    def test_competencia_preenchida_na_pendencia(self) -> None:
        """Competência da pendência vem do contexto, não do DataFrame."""
        from ranking_msc.config.settings import Settings
        ctx = EngineContext(
            competencia="2025-06",
            siconfi="250400",
            settings=Settings(),
            usuario="teste",
        )
        df = _make_dup_df(n=2)  # df tem competencia="2024-01" nos dados
        rule = R070()
        result = rule.execute(df, ctx)
        # Deve usar o valor do contexto, não da coluna competencia do df
        assert result.iloc[0]["competencia"] == "2025-06"

    def test_valor_esperado_descritivo(self, engine_context: EngineContext) -> None:
        """valor_esperado deve descrever unicidade esperada."""
        df = _make_dup_df(n=2)
        rule = R070()
        result = rule.execute(df, engine_context)
        assert "1 ocorrência" in result.iloc[0]["valor_esperado"]

    def test_linha_unica_por_conta_sem_pendencia(self, engine_context: EngineContext) -> None:
        """Múltiplas contas distintas (sem duplicatas) não geram pendência."""
        df = pd.concat([
            _make_df(conta_contabil=f"11111020{i}", fr=str(1000 + i))
            for i in range(5)
        ], ignore_index=True)
        rule = R070()
        result = rule.execute(df, engine_context)
        assert len(result) == 0
