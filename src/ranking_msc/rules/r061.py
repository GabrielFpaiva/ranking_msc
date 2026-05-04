"""
Regra R061 — Conta exclusivamente Financeira com FP=2.

Dimensão: PCASP
Severidade padrão: ALERTA

Lógica:
    Contas cujo IND_SF no PCASP é "Financeiro" não devem ter FP=2 (indicador
    de recurso Permanente). Indica que o recurso foi classificado no tipo errado.

    SE pcasp[CONTA].IND_SF == "Financeiro" AND FP == "2" → ALERTA

    Contas sem IND_SF ou com IND_SF == "Financeiro/Permanente" são ignoradas.

Referência:
    Portaria STN 642/2026 — PcaspEstendido2026 (IND_SF); R061
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

_IND_SF_FINANCEIRO = "Financeiro"
_FP_PERMANENTE = "2"


@register_rule
class R061(Rule):
    """Detecta contas Financeiras com FP=2 (indicador Permanente)."""

    rule_id = "R061"
    rule_name = "Conta Financeira com FP=2"
    dimensao = "PCASP"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Identifica linhas onde IND_SF=Financeiro mas FP=2.

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
                "R061: coluna 'ind_sf' ausente em pcasp.csv — regra desativada "
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
            & (merged["ind_sf"] == _IND_SF_FINANCEIRO)
        ]

        if merged.empty:
            return self.build_issues([])

        merged["fp"] = merged["fp"].fillna("")
        violacoes = merged[merged["fp"] == _FP_PERMANENTE].copy()

        if violacoes.empty:
            return self.build_issues([])

        logger.warning(
            "R061: %d linha(s) com IND_SF=Financeiro e FP=2. competência=%s",
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
                + "': IND_SF=Financeiro mas FP='" + fp_s
                + "' (esperado FP='1' para recurso Financeiro)."
            ).values,
            "valor_esperado": "1",
            "valor_encontrado": fp_s.values,
            "competencia": context.competencia,
        })

        return self.build_issues(issues_df.to_dict("records"))
