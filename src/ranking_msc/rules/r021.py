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

        issues: list[dict[str, object]] = []

        for _, row in df_com_po.drop_duplicates().iterrows():
            po_valor = str(row["po"])
            conta = str(row["conta_contabil"])

            if len(po_valor) != 5:
                issues.append({
                    "severidade": "ERRO",
                    "conta_contabil": conta,
                    "descricao": (
                        f"PO '{po_valor}' fora do formato: "
                        f"esperado 5 dígitos, encontrado {len(po_valor)}."
                    ),
                    "valor_esperado": "5 dígitos",
                    "valor_encontrado": po_valor,
                    "competencia": context.competencia,
                })
                continue

            if po_valor not in codigos_validos:
                issues.append({
                    "severidade": "ERRO",
                    "conta_contabil": conta,
                    "descricao": (
                        f"PO '{po_valor}' não encontrado na tabela oficial "
                        "de Poder/Órgão."
                    ),
                    "valor_esperado": "Código PO existente na tabela",
                    "valor_encontrado": po_valor,
                    "competencia": context.competencia,
                })

        if issues:
            logger.warning(
                "R021: %d pendência(s) de PO inválido. competência=%s",
                len(issues),
                context.competencia,
                extra=_extra,
            )

        return self.build_issues(issues)
