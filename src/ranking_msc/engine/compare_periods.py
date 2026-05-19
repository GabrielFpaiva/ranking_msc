"""
ranking_msc.engine.compare_periods
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Comparação de scores entre competências para análise de evolução temporal.

Uso:
    from ranking_msc.engine.compare_periods import compare_periods
    result = compare_periods(
        siconfi="250400",
        snapshots_dir=Path("data/snapshots"),
        settings=settings,
    )
    for i, period in enumerate(result.periods):
        delta = result.score_delta(i)
        print(period.competencia, period.score_result.pontuacao, delta)

Nota:
    executed_rule_ids é lido de ``scoring_metadata.json`` persistido junto ao
    snapshot de cada competência. Isso garante que o score histórico reflita
    as regras que **foram** executadas naquele período, não as atualmente
    habilitadas em settings.rules.enabled.

    Fallback: se o metadado não existir (snapshots anteriores à F4-fix),
    settings.rules.enabled é usado com aviso explícito no log — os scores
    históricos podem ser imprecisos nesse caso.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from ranking_msc.config.settings import Settings
from ranking_msc.engine.score_engine import ScoreResult, calculate_score
from ranking_msc.exceptions import SnapshotError, SnapshotNotFoundError
from ranking_msc.outputs.snapshot import read_scoring_metadata, read_snapshot

logger = logging.getLogger("ranking_msc")


# ---------------------------------------------------------------------------
# Dataclasses de resultado
# ---------------------------------------------------------------------------


@dataclass
class PeriodScore:
    """Score de um período (competência) individual."""

    competencia: str
    """Período no formato YYYY-MM."""

    score_result: ScoreResult
    """Resultado completo do cálculo de pontuação."""

    total_pendencias: int
    """Total de pendências (issues) encontradas neste período."""


@dataclass
class PeriodComparison:
    """Comparação de scores entre competências de um mesmo ente."""

    siconfi: str
    """Código do ente SICONFI."""

    periods: list[PeriodScore] = field(default_factory=list)
    """Períodos comparados, ordenados por competência (ascendente)."""

    def score_delta(self, idx: int) -> float | None:
        """Retorna a variação de score entre o período idx e o anterior.

        Args:
            idx: posição do período em self.periods.

        Returns:
            Delta de pontuação (positivo = melhora) ou None para idx=0.
        """
        if idx == 0 or not self.periods:
            return None
        return round(
            self.periods[idx].score_result.pontuacao
            - self.periods[idx - 1].score_result.pontuacao,
            2,
        )


# ---------------------------------------------------------------------------
# Funções públicas
# ---------------------------------------------------------------------------


def compare_periods(
    siconfi: str,
    *,
    snapshots_dir: str | Path,
    settings: Settings,
    competencias: list[str] | None = None,
) -> PeriodComparison:
    """Compara scores de múltiplas competências para um ente SICONFI.

    Lê os snapshots de resultado_regras de cada período, calcula o score
    via calculate_score e retorna a comparação ordenada por competência.

    Args:
        siconfi: código do ente SICONFI.
        snapshots_dir: diretório raiz de snapshots (ex: data/snapshots).
        settings: configurações do projeto (usa settings.rules.enabled como
            proxy de regras executadas em cada período).
        competencias: lista de "YYYY-MM" a comparar. Se None, descobre
            automaticamente todos os períodos disponíveis em disco.

    Returns:
        PeriodComparison com todos os períodos encontrados, ordenados.

    Raises:
        Nenhuma — períodos sem snapshot são logados como aviso e ignorados.
    """
    base_dir = Path(snapshots_dir)
    executed_rule_ids = list(settings.rules.enabled)

    if competencias is None:
        competencias = _discover_competencias(base_dir, siconfi)

    if not competencias:
        logger.warning(
            "Nenhuma competência encontrada para siconfi=%s em %s",
            siconfi,
            base_dir / siconfi,
        )
        return PeriodComparison(siconfi=siconfi)

    periods: list[PeriodScore] = []

    for competencia in sorted(competencias):
        period = _load_period_score(
            siconfi=siconfi,
            competencia=competencia,
            base_dir=base_dir,
            executed_rule_ids=executed_rule_ids,
        )
        if period is not None:
            periods.append(period)

    return PeriodComparison(siconfi=siconfi, periods=periods)


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------


def _discover_competencias(base_dir: Path, siconfi: str) -> list[str]:
    """Descobre competências disponíveis varrendo o diretório de snapshots.

    Args:
        base_dir: diretório raiz de snapshots.
        siconfi: código do ente.

    Returns:
        Lista de competências no formato YYYY-MM, ordenadas.
    """
    siconfi_dir = base_dir / siconfi
    if not siconfi_dir.is_dir():
        return []

    competencias = [
        p.parent.name
        for p in siconfi_dir.glob("*/resultado_regras.parquet")
    ]
    return sorted(competencias)


def _load_period_score(
    *,
    siconfi: str,
    competencia: str,
    base_dir: Path,
    executed_rule_ids: list[str],
) -> PeriodScore | None:
    """Lê snapshot e calcula score de um único período.

    Args:
        siconfi: código do ente.
        competencia: período YYYY-MM.
        base_dir: diretório raiz de snapshots.
        executed_rule_ids: regras a considerar no cálculo.

    Returns:
        PeriodScore calculado, ou None se snapshot ausente.
    """
    try:
        pendencias = read_snapshot(
            competencia,
            base_dir=base_dir / siconfi,
            label="resultado_regras",
        )
    except SnapshotNotFoundError:
        logger.warning(
            "Snapshot ausente para siconfi=%s competencia=%s — período ignorado.",
            siconfi,
            competencia,
        )
        return None
    except SnapshotError as exc:
        logger.warning(
            "Snapshot inválido para siconfi=%s competencia=%s — período ignorado: %s",
            siconfi,
            competencia,
            exc,
        )
        return None
    except Exception as exc:
        logger.warning(
            "Falha inesperada ao ler snapshot para siconfi=%s competencia=%s "
            "— período ignorado: %s: %s",
            siconfi,
            competencia,
            type(exc).__name__,
            exc,
        )
        return None

    # Usa regras realmente executadas no período, se disponíveis.
    # Sem metadados (snapshots anteriores à F4-fix), cai de volta na lista atual
    # com aviso explícito — scores históricos podem ser imprecisos.
    persisted_ids = read_scoring_metadata(
        competencia,
        base_dir=base_dir / siconfi,
    )
    if persisted_ids is None:
        logger.warning(
            "Metadados de scoring ausentes para siconfi=%s competencia=%s — "
            "usando regras configuradas como fallback. "
            "Scores históricos podem ser imprecisos se o conjunto de regras mudou.",
            siconfi,
            competencia,
        )
        rule_ids_to_use = executed_rule_ids
    else:
        rule_ids_to_use = persisted_ids

    score_result = calculate_score(pendencias, rule_ids_to_use)

    return PeriodScore(
        competencia=competencia,
        score_result=score_result,
        total_pendencias=len(pendencias),
    )
