"""
app.api.routes.competencias
~~~~~~~~~~~~~~~~~~~~~~~~~~~

GET /api/competencias — competências (prévias) com resultado no armazenamento.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user, get_store
from app.api.schemas import CompetenciaOut

router = APIRouter(
    prefix="/api",
    tags=["competencias"],
    dependencies=[Depends(get_current_user)],
)


@router.get(
    "/competencias",
    response_model=list[CompetenciaOut],
    summary="Lista competências (mês/ente) com snapshot disponível",
)
def list_competencias(
    siconfi: str | None = Query(
        None,
        description="Filtra por código SICONFI",
        pattern=r"^[a-zA-Z0-9_-]+$",
    ),
) -> list[CompetenciaOut]:
    """Competências com resultado no armazenamento, por ente e competência desc."""
    out = [
        CompetenciaOut(siconfi=r.siconfi, competencia=r.competencia, has_resultado=True)
        for r in get_store().list_refs(siconfi, "previa")
    ]
    # Ente crescente; dentro do ente, competência mais recente primeiro.
    out.sort(key=lambda c: c.competencia, reverse=True)
    out.sort(key=lambda c: c.siconfi)
    return out
