"""Regra R046 — ND não deve ser genérica.

Dimensão: IC
Severidade padrão: ALERTA

Lógica:
    NDs cujo nome na tabela ND 2026 contém a substring "Genéric" (como
    "Modalidade Genérica" ou "Elemento Genérico") existem apenas para De-Para
    e não devem ser usadas em registros de execução orçamentária.

Referência:
    Leiaute MSC 2026 — campo ND; ref/regras_catalogo.md R046
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pandas as pd

from ranking_msc.io.ref_loader import load_tabela_nd
from ranking_msc.rules.base import Rule, ic_mask_informada, register_rule

if TYPE_CHECKING:
    from ranking_msc.engine.executor import EngineContext

logger = logging.getLogger("ranking_msc")


@register_rule
class R046(Rule):
    """Valida se a ND informada não é uma categoria genérica."""

    rule_id = "R046"
    rule_name = "ND não deve ser genérica (De-Para)"
    dimensao = "IC"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Verifica se cada ND informada não tem 'Genéric' no nome da tabela ND.

        Args:
            df: DataFrame normalizado com colunas ``nd`` e ``conta_contabil``.
            context: metadados da execução.

        Returns:
            DataFrame de pendências — uma linha por ND genérica encontrada.
        """
        _extra = {"regra_id": self.rule_id, "competencia": context.competencia}

        if "nd" not in df.columns:
            return self.build_issues([])

        tabela = load_tabela_nd(context.settings.paths.ref_dir)
        nd_genericas: set[str] = set(
            tabela.loc[
                tabela["nome"].str.strip().str.contains("Genéric", na=False, case=False),
                "codigo",
            ]
            .astype(str)
            .str.strip()
            .str.zfill(8)
        )

        df_com_nd = df[["conta_contabil", "nd"]].copy()
        df_com_nd = df_com_nd[ic_mask_informada(df_com_nd["nd"])]

        if df_com_nd.empty:
            return self.build_issues([])

        df_unica = df_com_nd.drop_duplicates(subset=["conta_contabil", "nd"]).copy()
        df_unica["nd_val"] = df_unica["nd"].astype(str).str.strip().str.zfill(8)

        mask_generica = df_unica["nd_val"].isin(nd_genericas)
        df_viol = df_unica[mask_generica]

        if df_viol.empty:
            return self.build_issues([])

        conta_s = df_viol["conta_contabil"].astype(str)
        nd_s = df_viol["nd_val"]

        issues_df = pd.DataFrame({
            "severidade": "ALERTA",
            "conta_contabil": conta_s.values,
            "descricao": (
                "ND '" + nd_s + "' é genérica (De-Para) para conta '"
                + conta_s + "': NDs genéricas não devem ser usadas em execução."
            ).values,
            "valor_esperado": "ND específica de execução",
            "valor_encontrado": nd_s.values,
            "competencia": context.competencia,
        })

        logger.warning(
            "R046: %d pendência(s) de ND genérica. competência=%s",
            len(issues_df),
            context.competencia,
            extra=_extra,
        )

        return self.build_issues(issues_df.to_dict("records"))
