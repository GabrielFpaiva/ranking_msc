"""
app.api.routes.contas
~~~~~~~~~~~~~~~~~~~~~

Detalhe de uma conta contábil — saldos da MSC + classificadores PCASP.
Usado pelo Drawer Conta.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import PROJECT_ROOT, absolute_snapshots_dir, get_current_user, get_settings
from app.api.schemas import ContaDetailOut, ContaSaldosOut
from ranking_msc.exceptions import ConfigError
from ranking_msc.io.ref_loader import load_pcasp
from ranking_msc.outputs.aggregations import aggregate_conta

router = APIRouter(
    prefix="/api",
    tags=["contas"],
    dependencies=[Depends(get_current_user)],
)

logger = logging.getLogger("ranking_msc")


@router.get(
    "/contas/{conta_contabil}",
    response_model=ContaDetailOut,
    summary="Detalhe de uma conta contábil (Drawer Conta)",
)
def get_conta(
    conta_contabil: str,
    siconfi: str = Query(..., description="Código SICONFI", pattern=r"^[a-zA-Z0-9_-]+$"),
    competencia: str = Query(..., description="YYYY-MM", pattern=r"^[0-9]{4}-[0-9]{2}$"),
) -> ContaDetailOut:
    """Lê msc_normalizado snapshot, agrega saldos e devolve para o Drawer."""
    settings = get_settings()
    ref_dir = (PROJECT_ROOT / settings.paths.ref_dir).resolve()
    try:
        pcasp = load_pcasp(ref_dir=ref_dir)
    except ConfigError:
        logger.warning("Tabela PCASP não encontrada em %s — Drawer omite classificadores.", ref_dir)
        pcasp = None

    detail = aggregate_conta(
        absolute_snapshots_dir(),
        siconfi,
        competencia,
        conta_contabil,
        pcasp=pcasp,
    )
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conta {conta_contabil} não encontrada em {siconfi}/{competencia}.",
        )

    return ContaDetailOut(
        conta_contabil=detail.conta_contabil,
        competencia=detail.competencia,
        siconfi=siconfi,
        saldos=ContaSaldosOut(
            saldo_inicial_devedor=detail.saldos.saldo_inicial_devedor,
            saldo_inicial_credor=detail.saldos.saldo_inicial_credor,
            movimento_devedor=detail.saldos.movimento_devedor,
            movimento_credor=detail.saldos.movimento_credor,
            saldo_final_devedor=detail.saldos.saldo_final_devedor,
            saldo_final_credor=detail.saldos.saldo_final_credor,
        ),
        classificadores=detail.classificadores,
        pcasp=detail.pcasp,
        pendencias_count=detail.pendencias_count,
    )
