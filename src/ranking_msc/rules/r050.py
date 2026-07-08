"""
Regra R050 — Ativo = Passivo + PL (equação patrimonial).

Dimensão: Interconta
Severidade padrão: ERRO

Lógica:
    Equação patrimonial estendida (válida durante o exercício, antes do
    encerramento anual). O resultado do período (VPA − VPD) ainda não foi
    incorporado ao PL — fica acumulado nas classes 3 e 4 — portanto o balanço
    só fecha incluindo o resultado:

        Ativo (1) + VPD (3)  =  Passivo + PL (2) + VPA (4)

    lado_devedor = SUM(SF_D - SF_C)  para classes {1, 3}  (Ativo + VPD)
    lado_credor  = SUM(SF_C - SF_D)  para classes {2, 4}  (Passivo+PL + VPA)
    SE abs(lado_devedor - lado_credor) > tolerancia → ERRO

    No encerramento (VPD = VPA = 0), a equação reduz-se a Ativo = Passivo + PL.

Referência:
    Portaria STN 642/2026 — Regras Gerais MSC, R050; MCASP — equação
    patrimonial e apuração do resultado (classes 3 e 4).
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

        primeiro_digito = work["conta_contabil"].str[:1]
        devedor = work[primeiro_digito.isin(("1", "3"))]   # Ativo + VPD
        credor = work[primeiro_digito.isin(("2", "4"))]     # Passivo+PL + VPA

        lado_devedor = (
            devedor["saldo_final_debito"] - devedor["saldo_final_credito"]
        ).sum()
        lado_credor = (
            credor["saldo_final_credito"] - credor["saldo_final_debito"]
        ).sum()

        diferenca = abs(lado_devedor - lado_credor)

        if diferenca <= TOLERANCIA_CENTAVO:
            return self.build_issues([])

        logger.warning(
            "R050: patrimônio não fecha — Ativo+VPD (%.2f) ≠ Passivo+PL+VPA (%.2f), "
            "diferença=%.2f. competência=%s",
            lado_devedor,
            lado_credor,
            diferenca,
            context.competencia,
            extra=_extra,
        )

        return self.build_issues([{
            "severidade": "ERRO",
            "conta_contabil": "",
            "descricao": (
                f"Equação patrimonial desequilibrada: "
                f"Ativo+VPD={lado_devedor:.2f}, Passivo+PL+VPA={lado_credor:.2f}, "
                f"diferença={diferenca:.2f}."
            ),
            "valor_esperado": f"Ativo+VPD={lado_devedor:.2f}",
            "valor_encontrado": f"Passivo+PL+VPA={lado_credor:.2f}",
            "competencia": context.competencia,
        }])
