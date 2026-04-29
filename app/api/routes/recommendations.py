"""
app.api.routes.recommendations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

GET /api/recommendations — ações sugeridas para a Visão Executiva,
derivadas heuristicamente do estado atual (top regras ERRO, dimensão fraca,
tendência de score).
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import absolute_snapshots_dir, get_settings
from app.api.schemas import RecommendationOut, RecommendationsOut
from ranking_msc.engine.compare_periods import compare_periods
from ranking_msc.engine.score_engine import calculate_score
from ranking_msc.exceptions import SnapshotNotFoundError
from ranking_msc.outputs.aggregations import derive_recommendations
from ranking_msc.outputs.snapshot import read_scoring_metadata, read_snapshot

router = APIRouter(prefix="/api", tags=["recommendations"])


@router.get(
    "/recommendations",
    response_model=RecommendationsOut,
    summary="Ações recomendadas para a Visão Executiva",
)
def get_recommendations(
    siconfi: str = Query(..., description="Código SICONFI", pattern=r"^[a-zA-Z0-9_-]+$"),
    competencia: str = Query(..., description="YYYY-MM", pattern=r"^[0-9]{4}-[0-9]{2}$"),
) -> RecommendationsOut:
    base = absolute_snapshots_dir() / siconfi
    try:
        pendencias = read_snapshot(competencia, base_dir=base, label="resultado_regras")
    except SnapshotNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Snapshot ausente para {siconfi}/{competencia}.",
        ) from exc

    settings = get_settings()
    meta = read_scoring_metadata(competencia, base_dir=base)
    rule_ids = meta if meta is not None else list(settings.rules.enabled)
    score_atual = calculate_score(pendencias, rule_ids)

    # Score anterior — pega o último ponto antes da competência atual
    comparison = compare_periods(
        siconfi=siconfi,
        snapshots_dir=absolute_snapshots_dir(),
        settings=settings,
    )
    score_anterior: float | None = None
    for i, period in enumerate(comparison.periods):
        if period.competencia == competencia and i > 0:
            score_anterior = comparison.periods[i - 1].score_result.pontuacao
            break

    pior_dim: str | None = None
    pior_dim_score: float | None = None
    if score_atual.dimensions:
        sorted_dims = sorted(score_atual.dimensions.values(), key=lambda d: d.score)
        if sorted_dims:
            pior_dim = sorted_dims[0].dimension
            pior_dim_score = sorted_dims[0].score

    items = derive_recommendations(
        pendencias,
        score_atual=score_atual.pontuacao,
        score_anterior=score_anterior,
        pior_dimensao=pior_dim,
        pior_dimensao_score=pior_dim_score,
    )

    return RecommendationsOut(
        siconfi=siconfi,
        competencia=competencia,
        items=[
            RecommendationOut(
                titulo=r.titulo,
                descricao=r.descricao,
                severidade=r.severidade,  # type: ignore[arg-type]
                referencia=r.referencia,
            )
            for r in items
        ],
    )
