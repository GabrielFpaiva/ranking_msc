"""
Regra R050 — Ativo = Passivo + PL (equação patrimonial).

Dimensão: Interconta
Severidade padrão: ERRO

Lógica:
    Soma dos saldos finais líquidos da classe 1 (Ativo) deve igualar
    a soma dos saldos finais líquidos da classe 2 (Passivo + PL).

    ativo   = SUM(SF_D - SF_C)  para contas onde conta_contabil[0] == "1"
    passivo = SUM(SF_C - SF_D)  para contas onde conta_contabil[0] == "2"
    SE abs(ativo - passivo) > tolerancia → ERRO

Referência:
    Portaria STN 642/2026 — Regras Gerais MSC, R050
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
class R050(Rule):
    """Verifica que o Ativo (classe 1) = Passivo + PL (classe 2)."""

    rule_id = "R050"
    rule_name = "Ativo = Passivo + PL"
    dimensao = "Interconta"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Detecta desequilíbrio entre Ativo (classe 1) e Passivo+PL (classe 2).

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

        classe1 = work[work["conta_contabil"].str[:1] == "1"]
        classe2 = work[work["conta_contabil"].str[:1] == "2"]

        ativo = (classe1["saldo_final_debito"] - classe1["saldo_final_credito"]).sum()
        passivo = (classe2["saldo_final_credito"] - classe2["saldo_final_debito"]).sum()

        diferenca = abs(ativo - passivo)

        if diferenca <= TOLERANCIA_CENTAVO:
            return self.build_issues([])

        logger.warning(
            "R050: Ativo (%.2f) ≠ Passivo+PL (%.2f), diferença=%.2f. competência=%s",
            ativo,
            passivo,
            diferenca,
            context.competencia,
            extra=_extra,
        )

        return self.build_issues([{
            "severidade": "ERRO",
            "conta_contabil": "",
            "descricao": (
                f"Equação patrimonial desequilibrada: "
                f"Ativo={ativo:.2f}, Passivo+PL={passivo:.2f}, "
                f"diferença={diferenca:.2f}."
            ),
            "valor_esperado": f"Ativo={ativo:.2f}",
            "valor_encontrado": f"Passivo+PL={passivo:.2f}",
            "competencia": context.competencia,
        }])
