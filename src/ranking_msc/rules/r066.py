"""
Regra R066 — Existe pelo menos 1 conta de receita (com NR).

Dimensão: Completude
Severidade padrão: ALERTA

Lógica:
    Um ente deve ter receitas orçamentárias. Se nenhuma conta com NR informado
    existir na MSC, pode indicar problema sistêmico na exportação.

    SE COUNT(registros WHERE nr preenchido) == 0 → ALERTA

Referência:
    ref/regras_catalogo.md — R066; Portaria STN 642/2026
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

from ranking_msc.rules.base import Rule, ic_mask_informada, register_rule

if TYPE_CHECKING:
    from ranking_msc.engine.executor import EngineContext


@register_rule
class R066(Rule):
    """Verifica se existe ao menos uma conta de receita (NR informado) na MSC."""

    rule_id = "R066"
    rule_name = "Receita presente"
    dimensao = "Completude"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Detecta ausência total de contas com NR na MSC.

        Args:
            df: DataFrame normalizado com coluna ``nr``.
            context: metadados da execução.

        Returns:
            DataFrame de pendências — uma linha se nenhum NR estiver preenchido.
        """
        if df.empty:
            return self.build_issues([])

        tem_nr = ic_mask_informada(df["nr"]).any()
        if tem_nr:
            return self.build_issues([])

        return self.build_issues([
            {
                "severidade": "ALERTA",
                "conta_contabil": "—",
                "descricao": "Nenhuma conta com NR (Natureza da Receita) encontrada na MSC.",
                "valor_esperado": "≥ 1 registro com NR preenchido",
                "valor_encontrado": "0 registros com NR",
                "competencia": context.competencia,
            }
        ])
