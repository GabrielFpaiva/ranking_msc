"""Smoke tests para o Tab Registry do dashboard."""
from __future__ import annotations

import pandas as pd
import pytest

from ranking_msc.config.settings import Settings
from ranking_msc.engine.executor import EngineContext, EngineResult
from ranking_msc.schemas import FACT_RESULTADO_REGRAS_COLUMNS


@pytest.fixture
def empty_result() -> EngineResult:
    """EngineResult vazio (sem pendências)."""
    ctx = EngineContext(competencia="2026-01", siconfi="250400", settings=Settings())
    return EngineResult(context=ctx)


@pytest.fixture
def result_with_issues() -> EngineResult:
    """EngineResult com pendências simuladas de R032."""
    ctx = EngineContext(competencia="2026-01", siconfi="250400", settings=Settings())
    df = pd.DataFrame([
        {
            "regra_id": "R032",
            "regra_nome": "Saldo Devedor",
            "dimensao": "PCASP",
            "severidade": "ERRO",
            "conta_contabil": "1.1.1.1.1.01.00",
            "descricao": "Conta credora com saldo devedor",
            "valor_esperado": "Credora",
            "valor_encontrado": "100.00",
            "competencia": "2026-01",
        },
        {
            "regra_id": "R021",
            "regra_nome": "Outra Regra",
            "dimensao": "Domínio",
            "severidade": "ALERTA",
            "conta_contabil": "2.1.1.1.1.01.00",
            "descricao": "Alerta genérico",
            "valor_esperado": "",
            "valor_encontrado": "",
            "competencia": "2026-01",
        },
    ], columns=FACT_RESULTADO_REGRAS_COLUMNS)
    return EngineResult(context=ctx, pendencias=df, regras_executadas=2)


@pytest.mark.skip(reason="Tab not implemented yet — Task 2/3/4")
def test_tab_registry_importa_todas_abas():
    """Após importar app.tabs, registry deve ter 3 abas."""
    import app.tabs  # noqa: F401 — importação dispara registro
    from app.tabs.base import TAB_REGISTRY

    assert "status_geral" in TAB_REGISTRY
    assert "pendencias" in TAB_REGISTRY
    assert "saldo_devedor" in TAB_REGISTRY


def test_tab_registry_ordem():
    """Abas devem ter order distintos e crescentes."""
    import app.tabs  # noqa: F401
    from app.tabs.base import TAB_REGISTRY

    orders = sorted(tab.order for tab in TAB_REGISTRY.values())
    assert len(orders) == len(set(orders)), "order deve ser único por aba"
    assert orders == sorted(orders), "order deve ser crescente"


def test_render_none_retorna_viewable(empty_result):
    """render(None) de cada aba deve retornar Panel Viewable."""
    import app.tabs  # noqa: F401
    import panel as pn
    from app.tabs.base import TAB_REGISTRY

    for tab_id, tab in TAB_REGISTRY.items():
        result = tab.render(None)
        assert isinstance(result, pn.viewable.Viewable), (
            f"Tab '{tab_id}': render(None) deve retornar Viewable, got {type(result)}"
        )


def test_render_result_retorna_viewable(result_with_issues):
    """render(EngineResult) de cada aba deve retornar Panel Viewable."""
    import app.tabs  # noqa: F401
    import panel as pn
    from app.tabs.base import TAB_REGISTRY

    for tab_id, tab in TAB_REGISTRY.items():
        result = tab.render(result_with_issues)
        assert isinstance(result, pn.viewable.Viewable), (
            f"Tab '{tab_id}': render(result) deve retornar Viewable, got {type(result)}"
        )


def test_status_geral_conta_severidades(result_with_issues):
    """StatusGeralTab deve contar ERROs e ALERTAs corretamente."""
    import app.tabs  # noqa: F401
    import panel as pn
    from app.tabs.base import TAB_REGISTRY

    tab = TAB_REGISTRY["status_geral"]
    viewable = tab.render(result_with_issues)
    assert viewable is not None
    # Verify Number indicators show correct counts.
    # Numbers are nested inside a Row inside the Column — walk one level deep.
    numbers: list[pn.indicators.Number] = []
    for obj in viewable.objects:
        if isinstance(obj, pn.indicators.Number):
            numbers.append(obj)
        elif hasattr(obj, "objects"):
            numbers.extend(o for o in obj.objects if isinstance(o, pn.indicators.Number))
    by_name = {n.name: n.value for n in numbers}
    assert by_name["ERROs"] == 1
    assert by_name["ALERTAs"] == 1
    assert by_name["INFOs"] == 0


@pytest.mark.skip(reason="Tab not implemented yet — Task 2/3/4")
def test_saldo_devedor_filtra_r032(result_with_issues):
    """SaldoDevedorTab deve filtrar só regra R032."""
    import app.tabs  # noqa: F401
    from app.tabs.base import TAB_REGISTRY

    tab = TAB_REGISTRY["saldo_devedor"]
    viewable = tab.render(result_with_issues)
    assert viewable is not None


@pytest.mark.skip(reason="Tab not implemented yet — Task 2/3/4")
def test_saldo_devedor_sem_r032(empty_result):
    """SaldoDevedorTab com result vazio deve mostrar mensagem de sucesso."""
    import app.tabs  # noqa: F401
    from app.tabs.base import TAB_REGISTRY

    tab = TAB_REGISTRY["saldo_devedor"]
    viewable = tab.render(empty_result)
    assert viewable is not None
