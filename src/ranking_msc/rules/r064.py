"""Regra R064 — CO x classe da conta (informativo).

Dimensão: IC
Severidade padrão: INFO — fora da pontuação (is_scoring=False)

Lógica:
    Sinaliza CO do bloco de Despesa fora das classes 1, 2, 5 e 6 e CO do bloco de
    Receita fora das classes 4, 7 e 8. Essa restrição por classe não consta do
    leiaute: a conta 721900000, por exemplo, tem ID_IC 5 (PO - FR - CO) e carrega
    CO legitimamente. A conformidade do conjunto de IC de cada conta é verificada
    pela R020.

Referência:
    doc/calibracao_regras_respostas_rodrigo.md, pergunta 8.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, ClassVar

import pandas as pd

from ranking_msc.rules.base import Rule, ic_mask_informada, register_rule

if TYPE_CHECKING:
    from ranking_msc.engine.executor import EngineContext

logger = logging.getLogger("ranking_msc")

_CLASSES_DESPESA: frozenset[str] = frozenset({"1", "2", "5", "6"})
_CLASSES_RECEITA: frozenset[str] = frozenset({"4", "7", "8"})


@register_rule
class R064(Rule):
    """Sinaliza CO incompatível com a classe da conta — informativo, fora da pontuação."""

    rule_id = "R064"
    rule_name = "CO x classe da conta (informativo)"
    dimensao = "IC"
    is_scoring: ClassVar[bool] = False

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
                "severidade": "INFO",
                "conta_contabil": conta_s.values,
                "descricao": (
                    "CO '" + co_s + "' (Despesa) em conta classe '"
                    + classe_s + "' (" + conta_s + ") — CO de despesa esperado"
                    " em contas das classes 1, 2, 5 ou 6 (informativo, fora da pontuação)."
                ).values,
                "valor_esperado": "conta de classe 1, 2, 5 ou 6",
                "valor_encontrado": ("classe " + classe_s).values,
                "competencia": context.competencia,
            }))

        if mask_viol_receita.any():
            viol = df_check[mask_viol_receita]
            conta_s = viol["conta_norm"]
            co_s = viol["co_raw"]
            classe_s = viol["classe"]
            dfs_issues.append(pd.DataFrame({
                "severidade": "INFO",
                "conta_contabil": conta_s.values,
                "descricao": (
                    "CO '" + co_s + "' (Receita) em conta classe '"
                    + classe_s + "' (" + conta_s + ") — CO de receita esperado"
                    " em contas das classes 4, 7 ou 8 (informativo, fora da pontuação)."
                ).values,
                "valor_esperado": "conta de classe 4, 7 ou 8",
                "valor_encontrado": ("classe " + classe_s).values,
                "competencia": context.competencia,
            }))

        if not dfs_issues:
            return self.build_issues([])

        issues_df = pd.concat(dfs_issues, ignore_index=True)

        logger.info(
            "R064: %d pendência(s) de CO incompatível com classe de conta (informativo)."
            " competência=%s",
            len(issues_df),
            context.competencia,
            extra=_extra,
        )

        return self.build_issues(issues_df.to_dict("records"))
