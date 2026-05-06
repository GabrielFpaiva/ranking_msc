"""
Regra R071 — Valores com mais de 2 casas decimais.

Dimensão: Qualidade
Severidade padrão: INFO

Lógica:
    Valores monetários devem estar na escala de R$ (2 casas decimais).
    Mais de 2 decimais pode indicar erro de conversão de unidade.

    A verificação é feita pré-pivot pelo reader_msc._pivot_values,
    sobre o campo Valor bruto do CSV, antes de pivot_table(aggfunc="sum")
    colapsar duplicatas.  Isso evita falsos negativos onde dois valores
    como 0.005 + 0.005 somam 0.01, que passaria na verificação pós-pivot.

    Os resultados são acumulados em context.pre_pivot_issues com
    "regra": "R071" e drenados aqui.

Referência:
    ref/regras_catalogo.md — R071; Portaria STN 642/2026
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, ClassVar

import pandas as pd

from ranking_msc.rules.base import Rule, register_rule

if TYPE_CHECKING:
    from ranking_msc.engine.executor import EngineContext

logger = logging.getLogger("ranking_msc")


@register_rule
class R071(Rule):
    """Detecta valores com mais de 2 casas decimais na MSC (via drenagem pré-pivot)."""

    rule_id = "R071"
    rule_name = "Valores com > 2 decimais"
    dimensao = "Qualidade"
    is_scoring: ClassVar[bool] = False

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Drena issues R071 acumulados pelo reader_msc pré-pivot.

        A inspeção de escala decimal ocorre no reader antes de pivot_table
        agregar duplicatas por soma, garantindo que valores como 0.005 + 0.005
        (soma = 0.01, aparentemente válido) sejam capturados.

        Args:
            df: DataFrame normalizado (não utilizado diretamente).
            context: metadados da execução, incluindo ``pre_pivot_issues``.

        Returns:
            DataFrame de pendências — uma linha por valor com >2 decimais.
        """
        _extra = {"regra_id": self.rule_id, "competencia": context.competencia}

        violacoes = [
            issue for issue in context.pre_pivot_issues
            if issue.get("regra") == "R071"
        ]

        if not violacoes:
            return self.build_issues([])

        logger.info(
            "R071: %d valor(es) com mais de 2 casas decimais. competencia=%s",
            len(violacoes),
            context.competencia,
            extra=_extra,
        )

        issues: list[dict[str, object]] = []
        for v in violacoes:
            conta = str(v.get("conta_contabil", ""))
            val_str = str(v.get("valor_encontrado", ""))
            val_esperado = str(v.get("valor_esperado", ""))
            issues.append({
                "severidade": "INFO",
                "conta_contabil": conta,
                "descricao": (
                    f"Campo 'Valor' com mais de 2 casas decimais: {val_str}."
                ),
                "valor_esperado": val_esperado,
                "valor_encontrado": val_str,
                "competencia": context.competencia,
            })

        return self.build_issues(issues)
