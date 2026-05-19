"""
app.api.routes.superavit
~~~~~~~~~~~~~~~~~~~~~~~~

GET /api/superavit — resultado financeiro por fonte de recurso (FR).

A derivação contábil (ativo financeiro − passivo financeiro por FR) ainda
não está implementada no motor. Esta rota responde com payload informativo
com referência à task que vai entregar a lógica (F0-04 — ver doc/fase0_plan.md).
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.schemas import DeferredFeatureOut

router = APIRouter(prefix="/api", tags=["contas"])


@router.get(
    "/superavit",
    response_model=DeferredFeatureOut,
    summary="Resultado financeiro por FR — indisponível até derivação contábil",
)
def get_superavit(
    siconfi: str = Query(..., description="Código SICONFI", pattern=r"^[a-zA-Z0-9_-]+$"),
    competencia: str = Query(..., description="YYYY-MM", pattern=r"^[0-9]{4}-[0-9]{2}$"),
) -> DeferredFeatureOut:
    """Retorna payload informativo com referência à task que vai entregar a lógica."""
    _ = (siconfi, competencia)  # mantém assinatura estável para quando F0-04 chegar
    return DeferredFeatureOut(
        detail=(
            "Resultado financeiro por FR depende de derivação contábil "
            "(ativo financeiro − passivo financeiro por FR) ainda não implementada no motor."
        ),
        see="F0-04",
    )
