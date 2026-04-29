"""Regra R023 — DC (Dívida Consolidada) válido.

Categoria: IC
Severidade padrão: ERRO

Lógica:
    Quando a coluna `dc` está informada, o valor deve ser "1"
    (não compõe Dívida Consolidada). Qualquer outro valor é inválido.

Referência:
    Leiaute MSC 2026 — campo DC; Portaria STN 642/2026
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pandas as pd

from ranking_msc.io.ref_loader import DC_DOMAIN
from ranking_msc.rules.base import Rule, ic_mask_informada, register_rule

if TYPE_CHECKING:
    from ranking_msc.engine.executor import EngineContext

logger = logging.getLogger("ranking_msc")


@register_rule
class R023(Rule):
    """Valida se o valor de DC é "1" (não compõe Dívida Consolidada)."""

    rule_id = "R023"
    rule_name = "DC válido — valor 1"
    dimensao = "IC"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Verifica se os valores de DC estão no domínio permitido {"1"}.

        Args:
            df: DataFrame normalizado com colunas ``dc`` e ``conta_contabil``.
            context: metadados da execução.

        Returns:
            DataFrame de pendências — uma linha por combinação
            conta/DC inválida encontrada.
        """
        _extra = {"regra_id": self.rule_id, "competencia": context.competencia}

        if "dc" not in df.columns:
            return self.build_issues([])

        df_com_dc = df[["conta_contabil", "dc"]].copy()
        df_com_dc = df_com_dc[ic_mask_informada(df_com_dc["dc"])]
        df_com_dc["dc"] = df_com_dc["dc"].astype(str).str.strip()

        if df_com_dc.empty:
            return self.build_issues([])

        df_invalidos = df_com_dc[~df_com_dc["dc"].isin(DC_DOMAIN)].drop_duplicates().copy()

        if df_invalidos.empty:
            return self.build_issues([])

        conta_s = df_invalidos["conta_contabil"].astype(str)
        dc_s = df_invalidos["dc"].astype(str)

        issues_df = pd.DataFrame({
            "severidade": "ERRO",
            "conta_contabil": conta_s.values,
            "descricao": (
                "DC '" + dc_s + "' inválido para conta '" + conta_s + "': "
                "esperado '1' (não compõe DC)."
            ).values,
            "valor_esperado": "1",
            "valor_encontrado": dc_s.values,
            "competencia": context.competencia,
        })

        logger.warning(
            "R023: %d pendência(s) de DC inválido. competência=%s",
            len(issues_df),
            context.competencia,
            extra=_extra,
        )

        return self.build_issues(issues_df.to_dict("records"))
