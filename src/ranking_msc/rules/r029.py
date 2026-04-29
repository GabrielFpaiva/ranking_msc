"""Regra R029 — AI (Ano Inscrição RP) válido.

Categoria: IC
Severidade: ERRO (formato inválido) | ALERTA (ano implausível)

Lógica:
    Quando uma conta possui IC do tipo AI (Ano de Inscrição em Restos a Pagar),
    o valor deve:
    1. Ter exatamente 4 dígitos numéricos → ERRO se violado.
    2. Ser um ano plausível: >= 2000 e <= ano da competência → ALERTA se violado.

    Linhas sem AI (ic_esta_informada retorna False) são ignoradas.

Referência:
    Leiaute MSC 2026 — IC tipo AI; Portaria STN 642/2026
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pandas as pd

from ranking_msc.rules.base import Rule, ic_mask_informada, register_rule

if TYPE_CHECKING:
    from ranking_msc.engine.executor import EngineContext

logger = logging.getLogger("ranking_msc")


@register_rule
class R029(Rule):
    """Valida formato (4 dígitos) e plausibilidade do Ano Inscrição RP."""

    rule_id = "R029"
    rule_name = "AI — Ano Inscrição RP válido"
    dimensao = "IC"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Verifica formato e plausibilidade do campo ai.

        Args:
            df: DataFrame normalizado com colunas ``conta_contabil`` e ``ai``.
            context: metadados da execução (competência, siconfi, settings).

        Returns:
            DataFrame de pendências — ERRO para formato inválido,
            ALERTA para ano fora do intervalo [2000, ano_competencia].
        """
        _extra = {"regra_id": self.rule_id, "competencia": context.competencia}

        ano_competencia = int(context.competencia.split("-")[0])

        df_com_ai = (
            df[ic_mask_informada(df["ai"])][["conta_contabil", "ai"]]
            .copy()
            .assign(ai=lambda x: x["ai"].astype(str).str.strip())
            .drop_duplicates()
        )

        if df_com_ai.empty:
            return self.build_issues([])

        df_unica = df_com_ai.copy()
        mask_formato = (df_unica["ai"].str.len() != 4) | (~df_unica["ai"].str.isdigit())
        
        # Safe cast for valid years
        df_validos = df_unica[~mask_formato].copy()
        df_validos["ano"] = pd.to_numeric(df_validos["ai"], errors='coerce').fillna(0).astype(int)
        mask_plausivel = (df_validos["ano"] < 2000) | (df_validos["ano"] > ano_competencia)
        
        dfs_issues = []

        if mask_formato.any():
            viol = df_unica[mask_formato]
            dfs_issues.append(pd.DataFrame({
                "severidade": "ERRO",
                "conta_contabil": viol["conta_contabil"].astype(str),
                "descricao": "AI '" + viol["ai"] + "' fora do formato: esperado exatamente 4 dígitos numéricos, encontrado '" + viol["ai"] + "'. Conta: " + viol["conta_contabil"].astype(str) + ".",
                "valor_esperado": "4 dígitos numéricos (ex: '2023')",
                "valor_encontrado": viol["ai"],
                "competencia": context.competencia,
            }))

        if mask_plausivel.any():
            viol = df_validos[mask_plausivel]
            dfs_issues.append(pd.DataFrame({
                "severidade": "ALERTA",
                "conta_contabil": viol["conta_contabil"].astype(str),
                "descricao": "AI '" + viol["ai"] + "' implausível: esperado ano entre 2000 e " + str(ano_competencia) + ", encontrado " + viol["ano"].astype(str) + ".",
                "valor_esperado": "2000 ≤ ano ≤ " + str(ano_competencia),
                "valor_encontrado": viol["ai"],
                "competencia": context.competencia,
            }))

        if dfs_issues:
            issues_df = pd.concat(dfs_issues, ignore_index=True)
            logger.warning(
                "R029: %d pendência(s) de AI inválido. competência=%s",
                len(issues_df),
                context.competencia,
                extra=_extra,
            )
            return self.build_issues(issues_df.to_dict("records"))

        return self.build_issues([])
