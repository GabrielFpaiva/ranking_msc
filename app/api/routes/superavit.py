"""
app.api.routes.superavit
~~~~~~~~~~~~~~~~~~~~~~~~

GET /api/superavit — resultado financeiro por fonte de recurso (FR).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import PROJECT_ROOT, absolute_snapshots_dir, get_current_user, get_settings
from app.api.schemas import SuperavitOut, SuperavitRowOut
from ranking_msc.exceptions import ConfigError, SnapshotNotFoundError
from ranking_msc.io.ref_loader import load_pcasp
from ranking_msc.outputs.aggregations import aggregate_superavit

router = APIRouter(
    prefix="/api",
    tags=["contas"],
    dependencies=[Depends(get_current_user)],
)
logger = logging.getLogger("ranking_msc")


@router.get(
    "/superavit",
    response_model=SuperavitOut,
    summary="Resultado financeiro por FR",
)
def get_superavit(
    siconfi: str = Query(..., description="Código SICONFI", pattern=r"^[a-zA-Z0-9_-]+$"),
    competencia: str = Query(..., description="YYYY-MM", pattern=r"^[0-9]{4}-[0-9]{2}$"),
) -> SuperavitOut:
    settings = get_settings()
    ref_dir = (PROJECT_ROOT / settings.paths.ref_dir).resolve()
    try:
        pcasp = load_pcasp(ref_dir=ref_dir)
    except ConfigError as exc:
        logger.exception("Falha ao carregar PCASP para superavit em %s.", ref_dir)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Tabela PCASP indisponível para derivar o superávit por FR.",
        ) from exc

    try:
        summary = aggregate_superavit(
            absolute_snapshots_dir(),
            siconfi,
            competencia,
            pcasp=pcasp,
        )
    except ConfigError as exc:
        logger.warning("PCASP incompleto para superavit: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except SnapshotNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Snapshot não encontrado para {siconfi}/{competencia}.",
        ) from exc

    return SuperavitOut(
        siconfi=siconfi,
        competencia=competencia,
        total_ativo_financeiro=summary.total_ativo_financeiro,
        total_passivo_financeiro=summary.total_passivo_financeiro,
        total_resultado_financeiro=summary.total_resultado_financeiro,
        linhas_consideradas=summary.linhas_consideradas,
        contas_consideradas=summary.contas_consideradas,
        items=[
            SuperavitRowOut(
                fr=item.fr,
                ativo_financeiro=item.ativo_financeiro,
                passivo_financeiro=item.passivo_financeiro,
                resultado_financeiro=item.resultado_financeiro,
            )
            for item in summary.items
        ],
    )
