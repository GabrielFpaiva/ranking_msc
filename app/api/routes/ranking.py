"""
app.api.routes.ranking
~~~~~~~~~~~~~~~~~~~~~~

GET /api/ranking — comparativo regional (PMJP vs outros entes).

A fonte de dados regional ainda não está integrada ao motor — esta rota
retorna 501 com referência à task F0-03 (ver doc/fase0_plan.md).
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

router = APIRouter(prefix="/api", tags=["ranking"])


@router.get(
    "/ranking",
    summary="Ranking Regional — a ser implementado (F0-03)",
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
)
def get_ranking() -> dict[str, str]:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=(
            "Ranking regional depende de fonte de dados externa (planilha SICONFI, "
            "API STN ou import de CSVs de outros entes) ainda não integrada ao motor. "
            "Acompanhe F0-03 em doc/fase0_plan.md."
        ),
    )
