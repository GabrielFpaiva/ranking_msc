"""Regra R006 — Código Siconfi válido.

Categoria: Estrutura
Severidade padrão: ERRO

Lógica:
    O código da instituição Siconfi na primeira linha do CSV deve seguir
    o padrão oficial: 7 dígitos IBGE + sufixo "EX" (ex: 2507507EX).
    Violações são capturadas pelo reader_msc antes do parsing do DataFrame.
Referência:
    Doc. Validações MSC Siconfi — item (a)
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
class R006(Rule):
    """Valida que o código Siconfi segue o padrão 7 dígitos + 'EX'."""

    rule_id = "R006"
    rule_name = "Código Siconfi válido"
    dimensao = "Estrutura"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Retorna pendências de código Siconfi inválido capturadas pelo reader.

        Args:
            df: DataFrame normalizado (não utilizado — violações estão no context).
            context: metadados da execução, incluindo ``pre_pivot_issues``.

        Returns:
            DataFrame de pendências — uma linha por violação encontrada.
        """
        _extra = {"regra_id": self.rule_id, "competencia": context.competencia}

        violacoes = [
            issue for issue in context.pre_pivot_issues
            if issue.get("regra") == "R006"
        ]

        if not violacoes:
            return self.build_issues([])

        logger.warning(
            "R006: código Siconfi inválido '%s'. competência=%s",
            violacoes[0].get("valor_encontrado", ""),
            context.competencia,
            extra=_extra,
        )

        issues: list[dict[str, object]] = [
            {
                "severidade": "ERRO",
                "conta_contabil": "",
                "descricao": (
                    f"Código Siconfi '{v['valor_encontrado']}' fora do padrão. "
                    "Esperado: 7 dígitos IBGE + 'EX' (ex: 2507507EX)."
                ),
                "valor_esperado": r"\d{7}EX",
                "valor_encontrado": str(v.get("valor_encontrado", "")),
                "competencia": context.competencia,
            }
            for v in violacoes
        ]

        return self.build_issues(issues)
