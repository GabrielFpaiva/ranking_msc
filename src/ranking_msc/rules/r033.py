"""
Regra R033 — Pares IC/TIPO sempre emparelhados.

Dimensão: IC
Severidade padrão: ERRO

Lógica:
    Para cada posição n (1..6) no CSV MSC, IC_n e TIPO_n devem estar
    ambos preenchidos ou ambos vazios.  IC presente sem TIPO (ou vice-versa)
    indica extração incorreta ou dados malformados.

    A verificação é feita no reader_msc antes da normalização IC → FACT_MSC
    (onde a informação posicional se perde).  Os resultados ficam em
    ``context.pre_pivot_issues`` e são drenados aqui.

Referência:
    Leiaute MSC Siconfi — cada IC deve ser acompanhada de seu tipo descritivo.
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
class R033(Rule):
    """Verifica que cada IC_n está emparelhada com TIPO_n e vice-versa."""

    rule_id = "R033"
    rule_name = "Pares IC/TIPO presentes"
    dimensao = "IC"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Drena issues R033 acumulados pelo reader_msc.

        Args:
            df: DataFrame normalizado (não utilizado diretamente).
            context: metadados da execução, incluindo ``pre_pivot_issues``.

        Returns:
            DataFrame de pendências — uma linha por par IC/TIPO desemparelhado.
        """
        _extra = {"regra_id": self.rule_id, "competencia": context.competencia}

        violacoes = [
            issue for issue in context.pre_pivot_issues
            if issue.get("regra") == "R033"
        ]

        if not violacoes:
            return self.build_issues([])

        logger.warning(
            "R033: %d par(es) IC/TIPO desemparelhado(s). competencia=%s",
            len(violacoes),
            context.competencia,
            extra=_extra,
        )

        issues: list[dict[str, object]] = []
        for v in violacoes:
            conta = str(v.get("conta_contabil", ""))
            descricao = str(v.get("valor_encontrado", ""))
            issues.append({
                "severidade": "ERRO",
                "conta_contabil": conta,
                "descricao": (
                    f"Conta '{conta}': par IC/TIPO desemparelhado — {descricao}."
                ),
                "valor_esperado": "IC e TIPO ambos preenchidos ou ambos vazios",
                "valor_encontrado": descricao,
                "competencia": context.competencia,
            })

        return self.build_issues(issues)
