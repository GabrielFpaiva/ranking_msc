"""
ranking_msc.benchmark.profiler
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Instrumentação de performance do pipeline MSC.

Mede tempo de execução (wall time via ``time.perf_counter``) e consumo
de memória (RSS via ``resource.getrusage``) por etapa do pipeline e
por regra individual.

Nota sobre memória: ``ru_maxrss`` é global ao processo (não por etapa).
Registramos RSS delta por etapa como aproximação e peak global como
valor honesto no relatório final.
"""

from __future__ import annotations

import logging
import platform
import resource
import time
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("ranking_msc")


@dataclass(frozen=True)
class StageMetrics:
    """Métricas de uma etapa do pipeline."""

    name: str
    wall_seconds: float
    rss_delta_mb: float


@dataclass(frozen=True)
class RuleMetrics:
    """Métricas de execução de uma regra individual."""

    rule_id: str
    wall_seconds: float
    issue_count: int
    failed: bool = False


@dataclass(frozen=True)
class BenchmarkResult:
    """Resultado consolidado de benchmark para um tamanho de dataset."""

    n_rows: int
    total_seconds: float
    peak_rss_mb: float
    throughput_rows_per_sec: float
    stages: list[StageMetrics] = field(default_factory=list)
    rules: list[RuleMetrics] = field(default_factory=list)
    failed: bool = False
    failure_reason: str | None = None


class _MeasureContext:
    """Objeto retornado pelo context manager ``measure()``.

    Acumula métricas durante a execução do bloco ``with``.
    """

    def __init__(self, name: str) -> None:
        self.name = name
        self.wall_seconds: float = 0.0
        self.rss_delta_mb: float = 0.0
        self._start_time: float = 0.0
        self._start_rss: int = 0

    def to_stage(self) -> StageMetrics:
        """Converte para StageMetrics imutável."""
        return StageMetrics(
            name=self.name,
            wall_seconds=self.wall_seconds,
            rss_delta_mb=self.rss_delta_mb,
        )


def _get_rss_kb() -> int:
    """Retorna RSS atual em kilobytes (Linux) ou bytes (macOS)."""
    usage = resource.getrusage(resource.RUSAGE_SELF)  # type: ignore[attr-defined]
    rss: int = usage.ru_maxrss
    # Linux: ru_maxrss em KB; macOS: em bytes
    if platform.system() == "Darwin":
        return rss // 1024
    return rss


def read_peak_rss_mb() -> float:
    """Retorna pico de RSS do processo em megabytes."""
    return _get_rss_kb() / 1024.0


@contextmanager
def measure(name: str) -> Generator[_MeasureContext, None, None]:
    """Context manager que mede wall time e RSS delta de um bloco.

    Args:
        name: nome da etapa sendo medida.

    Yields:
        Objeto ``_MeasureContext`` com métricas populadas após o bloco.

    Exemplo::

        with measure("read_csv") as m:
            df = read_msc_csv(path)
        print(f"Tempo: {m.wall_seconds:.2f}s, RSS delta: {m.rss_delta_mb:.1f}MB")
    """
    ctx = _MeasureContext(name)
    ctx._start_time = time.perf_counter()
    ctx._start_rss = _get_rss_kb()
    try:
        yield ctx
    finally:
        elapsed = time.perf_counter() - ctx._start_time
        rss_delta = (_get_rss_kb() - ctx._start_rss) / 1024.0
        ctx.wall_seconds = elapsed
        ctx.rss_delta_mb = rss_delta


@contextmanager
def instrument_rules() -> Generator[list[RuleMetrics], None, None]:
    """Context manager que instrumenta ``Rule.execute`` para capturar métricas por regra.

    Patcha temporariamente o método ``execute`` de cada subclasse registrada
    em ``RULE_REGISTRY`` para medir tempo de execução e contagem de pendências.
    Os patches são revertidos no ``__exit__``.

    Yields:
        Lista de ``RuleMetrics`` populada após a execução do bloco.

    Exemplo::

        with instrument_rules() as rule_metrics:
            result = run_engine(df, context)
        for rm in rule_metrics:
            print(f"{rm.rule_id}: {rm.wall_seconds:.2f}s, {rm.issue_count} issues")
    """
    from ranking_msc.rules.base import RULE_REGISTRY

    metrics: list[RuleMetrics] = []
    originals: dict[type, Any] = {}

    def _make_wrapper(orig: Any) -> Any:
        def _instrumented_execute(self: Any, df: Any, context: Any) -> Any:
            """Wrapper que mede tempo e issues de cada regra."""
            start = time.perf_counter()
            failed = False
            issue_count = 0
            try:
                result = orig(self, df, context)
                issue_count = len(result) if result is not None else 0
                return result
            except Exception:
                failed = True
                raise
            finally:
                elapsed = time.perf_counter() - start
                metrics.append(RuleMetrics(
                    rule_id=self.rule_id,
                    wall_seconds=elapsed,
                    issue_count=issue_count,
                    failed=failed,
                ))
        return _instrumented_execute

    # Salvar e patchar cada subclasse registrada
    for rule_cls in RULE_REGISTRY.values():
        originals[rule_cls] = rule_cls.execute
        rule_cls.execute = _make_wrapper(rule_cls.execute)  # type: ignore[assignment]

    try:
        yield metrics
    finally:
        # Reverter patches
        for rule_cls, orig in originals.items():
            rule_cls.execute = orig  # type: ignore[assignment]

