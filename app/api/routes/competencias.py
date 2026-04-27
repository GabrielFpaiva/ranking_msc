"""
app.api.routes.competencias
~~~~~~~~~~~~~~~~~~~~~~~~~~~

GET /api/competencias — descobre competências disponíveis em snapshots.

Estrutura no disco:
    data/snapshots/<siconfi>/<competencia>/resultado_regras.parquet
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.deps import absolute_snapshots_dir
from app.api.schemas import CompetenciaOut

router = APIRouter(prefix="/api", tags=["competencias"])


@router.get(
    "/competencias",
    response_model=list[CompetenciaOut],
    summary="Lista competências (mês/ente) com snapshot disponível",
)
def list_competencias(
    siconfi: str | None = Query(None, description="Filtra por código SICONFI", pattern=r"^[a-zA-Z0-9_-]+$"),
) -> list[CompetenciaOut]:
    """Varre ``data/snapshots/`` e devolve a lista ordenada por competência desc."""
    base_dir = absolute_snapshots_dir()
    if not base_dir.is_dir():
        return []

    out: list[CompetenciaOut] = []
    for siconfi_dir in sorted(base_dir.iterdir()):
        if not siconfi_dir.is_dir():
            continue
        if siconfi and siconfi_dir.name != siconfi:
            continue
        for competencia_dir in sorted(siconfi_dir.iterdir(), reverse=True):
            if not competencia_dir.is_dir():
                continue
            resultado = competencia_dir / "resultado_regras.parquet"
            if resultado.is_file():
                out.append(
                    CompetenciaOut(
                        siconfi=siconfi_dir.name,
                        competencia=competencia_dir.name,
                        has_resultado=True,
                    )
                )
    return out
