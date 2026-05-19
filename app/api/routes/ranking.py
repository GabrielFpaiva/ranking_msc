"""
app.api.routes.ranking
~~~~~~~~~~~~~~~~~~~~~~

GET /api/ranking — comparativo regional (PMJP vs outros entes).

A fonte de dados regional ainda não está integrada ao motor. A rota responde
com payload informativo e referencia a task F0-03 (ver doc/fase0_plan.md).
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.schemas import DeferredFeatureOut

router = APIRouter(prefix="/api", tags=["ranking"])


@router.get(
    "/ranking",
    response_model=DeferredFeatureOut,
    summary="Ranking Regional — indisponível até integração da fonte externa",
)
def get_ranking() -> DeferredFeatureOut:
    return DeferredFeatureOut(
        detail=(
            "Ranking regional depende de fonte de dados externa (planilha SICONFI, "
            "API STN ou import de CSVs de outros entes) ainda não integrada ao motor."
        ),
        see="F0-03",
    )
