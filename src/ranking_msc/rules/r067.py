"""
Regra R067 — Existe pelo menos 1 conta de despesa (com ND).

Dimensão: Completude
Severidade padrão: ALERTA

Lógica:
    Um ente deve ter despesas orçamentárias. Se nenhuma conta com ND informado
    existir na MSC, pode indicar problema sistêmico na exportação.

    SE COUNT(registros WHERE nd preenchido) == 0 → ALERTA

Referência:
    ref/regras_catalogo.md — R067; Portaria STN 642/2026
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

from ranking_msc.rules.base import Rule, ic_mask_informada, register_rule

if TYPE_CHECKING:
    from ranking_msc.engine.executor import EngineContext


@register_rule
class R067(Rule):
    """Verifica se existe ao menos uma conta de despesa (ND informado) na MSC."""

    rule_id = "R067"
    rule_name = "Despesa presente"
    dimensao = "Completude"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Detecta ausência total de contas com ND na MSC.

        Args:
            df: DataFrame normalizado com coluna ``nd``.
            context: metadados da execução.

        Returns:
            DataFrame de pendências — uma linha se nenhum ND estiver preenchido.
        """
        if df.empty:
            return self.build_issues([])

        tem_nd = ic_mask_informada(df["nd"]).any()
        if tem_nd:
            return self.build_issues([])

        return self.build_issues([
            {
                "severidade": "ALERTA",
                "conta_contabil": "—",
                "descricao": "Nenhuma conta com ND (Natureza da Despesa) encontrada na MSC.",
                "valor_esperado": "≥ 1 registro com ND preenchido",
                "valor_encontrado": "0 registros com ND",
                "competencia": context.competencia,
            }
        ])
