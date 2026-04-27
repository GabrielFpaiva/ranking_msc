"""
app.api.routes.rules
~~~~~~~~~~~~~~~~~~~~

Catálogo de regras (RULE_REGISTRY), detalhes para o Drawer Regra,
heatmap regras × competências e histórico de uma regra.
"""

from __future__ import annotations

import inspect
import re

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import absolute_snapshots_dir
from app.api.schemas import (
    HeatmapCellOut,
    HeatmapOut,
    HeatmapRegraOut,
    RuleDetailOut,
    RuleHistoryOut,
    RuleOut,
)
from ranking_msc.outputs.aggregations import build_heatmap, rule_history
from ranking_msc.rules.base import RULE_REGISTRY

router = APIRouter(prefix="/api", tags=["rules"])


@router.get(
    "/rules",
    response_model=list[RuleOut],
    summary="Catálogo de regras registradas em RULE_REGISTRY",
)
def list_rules() -> list[RuleOut]:
    """Lista todas as regras do RULE_REGISTRY ordenadas por id."""
    return [
        RuleOut(
            rule_id=rid,
            rule_name=cls.rule_name,
            dimensao=cls.dimensao,
            is_scoring=cls.is_scoring,
        )
        for rid, cls in sorted(RULE_REGISTRY.items())
    ]


@router.get(
    "/rules/{rule_id}",
    response_model=RuleDetailOut,
    summary="Detalhe de uma regra para o Drawer Regra",
)
def get_rule(rule_id: str) -> RuleDetailOut:
    """Devolve metadados + descrição extraída da docstring do módulo."""
    cls = RULE_REGISTRY.get(rule_id)
    if cls is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Regra {rule_id} não está registrada.",
        )

    module_doc = inspect.getmodule(cls).__doc__ or ""
    descricao = _extract_descricao(module_doc) or cls.rule_name
    formula = _extract_formula(module_doc)

    return RuleDetailOut(
        rule_id=rule_id,
        rule_name=cls.rule_name,
        dimensao=cls.dimensao,
        is_scoring=cls.is_scoring,
        descricao=descricao,
        formula=formula,
    )


@router.get(
    "/heatmap",
    response_model=HeatmapOut,
    summary="Matriz regras × competências (últimos N meses)",
)
def get_heatmap(
    siconfi: str = Query(..., description="Código SICONFI do ente"),
    meses: int = Query(6, ge=1, le=24),
) -> HeatmapOut:
    """Heatmap completo da tela Regras."""
    matrix = build_heatmap(absolute_snapshots_dir(), siconfi, meses=meses)
    return HeatmapOut(
        siconfi=siconfi,
        competencias=matrix.competencias,
        regras=[HeatmapRegraOut(**r) for r in matrix.regras],
        cells=[
            HeatmapCellOut(
                regra_id=c.regra_id,
                competencia=c.competencia,
                pendencias=c.pendencias,
                severidade_max=c.severidade_max,  # type: ignore[arg-type]
            )
            for c in matrix.cells
        ],
    )


@router.get(
    "/rule-history/{rule_id}",
    response_model=RuleHistoryOut,
    summary="Histórico de uma regra ao longo das últimas competências",
)
def get_rule_history(
    rule_id: str,
    siconfi: str = Query(..., description="Código SICONFI do ente"),
    meses: int = Query(6, ge=1, le=24),
) -> RuleHistoryOut:
    if rule_id not in RULE_REGISTRY:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Regra {rule_id} não está registrada.",
        )
    cells = rule_history(absolute_snapshots_dir(), siconfi, rule_id, meses=meses)
    return RuleHistoryOut(
        siconfi=siconfi,
        rule_id=rule_id,
        cells=[
            HeatmapCellOut(
                regra_id=c.regra_id,
                competencia=c.competencia,
                pendencias=c.pendencias,
                severidade_max=c.severidade_max,  # type: ignore[arg-type]
            )
            for c in cells
        ],
    )


# ---------------------------------------------------------------------------
# Helpers — extração da docstring do módulo da regra
# ---------------------------------------------------------------------------


def _extract_descricao(doc: str) -> str:
    """Extrai a primeira linha não-vazia/heading como resumo."""
    for line in doc.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(("Regra", "~", "=", "-")) and "—" not in stripped:
            continue
        if stripped.startswith("Regra ") and "—" in stripped:
            return stripped.split("—", 1)[1].strip()
        return stripped
    return ""


_FORMULA_RE = re.compile(r"Lógica:\s*(.*?)(?:\n\s*\n|\nReferência:|\Z)", re.DOTALL)


def _extract_formula(doc: str) -> str | None:
    """Extrai o bloco ``Lógica:`` da docstring (se existir)."""
    match = _FORMULA_RE.search(doc)
    if not match:
        return None
    text = match.group(1).strip()
    # Remove indent comum
    lines = [ln[4:] if ln.startswith("    ") else ln for ln in text.splitlines()]
    return "\n".join(lines).strip() or None
