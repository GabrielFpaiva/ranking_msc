"""
ranking_msc.engine.executor
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Motor principal de execução das regras de validação.

Fluxo futuro (a ser implementado):
    1. Receber DataFrame MSC já lido e normalizado.
    2. Montar EngineContext com metadados (competência, siconfi, settings).
    3. Carregar regras habilitadas (settings.rules.enabled) via RULE_REGISTRY.
    4. Executar cada regra em sequência (ou paralelo controlado).
    5. Consolidar pendências em um único DataFrame.
    6. Calcular scoring / nota final.
    7. Retornar EngineResult com pendências, logs e estatísticas.

Concorrência (multiusuário):
    - Cada execução recebe um ``execucao_id`` (UUID) para rastreabilidade.
    - TODO: implementar semáforo por competência para evitar que dois
      usuários processem o mesmo mês simultaneamente (ver SecuritySettings).
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import pandas as pd

from ranking_msc.config.settings import Settings
from ranking_msc.exceptions import RuleExecutionError
from ranking_msc.rules.base import RULE_REGISTRY
from ranking_msc.schemas import FACT_RESULTADO_REGRAS_COLUMNS

logger = logging.getLogger("ranking_msc")


@dataclass
class EngineContext:
    """Metadados de uma execução do motor.

    Criado pelo chamador (web_app ou script) e passado para cada regra.
    """
    competencia: str                  # "YYYY-MM"
    siconfi: str                      # código do ente
    settings: Settings
    execucao_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    usuario: str = "sistema"          # quem disparou a execução
    inicio: datetime = field(default_factory=datetime.now)

    # TODO (multiusuário): adicionar campo ``lock_token`` para controle
    # de concorrência por competência.


@dataclass
class EngineResult:
    """Resultado consolidado de uma execução do motor."""
    context: EngineContext
    pendencias: pd.DataFrame = field(
        default_factory=lambda: pd.DataFrame(columns=FACT_RESULTADO_REGRAS_COLUMNS)
    )
    regras_executadas: int = 0
    regras_com_erro: int = 0
    erros: list[dict[str, Any]] = field(default_factory=list)
    fim: datetime = field(default_factory=datetime.now)

    @property
    def status(self) -> str:
        if self.regras_com_erro == 0:
            return "OK"
        if any(error.get("fatal", False) for error in self.erros):
            return "ERRO"
        if self.regras_com_erro > 0:
            return "PARCIAL"
        return "OK"

    @property
    def total_pendencias(self) -> int:
        return len(self.pendencias)


# ---------------------------------------------------------------------------
# Função principal
# ---------------------------------------------------------------------------

def run_engine(df: pd.DataFrame, context: EngineContext) -> EngineResult:
    """Executa todas as regras habilitadas sobre o DataFrame MSC.

    Args:
        df: DataFrame com colunas de FACT_MSC_COLUMNS (já normalizado).
        context: metadados da execução.

    Returns:
        EngineResult com pendências consolidadas.

    """
    enabled_rule_ids = context.settings.rules.enabled
    pendencias_parts: list[pd.DataFrame] = []

    result = EngineResult(context=context)

    for rule_id in enabled_rule_ids:
        result.regras_executadas += 1
        rule_class = RULE_REGISTRY.get(rule_id)

        if rule_class is None:
            error = RuleExecutionError(
                rule_id,
                "Regra habilitada não está registrada no RULE_REGISTRY.",
            )
            _handle_rule_error(
                error,
                context,
                result,
                fatal=context.settings.rules.fail_fast,
                include_traceback=False,
            )
            if context.settings.rules.fail_fast:
                break
            continue

        try:
            rule = rule_class()
            issues_df = _validate_rule_output(rule.execute(df, context), rule_id=rule_id)
            pendencias_parts.append(issues_df)
        except Exception as exc:  # noqa: BLE001
            error = _build_rule_error(rule_id=rule_id, exc=exc)
            _handle_rule_error(
                error,
                context,
                result,
                fatal=context.settings.rules.fail_fast,
                include_traceback=True,
            )
            if context.settings.rules.fail_fast:
                break

    if pendencias_parts:
        result.pendencias = pd.concat(pendencias_parts, ignore_index=True)
    else:
        result.pendencias = pd.DataFrame(columns=FACT_RESULTADO_REGRAS_COLUMNS)

    result.fim = datetime.now()
    return result


def _validate_rule_output(raw_output: object, *, rule_id: str) -> pd.DataFrame:
    """Valida e normaliza o retorno de uma regra para o schema esperado."""
    if not isinstance(raw_output, pd.DataFrame):
        raise RuleExecutionError(
            rule_id,
            "Retorno inválido da regra: esperado pandas.DataFrame.",
        )

    df = raw_output.copy()

    for column in FACT_RESULTADO_REGRAS_COLUMNS:
        if column not in df.columns:
            df[column] = None

    extra_columns = [c for c in df.columns if c not in FACT_RESULTADO_REGRAS_COLUMNS]
    ordered_columns = FACT_RESULTADO_REGRAS_COLUMNS + extra_columns
    return df[ordered_columns]


def _build_rule_error(rule_id: str, exc: Exception) -> RuleExecutionError:
    """Converte exceções inesperadas no erro padronizado do motor."""
    if isinstance(exc, RuleExecutionError):
        return exc
    return RuleExecutionError(rule_id, str(exc))


def _handle_rule_error(
    error: RuleExecutionError,
    context: EngineContext,
    result: EngineResult,
    *,
    fatal: bool,
    include_traceback: bool,
) -> None:
    """Registra erro de regra no log e no EngineResult."""
    result.regras_com_erro += 1
    result.erros.append(
        {
            "rule_id": error.rule_id,
            "erro": str(error),
            "fatal": fatal,
        },
    )
    logger.error(
        "Erro na execução da regra %s: %s",
        error.rule_id,
        error,
        exc_info=include_traceback,
        extra={
            "execucao_id": context.execucao_id,
            "competencia": context.competencia,
            "siconfi": context.siconfi,
            "regra_id": error.rule_id,
            "usuario": context.usuario,
        },
    )
