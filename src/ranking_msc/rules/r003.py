"""Regra R003 — Tipo_valor válido.

Categoria: Estrutura
Severidade padrão: ERRO
Lógica:
    O campo Tipo_valor deve ser um dos 3 valores padronizados:
    beginning_balance, ending_balance ou period_change.
    Violações são capturadas antes do pivot em reader_msc e
    disponibilizadas em EngineContext.pre_pivot_issues.
Referência:
    Leiaute MSC 2026 — Observações item 4; Portaria STN 642/2026
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pandas as pd

from ranking_msc.rules.base import Rule, register_rule

if TYPE_CHECKING:
    from ranking_msc.engine.executor import EngineContext

logger = logging.getLogger("ranking_msc")

_TIPO_VALOR_DOMAIN: frozenset[str] = frozenset(
    {"beginning_balance", "ending_balance", "period_change"}
)


@register_rule
class R003(Rule):
    """Valida que Tipo_valor pertence ao domínio fixo de 3 valores."""

    rule_id = "R003"
    rule_name = "Tipo_valor válido"
    dimensao = "Estrutura"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Retorna pendências de Tipo_valor inválido capturadas pelo reader.

        Args:
            df: DataFrame normalizado (não utilizado diretamente — as
                violações pré-pivot são lidas de ``context``).
            context: metadados da execução, incluindo ``pre_pivot_issues``.

        Returns:
            DataFrame de pendências — uma linha por linha do CSV original
            com Tipo_valor fora do domínio.
        """
        _extra = {"regra_id": self.rule_id, "competencia": context.competencia}

        violacoes = [
            issue for issue in context.pre_pivot_issues
            if issue.get("regra") == "R003"
        ]

        if not violacoes:
            return self.build_issues([])

        logger.warning(
            "R003: %d linha(s) com Tipo_valor inválido. competência=%s",
            len(violacoes),
            context.competencia,
            extra=_extra,
        )

        issues: list[dict[str, object]] = [
            {
                "severidade": "ERRO",
                "conta_contabil": str(v.get("conta_contabil", "")),
                "descricao": (
                    f"Tipo_valor '{v['valor_encontrado']}' fora do domínio. "
                    f"Valores válidos: {sorted(_TIPO_VALOR_DOMAIN)}."
                ),
                "valor_esperado": "beginning_balance | ending_balance | period_change",
                "valor_encontrado": str(v.get("valor_encontrado", "")),
                "competencia": context.competencia,
            }
            for v in violacoes
        ]

        return self.build_issues(issues)
