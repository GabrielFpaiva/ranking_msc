"""Regra R008 — Separador ponto-e-vírgula no CSV.

Categoria: Estrutura
Severidade padrão: ERRO

Lógica:
    Campos do CSV devem ser separados por ponto-e-vírgula (;), conforme
    padrão oficial do Siconfi. O reader_msc detecta uso de vírgula como
    separador na linha de cabeçalho e registra violação pré-pivot.
Referência:
    Doc. Validações MSC Siconfi — item (e)
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
class R008(Rule):
    """Valida que o separador de colunas do CSV é ponto-e-vírgula."""

    rule_id = "R008"
    rule_name = "Separador ponto-e-vírgula"
    dimensao = "Estrutura"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Retorna pendências de separador incorreto capturadas pelo reader.

        Args:
            df: DataFrame normalizado (não utilizado — violações estão no context).
            context: metadados da execução, incluindo ``pre_pivot_issues``.

        Returns:
            DataFrame de pendências — uma linha por violação encontrada.
        """
        _extra = {"regra_id": self.rule_id, "competencia": context.competencia}

        violacoes = [
            issue for issue in context.pre_pivot_issues
            if issue.get("regra") == "R008"
        ]

        if not violacoes:
            return self.build_issues([])

        logger.warning(
            "R008: separador CSV incorreto '%s'. competência=%s",
            violacoes[0].get("valor_encontrado", ""),
            context.competencia,
            extra=_extra,
        )

        issues: list[dict[str, object]] = [
            {
                "severidade": "ERRO",
                "conta_contabil": "",
                "descricao": (
                    f"Separador de colunas '{v['valor_encontrado']}' incorreto. "
                    "O Siconfi exige ponto-e-vírgula (;) como delimitador."
                ),
                "valor_esperado": ";",
                "valor_encontrado": str(v.get("valor_encontrado", "")),
                "competencia": context.competencia,
            }
            for v in violacoes
        ]

        return self.build_issues(issues)
