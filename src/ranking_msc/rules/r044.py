"""Regra R044 — NR deve ser valorizável (último nível).

Dimensão: IC
Severidade padrão: ALERTA

Lógica:
    NRs informadas devem ser de nível valorizável (coluna `valorizavel` == "SIM"
    na tabela NR 2026). NRs sintéticas (valorizavel == "NÃO") existem apenas
    para agrupamento e não devem receber valores na MSC.

Referência:
    Leiaute MSC 2026 — campo NR; ref/regras_catalogo.md R044
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pandas as pd

from ranking_msc.io.ref_loader import load_tabela_nr
from ranking_msc.rules.base import Rule, ic_mask_informada, register_rule

if TYPE_CHECKING:
    from ranking_msc.engine.executor import EngineContext

logger = logging.getLogger("ranking_msc")


@register_rule
class R044(Rule):
    """Valida se a NR informada é valorizável (não sintética)."""

    rule_id = "R044"
    rule_name = "NR deve ser valorizável (último nível)"
    dimensao = "IC"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Verifica se cada NR informada tem valorizavel == 'SIM' na tabela NR.

        Args:
            df: DataFrame normalizado com colunas ``nr`` e ``conta_contabil``.
            context: metadados da execução.

        Returns:
            DataFrame de pendências — uma linha por NR sintética encontrada.
        """
        _extra = {"regra_id": self.rule_id, "competencia": context.competencia}

        if "nr" not in df.columns:
            return self.build_issues([])

        tabela = load_tabela_nr(context.settings.paths.ref_dir)
        nao_valorizaveis: set[str] = set(
            tabela.loc[
                tabela["valorizavel"].str.upper().str.strip().isin({"NÃO", "NAO", "N", "NO"}),
                "codigo",
            ]
            .astype(str)
            .str.strip()
            .str.zfill(8)
        )

        df_com_nr = df[["conta_contabil", "nr"]].copy()
        df_com_nr = df_com_nr[ic_mask_informada(df_com_nr["nr"])]

        if df_com_nr.empty:
            return self.build_issues([])

        df_unica = df_com_nr.drop_duplicates(subset=["conta_contabil", "nr"]).copy()
        df_unica["nr_val"] = df_unica["nr"].astype(str).str.strip().str.zfill(8)

        mask_sintetica = df_unica["nr_val"].isin(nao_valorizaveis)
        df_viol = df_unica[mask_sintetica]

        if df_viol.empty:
            return self.build_issues([])

        conta_s = df_viol["conta_contabil"].astype(str)
        nr_s = df_viol["nr_val"]

        issues_df = pd.DataFrame({
            "severidade": "ALERTA",
            "conta_contabil": conta_s.values,
            "descricao": (
                "NR '" + nr_s + "' é sintética (não valorizável) para conta '"
                + conta_s + "': NRs de agrupamento não devem receber valores."
            ).values,
            "valor_esperado": "NR valorizável (último nível)",
            "valor_encontrado": nr_s.values,
            "competencia": context.competencia,
        })

        logger.warning(
            "R044: %d pendência(s) de NR sintética. competência=%s",
            len(issues_df),
            context.competencia,
            extra=_extra,
        )

        return self.build_issues(issues_df.to_dict("records"))
