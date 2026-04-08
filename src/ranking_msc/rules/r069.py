"""
Regra R069 — MSC encerramento (mês 13) com resultado zerado.

Dimensão: Temporal
Severidade padrão: ALERTA

Lógica:
    Na MSC-13 (competência YYYY-13, encerramento do exercício), contas de
    resultado (classes 3 e 4) devem ter saldo final igual a zero, indicando
    que o encerramento foi realizado corretamente.

Referência:
    MCASP / Nota Técnica de Encerramento — o resultado do exercício deve
    ser transferido ao patrimônio líquido, zerando classes 3 e 4.
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
class R069(Rule):
    """Verifica que contas de resultado (classes 3/4) estao zeradas na MSC-13."""

    rule_id = "R069"
    rule_name = "Resultado zerado no encerramento"
    dimensao = "Temporal"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Detecta contas de resultado com saldo final não-zero na MSC-13.

        Args:
            df: DataFrame normalizado com colunas conta_contabil,
                saldo_final_debito e saldo_final_credito.
            context: metadados da execução.

        Returns:
            DataFrame de pendências — uma linha por conta com SF != 0.
        """
        _extra = {"regra_id": self.rule_id, "competencia": context.competencia}

        mes = context.competencia[5:]
        if mes != "13":
            return self.build_issues([])

        if df.empty:
            return self.build_issues([])

        work = df[df["conta_contabil"].astype(str).str[:1].isin(_CLASSES_RESULTADO)].copy()
        if work.empty:
            return self.build_issues([])

        for col in ("saldo_final_debito", "saldo_final_credito"):
            work[col] = pd.to_numeric(work[col], errors="coerce").fillna(0.0)

        agg = (
            work.groupby("conta_contabil", as_index=False)[
                ["saldo_final_debito", "saldo_final_credito"]
            ]
            .sum()
        )
        agg["_sf_liq"] = (agg["saldo_final_debito"] - agg["saldo_final_credito"]).abs()

        violacoes = agg[agg["_sf_liq"] > TOLERANCIA_CENTAVO]
        if violacoes.empty:
            return self.build_issues([])

        logger.warning(
            "R069: %d conta(s) de resultado com SF != 0 no encerramento. competencia=%s",
            len(violacoes),
            context.competencia,
            extra=_extra,
        )

        issues: list[dict[str, object]] = [
            {
                "severidade": "ALERTA",
                "conta_contabil": str(row["conta_contabil"]),
                "descricao": (
                    f"Conta de resultado '{row['conta_contabil']}' com saldo final "
                    f"não-zero no encerramento: SF_D={row['saldo_final_debito']:.2f}, "
                    f"SF_C={row['saldo_final_credito']:.2f} "
                    f"(líquido={row['_sf_liq']:.2f})."
                ),
                "valor_esperado": "0.00",
                "valor_encontrado": f"{row['_sf_liq']:.2f}",
                "competencia": context.competencia,
            }
            for _, row in violacoes.iterrows()
        ]

        return self.build_issues(issues)
