"""
app.api.routes.superavit
~~~~~~~~~~~~~~~~~~~~~~~~

GET /api/superavit — resultado financeiro por fonte de recurso (FR).

A derivação contábil (ativo financeiro − passivo financeiro por FR) ainda
não está implementada no motor. Esta rota retorna 501 com referência à
task que vai entregar a lógica (F0-04 — ver doc/fase0_plan.md).
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

router = APIRouter(prefix="/api", tags=["contas"])


@router.get(
    "/superavit",
    summary="Resultado financeiro por FR — a ser implementado (F0-04)",
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
    responses={
        501: {
            "description": "Derivação contábil ainda não implementada",
            "content": {
                "application/json": {
                    "example": {
                        "detail": (
                            "Resultado financeiro por FR depende de derivação contábil "
                            "(ativo financeiro − passivo financeiro por FR) ainda não "
                            "implementada no motor."
                        ),
                        "code": "not_implemented",
                        "see": "F0-04",
                    }
                }
            },
        }
    },
)
def get_superavit(
    siconfi: str = Query(..., description="Código SICONFI", pattern=r"^[a-zA-Z0-9_-]+$"),
    competencia: str = Query(..., description="YYYY-MM", pattern=r"^[0-9]{4}-[0-9]{2}$"),
) -> dict[str, str]:
    """Retorna 501 com referência à task que vai entregar a lógica."""
    _ = (siconfi, competencia)  # mantém assinatura estável para quando F0-04 chegar
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=(
            "Resultado financeiro por FR depende de derivação contábil "
            "(ativo financeiro − passivo financeiro por FR) ainda não implementada "
            "no motor. Acompanhe F0-04 em doc/fase0_plan.md."
        ),
    )
