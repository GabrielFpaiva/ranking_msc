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
    executed_rule_ids é derivado de settings.rules.enabled — assume que as
    regras configuradas hoje são as mesmas que foram executadas em cada período.
    Se o conjunto de regras mudou entre competências, os scores não são
    diretamente comparáveis.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from ranking_msc.config.settings import Settings
from ranking_msc.engine.score_engine import ScoreResult, calculate_score
from ranking_msc.exceptions import SnapshotNotFoundError
from ranking_msc.outputs.snapshot import read_snapshot

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

    score_result = calculate_score(pendencias, executed_rule_ids)

    return PeriodScore(
        competencia=competencia,
        score_result=score_result,
        total_pendencias=len(pendencias),
    )
