"""
app.api.routes.pendencias
~~~~~~~~~~~~~~~~~~~~~~~~~

GET /api/pendencias — lista paginada de pendências de uma competência,
filtráveis por regra/severidade/conta.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_current_user, get_store
from app.api.schemas import PendenciaOut, PendenciasPageOut
from ranking_msc.exceptions import SnapshotNotFoundError
from ranking_msc.io.store import MatrizRef
from ranking_msc.outputs.aggregations import filter_pendencias

router = APIRouter(
    prefix="/api",
    tags=["pendencias"],
    dependencies=[Depends(get_current_user)],
)


@router.get(
    "/pendencias",
    response_model=PendenciasPageOut,
    summary="Lista paginada de pendências de uma competência",
)
def list_pendencias(
    siconfi: str = Query(..., description="Código SICONFI do ente", pattern=r"^[a-zA-Z0-9_-]+$"),
    competencia: str = Query(..., description="YYYY-MM", pattern=r"^[0-9]{4}-[0-9]{2}$"),
    regra_id: str | None = Query(None, description="Filtra por uma regra (ex: R054)"),
    severidade: str | None = Query(None, description="ERRO | ALERTA | INFO"),
    conta_prefix: str | None = Query(
        None, description="Filtra contas que começam com este prefixo"
    ),
    dimensao: str | None = Query(
        None, description="Dimensão de pontuação (ex: Fechamento, IC_Dominio)"
    ),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
) -> PendenciasPageOut:
    """Lê o snapshot ``resultado_regras`` e aplica filtros + paginação."""
    store, ref = get_store(), MatrizRef(siconfi, competencia)
    try:
        df = store.load_resultado(ref)
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
        dimensao=dimensao,
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
