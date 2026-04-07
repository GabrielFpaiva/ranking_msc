"""
Regra R052 — Controles devedores = Controles credores (7/8).

Dimensão: Interconta
Severidade padrão: ALERTA

Lógica:
    Saldos finais líquidos da classe 7 (Controles Devedores) devem
    igualar saldos finais líquidos da classe 8 (Controles Credores).

    ctrl_d = SUM(SF_D - SF_C)  para contas onde conta_contabil[0] == "7"
    ctrl_c = SUM(SF_C - SF_D)  para contas onde conta_contabil[0] == "8"
    SE abs(ctrl_d - ctrl_c) > tolerancia → ALERTA

Referência:
    Portaria STN 642/2026 — Regras Gerais MSC, R052
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pandas as pd

from ranking_msc.rules.base import TOLERANCIA_CENTAVO, Rule, register_rule

if TYPE_CHECKING:
    from ranking_msc.engine.executor import EngineContext

logger = logging.getLogger("ranking_msc")


@register_rule
class R052(Rule):
    """Verifica que os saldos finais da classe 7 igualam os da classe 8."""

    rule_id = "R052"
    rule_name = "Controles devedores = Controles credores"
    dimensao = "Interconta"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Detecta desequilíbrio entre controles devedores (7) e credores (8).

        Args:
            df: DataFrame normalizado com colunas conta_contabil,
                saldo_final_debito e saldo_final_credito.
            context: metadados da execução.

        Returns:
            DataFrame de pendências — vazio se equilíbrio, uma linha se desequilíbrio.
        """
        _extra = {"regra_id": self.rule_id, "competencia": context.competencia}

        if df.empty:
            return self.build_issues([])

        work = df.copy()
        for col in ("saldo_final_debito", "saldo_final_credito"):
            work[col] = pd.to_numeric(work[col], errors="coerce").fillna(0.0)

        classe7 = work[work["conta_contabil"].str[:1] == "7"]
        classe8 = work[work["conta_contabil"].str[:1] == "8"]

        if classe7.empty and classe8.empty:
            return self.build_issues([])

        ctrl_d = (classe7["saldo_final_debito"] - classe7["saldo_final_credito"]).sum()
        ctrl_c = (classe8["saldo_final_credito"] - classe8["saldo_final_debito"]).sum()

        diferenca = abs(ctrl_d - ctrl_c)

        if diferenca <= TOLERANCIA_CENTAVO:
            return self.build_issues([])

        logger.warning(
            "R052: Controles 7 (%.2f) ≠ Controles 8 (%.2f), diferença=%.2f. competência=%s",
            ctrl_d,
            ctrl_c,
            diferenca,
            context.competencia,
            extra=_extra,
        )

        return self.build_issues([{
            "severidade": "ALERTA",
            "conta_contabil": "",
            "descricao": (
                f"Desequilíbrio entre controles: "
                f"Classe 7={ctrl_d:.2f}, Classe 8={ctrl_c:.2f}, "
                f"diferença={diferenca:.2f}."
            ),
            "valor_esperado": f"Classe 7={ctrl_d:.2f}",
            "valor_encontrado": f"Classe 8={ctrl_c:.2f}",
            "competencia": context.competencia,
        }])
