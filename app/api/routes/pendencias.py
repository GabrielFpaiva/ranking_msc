"""
app.api.routes.pendencias
~~~~~~~~~~~~~~~~~~~~~~~~~

GET /api/pendencias — lista paginada de pendências de uma competência,
filtráveis por regra/severidade/conta.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import absolute_snapshots_dir
from app.api.schemas import PendenciaOut, PendenciasPageOut
from ranking_msc.exceptions import SnapshotNotFoundError
from ranking_msc.outputs.aggregations import filter_pendencias
from ranking_msc.outputs.snapshot import read_snapshot

router = APIRouter(prefix="/api", tags=["pendencias"])


@router.get(
    "/pendencias",
    response_model=PendenciasPageOut,
    summary="Lista paginada de pendências de uma competência",
)
def list_pendencias(
    siconfi: str = Query(..., description="Código SICONFI do ente"),
    competencia: str = Query(..., description="YYYY-MM"),
    regra_id: str | None = Query(None, description="Filtra por uma regra (ex: R054)"),
    severidade: str | None = Query(None, description="ERRO | ALERTA | INFO"),
    conta_prefix: str | None = Query(
        None, description="Filtra contas que começam com este prefixo"
    ),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
) -> PendenciasPageOut:
    """Lê o snapshot ``resultado_regras`` e aplica filtros + paginação."""
    base = absolute_snapshots_dir() / siconfi
    try:
        df = read_snapshot(competencia, base_dir=base, label="resultado_regras")
    except SnapshotNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Snapshot não encontrado para {siconfi}/{competencia}.",
        ) from exc

    filtered = filter_pendencias(
        df,
        regra_id=regra_id,
        severidade=severidade,
        conta_contabil_prefix=conta_prefix,
    )
    total = int(len(filtered))
    page = filtered.iloc[offset : offset + limit]

    items = [
        PendenciaOut(
            regra_id=str(row.get("regra_id", "")),
            regra_nome=str(row.get("regra_nome", "")),
            dimensao=str(row.get("dimensao", "")),
            severidade=str(row.get("severidade", "INFO")),  # type: ignore[arg-type]
            conta_contabil=str(row.get("conta_contabil", "")),
            descricao=str(row.get("descricao", "")),
            valor_esperado=_optional_str(row.get("valor_esperado")),
            valor_encontrado=_optional_str(row.get("valor_encontrado")),
            competencia=str(row.get("competencia", competencia)),
        )
        for _, row in page.iterrows()
    ]

    return PendenciasPageOut(
        competencia=competencia,
        siconfi=siconfi,
        total=total,
        items=items,
    )


def _optional_str(value: object) -> str | None:
    """Converte célula em string ou None — trata NaN/None vazios."""
    if value is None:
        return None
    text = str(value)
    if text == "" or text.lower() == "nan":
        return None
    return text
