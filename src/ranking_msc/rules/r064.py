"""Regra R064 — CO de despesa deve aparecer apenas em contas de despesa.

Dimensão: IC
Severidade padrão: ALERTA

Lógica:
    COs do bloco de Despesa Orçamentária (1001–2999) só devem aparecer em
    contas das classes orçamentárias de despesa (classes 5 e 6) ou de
    Variações Patrimoniais Diminutivas — VPD (classe 3).
    COs do bloco de Receita Orçamentária (5001–5999) só devem aparecer em
    contas de Variações Patrimoniais Aumentativas — VPA (classe 4) ou
    controles de receita (classes 7 e 8).

    A classe contábil é determinada pelo 1º dígito da conta_contabil.

Referência:
    Leiaute MSC 2026 — campo CO; ref/regras_catalogo.md R064
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pandas as pd

from ranking_msc.rules.base import Rule, ic_mask_informada, register_rule

if TYPE_CHECKING:
    from ranking_msc.engine.executor import EngineContext

logger = logging.getLogger("ranking_msc")

_CLASSES_DESPESA: frozenset[str] = frozenset({"3", "5", "6"})
_CLASSES_RECEITA: frozenset[str] = frozenset({"4", "7", "8"})


@register_rule
class R064(Rule):
    """Valida se o CO é compatível com o tipo de conta (despesa vs receita)."""

    rule_id = "R064"
    rule_name = "CO de despesa somente em conta de despesa"
    dimensao = "IC"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Verifica se cada CO é compatível com a classe da conta contábil.

        Args:
            df: DataFrame normalizado com colunas ``co`` e ``conta_contabil``.
            context: metadados da execução.

        Returns:
            DataFrame de pendências — uma linha por CO incompatível com a conta.
        """
        _extra = {"regra_id": self.rule_id, "competencia": context.competencia}

        if "co" not in df.columns:
            return self.build_issues([])

        df_com_co = df[["conta_contabil", "co"]].copy()
        df_com_co = df_com_co[ic_mask_informada(df_com_co["co"])]

        if df_com_co.empty:
            return self.build_issues([])

        df_unica = df_com_co.drop_duplicates(subset=["conta_contabil", "co"]).copy()
        df_unica["co_raw"] = df_unica["co"].astype(str).str.strip().str.zfill(4)
        df_unica["conta_norm"] = df_unica["conta_contabil"].astype(str).str.strip()
        df_unica["classe"] = df_unica["conta_norm"].str[:1]

        co_numeric = pd.to_numeric(df_unica["co_raw"], errors="coerce")
        df_unica["co_int"] = co_numeric

        mask_co_valido = co_numeric.notna()
        df_check = df_unica[mask_co_valido].copy()

        if df_check.empty:
            return self.build_issues([])

        mask_co_despesa = (df_check["co_int"] >= 1001) & (df_check["co_int"] <= 2999)
        mask_co_receita = (df_check["co_int"] >= 5001) & (df_check["co_int"] <= 5999)

        mask_viol_despesa = mask_co_despesa & ~df_check["classe"].isin(_CLASSES_DESPESA)
        mask_viol_receita = mask_co_receita & ~df_check["classe"].isin(_CLASSES_RECEITA)

        dfs_issues = []

        if mask_viol_despesa.any():
            viol = df_check[mask_viol_despesa]
            conta_s = viol["conta_norm"]
            co_s = viol["co_raw"]
            classe_s = viol["classe"]
            dfs_issues.append(pd.DataFrame({
                "severidade": "ALERTA",
                "conta_contabil": conta_s.values,
                "descricao": (
                    "CO '" + co_s + "' (Despesa) em conta classe '"
                    + classe_s + "' (" + conta_s + ") — CO de despesa esperado"
                    " em contas das classes 3, 5 ou 6."
                ).values,
                "valor_esperado": "conta de classe 3, 5 ou 6",
                "valor_encontrado": ("classe " + classe_s).values,
                "competencia": context.competencia,
            }))

        if mask_viol_receita.any():
            viol = df_check[mask_viol_receita]
            conta_s = viol["conta_norm"]
            co_s = viol["co_raw"]
            classe_s = viol["classe"]
            dfs_issues.append(pd.DataFrame({
                "severidade": "ALERTA",
                "conta_contabil": conta_s.values,
                "descricao": (
                    "CO '" + co_s + "' (Receita) em conta classe '"
                    + classe_s + "' (" + conta_s + ") — CO de receita esperado"
                    " em contas das classes 4, 7 ou 8."
                ).values,
                "valor_esperado": "conta de classe 4, 7 ou 8",
                "valor_encontrado": ("classe " + classe_s).values,
                "competencia": context.competencia,
            }))

        if not dfs_issues:
            return self.build_issues([])

        issues_df = pd.concat(dfs_issues, ignore_index=True)

        logger.warning(
            "R064: %d pendência(s) de CO incompatível com classe de conta. competência=%s",
            len(issues_df),
            context.competencia,
            extra=_extra,
        )

        return self.build_issues(issues_df.to_dict("records"))
