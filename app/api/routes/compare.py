"""
app.api.routes.compare
~~~~~~~~~~~~~~~~~~~~~~

GET /api/compare?siconfi=&a=&b= — diff de score entre 2 competências.
Reaproveita ranking_msc.engine.compare_periods para garantir consistência
com o relatório Excel consolidado.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import absolute_snapshots_dir, get_settings
from app.api.schemas import CompareDimensionOut, CompareOut, CompareSideOut
from ranking_msc.engine.compare_periods import compare_periods

router = APIRouter(prefix="/api", tags=["compare"])


@router.get(
    "/compare",
    response_model=CompareOut,
    summary="Diff de score + dimensões entre 2 competências",
)
def get_compare(
    siconfi: str = Query(..., description="Código SICONFI", pattern=r"^[a-zA-Z0-9_-]+$"),
    a: str = Query(..., description="Competência A (YYYY-MM)"),
    b: str = Query(..., description="Competência B (YYYY-MM)"),
) -> CompareOut:
    if a == b:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Competências A e B devem ser diferentes.",
        )

    settings = get_settings()
    comparison = compare_periods(
        siconfi=siconfi,
        snapshots_dir=absolute_snapshots_dir(),
        settings=settings,
    )

    by_comp = {p.competencia: p for p in comparison.periods}
    period_a = by_comp.get(a)
    period_b = by_comp.get(b)

    if period_a is None or period_b is None:
        missing = [c for c in (a, b) if c not in by_comp]
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Snapshot ausente para {siconfi}: {missing}.",
        )

    dims_a = period_a.score_result.dimensions
    dims_b = period_b.score_result.dimensions
    keys = sorted(set(dims_a.keys()) | set(dims_b.keys()))
    dimensions = [
        CompareDimensionOut(
            dimension=k,
            score_a=dims_a[k].score if k in dims_a else 0.0,
            score_b=dims_b[k].score if k in dims_b else 0.0,
            delta=(dims_b[k].score if k in dims_b else 0.0)
            - (dims_a[k].score if k in dims_a else 0.0),
        )
        for k in keys
    ]

    return CompareOut(
        siconfi=siconfi,
        a=CompareSideOut(
            competencia=period_a.competencia,
            pontuacao=period_a.score_result.pontuacao,
            banda=period_a.score_result.banda,  # type: ignore[arg-type]
            total_pendencias=period_a.total_pendencias,
        ),
        b=CompareSideOut(
            competencia=period_b.competencia,
            pontuacao=period_b.score_result.pontuacao,
            banda=period_b.score_result.banda,  # type: ignore[arg-type]
            total_pendencias=period_b.total_pendencias,
        ),
        delta_score=round(
            period_b.score_result.pontuacao - period_a.score_result.pontuacao, 2
        ),
        delta_pendencias=period_b.total_pendencias - period_a.total_pendencias,
        dimensions=dimensions,
    )
