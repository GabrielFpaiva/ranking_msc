"""
Testes de ranking_msc.outputs.aggregations.
"""

from __future__ import annotations

import pandas as pd

from ranking_msc.outputs.aggregations import (
    TopRule,
    filter_pendencias,
    top_violated_rules,
)


def _build_pendencias(rows: list[dict[str, object]]) -> pd.DataFrame:
    return pd.DataFrame(rows)


class TestTopViolatedRules:
    def test_dataframe_vazio_retorna_lista_vazia(self) -> None:
        df = _build_pendencias([])
        assert top_violated_rules(df) == []

    def test_ordena_por_quantidade_desc(self) -> None:
        df = _build_pendencias(
            [
                {"regra_id": "R001", "regra_nome": "A", "dimensao": "X", "severidade": "ALERTA"},
                {"regra_id": "R001", "regra_nome": "A", "dimensao": "X", "severidade": "ALERTA"},
                {"regra_id": "R002", "regra_nome": "B", "dimensao": "Y", "severidade": "ERRO"},
            ]
        )
        top = top_violated_rules(df, limit=10)
        assert top[0].regra_id == "R001"
        assert top[0].pendencias == 2
        assert top[1].regra_id == "R002"

    def test_severidade_max_capta_pior_caso(self) -> None:
        df = _build_pendencias(
            [
                {"regra_id": "R001", "regra_nome": "A", "dimensao": "X", "severidade": "ALERTA"},
                {"regra_id": "R001", "regra_nome": "A", "dimensao": "X", "severidade": "ERRO"},
            ]
        )
        top = top_violated_rules(df)
        assert top[0].severidade_max == "ERRO"

    def test_respeita_limit(self) -> None:
        df = _build_pendencias(
            [
                {
                    "regra_id": f"R{i:03d}",
                    "regra_nome": f"R{i}",
                    "dimensao": "X",
                    "severidade": "INFO",
                }
                for i in range(20)
            ]
        )
        top = top_violated_rules(df, limit=5)
        assert len(top) == 5
        assert all(isinstance(t, TopRule) for t in top)


class TestFilterPendencias:
    def _df(self) -> pd.DataFrame:
        return _build_pendencias(
            [
                {"regra_id": "R020", "severidade": "ERRO", "conta_contabil": "111110200"},
                {"regra_id": "R020", "severidade": "ALERTA", "conta_contabil": "211110100"},
                {"regra_id": "R030", "severidade": "ERRO", "conta_contabil": "111120300"},
            ]
        )

    def test_filtro_por_regra_id(self) -> None:
        out = filter_pendencias(self._df(), regra_id="R020")
        assert len(out) == 2

    def test_filtro_por_severidade(self) -> None:
        out = filter_pendencias(self._df(), severidade="ERRO")
        assert len(out) == 2

    def test_filtro_por_conta_prefix(self) -> None:
        out = filter_pendencias(self._df(), conta_contabil_prefix="1.1.1")
        # Não casa porque prefixo é literal — agora testamos com prefixo real:
        out = filter_pendencias(self._df(), conta_contabil_prefix="111")
        assert len(out) == 2

    def test_filtros_combinados(self) -> None:
        out = filter_pendencias(self._df(), regra_id="R020", severidade="ERRO")
        assert len(out) == 1
