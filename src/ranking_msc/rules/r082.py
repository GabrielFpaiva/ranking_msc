"""
Regra R082 — Ordem das ICs conforme padrão do leiaute.

Dimensão: IC
Severidade padrão: ALERTA

Lógica:
    O leiaute MSC define uma ordem canônica para os tipos de IC:
    PO sempre na primeira posição, seguido de FP/FS, depois FR/DC, etc.
    A sequência de tipos não-vazios (TIPO1..TIPO6) deve ser uma das
    combinações válidas do IC_MAP.

    A verificação é feita no reader_msc antes da normalização (onde a
    informação posicional se perde).  Os resultados ficam em
    ``context.pre_pivot_issues`` e são drenados aqui.

    Depende de R033: a verificação de ordem só é significativa quando
    os pares IC/TIPO estão corretamente emparelhados.

Referência:
    Leiaute MSC Siconfi — ordem de ICs; Portaria STN 642/2026.
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
class R082(Rule):
    """Verifica que a sequência de tipos de IC segue a ordem canônica do leiaute."""

    rule_id = "R082"
    rule_name = "Ordem das ICs conforme leiaute"
    dimensao = "IC"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Drena issues R082 acumulados pelo reader_msc.

        Args:
            df: DataFrame normalizado (não utilizado diretamente).
            context: metadados da execução, incluindo ``pre_pivot_issues``.

        Returns:
            DataFrame de pendências — uma linha por conta com IC fora de ordem.
        """
        _extra = {"regra_id": self.rule_id, "competencia": context.competencia}

        violacoes = [
            issue for issue in context.pre_pivot_issues
            if issue.get("regra") == "R082"
        ]

        if not violacoes:
            return self.build_issues([])

        logger.warning(
            "R082: %d conta(s) com ICs fora da ordem canônica. competencia=%s",
            len(violacoes),
            context.competencia,
            extra=_extra,
        )

        issues: list[dict[str, object]] = []
        for v in violacoes:
            conta = str(v.get("conta_contabil", ""))
            seq_encontrada = str(v.get("valor_encontrado", ""))
            issues.append({
                "severidade": "ALERTA",
                "conta_contabil": conta,
                "descricao": (
                    f"Conta '{conta}': sequência de tipos IC fora da ordem canônica "
                    f"do leiaute MSC. Sequência encontrada: {seq_encontrada}."
                ),
                "valor_esperado": "sequência canônica (ex: PO,FP,FR,CO)",
                "valor_encontrado": seq_encontrada,
                "competencia": context.competencia,
            })

        return self.build_issues(issues)
