"""
Testes de ranking_msc.outputs.aggregations.
"""

from __future__ import annotations

import pandas as pd
import pytest

from ranking_msc.exceptions import ConfigError
from ranking_msc.outputs.aggregations import (
    SuperavitSummary,
    TopRule,
    aggregate_superavit_rows,
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


class TestAggregateSuperavitRows:
    def test_agrega_ativo_e_passivo_por_fr(self) -> None:
        df = pd.DataFrame(
            [
                {
                    "conta_contabil": "111110200",
                    "fr": "1500",
                    "saldo_final_debito": 1200.0,
                    "saldo_final_credito": 0.0,
                },
                {
                    "conta_contabil": "218810101",
                    "fr": "1500",
                    "saldo_final_debito": 0.0,
                    "saldo_final_credito": 450.0,
                },
                {
                    "conta_contabil": "111110100",
                    "fr": "1700",
                    "saldo_final_debito": 300.0,
                    "saldo_final_credito": 0.0,
                },
            ]
        )
        pcasp = pd.DataFrame(
            [
                {"conta_contabil": "111110200", "nat_saldo": "Devedora", "ind_sf": "Financeiro"},
                {"conta_contabil": "218810101", "nat_saldo": "Credora", "ind_sf": "Financeiro"},
                {"conta_contabil": "111110100", "nat_saldo": "Devedora", "ind_sf": "Financeiro"},
            ]
        )

        out = aggregate_superavit_rows(df, pcasp=pcasp)

        assert isinstance(out, SuperavitSummary)
        assert out.total_ativo_financeiro == 1500.0
        assert out.total_passivo_financeiro == 450.0
        assert out.total_resultado_financeiro == 1050.0
        assert [item.fr for item in out.items] == ["1500", "1700"]
        by_fr = {item.fr: item for item in out.items}
        assert by_fr["1500"].passivo_financeiro == 450.0
        assert by_fr["1500"].resultado_financeiro == 750.0

    def test_exclui_fr_vazia_sem_match_e_financeiro_permanente(self) -> None:
        df = pd.DataFrame(
            [
                {
                    "conta_contabil": "111110200",
                    "fr": "",
                    "saldo_final_debito": 100.0,
                    "saldo_final_credito": 0.0,
                },
                {
                    "conta_contabil": "999999999",
                    "fr": "1500",
                    "saldo_final_debito": 100.0,
                    "saldo_final_credito": 0.0,
                },
                {
                    "conta_contabil": "123456789",
                    "fr": "1500",
                    "saldo_final_debito": 200.0,
                    "saldo_final_credito": 0.0,
                },
            ]
        )
        pcasp = pd.DataFrame(
            [
                {
                    "conta_contabil": "123456789",
                    "nat_saldo": "Devedora",
                    "ind_sf": "Financeiro/Permanente",
                }
            ]
        )

        out = aggregate_superavit_rows(df, pcasp=pcasp)

        assert out.items == []
        assert out.total_resultado_financeiro == 0.0
        assert out.contas_consideradas == 0


    def test_exclui_fr_placeholder_zero_e_nan(self) -> None:
        df = pd.DataFrame(
            [
                {
                    "conta_contabil": "111110200",
                    "fr": "0",
                    "saldo_final_debito": 100.0,
                    "saldo_final_credito": 0.0,
                },
                {
                    "conta_contabil": "218810101",
                    "fr": "nan",
                    "saldo_final_debito": 0.0,
                    "saldo_final_credito": 50.0,
                },
                {
                    "conta_contabil": "111110100",
                    "fr": "1500",
                    "saldo_final_debito": 300.0,
                    "saldo_final_credito": 0.0,
                },
            ]
        )
        pcasp = pd.DataFrame(
            [
                {"conta_contabil": "111110200", "nat_saldo": "Devedora", "ind_sf": "Financeiro"},
                {"conta_contabil": "218810101", "nat_saldo": "Credora", "ind_sf": "Financeiro"},
                {"conta_contabil": "111110100", "nat_saldo": "Devedora", "ind_sf": "Financeiro"},
            ]
        )

        out = aggregate_superavit_rows(df, pcasp=pcasp)

        assert [item.fr for item in out.items] == ["1500"]
        assert out.total_ativo_financeiro == 300.0
        assert out.total_passivo_financeiro == 0.0
        assert out.total_resultado_financeiro == 300.0

    def test_erro_controlado_quando_pcasp_esta_vazio(self) -> None:
        df = pd.DataFrame(
            [
                {
                    "conta_contabil": "111110100",
                    "fr": "1500",
                    "saldo_final_debito": 300.0,
                    "saldo_final_credito": 0.0,
                }
            ]
        )
        pcasp = pd.DataFrame(columns=["conta_contabil", "nat_saldo", "ind_sf"])

        with pytest.raises(ConfigError, match="PCASP vazia"):
            aggregate_superavit_rows(df, pcasp=pcasp)

    def test_erro_controlado_quando_pcasp_nao_tem_colunas_exigidas(self) -> None:
        df = pd.DataFrame(
            [
                {
                    "conta_contabil": "111110100",
                    "fr": "1500",
                    "saldo_final_debito": 300.0,
                    "saldo_final_credito": 0.0,
                }
            ]
        )
        pcasp = pd.DataFrame([{"conta_contabil": "111110100"}])

        with pytest.raises(ConfigError, match="faltam colunas"):
            aggregate_superavit_rows(df, pcasp=pcasp)
