"""Regra R002 — Linhas sem CONTA vazia.

Categoria: Estrutura
Severidade padrão: ERRO

Lógica:
    Toda linha de dados deve ter o campo CONTA preenchido.
    Após normalização, o campo correspondente é ``conta_contabil``.
    Verifica diretamente no DataFrame normalizado (não usa pre_pivot_issues).

Referência:
    Leiaute MSC 2026 — campo CONTA obrigatório; Portaria STN 642/2026
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
class R002(Rule):
    """Valida que nenhuma linha possui CONTA vazia ou nula."""

    rule_id = "R002"
    rule_name = "CONTA preenchida em todas as linhas"
    dimensao = "Estrutura"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Detecta linhas com conta_contabil vazia no DataFrame normalizado.

        Args:
            df: DataFrame normalizado com coluna ``conta_contabil``.
            context: metadados da execução.

        Returns:
            DataFrame de pendências — uma linha por registro com CONTA vazia.
        """
        if "conta_contabil" not in df.columns:
            return self.build_issues([])

        _extra = {"regra_id": self.rule_id, "competencia": context.competencia}

        linhas_vazias = df[df["conta_contabil"].eq("") | df["conta_contabil"].isna()]

        if linhas_vazias.empty:
            return self.build_issues([])

        logger.warning(
            "R002: %d linha(s) com CONTA vazia. competência=%s",
            len(linhas_vazias),
            context.competencia,
            extra=_extra,
        )

        issues: list[dict[str, object]] = [
            {
                "severidade": "ERRO",
                "conta_contabil": "",
                "descricao": "Linha com campo CONTA vazio ou nulo. O campo CONTA é obrigatório.",
                "valor_esperado": "código de conta PCASP (9 dígitos numéricos)",
                "valor_encontrado": str(row["conta_contabil"]),
                "competencia": context.competencia,
            }
            for _, row in linhas_vazias.iterrows()
        ]

        return self.build_issues(issues)
