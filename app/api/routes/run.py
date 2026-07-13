"""
app.api.routes.run
~~~~~~~~~~~~~~~~~~

POST /api/run - receives a MSC CSV upload, runs the full pipeline, persists
snapshots/reports/logs and returns a summary for the frontend.
"""

from __future__ import annotations

import io
import logging
import re
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.api.deps import (
    absolute_reports_dir,
    absolute_snapshots_dir,
    get_current_user,
    get_logger,
    get_settings,
)
from app.api.schemas import (
    DimensionScoreOut,
    RunSummaryOut,
    ScoreOut,
    TopRuleOut,
)
from ranking_msc.engine.locks import (
    ExecutionLock,
    ExecutionLockExistsError,
    acquire_execution_lock,
    release_execution_lock,
)
from ranking_msc.exceptions import ConfigError, InputFormatError, ReportError, SnapshotError
from ranking_msc.io.reader_msc import read_msc_csv
from ranking_msc.outputs.aggregations import top_violated_rules
from ranking_msc.services.pipeline import run_full_pipeline

router = APIRouter(
    prefix="/api",
    tags=["run"],
    dependencies=[Depends(get_current_user)],
)

logger = logging.getLogger("ranking_msc")


@router.post(
    "/run",
    response_model=RunSummaryOut,
    summary="Executa o pipeline MCRA sobre um CSV MSC enviado",
)
async def run_pipeline(
    file: UploadFile = File(..., description="CSV MSC"),  # noqa: B008
    current_user: str = Depends(get_current_user),  # noqa: B008
) -> RunSummaryOut:
    """Run the engine over the uploaded CSV and return an execution summary."""

    raw_bytes = await file.read()
    if not raw_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Arquivo MSC vazio.",
        )

    settings = get_settings()
    api_logger = get_logger()
    snapshots_dir = absolute_snapshots_dir()
    reports_dir = absolute_reports_dir()

    try:
        raw = read_msc_csv(io.BytesIO(raw_bytes))
    except InputFormatError as exc:
        api_logger.warning("Falha ao ler CSV no /api/run: %s", exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if not re.match(r"^[a-zA-Z0-9_-]+$", raw.siconfi):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Identificador siconfi invalido: {raw.siconfi}",
        )

    lock = _acquire_run_lock(
        snapshots_dir=snapshots_dir,
        siconfi=raw.siconfi,
        competencia=raw.competencia,
        current_user=current_user,
    )
    try:
        try:
            run = run_full_pipeline(
                raw,
                settings=settings,
                snapshots_dir=snapshots_dir,
                reports_dir=reports_dir,
                logger=api_logger,
                usuario=current_user,
                lock_token=lock.token,
                report_filename=f"pendencias_{raw.siconfi}_{raw.competencia}.xlsx",
                log_message="Execucao /api/run concluida",
            )
        except (InputFormatError, ConfigError) as exc:
            api_logger.error("Falha ao normalizar CSV no /api/run: %s", exc, exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Erro na normalizacao: {exc}",
            ) from exc
        except (SnapshotError, ReportError) as exc:
            api_logger.error("Falha ao persistir resultados: %s", exc, exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Falha ao persistir os resultados (snapshots/relatorios).",
            ) from exc
        except Exception as exc:  # noqa: BLE001
            api_logger.error("Falha no motor no /api/run: %s", exc, exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Erro no motor: {exc}",
            ) from exc

        ctx = run.context
        result = run.engine_result
        score_result = run.score_result

        top = top_violated_rules(result.pendencias, limit=8)

        return RunSummaryOut(
            execucao_id=ctx.execucao_id,
            siconfi=raw.siconfi,
            competencia=raw.competencia,
            status=result.status,  # type: ignore[arg-type]
            regras_executadas=result.regras_executadas,
            regras_com_erro=result.regras_com_erro,
            total_pendencias=result.total_pendencias,
            score=ScoreOut(
                pontuacao=score_result.pontuacao,
                banda=score_result.banda,  # type: ignore[arg-type]
                dimensions={
                    k: DimensionScoreOut(
                        dimension=v.dimension,
                        score=v.score,
                        weight_normalized=v.weight_normalized,
                        rules_total=v.rules_total,
                        rules_passed=v.rules_passed,
                        rules_failed_alerta=v.rules_failed_alerta,
                        rules_failed_erro=v.rules_failed_erro,
                    )
                    for k, v in score_result.dimensions.items()
                },
                regras_executadas=score_result.regras_executadas,
                regras_falhas_erro=score_result.regras_falhas_erro,
                regras_falhas_alerta=score_result.regras_falhas_alerta,
            ),
            top_regras=[
                TopRuleOut(
                    regra_id=r.regra_id,
                    regra_nome=r.regra_nome,
                    dimensao=r.dimensao,
                    severidade_max=r.severidade_max,  # type: ignore[arg-type]
                    pendencias=r.pendencias,
                )
                for r in top
            ],
            inicio=ctx.inicio.isoformat(),
            fim=result.fim.isoformat(),
        )
    finally:
        release_execution_lock(lock)


def _acquire_run_lock(
    *,
    snapshots_dir: Path,
    siconfi: str,
    competencia: str,
    current_user: str,
) -> ExecutionLock:
    try:
        return acquire_execution_lock(
            snapshots_dir / ".locks",
            siconfi=siconfi,
            competencia=competencia,
            usuario=current_user,
        )
    except ExecutionLockExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ja existe uma execucao em andamento para {siconfi}/{competencia}.",
        ) from exc
