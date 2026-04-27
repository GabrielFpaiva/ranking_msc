"""
app.api.routes.caixa
~~~~~~~~~~~~~~~~~~~~

GET /api/caixa — disponibilidades (Ativo Circulante 1.1.1.x).
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.deps import absolute_snapshots_dir
from app.api.schemas import ContaListGroupOut, ContaListOut, ContaResumoOut
from ranking_msc.exceptions import SnapshotNotFoundError
from ranking_msc.outputs.aggregations import accounts_by_prefix

router = APIRouter(prefix="/api", tags=["contas"])


@router.get(
    "/caixa",
    response_model=ContaListOut,
    summary="Disponibilidades — Ativo Circulante 1.1.1.x",
)
def get_caixa(
    siconfi: str = Query(..., description="Código SICONFI", pattern=r"^[a-zA-Z0-9_-]+$"),
    competencia: str = Query(..., description="YYYY-MM", pattern=r"^[0-9]{4}-[0-9]{2}$"),
) -> ContaListOut:
    try:
        items = accounts_by_prefix(
            absolute_snapshots_dir(),
            siconfi,
            competencia,
            prefixes=["111"],
            nat_saldo="D",
        )
    except SnapshotNotFoundError as exc:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Snapshot não encontrado para {siconfi}/{competencia}.",
        ) from exc
    total = sum(i.saldo_final for i in items)
    return ContaListOut(
        siconfi=siconfi,
        competencia=competencia,
        groups=[
            ContaListGroupOut(
                label="Caixa e Equivalentes",
                prefixes=["1.1.1.x"],
                total_saldo_final=total,
                items=[
                    ContaResumoOut(
                        conta_contabil=i.conta_contabil,
                        saldo_inicial=i.saldo_inicial,
                        saldo_final=i.saldo_final,
                        movimento_liquido=i.movimento_liquido,
                        fr=i.fr,
                    )
                    for i in items
                ],
            )
        ],
    )
