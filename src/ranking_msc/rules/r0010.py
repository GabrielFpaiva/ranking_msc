"""Regra R0010 — Header na primeira linha.

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
class R0010(Rule):
    """Valida que a primeira linha do arquivo é a metadata, não o header."""

    rule_id = "R0010"
    rule_name = "Header após metadata"
    dimensao = "Estrutura"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        violacoes = [
            issue for issue in context.pre_pivot_issues
            if issue.get("regra") == "R0010"
        ]

        if not violacoes:
            return self.build_issues([])

        logger.warning(
            "R0010: header encontrado na primeira linha. competência=%s",
            context.competencia,
            extra={"regra_id": self.rule_id, "competencia": context.competencia},
        )

        issues = [
            {
                "severidade": "ERRO",
                "conta_contabil": "",
                "descricao": (
                    "O arquivo MSC começou diretamente no cabeçalho. "
                    "A primeira linha deve conter a metadata "
                    "'<SICONFI>;<YYYY-MM>' antes do header."
                ),
                "valor_esperado": "<SICONFI>;<YYYY-MM> na primeira linha",
                "valor_encontrado": str(v.get("valor_encontrado", "")),
                "competencia": context.competencia,
            }
            for v in violacoes
        ]
        return self.build_issues(issues)
