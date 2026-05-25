"""
app.api.routes.run
~~~~~~~~~~~~~~~~~~

POST /api/run — recebe CSV MSC via multipart, executa o pipeline completo
(read_msc_csv → normalize_ic → run_engine → calculate_score), persiste
snapshots/Excel/scoring metadata/log e devolve um resumo para a Home.
"""

from __future__ import annotations

import io
import logging

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
from ranking_msc.engine.executor import EngineContext, run_engine
from ranking_msc.engine.score_engine import calculate_score
from ranking_msc.exceptions import InputFormatError
from ranking_msc.io.reader_msc import read_msc_csv
from ranking_msc.outputs.aggregations import top_violated_rules
from ranking_msc.outputs.logs import log_execucao
from ranking_msc.outputs.reports import export_issues_excel
from ranking_msc.outputs.snapshot import write_scoring_metadata, write_snapshot_atomic
from ranking_msc.transform.ic_normalize import normalize_ic

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
    """Roda o motor sobre o CSV recebido e devolve o resumo da execução."""
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

    # Validate siconfi to prevent path traversal
    import re
    if not re.match(r"^[a-zA-Z0-9_-]+$", raw.siconfi):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Identificador siconfi inválido: {raw.siconfi}"
        )

    try:
        df = normalize_ic(raw.df)
    except Exception as exc:  # noqa: BLE001
        api_logger.error("Falha ao normalizar CSV no /api/run: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Erro na normalização: {exc}",
        ) from exc

    ctx = EngineContext(
        competencia=raw.competencia,
        siconfi=raw.siconfi,
        settings=settings,
        pre_pivot_issues=raw.pre_pivot_issues,
        snapshots_dir=snapshots_dir,
        usuario=current_user,
    )

    try:
        result = run_engine(df, ctx)
    except Exception as exc:  # noqa: BLE001
        api_logger.error("Falha no motor no /api/run: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro no motor: {exc}",
        ) from exc

    score_result = calculate_score(result.pendencias, result.executed_rule_ids)

    snap_base = snapshots_dir / raw.siconfi
    try:
        write_snapshot_atomic(df, raw.competencia, base_dir=snap_base, label="msc_normalizado")
        write_snapshot_atomic(
            result.pendencias,
            raw.competencia,
            base_dir=snap_base,
            label="resultado_regras",
        )
        write_scoring_metadata(
            result.executed_rule_ids,
            raw.competencia,
            base_dir=snap_base,
        )
        export_issues_excel(
            result.pendencias,
            raw.competencia,
            output_dir=reports_dir,
            filename=f"pendencias_{raw.siconfi}_{raw.competencia}.xlsx",
        )
        log_execucao(
            api_logger,
            execucao_id=ctx.execucao_id,
            competencia=raw.competencia,
            status=result.status,
            message="Execução /api/run concluída",
            siconfi=raw.siconfi,
            usuario=ctx.usuario,
        )
    except Exception as exc:  # noqa: BLE001
        api_logger.error("Falha ao persistir resultados: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Falha ao persistir os resultados (snapshots/relatórios).",
        ) from exc

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
