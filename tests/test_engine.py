"""
tests/test_engine.py
~~~~~~~~~~~~~~~~~~~~

Testes do loop de execução do motor em ``ranking_msc.engine.executor``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd
import pytest

from ranking_msc.config.settings import RulesSettings, Settings
from ranking_msc.engine.executor import EngineContext, run_engine
from ranking_msc.rules.base import RULE_REGISTRY, Rule
from ranking_msc.schemas import FACT_RESULTADO_REGRAS_COLUMNS

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture
def isolated_registry() -> Iterator[None]:
    """Isola RULE_REGISTRY para evitar vazamento entre testes."""
    snapshot = RULE_REGISTRY.copy()
    RULE_REGISTRY.clear()
    try:
        yield
    finally:
        RULE_REGISTRY.clear()
        RULE_REGISTRY.update(snapshot)


def _build_context(*, enabled: list[str], fail_fast: bool) -> EngineContext:
    """Cria EngineContext para os cenários de teste do motor."""
    settings = Settings(rules=RulesSettings(enabled=enabled, fail_fast=fail_fast))
    return EngineContext(
        competencia="2024-01",
        siconfi="250400",
        settings=settings,
        usuario="teste",
    )


class RIssueDummy(Rule):
    """Regra dummy que sempre gera uma pendência."""

    rule_id = "R_ISSUE"
    rule_name = "Dummy com pendência"
    dimensao = "Teste"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        return self.build_issues(
            [
                {
                    "severidade": "ERRO",
                    "conta_contabil": "111110200",
                    "descricao": "Pendência dummy",
                    "valor_esperado": "0",
                    "valor_encontrado": "1",
                    "competencia": context.competencia,
                },
            ],
        )


class RErrorDummy(Rule):
    """Regra dummy que sempre falha."""

    rule_id = "R_ERROR"
    rule_name = "Dummy com erro"
    dimensao = "Teste"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        raise ValueError("Falha simulada na regra")


def test_run_engine_sem_regras_retorna_resultado_vazio(isolated_registry: None) -> None:
    """Com 0 regras habilitadas, retorno é vazio e status é OK."""
    context = _build_context(enabled=[], fail_fast=False)

    result = run_engine(pd.DataFrame(), context)

    assert result.status == "OK"
    assert result.regras_executadas == 0
    assert result.regras_com_erro == 0
    assert result.total_pendencias == 0
    assert list(result.pendencias.columns) == FACT_RESULTADO_REGRAS_COLUMNS


def test_run_engine_com_regra_dummy_concatena_pendencias(isolated_registry: None) -> None:
    """Com regra dummy válida, pendências aparecem no EngineResult."""
    RULE_REGISTRY[RIssueDummy.rule_id] = RIssueDummy
    context = _build_context(enabled=[RIssueDummy.rule_id], fail_fast=False)

    result = run_engine(pd.DataFrame(), context)

    assert result.status == "OK"
    assert result.regras_executadas == 1
    assert result.regras_com_erro == 0
    assert result.total_pendencias == 1
    assert result.pendencias.iloc[0]["regra_id"] == RIssueDummy.rule_id
    assert result.pendencias.iloc[0]["descricao"] == "Pendência dummy"


def test_run_engine_erro_uma_regra_nao_bloqueia_outras_quando_fail_fast_false(
    isolated_registry: None,
) -> None:
    """Erro individual não interrompe execução das demais regras."""
    RULE_REGISTRY[RErrorDummy.rule_id] = RErrorDummy
    RULE_REGISTRY[RIssueDummy.rule_id] = RIssueDummy
    context = _build_context(
        enabled=[RErrorDummy.rule_id, RIssueDummy.rule_id],
        fail_fast=False,
    )

    result = run_engine(pd.DataFrame(), context)

    assert result.status == "PARCIAL"
    assert result.regras_executadas == 2
    assert result.regras_com_erro == 1
    assert result.total_pendencias == 1
    assert len(result.erros) == 1
    assert result.erros[0]["rule_id"] == RErrorDummy.rule_id
    assert result.erros[0]["fatal"] is False
    assert result.pendencias.iloc[0]["regra_id"] == RIssueDummy.rule_id


def test_run_engine_fail_fast_true_interrompe_na_primeira_falha(isolated_registry: None) -> None:
    """Com fail_fast=True, motor interrompe após primeiro erro e status é ERRO."""
    RULE_REGISTRY[RErrorDummy.rule_id] = RErrorDummy
    RULE_REGISTRY[RIssueDummy.rule_id] = RIssueDummy
    context = _build_context(
        enabled=[RErrorDummy.rule_id, RIssueDummy.rule_id],
        fail_fast=True,
    )

    result = run_engine(pd.DataFrame(), context)

    assert result.status == "ERRO"
    assert result.regras_executadas == 1
    assert result.regras_com_erro == 1
    assert result.total_pendencias == 0
    assert len(result.erros) == 1
    assert result.erros[0]["rule_id"] == RErrorDummy.rule_id
    assert result.erros[0]["fatal"] is True
