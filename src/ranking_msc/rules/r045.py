"""Regra R045 — ND deve ser de último nível.

Dimensão: IC
Severidade padrão: ALERTA

Lógica:
    NDs informadas devem ser de último nível (coluna `nivel` NÃO inicia com
    "Superior" na tabela ND 2026). NDs de nível Superior existem apenas para
    agrupamento ("De-Para") e não devem aparecer em registros de execução.

Referência:
    Leiaute MSC 2026 — campo ND; ref/regras_catalogo.md R045
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
class R045(Rule):
    """Valida se a ND informada é de último nível (não sintética/superior)."""

    rule_id = "R045"
    rule_name = "ND deve ser de último nível"
    dimensao = "IC"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Verifica se cada ND informada tem nivel == 'Último' na tabela ND.

        Args:
            df: DataFrame normalizado com colunas ``nd`` e ``conta_contabil``.
            context: metadados da execução.

        Returns:
            DataFrame de pendências — uma linha por ND de nível superior encontrada.
        """
        _extra = {"regra_id": self.rule_id, "competencia": context.competencia}

        if "nd" not in df.columns:
            return self.build_issues([])

        tabela = load_tabela_nd(context.settings.paths.ref_dir)
        nivel_superior: set[str] = set(
            tabela.loc[
                tabela["nivel"].str.strip().str.startswith("Superior"),
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

        mask_superior = df_unica["nd_val"].isin(nivel_superior)
        df_viol = df_unica[mask_superior]

        if df_viol.empty:
            return self.build_issues([])

        conta_s = df_viol["conta_contabil"].astype(str)
        nd_s = df_viol["nd_val"]

        issues_df = pd.DataFrame({
            "severidade": "ALERTA",
            "conta_contabil": conta_s.values,
            "descricao": (
                "ND '" + nd_s + "' é de nível Superior (sintética) para conta '"
                + conta_s + "': usar apenas NDs de último nível em execução."
            ).values,
            "valor_esperado": "ND de último nível",
            "valor_encontrado": nd_s.values,
            "competencia": context.competencia,
        })

        logger.warning(
            "R045: %d pendência(s) de ND de nível superior. competência=%s",
            len(issues_df),
            context.competencia,
            extra=_extra,
        )

        return self.build_issues(issues_df.to_dict("records"))
