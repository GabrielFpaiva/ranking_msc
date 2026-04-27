"""
app.api.routes.score
~~~~~~~~~~~~~~~~~~~~

GET /api/score — recalcula score de uma competência a partir do snapshot.
GET /api/score-history — histórico de score por competência (compare_periods).
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import absolute_snapshots_dir, get_settings
from app.api.schemas import (
    DimensionScoreOut,
    ScoreHistoryOut,
    ScoreHistoryPointOut,
    ScoreOut,
)
from ranking_msc.engine.compare_periods import compare_periods
from ranking_msc.engine.score_engine import calculate_score
from ranking_msc.exceptions import SnapshotNotFoundError
from ranking_msc.outputs.snapshot import read_scoring_metadata, read_snapshot

router = APIRouter(prefix="/api", tags=["score"])


@router.get(
    "/score",
    response_model=ScoreOut,
    summary="Score recalculado de uma competência específica",
)
def get_score(
    siconfi: str = Query(..., description="Código SICONFI do ente", pattern=r"^[a-zA-Z0-9_-]+$"),
    competencia: str = Query(..., description="YYYY-MM", pattern=r"^[0-9]{4}-[0-9]{2}$"),
) -> ScoreOut:
    """Lê snapshot e devolve score com breakdown por dimensão."""
    base = absolute_snapshots_dir() / siconfi
    try:
        pendencias = read_snapshot(competencia, base_dir=base, label="resultado_regras")
    except SnapshotNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Snapshot não encontrado para {siconfi}/{competencia}.",
        ) from exc

    meta = read_scoring_metadata(competencia, base_dir=base)
    rule_ids = meta if meta is not None else list(get_settings().rules.enabled)
    score_result = calculate_score(pendencias, rule_ids)

    return ScoreOut(
        pontuacao=score_result.pontuacao,
        banda=score_result.banda,  # type: ignore[arg-type]
        dimensions={
            k: DimensionScoreOut(
                dimension=v.dimension,
                score=v.score,
                weight_normalized=v.weight_normalized,
                rules_total=v.rules_total,
                rules_passed=v.rules_passed,
                rules_failed_alerta=v.rules_failed_alerta,
                rules_failed_erro=v.rules_failed_erro,
            )
            for k, v in score_result.dimensions.items()
        },
        regras_executadas=score_result.regras_executadas,
        regras_falhas_erro=score_result.regras_falhas_erro,
        regras_falhas_alerta=score_result.regras_falhas_alerta,
    )


@router.get(
    "/score-history",
    response_model=ScoreHistoryOut,
    summary="Linha do tempo de scores por competência",
)
def get_score_history(
    siconfi: str = Query(..., description="Código SICONFI do ente", pattern=r"^[a-zA-Z0-9_-]+$"),
    meses: int = Query(6, ge=1, le=24, description="Quantidade de pontos (mais recentes)"),
) -> ScoreHistoryOut:
    """Usa compare_periods para retornar até ``meses`` pontos mais recentes."""
    settings = get_settings()
    comparison = compare_periods(
        siconfi=siconfi,
        snapshots_dir=absolute_snapshots_dir(),
        settings=settings,
    )

    points = [
        ScoreHistoryPointOut(
            competencia=p.competencia,
            pontuacao=p.score_result.pontuacao,
            banda=p.score_result.banda,  # type: ignore[arg-type]
            total_pendencias=p.total_pendencias,
        )
        for p in comparison.periods
    ][-meses:]

    return ScoreHistoryOut(siconfi=siconfi, points=points)
