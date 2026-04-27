"""
ranking_msc.benchmark.reporter
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Geração do relatório markdown de benchmark.

Produz ``ref/benchmark_performance.md`` com:
    - Resumo geral (tempo, memória, throughput por tamanho)
    - Tempo por etapa do pipeline
    - Top-5 regras mais lentas por tamanho
    - Metadados de ambiente (commit, Python, pandas, máquina)
"""

from __future__ import annotations

import logging
import platform
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from ranking_msc.benchmark.profiler import BenchmarkResult

logger = logging.getLogger("ranking_msc")


def write_report(
    results: list[BenchmarkResult],
    output_path: Path,
    *,
    interrupted: bool = False,
) -> None:
    """Gera relatório markdown com resultados do benchmark.

    Args:
        results: lista de BenchmarkResult (um por tamanho de dataset).
        output_path: caminho de destino do relatório markdown.
        interrupted: se True, adiciona aviso de interrupção ao relatório.
    """
    lines: list[str] = []

    # Header
    lines.append("# Benchmark de Performance")
    lines.append("")
    lines.append(f"**Gerado em:** {datetime.now(tz=UTC).strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append(f"**Commit:** {_get_git_hash()}")
    lines.append(f"**Python:** {sys.version.split()[0]} · **pandas:** {pd.__version__}")
    lines.append(f"**Máquina:** {platform.processor() or platform.machine()}")
    lines.append("")

    if interrupted:
        lines.append("> ⚠️ **INTERROMPIDO** — relatório parcial com os tamanhos completados.")
        lines.append("")

    # Resumo geral
    lines.append("## Resumo geral")
    lines.append("")
    lines.append("| Tamanho | Tempo total | Memória pico | Throughput |")
    lines.append("|---|---|---|---|")
    for r in results:
        if r.failed:
            reason = r.failure_reason or "erro desconhecido"
            lines.append(f"| {_fmt_rows(r.n_rows)} | FAIL: {reason} | — | — |")
        else:
            lines.append(
                f"| {_fmt_rows(r.n_rows)} | {r.total_seconds:.1f}s "
                f"| {r.peak_rss_mb:.0f} MB "
                f"| {r.throughput_rows_per_sec:.1f} rows/s |"
            )
    lines.append("")

    # Tempo por etapa
    non_failed = [r for r in results if not r.failed]
    if non_failed:
        lines.append("## Tempo por etapa")
        lines.append("")

        # Coletar nomes de etapas
        stage_names: list[str] = []
        for r in non_failed:
            for s in r.stages:
                if s.name not in stage_names:
                    stage_names.append(s.name)

        header_cols = " | ".join(stage_names)
        lines.append(f"| Tamanho | {header_cols} |")
        lines.append("|---" + "|---" * len(stage_names) + "|")

        for r in non_failed:
            stage_map = {s.name: s for s in r.stages}
            cols = []
            for sn in stage_names:
                stage = stage_map.get(sn)
                cols.append(f"{stage.wall_seconds:.1f}s" if stage else "—")
            lines.append(f"| {_fmt_rows(r.n_rows)} | {' | '.join(cols)} |")
        lines.append("")

    # Top-5 regras mais lentas por tamanho
    has_rules = any(r.rules for r in non_failed)
    if has_rules:
        lines.append("## Top-5 regras mais lentas")
        lines.append("")

        for r in non_failed:
            if not r.rules:
                continue
            lines.append(f"### {_fmt_rows(r.n_rows)} linhas")
            lines.append("")
            lines.append("| Regra | Tempo | Pendências | Status |")
            lines.append("|---|---|---|---|")

            sorted_rules = sorted(r.rules, key=lambda x: x.wall_seconds, reverse=True)
            for rm in sorted_rules[:5]:
                status = "❌ FAIL" if rm.failed else "✅"
                lines.append(
                    f"| {rm.rule_id} | {rm.wall_seconds:.2f}s "
                    f"| {rm.issue_count} | {status} |"
                )
            lines.append("")

    # Escrever arquivo
    output_path.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(lines) + "\n"
    output_path.write_text(content, encoding="utf-8")
    logger.info("Relatório de benchmark escrito em %s", output_path)


def _get_git_hash() -> str:
    """Retorna o hash curto do commit atual, ou 'N/A' se não estiver em um repo git."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return "N/A"


def _fmt_rows(n: int) -> str:
    """Formata número de linhas com sufixo k/M para legibilidade."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.0f}M"
    if n >= 1_000:
        return f"{n / 1_000:.0f}k"
    return str(n)
