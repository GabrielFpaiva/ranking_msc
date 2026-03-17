"""Regra R004 — Natureza_valor válida.

Categoria: Estrutura
Severidade padrão: ERRO
Lógica:
    O campo Natureza_valor deve ser D (devedor) ou C (credor).
    Violações são capturadas antes do pivot em reader_msc e
    disponibilizadas em EngineContext.pre_pivot_issues.
Referência:
    Leiaute MSC 2026 — Observações item 5; Portaria STN 642/2026
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pandas as pd

from ranking_msc.rules.base import Rule, register_rule

if TYPE_CHECKING:
    from ranking_msc.engine.executor import EngineContext

logger = logging.getLogger("ranking_msc")

_NATUREZA_VALOR_DOMAIN: frozenset[str] = frozenset({"D", "C"})


@register_rule
class R004(Rule):
    """Valida que Natureza_valor pertence ao domínio fixo D ou C."""

    rule_id = "R004"
    rule_name = "Natureza_valor válida"
    dimensao = "Estrutura"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Retorna pendências de Natureza_valor inválida capturadas pelo reader.

        Args:
            df: DataFrame normalizado (não utilizado diretamente — as
                violações pré-pivot são lidas de ``context``).
            context: metadados da execução, incluindo ``pre_pivot_issues``.

        Returns:
            DataFrame de pendências — uma linha por linha do CSV original
            com Natureza_valor diferente de D ou C.
        """
        violacoes = [
            issue for issue in context.pre_pivot_issues
            if issue.get("regra") == "R004"
        ]

        if not violacoes:
            return self.build_issues([])

        logger.warning(
            "R004: %d linha(s) com Natureza_valor inválida. competencia=%s",
            len(violacoes),
            context.competencia,
        )

        issues: list[dict[str, object]] = [
            {
                "severidade": "ERRO",
                "conta_contabil": str(v.get("conta_contabil", "")),
                "descricao": (
                    f"Natureza_valor '{v['valor_encontrado']}' fora do domínio. "
                    f"Valores válidos: {sorted(_NATUREZA_VALOR_DOMAIN)}."
                ),
                "valor_esperado": "D | C",
                "valor_encontrado": str(v.get("valor_encontrado", "")),
                "competencia": context.competencia,
            }
            for v in violacoes
        ]

        return self.build_issues(issues)
