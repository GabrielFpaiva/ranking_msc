"""Regra R005 — Valor numérico válido.

Categoria: Estrutura
Severidade padrão: ERRO

Lógica:
    O campo Valor deve ser numérico, usando ponto como separador decimal
    (escala R$ 1,00). Vírgulas como separador de milhares não são aceitas
    pelo Siconfi. Violações são capturadas antes do pivot em reader_msc e
    disponibilizadas em EngineContext.pre_pivot_issues com regra="R005".

Referência:
    Leiaute MSC 2026 — Observações item 3; Portaria STN 642/2026
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
class R005(Rule):
    """Valida que a coluna Valor contém apenas valores numéricos válidos."""

    rule_id = "R005"
    rule_name = "Valor numérico válido"
    dimensao = "Estrutura"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Retorna pendências de Valor não-numérico capturadas pelo reader.

        Args:
            df: DataFrame normalizado (não utilizado diretamente — as
                violações são lidas de ``context.pre_pivot_issues``).
            context: metadados da execução.

        Returns:
            DataFrame de pendências — uma linha por registro com Valor inválido.
        """
        _extra = {"regra_id": self.rule_id, "competencia": context.competencia}

        violacoes = [
            issue for issue in context.pre_pivot_issues
            if issue.get("regra") == "R005"
        ]

        if not violacoes:
            return self.build_issues([])

        logger.warning(
            "R005: %d linha(s) com Valor não-numérico. competência=%s",
            len(violacoes),
            context.competencia,
            extra=_extra,
        )

        issues: list[dict[str, object]] = [
            {
                "severidade": "ERRO",
                "conta_contabil": str(v.get("conta_contabil", "")),
                "descricao": (
                    f"Campo Valor '{v['valor_encontrado']}' não é numérico. "
                    "Use ponto como separador decimal (ex: 1234.56). "
                    "Separadores de milhares não são aceitos."
                ),
                "valor_esperado": "número decimal com ponto (ex: 1234.56)",
                "valor_encontrado": str(v.get("valor_encontrado", "")),
                "competencia": context.competencia,
            }
            for v in violacoes
        ]

        return self.build_issues(issues)
