"""
app.api.routes.passivos
~~~~~~~~~~~~~~~~~~~~~~~

GET /api/passivos — Passivo Circulante (2.1.x) e Não-Circulante (2.2.x).
Saldo apresentado com natureza credora positiva (sinal invertido).
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.deps import absolute_snapshots_dir
from app.api.schemas import ContaListGroupOut, ContaListOut, ContaResumoOut
from ranking_msc.outputs.aggregations import accounts_by_prefix

router = APIRouter(prefix="/api", tags=["contas"])


@router.get(
    "/passivos",
    response_model=ContaListOut,
    summary="Obrigações — Passivo Circulante (2.1) e Não-Circulante (2.2)",
)
def get_passivos(
    siconfi: str = Query(..., description="Código SICONFI", pattern=r"^[a-zA-Z0-9_-]+$"),
    competencia: str = Query(..., description="YYYY-MM", pattern=r"^[0-9]{4}-[0-9]{2}$"),
) -> ContaListOut:
    snapshots = absolute_snapshots_dir()

    groups: list[ContaListGroupOut] = []
    for label, prefixes in (
        ("Passivo Circulante", ["21"]),
        ("Passivo Não-Circulante", ["22"]),
    ):
        try:
            items = accounts_by_prefix(
                snapshots, siconfi, competencia, prefixes=prefixes, nat_saldo="C"
            )
        except SnapshotNotFoundError as exc:
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Snapshot não encontrado para {siconfi}/{competencia}.",
            ) from exc
        total = sum(i.saldo_final for i in items)
        groups.append(
            ContaListGroupOut(
                label=label,
                prefixes=[f"{p[0]}.{p[1]}.x" for p in prefixes],
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
        )

    return ContaListOut(siconfi=siconfi, competencia=competencia, groups=groups)
