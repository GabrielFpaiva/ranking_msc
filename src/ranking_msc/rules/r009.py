"""Regra R009 — Exatamente 6 pares IC/TIPO (12 colunas) no CSV.

Categoria: Estrutura
Severidade padrão: ERRO

Lógica:
    O CSV deve ter exatamente 6 pares IC/TIPO (IC1..IC6, TIPO1..TIPO6),
    totalizando 12 colunas de informações complementares. Violações são
    capturadas pelo reader_msc após o parse do header.
Referência:
    Doc. Validações MSC Siconfi — item (c)
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
class R009(Rule):
    """Valida que o CSV possui exatamente 12 colunas IC/TIPO (6 pares)."""

    rule_id = "R009"
    rule_name = "6 pares IC/TIPO no header"
    dimensao = "Estrutura"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Retorna pendências de contagem incorreta de colunas IC/TIPO.

        Args:
            df: DataFrame normalizado (não utilizado — violações estão no context).
            context: metadados da execução, incluindo ``pre_pivot_issues``.

        Returns:
            DataFrame de pendências — uma linha por violação encontrada.
        """
        _extra = {"regra_id": self.rule_id, "competencia": context.competencia}

        violacoes = [
            issue for issue in context.pre_pivot_issues
            if issue.get("regra") == "R009"
        ]

        if not violacoes:
            return self.build_issues([])

        logger.warning(
            "R009: %s coluna(s) IC/TIPO encontrada(s), esperado 12. competência=%s",
            violacoes[0].get("valor_encontrado", "?"),
            context.competencia,
            extra=_extra,
        )

        issues: list[dict[str, object]] = [
            {
                "severidade": "ERRO",
                "conta_contabil": "",
                "descricao": (
                    f"CSV com {v['valor_encontrado']} coluna(s) IC/TIPO. "
                    "Esperado: 12 (6 pares — IC1..IC6, TIPO1..TIPO6)."
                ),
                "valor_esperado": "12",
                "valor_encontrado": str(v.get("valor_encontrado", "")),
                "competencia": context.competencia,
            }
            for v in violacoes
        ]

        return self.build_issues(issues)
