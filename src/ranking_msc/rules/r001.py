"""Regra R001 — Colunas obrigatórias presentes.

Categoria: Estrutura
Severidade padrão: ERRO

Lógica:
    Verifica se o CSV MSC contém todas as colunas obrigatórias do leiaute:
    CONTA, IC1-IC6, TIPO1-TIPO6, Valor, Tipo_valor, Natureza_valor.
    Violações são capturadas pelo reader (antes do pivot) e disponibilizadas
    em EngineContext.pre_pivot_issues com regra="R001".

Referência:
    Leiaute MSC 2026 — Portaria STN 642/2026, Anexo II (cabeçalho)
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
class R001(Rule):
    """Valida que todas as colunas obrigatórias do leiaute MSC estão presentes."""

    rule_id = "R001"
    rule_name = "Colunas obrigatórias presentes"
    dimensao = "Estrutura"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Retorna pendências de colunas ausentes capturadas pelo reader.

        Args:
            df: DataFrame normalizado (não utilizado diretamente — as
                violações são lidas de ``context.pre_pivot_issues``).
            context: metadados da execução.

        Returns:
            DataFrame de pendências — uma linha por coluna ausente no CSV.
        """
        _extra = {"regra_id": self.rule_id, "competencia": context.competencia}

        violacoes = [
            issue for issue in context.pre_pivot_issues
            if issue.get("regra") == "R001"
        ]

        if not violacoes:
            return self.build_issues([])

        logger.warning(
            "R001: %d coluna(s) obrigatória(s) ausente(s). competência=%s",
            len(violacoes),
            context.competencia,
            extra=_extra,
        )

        issues: list[dict[str, object]] = [
            {
                "severidade": "ERRO",
                "conta_contabil": "",
                "descricao": (
                    f"Coluna obrigatória '{v['campo']}' ausente no CSV MSC. "
                    "Verifique se o arquivo segue o leiaute da Portaria STN 642/2026."
                ),
                "valor_esperado": f"coluna '{v['campo']}' presente no cabeçalho",
                "valor_encontrado": str(v.get("valor_encontrado", "ausente")),
                "competencia": context.competencia,
            }
            for v in violacoes
        ]

        return self.build_issues(issues)
