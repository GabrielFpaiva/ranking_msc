"""Regra R042 — Contas de resultado sem saldo (apenas movimentos).

Dimensão: Completude
Severidade padrão: ALERTA

Lógica:
    Para cada conta de resultado (primeiro dígito em {3, 4}),
    agrega abs das colunas de saldo (SI_D, SI_C, SF_D, SF_C) por conta.
    Se qualquer conta apresentar saldo inicial ou final diferente de zero,
    a conta possui saldo além dos movimentos → ALERTA.

    Contas de resultado (variação patrimonial) devem acumular apenas
    movimentos do exercício; saldos persistentes indicam erro de encerramento.

Referência:
    Catálogo de Regras MSC — R042 (Completude)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pandas as pd

from ranking_msc.rules.base import Rule, register_rule

if TYPE_CHECKING:
    from ranking_msc.engine.executor import EngineContext

logger = logging.getLogger("ranking_msc")

_CLASSES_RESULTADO: frozenset[str] = frozenset({"3", "4"})

_COLS_SALDO = [
    "saldo_inicial_debito",
    "saldo_inicial_credito",
    "saldo_final_debito",
    "saldo_final_credito",
]


@register_rule
class R042(Rule):
    """Verifica que contas de resultado não possuem saldo (apenas movimentos)."""

    rule_id = "R042"
    rule_name = "Contas de resultado sem saldo (apenas movimentos)"
    dimensao = "Completude"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Detecta contas de resultado com saldo inicial ou final não zerado.

        Agrega por conta_contabil antes de validar: uma conta pode estar
        representada em múltiplas linhas (ICs diferentes). Reporta ALERTA
        se a soma de abs de qualquer coluna de saldo for maior que zero.

        Args:
            df: DataFrame normalizado com colunas ``conta_contabil``,
                ``saldo_inicial_debito``, ``saldo_inicial_credito``,
                ``saldo_final_debito`` e ``saldo_final_credito``.
            context: metadados da execução.

        Returns:
            DataFrame de pendências — uma linha por conta de resultado
            com saldo inicial ou final diferente de zero.
        """
        _extra = {"regra_id": self.rule_id, "competencia": context.competencia}

        df_res = df[
            df["conta_contabil"].astype(str).str[:1].isin(_CLASSES_RESULTADO)
        ][["conta_contabil"] + _COLS_SALDO].copy()

        if df_res.empty:
            return self.build_issues([])

        for col in _COLS_SALDO:
            df_res[col] = pd.to_numeric(df_res[col], errors="coerce").fillna(0.0)

        totais = (
            df_res
            .groupby("conta_contabil", as_index=False)
            .agg(
                si_d=("saldo_inicial_debito", "sum"),
                si_c=("saldo_inicial_credito", "sum"),
                sf_d=("saldo_final_debito", "sum"),
                sf_c=("saldo_final_credito", "sum"),
            )
        )

        totais["_soma_saldos"] = (
            totais["si_d"].abs()
            + totais["si_c"].abs()
            + totais["sf_d"].abs()
            + totais["sf_c"].abs()
        )
        violacoes = totais[totais["_soma_saldos"] > 0.0]

        if violacoes.empty:
            return self.build_issues([])

        logger.warning(
            "R042: %d conta(s) de resultado com saldo. competência=%s",
            len(violacoes),
            context.competencia,
            extra=_extra,
        )

        issues: list[dict[str, object]] = [
            {
                "severidade": "ALERTA",
                "conta_contabil": str(row["conta_contabil"]),
                "descricao": (
                    f"Conta de resultado '{row['conta_contabil']}' possui saldo "
                    f"(SI_D={row['si_d']:.2f}, SI_C={row['si_c']:.2f}, "
                    f"SF_D={row['sf_d']:.2f}, SF_C={row['sf_c']:.2f}). "
                    f"Contas de resultado devem ter apenas movimentos."
                ),
                "valor_esperado": "saldo_inicial = 0 e saldo_final = 0",
                "valor_encontrado": f"soma_abs_saldos={row['_soma_saldos']:.2f}",
                "competencia": context.competencia,
            }
            for _, row in violacoes.iterrows()
        ]

        return self.build_issues(issues)
