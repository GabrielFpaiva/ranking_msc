"""Regra R007 — Período YYYY-MM válido e plausível.

Categoria: Estrutura
Severidade padrão: ERRO

Lógica:
    O mês deve estar entre 01-13 (13=encerramento anual) e o ano deve
    ser plausível (2020 ao ano corrente + 1). Violações são capturadas
    pelo reader_msc antes do parsing do DataFrame.
Referência:
    Doc. Validações MSC Siconfi — item (b)
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
class R007(Rule):
    """Valida que o período YYYY-MM é válido (mês 01-13) e plausível."""

    rule_id = "R007"
    rule_name = "Período YYYY-MM válido"
    dimensao = "Estrutura"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Retorna pendências de período inválido capturadas pelo reader.

        Args:
            df: DataFrame normalizado (não utilizado — violações estão no context).
            context: metadados da execução, incluindo ``pre_pivot_issues``.

        Returns:
            DataFrame de pendências — uma linha por violação encontrada.
        """
        _extra = {"regra_id": self.rule_id, "competencia": context.competencia}

        violacoes = [
            issue for issue in context.pre_pivot_issues
            if issue.get("regra") == "R007"
        ]

        if not violacoes:
            return self.build_issues([])

        logger.warning(
            "R007: período inválido '%s'. competência=%s",
            violacoes[0].get("valor_encontrado", ""),
            context.competencia,
            extra=_extra,
        )

        issues: list[dict[str, object]] = [
            {
                "severidade": "ERRO",
                "conta_contabil": "",
                "descricao": (
                    f"Período '{v['valor_encontrado']}' inválido. "
                    "Mês deve ser 01-13 (13=encerramento); "
                    "ano deve ser de 2020 ao ano corrente + 1."
                ),
                "valor_esperado": "YYYY-MM (mês 01-13, ano 2020+)",
                "valor_encontrado": str(v.get("valor_encontrado", "")),
                "competencia": context.competencia,
            }
            for v in violacoes
        ]

        return self.build_issues(issues)
