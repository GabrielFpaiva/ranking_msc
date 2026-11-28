"""
app.api.routes.summary
~~~~~~~~~~~~~~~~~~~~~~~

GET /api/summary — resumo (score + total + top regras) de uma competência já
persistida, para a Home refletir a competência ativa sem um novo POST /api/run.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_current_user, get_settings, get_store
from app.api.schemas import (
    DimensionScoreOut,
    ScoreOut,
    SummaryOut,
    TopRuleOut,
)
from ranking_msc.engine.score_engine import calculate_score
from ranking_msc.exceptions import SnapshotNotFoundError
from ranking_msc.io.store import MatrizRef
from ranking_msc.outputs.aggregations import top_violated_rules

router = APIRouter(
    prefix="/api",
    tags=["summary"],
    dependencies=[Depends(get_current_user)],
)


@router.get(
    "/summary",
    response_model=SummaryOut,
    summary="Resumo (score, total e top regras) de uma competência",
)
def get_summary(
    siconfi: str = Query(..., description="Código SICONFI do ente", pattern=r"^[a-zA-Z0-9_-]+$"),
    competencia: str = Query(..., description="YYYY-MM", pattern=r"^[0-9]{4}-[0-9]{2}$"),
) -> SummaryOut:
    """Lê o snapshot e devolve score, total de pendências e top 8 regras."""
    store, ref = get_store(), MatrizRef(siconfi, competencia)
    try:
        pendencias = store.load_resultado(ref)
    except SnapshotNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Snapshot não encontrado para {siconfi}/{competencia}.",
        ) from exc

    meta = store.load_rule_ids(ref)
    rule_ids = meta if meta is not None else list(get_settings().rules.enabled)
    score_result = calculate_score(pendencias, rule_ids)
    top = top_violated_rules(pendencias, limit=8)

    return SummaryOut(
        siconfi=siconfi,
        competencia=competencia,
        total_pendencias=int(len(pendencias)),
        score=ScoreOut(
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
        ),
        top_regras=[
            TopRuleOut(
                regra_id=r.regra_id,
                regra_nome=r.regra_nome,
                dimensao=r.dimensao,
                severidade_max=r.severidade_max,  # type: ignore[arg-type]
                pendencias=r.pendencias,
            )
            for r in top
        ],
    )
