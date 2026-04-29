"""Regra R021 — PO válido: 5 dígitos e existente na tabela.

Categoria: PO
Severidade padrão: ERRO
Lógica:
    Quando uma conta possui IC do tipo PO, o valor deve ter exatamente
    5 dígitos e existir na tabela oficial de Poder/Órgão (92 códigos).
Referência:
    Leiaute MSC 2026 — Aba PO; Portaria STN 642/2026
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pandas as pd

from ranking_msc.io.ref_loader import load_tabela_po
from ranking_msc.rules.base import Rule, register_rule

if TYPE_CHECKING:
    from ranking_msc.engine.executor import EngineContext

logger = logging.getLogger("ranking_msc")


@register_rule
class R021(Rule):
    """Valida formato (5 dígitos) e existência do PO na tabela oficial."""

    rule_id = "R021"
    rule_name = "PO válido — 5 dígitos e existente na tabela"
    dimensao = "PO"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Verifica se os valores de PO são válidos em formato e domínio.

        Args:
            df: DataFrame normalizado com colunas ``po`` e ``conta_contabil``.
            context: metadados da execução.

        Returns:
            DataFrame de pendências — uma linha por combinação
            conta/PO inválida encontrada.
        """
        _extra = {"regra_id": self.rule_id, "competencia": context.competencia}

        tabela_po_df = load_tabela_po(context.settings.paths.ref_dir)
        codigos_validos: set[str] = set(tabela_po_df["codigo"].astype(str))

        df_com_po = df[df["po"].astype(str).str.strip() != ""][["conta_contabil", "po"]].copy()
        df_com_po["po"] = df_com_po["po"].astype(str).str.strip()

        if df_com_po.empty:
            return self.build_issues([])

        # Remover duplicatas para validação
        df_unica = df_com_po.drop_duplicates(subset=["conta_contabil", "po"]).copy()
        df_unica["po_raw"] = df_unica["po"].astype(str).str.strip()

        mask_len = df_unica["po_raw"].str.len() != 5
        mask_tabela = (~mask_len) & (~df_unica["po_raw"].isin(codigos_validos))

        dfs_issues = []

        if mask_len.any():
            viol = df_unica[mask_len]
            dfs_issues.append(pd.DataFrame({
                "severidade": "ERRO",
                "conta_contabil": viol["conta_contabil"].astype(str),
                "descricao": "PO '" + viol["po_raw"] + "' fora do formato: esperado 5 dígitos, encontrado " + viol["po_raw"].str.len().astype(str) + ".",
                "valor_esperado": "5 dígitos",
                "valor_encontrado": viol["po_raw"],
                "competencia": context.competencia,
            }))

        if mask_tabela.any():
            viol = df_unica[mask_tabela]
            dfs_issues.append(pd.DataFrame({
                "severidade": "ERRO",
                "conta_contabil": viol["conta_contabil"].astype(str),
                "descricao": "PO '" + viol["po_raw"] + "' não encontrado na tabela oficial de Poder/Órgão.",
                "valor_esperado": "Código PO existente na tabela",
                "valor_encontrado": viol["po_raw"],
                "competencia": context.competencia,
            }))

        if dfs_issues:
            issues_df = pd.concat(dfs_issues, ignore_index=True)
            logger.warning(
                "R021: %d pendência(s) de PO inválido. competência=%s",
                len(issues_df),
                context.competencia,
                extra=_extra,
            )
            return self.build_issues(issues_df.to_dict("records"))

        return self.build_issues([])
