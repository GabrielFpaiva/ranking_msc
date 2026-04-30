"""
Regra R055 — Contas de resultado zeradas no mês 01.

Dimensão: Temporal
Severidade padrão: ALERTA

Lógica:
    Em janeiro (competência YYYY-01), contas de resultado (classes 3 e 4)
    devem ter saldo inicial igual a zero. Se o saldo inicial líquido
    (débito - crédito) for diferente de zero, gera ALERTA.

Referência:
    MCASP / Doc. Validações MSC — contas de resultado são encerradas
    no exercício anterior, portanto devem iniciar janeiro zeradas.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pandas as pd

from ranking_msc.rules.base import TOLERANCIA_CENTAVO, Rule, register_rule

if TYPE_CHECKING:
    from ranking_msc.engine.executor import EngineContext

logger = logging.getLogger("ranking_msc")

_CLASSES_RESULTADO: frozenset[str] = frozenset({"3", "4"})


@register_rule
class R055(Rule):
    """Verifica que contas de resultado (classes 3/4) iniciam janeiro com saldo zero."""

    rule_id = "R055"
    rule_name = "Resultado zerado em janeiro"
    dimensao = "Temporal"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Detecta contas de resultado com saldo inicial não-zero em janeiro.

        Args:
            df: DataFrame normalizado com colunas conta_contabil,
                saldo_inicial_debito e saldo_inicial_credito.
            context: metadados da execução.

        Returns:
            DataFrame de pendências — uma linha por conta com SI != 0.
        """
        _extra = {"regra_id": self.rule_id, "competencia": context.competencia}

        mes = context.competencia[5:]
        if mes != "01":
            return self.build_issues([])

        if df.empty:
            return self.build_issues([])

        work = df[df["conta_contabil"].astype(str).str[:1].isin(_CLASSES_RESULTADO)].copy()
        if work.empty:
            return self.build_issues([])

        for col in ("saldo_inicial_debito", "saldo_inicial_credito"):
            work[col] = pd.to_numeric(work[col], errors="coerce").fillna(0.0)

        agg = (
            work.groupby("conta_contabil", as_index=False)[
                ["saldo_inicial_debito", "saldo_inicial_credito"]
            ]
            .sum()
        )
        agg["_si_liq"] = (agg["saldo_inicial_debito"] - agg["saldo_inicial_credito"]).abs()

        violacoes = agg[agg["_si_liq"] > TOLERANCIA_CENTAVO]
        if violacoes.empty:
            return self.build_issues([])

        logger.warning(
            "R055: %d conta(s) de resultado com SI != 0 em janeiro. competencia=%s",
            len(violacoes),
            context.competencia,
            extra=_extra,
        )

        conta_s = violacoes["conta_contabil"].astype(str)
        si_d_s = violacoes["saldo_inicial_debito"].map(lambda x: f"{x:.2f}")
        si_c_s = violacoes["saldo_inicial_credito"].map(lambda x: f"{x:.2f}")
        si_liq_s = violacoes["_si_liq"].map(lambda x: f"{x:.2f}")

        issues_df = pd.DataFrame({
            "severidade": "ALERTA",
            "conta_contabil": conta_s.values,
            "descricao": (
                "Conta de resultado '" + conta_s
                + "' com saldo inicial não-zero em janeiro: SI_D="
                + si_d_s + ", SI_C=" + si_c_s + " (líquido=" + si_liq_s + ")."
            ).values,
            "valor_esperado": "0.00",
            "valor_encontrado": si_liq_s.values,
            "competencia": context.competencia,
        })

        return self.build_issues(issues_df.to_dict("records"))
