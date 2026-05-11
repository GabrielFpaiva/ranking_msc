"""Regra R0011 — Valor não-negativo.

Categoria: Estrutura
Severidade padrão: ERRO
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pandas as pd

from ranking_msc.rules.base import Rule, register_rule

if TYPE_CHECKING:
    from ranking_msc.engine.executor import EngineContext

logger = logging.getLogger("ranking_msc")


@register_rule
class R0011(Rule):
    """Valida que o campo Valor não assume valores negativos."""

    rule_id = "R0011"
    rule_name = "Valor não-negativo"
    dimensao = "Estrutura"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        violacoes = [
            issue for issue in context.pre_pivot_issues
            if issue.get("regra") == "R0011"
        ]

        if not violacoes:
            return self.build_issues([])

        logger.warning(
            "R0011: %d linha(s) com Valor negativo. competência=%s",
            len(violacoes),
            context.competencia,
            extra={"regra_id": self.rule_id, "competencia": context.competencia},
        )

        issues = [
            {
                "severidade": "ERRO",
                "conta_contabil": str(v.get("conta_contabil", "")),
                "descricao": (
                    f"Campo Valor '{v.get('valor_encontrado', '')}' é negativo. "
                    "O leiaute MSC exige valor monetário maior ou igual a zero."
                ),
                "valor_esperado": "Valor >= 0",
                "valor_encontrado": str(v.get("valor_encontrado", "")),
                "competencia": context.competencia,
            }
            for v in violacoes
        ]
        return self.build_issues(issues)
