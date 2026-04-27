"""
app.api.routes.exports
~~~~~~~~~~~~~~~~~~~~~~

GET /api/exports/excel — download do último relatório Excel gerado para
uma competência/SICONFI. Se o arquivo não existir no disco, retorna 404
orientando o usuário a rodar o pipeline primeiro.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import FileResponse

from app.api.deps import absolute_reports_dir

router = APIRouter(prefix="/api", tags=["exports"])


@router.get(
    "/exports/excel",
    summary="Download do relatório Excel de pendências",
    response_class=FileResponse,
)
def download_excel(
    siconfi: str = Query(..., description="Código SICONFI do ente"),
    competencia: str = Query(..., description="Competência (YYYY-MM)"),
) -> FileResponse:
    """Retorna o Excel de pendências para o ente/competência indicados.

    O arquivo é gerado pelo ``POST /api/run`` e fica em
    ``data/reports/pendencias_<siconfi>_<competencia>.xlsx``.
    """
    reports = absolute_reports_dir()
    filename = f"pendencias_{siconfi}_{competencia}.xlsx"
    filepath: Path = reports / filename

    if not filepath.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Relatório '{filename}' não encontrado. "
                f"Execute o pipeline primeiro via POST /api/run."
            ),
        )

    return FileResponse(
        path=str(filepath),
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
