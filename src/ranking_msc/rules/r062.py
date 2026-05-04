"""
Regra R062 — Conta exclusivamente Permanente com FP=1.

Dimensão: PCASP
Severidade padrão: ALERTA

Lógica:
    Contas cujo IND_SF no PCASP é "Permanente" não devem ter FP=1 (indicador
    de recurso Financeiro). Indica que o recurso foi classificado no tipo errado.

    SE pcasp[CONTA].IND_SF == "Permanente" AND FP == "1" → ALERTA

    Contas sem IND_SF ou com IND_SF == "Financeiro/Permanente" são ignoradas.

Referência:
    Portaria STN 642/2026 — PcaspEstendido2026 (IND_SF); R062
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pandas as pd

from ranking_msc.io.ref_loader import load_pcasp
from ranking_msc.rules.base import Rule, register_rule

if TYPE_CHECKING:
    from ranking_msc.engine.executor import EngineContext

logger = logging.getLogger("ranking_msc")

_IND_SF_PERMANENTE = "Permanente"
_FP_FINANCEIRO = "1"


@register_rule
class R062(Rule):
    """Detecta contas Permanentes com FP=1 (indicador Financeiro)."""

    rule_id = "R062"
    rule_name = "Conta Permanente com FP=1"
    dimensao = "PCASP"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Identifica linhas onde IND_SF=Permanente mas FP=1.

        Args:
            df: DataFrame normalizado com colunas ``conta_contabil`` e ``fp``.
            context: metadados da execução (competência, siconfi, settings).

        Returns:
            DataFrame de pendências — uma linha por ocorrência detectada.
        """
        _extra = {"regra_id": self.rule_id, "competencia": context.competencia}

        pcasp_raw = load_pcasp(context.settings.paths.ref_dir)
        if "ind_sf" not in pcasp_raw.columns:
            logger.warning(
                "R062: coluna 'ind_sf' ausente em pcasp.csv — regra desativada "
                "para esta execução. Verifique se o PCASP está atualizado (PcaspEstendido2026).",
                extra=_extra,
            )
            return self.build_issues([])

        pcasp = pcasp_raw[["conta_contabil", "ind_sf"]].copy()
        pcasp["ind_sf"] = pcasp["ind_sf"].str.strip()

        _key_cols = ["conta_contabil", "po", "fr", "fp"]
        select_cols = [c for c in _key_cols if c in df.columns]
        merged = df[select_cols].merge(pcasp, on="conta_contabil", how="left")

        merged = merged[
            merged["ind_sf"].notna()
            & (merged["ind_sf"] != "")
            & (merged["ind_sf"] == _IND_SF_PERMANENTE)
        ]

        if merged.empty:
            return self.build_issues([])

        merged["fp"] = merged["fp"].fillna("")
        violacoes = merged[merged["fp"] == _FP_FINANCEIRO].copy()

        if violacoes.empty:
            return self.build_issues([])

        logger.warning(
            "R062: %d linha(s) com IND_SF=Permanente e FP=1. competência=%s",
            len(violacoes),
            context.competencia,
            extra=_extra,
        )

        conta_s = violacoes["conta_contabil"].astype(str)
        fp_s = violacoes["fp"].astype(str)

        issues_df = pd.DataFrame({
            "severidade": "ALERTA",
            "conta_contabil": conta_s.values,
            "descricao": (
                "Conta '" + conta_s
                + "': IND_SF=Permanente mas FP='" + fp_s
                + "' (esperado FP='2' para recurso Permanente)."
            ).values,
            "valor_esperado": "2",
            "valor_encontrado": fp_s.values,
            "competencia": context.competencia,
        })

        return self.build_issues(issues_df.to_dict("records"))
