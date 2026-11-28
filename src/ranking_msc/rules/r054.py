"""
Regra R054 — Saldo Inicial do mês N = Saldo Final do mês N-1.

Dimensão: Temporal
Severidade padrão: ALERTA

Lógica:
    Se existe snapshot msc_normalizado para o mês anterior (N-1), agrega por
    combo conta_contabil+ICs e compara o saldo inicial líquido do mês N com o
    saldo final líquido do mês N-1. Divergências acima de TOLERANCIA_CENTAVO
    geram ALERTA. Se o snapshot anterior não existir, a regra é saltada
    silenciosamente.

Referência:
    Portaria STN 642/2026 — Regras Gerais MSC, R054 (continuidade temporal)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pandas as pd

from ranking_msc.exceptions import SnapshotError, SnapshotNotFoundError
from ranking_msc.rules.base import TOLERANCIA_CENTAVO, Rule, register_rule

if TYPE_CHECKING:
    from ranking_msc.engine.executor import EngineContext

logger = logging.getLogger("ranking_msc")

# Colunas IC usadas como chave de agrupamento
_IC_COLS: list[str] = ["po", "fp", "dc", "fs", "fr", "co", "nr", "nd", "ai"]

# Colunas de valor necessárias
_COLS_SI: list[str] = ["saldo_inicial_debito", "saldo_inicial_credito"]
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


def _aggregate(df: pd.DataFrame, group_keys: list[str], cols_valor: list[str]) -> pd.DataFrame:
    """Agrega DataFrame por combo conta+ICs, somando colunas de valor.

    Args:
        df: DataFrame a agregar.
        group_keys: colunas de agrupamento.
        cols_valor: colunas numéricas a somar.

    Returns:
        DataFrame agregado.
    """
    work = df[group_keys + cols_valor].copy()
    for col in cols_valor:
        work[col] = pd.to_numeric(work[col], errors="coerce").fillna(0.0)
    return work.groupby(group_keys, as_index=False, dropna=False)[cols_valor].sum()


@register_rule
class R054(Rule):
    """Verifica que o Saldo Inicial do mês N coincide com o Saldo Final do mês N-1."""

    rule_id = "R054"
    rule_name = "SI(N) = SF(N-1)"
    dimensao = "Temporal"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Compara SI líquido do mês N com SF líquido do mês N-1.

        Lê a matriz do mês anterior (mesmo ente e origem) por
        ``context.get_store()``. Se o snapshot
        do mês anterior não existir, a regra é saltada silenciosamente. Erros
        de I/O ou permissão propagam para o engine como erro operacional.

        Args:
            df: DataFrame normalizado do mês N.
            context: metadados da execução, incluindo competência e settings.

        Returns:
            DataFrame de pendências — uma linha por combo CONTA+ICs onde
            abs(SI_líq_N − SF_líq_{N-1}) > TOLERANCIA_CENTAVO.
        """
        _extra = {"regra_id": self.rule_id, "competencia": context.competencia}

        prev_comp = _prev_competencia(context.competencia)
        try:
            prev_df = context.get_store().load_msc(context.ref(prev_comp))
        except SnapshotNotFoundError:
            logger.info(
                "R054: snapshot do mês anterior (%s) ausente — regra saltada.",
                prev_comp,
                extra=_extra,
            )
            return self.build_issues([])
        except SnapshotError:
            logger.error(
                "R054: falha ao ler snapshot do mês anterior (%s) — erro operacional.",
                prev_comp,
                extra=_extra,
                exc_info=True,
            )
            raise

        if df.empty or prev_df.empty:
            return self.build_issues([])

        # Determina quais colunas IC estão presentes (testes podem usar DFs mínimos)
        ic_keys_n = [c for c in _IC_COLS if c in df.columns]
        ic_keys_p = [c for c in _IC_COLS if c in prev_df.columns]
        # Usa a interseção para garantir agrupamento compatível
        ic_keys = [c for c in ic_keys_n if c in ic_keys_p]

        group_keys = ["conta_contabil"] + ic_keys

        # Colunas de SI presentes no mês N
        si_cols_n = [c for c in _COLS_SI if c in df.columns]
        # Colunas de SF presentes no mês N-1
        sf_cols_p = [c for c in _COLS_SF if c in prev_df.columns]

        if not si_cols_n or not sf_cols_p:
            logger.warning(
                "R054: colunas de SI/SF ausentes nos DataFrames — regra desativada.",
                extra=_extra,
            )
            return self.build_issues([])

        # Verifica se conta_contabil existe em ambos
        if "conta_contabil" not in df.columns or "conta_contabil" not in prev_df.columns:
            logger.warning(
                "R054: coluna 'conta_contabil' ausente — regra desativada.",
                extra=_extra,
            )
            return self.build_issues([])

        # Agrega mês N por combo conta+ICs — colunas de SI
        agg_n = _aggregate(df, group_keys, si_cols_n)

        # Garante colunas de SI no agg_n
        if "saldo_inicial_debito" not in agg_n.columns:
            agg_n["saldo_inicial_debito"] = 0.0
        if "saldo_inicial_credito" not in agg_n.columns:
            agg_n["saldo_inicial_credito"] = 0.0
        agg_n["_si_liq"] = agg_n["saldo_inicial_debito"] - agg_n["saldo_inicial_credito"]

        # Agrega mês N-1 — usa o mesmo group_keys (interseção calculada acima)
        agg_p = _aggregate(prev_df, group_keys, sf_cols_p)

        if "saldo_final_debito" not in agg_p.columns:
            agg_p["saldo_final_debito"] = 0.0
        if "saldo_final_credito" not in agg_p.columns:
            agg_p["saldo_final_credito"] = 0.0
        agg_p["_sf_liq"] = agg_p["saldo_final_debito"] - agg_p["saldo_final_credito"]

        agg_p = agg_p[group_keys + ["_sf_liq"]].copy()

        # Inner join — só compara combos presentes em ambos os meses
        merged = agg_n.merge(agg_p, on=group_keys, how="inner")

        if merged.empty:
            return self.build_issues([])

        merged["_diff"] = (merged["_si_liq"] - merged["_sf_liq"]).abs()
        violacoes = merged[merged["_diff"] > TOLERANCIA_CENTAVO]

        if violacoes.empty:
            return self.build_issues([])

        logger.warning(
            "R054: %d combo(s) com SI(N) ≠ SF(N-1). competência=%s mês_anterior=%s",
            len(violacoes),
            context.competencia,
            prev_comp,
            extra=_extra,
        )

        conta_s = violacoes["conta_contabil"].astype(str)
        si_liq_s = violacoes["_si_liq"].map(lambda x: f"{x:.2f}")
        sf_liq_s = violacoes["_sf_liq"].map(lambda x: f"{x:.2f}")
        diff_s = violacoes["_diff"].map(lambda x: f"{x:.2f}")

        issues_df = pd.DataFrame({
            "severidade": "ALERTA",
            "conta_contabil": conta_s.values,
            "descricao": ("Conta '" + conta_s + "': SI do mês " + context.competencia +
                          " (" + si_liq_s + ") ≠ SF do mês " + prev_comp +
                          " (" + sf_liq_s + "). Diferença: " + diff_s + ".").values,
            "valor_esperado": sf_liq_s.values,
            "valor_encontrado": si_liq_s.values,
            "competencia": context.competencia,
        })

        return self.build_issues(issues_df.to_dict("records"))
