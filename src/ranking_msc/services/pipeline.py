"""
ranking_msc.services.pipeline
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Orquestração única do pipeline de execução: normalizar → motor → score →
snapshots → Excel → log de auditoria.

Consumida pela CLI (``scripts/run_pipeline.py``) e pela API
(``app/api/routes/run.py``). Antes desta extração cada consumidor
reimplementava a sequência e as cópias divergiam (ex.: o Excel gerado pela
API era exportado sem ``score_result`` e saía sem a aba Score).
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from pathlib import Path

from ranking_msc.config.settings import Settings
from ranking_msc.engine.executor import EngineContext, EngineResult, run_engine
from ranking_msc.engine.score_engine import ScoreResult, calculate_score
from ranking_msc.io.reader_msc import RawMSC
from ranking_msc.io.store import ExecucaoRegistro, MatrizRef, SnapshotStore
from ranking_msc.outputs.logs import log_execucao
from ranking_msc.outputs.reports import export_issues_excel
from ranking_msc.transform.ic_normalize import normalize_ic


@dataclass(frozen=True)
class PipelineRunResult:
    """Resultados e artefatos de uma execução completa do pipeline."""

    context: EngineContext
    engine_result: EngineResult
    score_result: ScoreResult
    ref: MatrizRef
    report_path: Path


def registro_execucao(engine_result: EngineResult, score_result: ScoreResult) -> ExecucaoRegistro:
    """Monta o registro da execução gravado junto com as pendências."""
    context = engine_result.context
    return ExecucaoRegistro(
        execucao_id=context.execucao_id,
        usuario=context.usuario,
        inicio=context.inicio,
        status=engine_result.status,
        regras_executadas=engine_result.executed_rule_ids,
        pontuacao=score_result.pontuacao,
        banda=score_result.banda,
        dimensoes={k: asdict(v) for k, v in score_result.dimensions.items()},
    )


def run_full_pipeline(
    raw: RawMSC,
    *,
    settings: Settings,
    store: SnapshotStore,
    reports_dir: Path,
    logger: logging.Logger,
    usuario: str,
    lock_token: str | None = None,
    report_filename: str | None = None,
    log_message: str = "Execução concluída",
    origem: str = "previa",
) -> PipelineRunResult:
    """Executa a sequência completa do pipeline sobre um MSC já lido.

    Sequência: ``normalize_ic()`` → snapshot do normalizado → ``run_engine()``
    → ``calculate_score()`` → snapshot de resultado + metadata de scoring →
    Excel de pendências (com aba Score) → ``log_execucao()``.

    Args:
        raw: MSC lido por ``read_msc_csv()``.
        settings: configurações carregadas do projeto.
        store: armazenamento das matrizes e resultados (``make_store()``).
        reports_dir: diretório de saída do Excel de pendências.
        logger: logger configurado do projeto.
        usuario: quem disparou a execução (``"cli"`` ou usuário autenticado).
        lock_token: token do lock de execução, quando o chamador o adquiriu.
        report_filename: nome do arquivo Excel. Se ``None``, usa o padrão
            de ``export_issues_excel()``.
        log_message: mensagem registrada em ``log_execucao()``.
        origem: ``"previa"`` (upload) ou ``"homologada"`` (API do SICONFI).

    Returns:
        ``PipelineRunResult`` com contexto, resultados do motor e do score
        e caminhos dos artefatos gerados.

    Raises:
        InputFormatError: se a normalização encontrar colunas inválidas.
        ConfigError: se tabelas de referência estiverem ausentes/inválidas.
        SnapshotError: se a persistência dos snapshots falhar.
        ReportError: se a exportação do Excel falhar.
    """
    df = normalize_ic(raw.df, mapping_path=Path(settings.paths.ref_dir) / "mapeamento_ic_tipo.csv")

    ref = MatrizRef(raw.siconfi, raw.competencia, origem)
    # Matriz gravada ANTES das regras — R054 e demais regras temporais leem a
    # do mês anterior para comparar.
    store.save_msc(ref, df, usuario=usuario)

    context = EngineContext(
        competencia=raw.competencia,
        siconfi=raw.siconfi,
        settings=settings,
        usuario=usuario,
        pre_pivot_issues=raw.pre_pivot_issues,
        lock_token=lock_token,
        origem=origem,
        store=store,
    )
    logger.info(
        "Executando motor de regras para competencia=%s siconfi=%s",
        context.competencia,
        context.siconfi,
        extra={
            "execucao_id": context.execucao_id,
            "competencia": context.competencia,
            "siconfi": context.siconfi,
            "usuario": context.usuario,
        },
    )

    engine_result = run_engine(df, context)

    score_result = calculate_score(
        engine_result.pendencias,
        engine_result.executed_rule_ids,
    )
    logger.info(
        "Score calculado: pontuacao=%.2f banda=%s regras=%d",
        score_result.pontuacao,
        score_result.banda,
        score_result.regras_executadas,
        extra={
            "execucao_id": context.execucao_id,
            "competencia": context.competencia,
            "siconfi": context.siconfi,
        },
    )

    store.save_resultado(
        ref, engine_result.pendencias, registro_execucao(engine_result, score_result)
    )
    report_path = export_issues_excel(
        engine_result.pendencias,
        raw.competencia,
        output_dir=reports_dir,
        filename=report_filename,
        score_result=score_result,
    )

    log_execucao(
        logger,
        execucao_id=context.execucao_id,
        competencia=context.competencia,
        status=engine_result.status,
        message=log_message,
        siconfi=context.siconfi,
        usuario=context.usuario,
    )

    return PipelineRunResult(
        context=context,
        engine_result=engine_result,
        score_result=score_result,
        ref=ref,
        report_path=report_path,
    )
