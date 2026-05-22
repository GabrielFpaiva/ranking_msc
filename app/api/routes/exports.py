"""
app.api.routes.exports
~~~~~~~~~~~~~~~~~~~~~~

GET /api/exports/excel — download do último relatório Excel gerado.
GET /api/exports/pdf — gera/baixa o PDF da Visão Executiva.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import FileResponse

from app.api.deps import absolute_reports_dir, absolute_snapshots_dir, get_settings
from ranking_msc.engine.compare_periods import compare_periods
from ranking_msc.engine.score_engine import calculate_score
from ranking_msc.exceptions import SnapshotCorruptError, SnapshotNotFoundError
from ranking_msc.outputs.aggregations import derive_recommendations
from ranking_msc.outputs.executive_pdf import ExecutivePdfPayload, write_executive_pdf
from ranking_msc.outputs.snapshot import read_scoring_metadata, read_snapshot

router = APIRouter(prefix="/api", tags=["exports"])


def _load_snapshot_or_404(siconfi: str, competencia: str):
    base = absolute_snapshots_dir() / siconfi
    try:
        return read_snapshot(competencia, base_dir=base, label="resultado_regras")
    except SnapshotNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Snapshot não encontrado para {siconfi}/{competencia}.",
        ) from exc
    except SnapshotCorruptError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Snapshot inválido para {siconfi}/{competencia}: {exc}",
        ) from exc


def _discover_pdf_history_competencias(siconfi: str, competencia: str) -> list[str]:
    """Descobre apenas competências relevantes ao PDF solicitado."""
    siconfi_dir = absolute_snapshots_dir() / siconfi
    if not siconfi_dir.is_dir():
        return [competencia]

    competencias = sorted(
        path.parent.name
        for path in siconfi_dir.glob("*/resultado_regras.parquet")
        if path.parent.name <= competencia
    )
    if competencia not in competencias:
        competencias.append(competencia)
        competencias.sort()
    return competencias

def _build_pdf_payload(siconfi: str, competencia: str) -> ExecutivePdfPayload:
    settings = get_settings()
    pendencias = _load_snapshot_or_404(siconfi, competencia)
    meta = read_scoring_metadata(competencia, base_dir=absolute_snapshots_dir() / siconfi)
    rule_ids = meta if meta is not None else list(settings.rules.enabled)
    score = calculate_score(pendencias, rule_ids)
    comparison = compare_periods(
        siconfi=siconfi,
        snapshots_dir=absolute_snapshots_dir(),
        settings=settings,
        competencias=_discover_pdf_history_competencias(siconfi, competencia),
    )

    prev = None
    for period in comparison.periods:
        if period.competencia < competencia:
            prev = period

    pior_dim = min(score.dimensions.values(), key=lambda item: item.score, default=None)
    recommendations = derive_recommendations(
        pendencias,
        score_atual=score.pontuacao,
        score_anterior=prev.score_result.pontuacao if prev is not None else None,
        pior_dimensao=pior_dim.dimension if pior_dim is not None else None,
        pior_dimensao_score=pior_dim.score if pior_dim is not None else None,
    )

    delta_text: str | None = None
    if prev is not None:
        delta = score.pontuacao - prev.score_result.pontuacao
        sinal = "+" if delta >= 0 else ""
        delta_text = f"Delta vs {prev.competencia}: {sinal}{delta:.2f}"

    history_periods = [point for point in comparison.periods if point.competencia <= competencia]
    history_lines = [
        (
            f"{point.competencia}: score {point.score_result.pontuacao:.1f}, "
            f"banda {point.score_result.banda}, {point.total_pendencias} pendencia(s)"
        )
        for point in history_periods[-6:]
    ]
    dimension_lines = [
        (
            f"{dimension.dimension}: {dimension.score * 100:.0f}% "
            f"(peso {dimension.weight_normalized * 100:.0f}%, "
            f"ERRO {dimension.rules_failed_erro}, ALERTA {dimension.rules_failed_alerta})"
        )
        for dimension in sorted(score.dimensions.values(), key=lambda item: item.score)
    ]
    recommendation_lines = [
        f"{index}. [{item.severidade}] {item.titulo}: {item.descricao}"
        for index, item in enumerate(recommendations, start=1)
    ]

    return ExecutivePdfPayload(
        siconfi=siconfi,
        competencia=competencia,
        pontuacao=score.pontuacao,
        banda=score.banda,
        regras_executadas=score.regras_executadas,
        regras_falhas_erro=score.regras_falhas_erro,
        regras_falhas_alerta=score.regras_falhas_alerta,
        delta_text=delta_text,
        history_lines=history_lines,
        dimension_lines=dimension_lines,
        recommendation_lines=recommendation_lines,
    )


@router.get(
    "/exports/excel",
    summary="Download do relatório Excel de pendências",
    response_class=FileResponse,
)
def download_excel(
    siconfi: str = Query(
        ...,
        description="Código SICONFI do ente",
        pattern=r"^[a-zA-Z0-9_-]+$",
    ),
    competencia: str = Query(
        ...,
        description="Competência (YYYY-MM)",
        pattern=r"^[0-9]{4}-[0-9]{2}$",
    ),
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


@router.get(
    "/exports/pdf",
    summary="Download do PDF da Visão Executiva",
    response_class=FileResponse,
)
def download_pdf(
    siconfi: str = Query(
        ...,
        description="Código SICONFI do ente",
        pattern=r"^[a-zA-Z0-9_-]+$",
    ),
    competencia: str = Query(
        ...,
        description="Competência (YYYY-MM)",
        pattern=r"^[0-9]{4}-[0-9]{2}$",
    ),
) -> FileResponse:
    """Gera e retorna um PDF textual da Visão Executiva para o período."""
    reports = absolute_reports_dir()
    filename = f"executivo_{siconfi}_{competencia}.pdf"
    filepath = write_executive_pdf(
        _build_pdf_payload(siconfi=siconfi, competencia=competencia),
        reports / filename,
    )
    return FileResponse(
        path=str(filepath),
        filename=filename,
        media_type="application/pdf",
    )
