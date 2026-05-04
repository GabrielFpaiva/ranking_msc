"""Regra R063 — DC deve aparecer apenas nas 105 contas permitidas (ID_IC=8).

Dimensão: IC
Severidade padrão: ERRO

Lógica:
    A IC de Dívida Consolidada (DC) só pode aparecer nas contas que o leiaute
    MSC define com ID_IC=8 no PCASP. São exatamente 105 contas de financiamentos
    do passivo. Qualquer conta com DC informado que não esteja nessa lista é
    um erro estrutural.

Referência:
    Leiaute MSC 2026 — ID_IC=8; ref/regras_catalogo.md R063
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pandas as pd

from ranking_msc.io.ref_loader import load_pcasp
from ranking_msc.rules.base import Rule, ic_mask_informada, register_rule

if TYPE_CHECKING:
    from ranking_msc.engine.executor import EngineContext

logger = logging.getLogger("ranking_msc")


@register_rule
class R063(Rule):
    """Valida se a IC DC aparece apenas em contas com ID_IC=8 no PCASP."""

    rule_id = "R063"
    rule_name = "DC só em contas permitidas pelo leiaute (ID_IC=8)"
    dimensao = "IC"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Verifica se cada conta com DC informado está na lista ID_IC=8 do PCASP.

        Args:
            df: DataFrame normalizado com colunas ``dc`` e ``conta_contabil``.
            context: metadados da execução.

        Returns:
            DataFrame de pendências — uma linha por conta não permitida com DC.
        """
        _extra = {"regra_id": self.rule_id, "competencia": context.competencia}

        if "dc" not in df.columns:
            return self.build_issues([])

        pcasp = load_pcasp(context.settings.paths.ref_dir)

        if "id_ic" not in pcasp.columns:
            logger.warning(
                "R063: coluna 'id_ic' ausente no PCASP, regra ignorada. competência=%s",
                context.competencia,
                extra=_extra,
            )
            return self.build_issues([])

        contas_dc_permitidas: set[str] = set(
            pcasp.loc[
                pcasp["id_ic"].astype(str).str.strip() == "8",
                "conta_contabil",
            ]
            .astype(str)
            .str.strip()
        )

        df_com_dc = df[["conta_contabil", "dc"]].copy()
        df_com_dc = df_com_dc[ic_mask_informada(df_com_dc["dc"])]

        if df_com_dc.empty:
            return self.build_issues([])

        df_unica = df_com_dc.drop_duplicates(subset=["conta_contabil"]).copy()
        df_unica["conta_norm"] = df_unica["conta_contabil"].astype(str).str.strip()

        mask_nao_permitida = ~df_unica["conta_norm"].isin(contas_dc_permitidas)
        df_viol = df_unica[mask_nao_permitida]

        if df_viol.empty:
            return self.build_issues([])

        conta_s = df_viol["conta_norm"]

        issues_df = pd.DataFrame({
            "severidade": "ERRO",
            "conta_contabil": conta_s.values,
            "descricao": (
                "Conta '" + conta_s
                + "' possui DC informado mas não consta na lista de 105 contas"
                " com ID_IC=8 (financiamentos) do leiaute MSC."
            ).values,
            "valor_esperado": "conta com ID_IC=8 no PCASP",
            "valor_encontrado": conta_s.values,
            "competencia": context.competencia,
        })

        logger.warning(
            "R063: %d pendência(s) de DC em conta não permitida. competência=%s",
            len(issues_df),
            context.competencia,
            extra=_extra,
        )

        return self.build_issues(issues_df.to_dict("records"))
