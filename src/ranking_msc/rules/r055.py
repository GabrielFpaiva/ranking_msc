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

        issues: list[dict[str, object]] = [
            {
                "severidade": "ALERTA",
                "conta_contabil": str(row["conta_contabil"]),
                "descricao": (
                    f"Conta de resultado '{row['conta_contabil']}' com saldo inicial "
                    f"não-zero em janeiro: SI_D={row['saldo_inicial_debito']:.2f}, "
                    f"SI_C={row['saldo_inicial_credito']:.2f} "
                    f"(líquido={row['_si_liq']:.2f})."
                ),
                "valor_esperado": "0.00",
                "valor_encontrado": f"{row['_si_liq']:.2f}",
                "competencia": context.competencia,
            }
            for _, row in violacoes.iterrows()
        ]

        return self.build_issues(issues)
