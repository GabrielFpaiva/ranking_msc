"""
Regra R083 — Dados do executivo idênticos entre meses (SIGEF V7).

Dimensão: Temporal
Severidade padrão: ALERTA

Lógica:
    Se os registros do Poder Executivo (PO=10131 para município) de um mês
    são idênticos ao mês anterior em TODAS as contas (saldo_final_debito e
    saldo_final_credito), indica que o ente copiou o arquivo ao invés de
    gerar dados reais. Verificação V7 do Ranking Siconfi.

    SE existe_snapshot_anterior:
        Filtra df WHERE po == PO_EXECUTIVO_MUNICIPAL
        Agrega SF por conta+ICs para o mês atual e o anterior
        SE TODAS as linhas têm SF idêntico entre meses → 1 ALERTA global
        SE NÃO há diferença alguma → OK (ou mês sem registros executivos)

    Se o snapshot anterior não existir, a regra é saltada silenciosamente.

Referência:
    Ranking Siconfi 2026 — verificação V7; Portaria STN 642/2026; R054
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

from ranking_msc.exceptions import SnapshotError, SnapshotNotFoundError
from ranking_msc.outputs.snapshot import read_snapshot
from ranking_msc.rules.base import Rule, register_rule

if TYPE_CHECKING:
    from ranking_msc.engine.executor import EngineContext

logger = logging.getLogger("ranking_msc")

# PO do Poder Executivo para municípios (confirmado em tabela_po.csv e R039)
_PO_EXECUTIVO_MUNICIPAL = "10131"

_IC_COLS: list[str] = ["po", "fp", "dc", "fs", "fr", "co", "nr", "nd", "ai"]
_COLS_SF: list[str] = ["saldo_final_debito", "saldo_final_credito"]


def _prev_competencia(competencia: str) -> str:
    """Retorna a competência do mês anterior no formato YYYY-MM.

    Args:
        competencia: mês de referência no formato "YYYY-MM".

    Returns:
        String "YYYY-MM" correspondente ao mês anterior.
    """
    year, month = int(competencia[:4]), int(competencia[5:7])
    if month == 1:
        return f"{year - 1}-12"
    return f"{year}-{month - 1:02d}"


def _aggregate_sf(df: pd.DataFrame, group_keys: list[str]) -> pd.DataFrame:
    """Agrega saldos finais por combo conta+ICs.

    Args:
        df: DataFrame com colunas de saldo final.
        group_keys: colunas de agrupamento.

    Returns:
        DataFrame agregado com saldo_final_debito e saldo_final_credito.
    """
    sf_cols = [c for c in _COLS_SF if c in df.columns]
    if not sf_cols:
        return pd.DataFrame(columns=group_keys + _COLS_SF)
    work = df[group_keys + sf_cols].copy()
    for col in sf_cols:
        work[col] = pd.to_numeric(work[col], errors="coerce").fillna(0.0)
    return work.groupby(group_keys, as_index=False, dropna=False)[sf_cols].sum()


@register_rule
class R083(Rule):
    """Detecta dados do Poder Executivo idênticos ao mês anterior."""

    rule_id = "R083"
    rule_name = "Dados executivo iguais entre meses"
    dimensao = "Temporal"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Compara saldos finais do executivo entre o mês atual e o anterior.

        Usa context.snapshots_dir quando definido (ex: CLI com --output-dir),
        caindo para settings.paths.snapshots_dir como padrão. Se o snapshot
        anterior não existir, a regra é saltada silenciosamente. Erros de I/O
        propagam para o engine como erro operacional.

        Args:
            df: DataFrame normalizado do mês atual.
            context: metadados da execução (competência, siconfi, settings).

        Returns:
            DataFrame de pendências — 0 ou 1 linha (ALERTA global se 100% idêntico).
        """
        _extra = {"regra_id": self.rule_id, "competencia": context.competencia}

        if "po" not in df.columns:
            logger.warning(
                "R083: coluna 'po' ausente no DataFrame — regra desativada.",
                extra=_extra,
            )
            return self.build_issues([])

        # Filtra registros do Poder Executivo municipal
        df_exec = df[df["po"].astype(str).str.strip() == _PO_EXECUTIVO_MUNICIPAL]
        if df_exec.empty:
            return self.build_issues([])

        prev_comp = _prev_competencia(context.competencia)

        # P1: Respeita --output-dir via context.snapshots_dir
        snapshots_base: Path = (
            context.snapshots_dir
            if context.snapshots_dir is not None
            else Path(context.settings.paths.snapshots_dir)
        )
        snapshots_dir = snapshots_base / context.siconfi

        # P2: Dois except separados — SnapshotNotFoundError é legítimo (skip);
        #     SnapshotError indica falha de I/O e deve propagar.
        try:
            prev_df = read_snapshot(
                prev_comp,
                base_dir=snapshots_dir,
                label="msc_normalizado",
            )
        except SnapshotNotFoundError:
            logger.info(
                "R083: snapshot do mês anterior (%s) ausente — regra saltada.",
                prev_comp,
                extra=_extra,
            )
            return self.build_issues([])
        except SnapshotError:
            logger.error(
                "R083: falha ao ler snapshot do mês anterior (%s) — erro operacional.",
                prev_comp,
                extra=_extra,
                exc_info=True,
            )
            raise

        if prev_df.empty:
            return self.build_issues([])

        # Filtra executivo no snapshot anterior também
        if "po" in prev_df.columns:
            prev_exec = prev_df[
                prev_df["po"].astype(str).str.strip() == _PO_EXECUTIVO_MUNICIPAL
            ]
        else:
            prev_exec = prev_df

        if prev_exec.empty:
            return self.build_issues([])

        # Determina chaves IC disponíveis em ambos os DFs
        ic_n = [c for c in _IC_COLS if c in df_exec.columns]
        ic_p = [c for c in _IC_COLS if c in prev_exec.columns]
        ic_keys = [c for c in ic_n if c in ic_p]

        if "conta_contabil" not in df_exec.columns or "conta_contabil" not in prev_exec.columns:
            return self.build_issues([])

        group_keys = ["conta_contabil"] + ic_keys

        agg_atual = _aggregate_sf(df_exec, group_keys)
        agg_ant = _aggregate_sf(prev_exec, group_keys)

        if agg_atual.empty or agg_ant.empty:
            return self.build_issues([])

        # Sufixos para desambiguar colunas de SF após o merge
        merged = agg_atual.merge(
            agg_ant, on=group_keys, how="inner", suffixes=("_atual", "_ant")
        )

        if merged.empty:
            return self.build_issues([])

        # Verifica se TODOS os saldos são idênticos (dentro de tolerância zero —
        # cópias de arquivo têm valores exatamente iguais)
        sf_cols_atual = [c for c in merged.columns if c.endswith("_atual")]
        sf_cols_ant = [c for c in merged.columns if c.endswith("_ant")]

        todos_identicos = True
        for col_a, col_p in zip(sf_cols_atual, sf_cols_ant, strict=False):
            diff = (merged[col_a] - merged[col_p]).abs()
            if diff.max() > 0:
                todos_identicos = False
                break

        if not todos_identicos:
            return self.build_issues([])

        n_contas = len(merged)
        logger.warning(
            "R083: %d conta(s) do executivo com SF idêntico ao mês anterior (%s). "
            "Possível copy-paste do arquivo. competência=%s",
            n_contas,
            prev_comp,
            context.competencia,
            extra=_extra,
        )

        return self.build_issues([{
            "severidade": "ALERTA",
            "conta_contabil": "",
            "descricao": (
                f"Dados do Poder Executivo (PO={_PO_EXECUTIVO_MUNICIPAL}) idênticos "
                f"ao mês anterior ({prev_comp}) em {n_contas} conta(s). "
                "Possível copy-paste do arquivo MSC (SIGEF V7)."
            ),
            "valor_esperado": "saldos com diferença em relação ao mês anterior",
            "valor_encontrado": f"100% idêntico ao mês {prev_comp}",
            "competencia": context.competencia,
        }])
