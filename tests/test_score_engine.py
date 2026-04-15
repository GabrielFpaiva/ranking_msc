"""
tests/test_score_engine.py
~~~~~~~~~~~~~~~~~~~~~~~~~~

Testes do motor de pontuação (engine/score_engine.py).
"""

from __future__ import annotations

import pandas as pd
import pytest

from ranking_msc.engine.score_engine import (
    _CATEGORY_TO_DIMENSION,
    DIMENSION_CATEGORIES,
    DIMENSION_WEIGHTS,
    _classify_band,
    calculate_score,
)
from ranking_msc.rules.base import RULE_REGISTRY, Rule


class TestIsScoringAttribute:
    """Verifica que o atributo is_scoring existe na classe Rule."""

    def test_rule_has_is_scoring_attribute(self):
        """Rule ABC deve ter is_scoring = True por padrão."""
        assert hasattr(Rule, "is_scoring")
        assert Rule.is_scoring is True

    def test_is_scoring_inherits_true_by_default(self):
        """Subclasse sem is_scoring herda True da classe base."""

        class DummyRule(Rule):
            rule_id = "_TST_DEFAULT"
            rule_name = "test"
            dimensao = "Estrutura"

            def execute(self, df, context):
                return self.build_issues([])

        assert DummyRule.is_scoring is True

    def test_is_scoring_can_be_false(self):
        """Subclasse pode declarar is_scoring = False para regras INFO-only."""
        from typing import ClassVar

        class InfoOnlyRule(Rule):
            rule_id = "_TST_INFO"
            rule_name = "info only"
            dimensao = "Temporal"
            is_scoring: ClassVar[bool] = False

            def execute(self, df, context):
                return self.build_issues([])

        assert InfoOnlyRule.is_scoring is False


class TestConstants:
    """Verifica integridade das constantes do modelo de pontuação."""

    def test_dimension_weights_sum_to_one(self):
        """Os pesos das 5 dimensões devem somar exatamente 1.0."""
        assert abs(sum(DIMENSION_WEIGHTS.values()) - 1.0) < 1e-9

    def test_five_dimensions_defined(self):
        """Exactamente 5 dimensões devem existir."""
        assert set(DIMENSION_WEIGHTS.keys()) == {
            "Estrutura",
            "Fechamento",
            "IC_Dominio",
            "PCASP_Completude",
            "Temporal",
        }

    def test_all_categories_map_to_known_dimension(self):
        """Todo valor de dimensao usado nas regras mapeia a uma das 5 dimensões."""
        known_categories = {
            "Estrutura",
            "Formato",
            "Duplicidade",
            "Fechamento",
            "Interconta",
            "IC",
            "PO",
            "NR",
            "ND",
            "FR",
            "CO",
            "FS",
            "DC",
            "FP",
            "AI",
            "PCASP",
            "Completude",
            "Superávit",
            "Temporal",
            "Qualidade",
        }
        for cat in known_categories:
            assert cat in _CATEGORY_TO_DIMENSION, f"Categoria '{cat}' não mapeada"

    def test_category_to_dimension_inverse_is_consistent(self):
        """Lookup inverso é consistente com DIMENSION_CATEGORIES."""
        for dim, cats in DIMENSION_CATEGORIES.items():
            for cat in cats:
                assert _CATEGORY_TO_DIMENSION[cat] == dim


class TestBandClassification:
    """Verifica a classificação A-E por pontuação."""

    def test_band_a_at_95(self):
        assert _classify_band(95.0) == "A"

    def test_band_a_at_100(self):
        assert _classify_band(100.0) == "A"

    def test_band_b_at_85(self):
        assert _classify_band(85.0) == "B"

    def test_band_b_at_94_9(self):
        assert _classify_band(94.9) == "B"

    def test_band_c_at_75(self):
        assert _classify_band(75.0) == "C"

    def test_band_d_at_65(self):
        assert _classify_band(65.0) == "D"

    def test_band_e_below_65(self):
        assert _classify_band(64.9) == "E"

    def test_band_e_at_zero(self):
        assert _classify_band(0.0) == "E"


# ---------------------------------------------------------------------------
# Helpers para criar regras e pendências de teste
# ---------------------------------------------------------------------------


def _make_rule(rule_id: str, dimensao: str, is_scoring: bool = True) -> type[Rule]:
    """Cria uma subclasse Rule de teste dinamicamente."""

    class _R(Rule):
        pass

    _R.rule_id = rule_id
    _R.rule_name = f"Test {rule_id}"
    _R.dimensao = dimensao
    _R.is_scoring = is_scoring
    _R.__name__ = f"_TestRule_{rule_id}"
    _R.execute = lambda self, df, ctx: self.build_issues([])  # type: ignore[assignment]
    return _R


def _make_pendencias(rows: list[dict]) -> pd.DataFrame:
    """Cria DataFrame de pendências a partir de lista de dicts."""
    cols = [
        "regra_id",
        "regra_nome",
        "dimensao",
        "severidade",
        "conta_contabil",
        "descricao",
        "valor_esperado",
        "valor_encontrado",
        "competencia",
    ]
    if not rows:
        return pd.DataFrame(columns=cols)
    df = pd.DataFrame(rows)
    for col in cols:
        if col not in df.columns:
            df[col] = ""
    return df[cols]


@pytest.fixture
def registered_rules():
    """Registra regras de teste e limpa o registry ao fim."""
    rules = [
        _make_rule("TST_E1", "Estrutura"),
        _make_rule("TST_E2", "Estrutura"),
        _make_rule("TST_F1", "Fechamento"),
        _make_rule("TST_F2", "Fechamento"),
        _make_rule("TST_F3", "Fechamento"),
        _make_rule("TST_IC1", "IC"),
        _make_rule("TST_IC2", "IC"),
        _make_rule("TST_PC1", "PCASP"),
        _make_rule("TST_PC2", "Completude"),
        _make_rule("TST_T1", "Temporal"),
        _make_rule("TST_T2", "Qualidade"),
        _make_rule("TST_INFO", "Temporal", is_scoring=False),  # INFO-only
    ]
    for r in rules:
        RULE_REGISTRY[r.rule_id] = r
    yield rules
    for r in rules:
        RULE_REGISTRY.pop(r.rule_id, None)


class TestCalculateScore:
    """Testa a função calculate_score() com cenários controlados."""

    def test_all_rules_pass_score_100(self, registered_rules):
        """Todas as regras passam → score = 100.0, banda = A."""
        rule_ids = ["TST_E1", "TST_F1", "TST_IC1", "TST_PC1", "TST_T1"]
        result = calculate_score(_make_pendencias([]), rule_ids)

        assert result.pontuacao == 100.0
        assert result.banda == "A"
        assert result.regras_executadas == 5
        assert result.regras_falhas_erro == 0
        assert result.regras_falhas_alerta == 0

    def test_one_erro_reduces_score(self, registered_rules):
        """Uma regra ERRO reduz a pontuação abaixo de 100."""
        pendencias = _make_pendencias([
            {"regra_id": "TST_E1", "severidade": "ERRO", "competencia": "2024-01"},
        ])
        rule_ids = ["TST_E1", "TST_F1", "TST_IC1", "TST_PC1", "TST_T1"]
        result = calculate_score(pendencias, rule_ids)

        assert result.pontuacao < 100.0
        assert result.regras_falhas_erro == 1
        # Estrutura: TST_E1 falhou ERRO → w=2, ok=0 → P_Estrutura = 0/2 = 0
        assert result.dimensions["Estrutura"].score == 0.0

    def test_alerta_lighter_than_erro(self, registered_rules):
        """ALERTA penaliza menos do que ERRO (w=1 vs w=2)."""
        pendencias_erro = _make_pendencias([
            {"regra_id": "TST_E1", "severidade": "ERRO", "competencia": "2024-01"},
        ])
        pendencias_alerta = _make_pendencias([
            {"regra_id": "TST_E1", "severidade": "ALERTA", "competencia": "2024-01"},
        ])
        rule_ids = ["TST_E1", "TST_E2"]

        result_erro = calculate_score(pendencias_erro, rule_ids)
        result_alerta = calculate_score(pendencias_alerta, rule_ids)

        # ERRO:   TST_E2 pass w=1·ok=1=1, TST_E1 ERRO w=2·ok=0=0 → P = 1/(1+2) = 1/3
        # ALERTA: TST_E2 pass w=1·ok=1=1, TST_E1 ALT  w=1·ok=0=0 → P = 1/(1+1) = 1/2
        assert result_alerta.pontuacao > result_erro.pontuacao

    def test_info_only_excluded_from_score(self, registered_rules):
        """Regra INFO-only não afeta pontuação mesmo quando 'passa'."""
        rule_ids_with_info = ["TST_T1", "TST_INFO"]
        rule_ids_without_info = ["TST_T1"]

        result_with = calculate_score(_make_pendencias([]), rule_ids_with_info)
        result_without = calculate_score(_make_pendencias([]), rule_ids_without_info)

        assert result_with.pontuacao == result_without.pontuacao == 100.0
        assert result_with.regras_executadas == result_without.regras_executadas

    def test_temporal_excluded_weights_renormalize(self, registered_rules):
        """Sem regras Temporal, pesos renormalizam e score permanece válido."""
        rule_ids = ["TST_E1"]
        result = calculate_score(_make_pendencias([]), rule_ids)

        assert result.pontuacao == 100.0
        assert "Temporal" not in result.dimensions
        # Só Estrutura ativa: W_norm deve ser 1.0
        assert abs(result.dimensions["Estrutura"].weight_normalized - 1.0) < 1e-9

    def test_dimension_weights_sum_to_one(self, registered_rules):
        """Pesos normalizados das dimensões ativas devem somar 1.0."""
        rule_ids = ["TST_E1", "TST_F1", "TST_IC1", "TST_PC1", "TST_T1"]
        result = calculate_score(_make_pendencias([]), rule_ids)

        total_weight = sum(d.weight_normalized for d in result.dimensions.values())
        assert abs(total_weight - 1.0) < 1e-9

    def test_no_executed_rules_returns_zero(self):
        """Sem regras executadas → score = 0.0, banda = E."""
        result = calculate_score(_make_pendencias([]), [])
        assert result.pontuacao == 0.0
        assert result.banda == "E"
        assert result.regras_executadas == 0

    def test_model_example_section_7(self, registered_rules):
        """Reproduz o exemplo da seção 7 de modelo_pontuacao.md → ~83.4."""
        # Criar regras adicionais para chegar aos números do exemplo:
        # Estrutura: 14 passing
        # Fechamento: 8 pass + 1 ALERTA + 1 ERRO = 10 scoring
        # IC/Domínio: 18 pass + 2 ALERTA + 2 ERRO = 22 scoring
        # PCASP: 11 pass + 2 ALERTA = 13 scoring
        # Temporal: 3 pass = 3 scoring
        extra_rules = [
            *[_make_rule(f"TST_EX_E{i}", "Estrutura") for i in range(12)],
            *[_make_rule(f"TST_EX_F{i}", "Fechamento") for i in range(7)],
            *[_make_rule(f"TST_EX_IC{i}", "IC") for i in range(20)],
            *[_make_rule(f"TST_EX_PC{i}", "PCASP") for i in range(11)],
            _make_rule("TST_EX_T0", "Temporal"),
            _make_rule("TST_EX_INFO1", "Temporal", is_scoring=False),
            _make_rule("TST_EX_INFO2", "Temporal", is_scoring=False),
        ]
        for r in extra_rules:
            RULE_REGISTRY[r.rule_id] = r

        try:
            # 14 Estrutura: TST_E1, TST_E2 + EX_E0..EX_E11 = 14, all pass
            estrutura_ids = ["TST_E1", "TST_E2"] + [f"TST_EX_E{i}" for i in range(12)]

            # 10 Fechamento: TST_F1..F3 + EX_F0..EX_F6 = 10
            # TST_F2=ALERTA, TST_F3=ERRO, rest pass (8 pass)
            fechamento_ids = ["TST_F1", "TST_F2", "TST_F3"] + [f"TST_EX_F{i}" for i in range(7)]

            # 22 IC_Dominio scoring: TST_IC1, TST_IC2 + EX_IC0..EX_IC15 = 18
            # TST_IC1=ALERTA, TST_IC2=ERRO, EX_IC0=ALERTA, EX_IC1=ERRO, rest 18 pass
            ic_ids = ["TST_IC1", "TST_IC2"] + [f"TST_EX_IC{i}" for i in range(20)]

            # 13 PCASP: TST_PC1, TST_PC2 + EX_PC0..EX_PC8 = 11
            # TST_PC1=ALERTA, TST_PC2=ALERTA, rest 9 pass
            pc_ids = ["TST_PC1", "TST_PC2"] + [f"TST_EX_PC{i}" for i in range(11)]

            # 3 Temporal scoring: TST_T1, TST_T2, EX_T0 — all pass
            # 3 INFO excluded: TST_INFO, EX_INFO1, EX_INFO2
            temporal_ids = ["TST_T1", "TST_T2", "TST_EX_T0",
                           "TST_INFO", "TST_EX_INFO1", "TST_EX_INFO2"]

            all_rule_ids = estrutura_ids + fechamento_ids + ic_ids + pc_ids + temporal_ids

            pendencias = _make_pendencias([
                {"regra_id": "TST_F2", "severidade": "ALERTA", "competencia": "2025-01"},
                {"regra_id": "TST_F3", "severidade": "ERRO",   "competencia": "2025-01"},
                {"regra_id": "TST_IC1", "severidade": "ALERTA", "competencia": "2025-01"},
                {"regra_id": "TST_IC2", "severidade": "ERRO",   "competencia": "2025-01"},
                {"regra_id": "TST_EX_IC0", "severidade": "ALERTA", "competencia": "2025-01"},
                {"regra_id": "TST_EX_IC1", "severidade": "ERRO",   "competencia": "2025-01"},
                {"regra_id": "TST_PC1", "severidade": "ALERTA", "competencia": "2025-01"},
                {"regra_id": "TST_PC2", "severidade": "ALERTA", "competencia": "2025-01"},
            ])

            result = calculate_score(pendencias, all_rule_ids)

            # P_d per dimension (from modelo_pontuacao.md §7)
            assert abs(result.dimensions["Estrutura"].score - 1.000) < 0.001
            assert abs(result.dimensions["Fechamento"].score - 8 / 11) < 0.001
            assert abs(result.dimensions["IC_Dominio"].score - 18 / 24) < 0.001
            assert abs(result.dimensions["PCASP_Completude"].score - 11 / 13) < 0.001
            assert abs(result.dimensions["Temporal"].score - 1.000) < 0.001

            assert abs(result.pontuacao - 83.4) < 0.1
            assert result.banda == "C"

        finally:
            for r in extra_rules:
                RULE_REGISTRY.pop(r.rule_id, None)
