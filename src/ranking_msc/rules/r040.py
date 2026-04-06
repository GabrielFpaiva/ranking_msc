"""Regra R040 — Contas patrimoniais têm saldo inicial.

Dimensão: Completude
Severidade padrão: ALERTA

Lógica:
    Para cada conta patrimonial (primeiro dígito em {1, 2, 5, 6}),
    agrega abs(saldo_inicial_debito) + abs(saldo_inicial_credito) por conta.
    Se a soma for zero → a conta não possui saldo inicial → ALERTA.

Referência:
    Catálogo de Regras MSC — R040 (Completude)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pandas as pd

from ranking_msc.rules.base import Rule, register_rule

if TYPE_CHECKING:
    from ranking_msc.engine.executor import EngineContext

logger = logging.getLogger("ranking_msc")

_CLASSES_PATRIMONIAIS: frozenset[str] = frozenset({"1", "2", "5", "6"})


@register_rule
class R040(Rule):
    """Verifica que contas patrimoniais possuem saldo inicial informado."""

    rule_id = "R040"
    rule_name = "Contas patrimoniais têm saldo inicial"
    dimensao = "Completude"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Detecta contas patrimoniais com saldo inicial zerado.

        Agrega por conta_contabil antes de validar: uma conta pode estar
        representada em múltiplas linhas (ICs diferentes). Só reporta ALERTA
        se a soma de abs(SI_D) + abs(SI_C) for zero para o total da conta.

        Args:
            df: DataFrame normalizado com colunas ``conta_contabil``,
                ``saldo_inicial_debito`` e ``saldo_inicial_credito``.
            context: metadados da execução.

        Returns:
            DataFrame de pendências — uma linha por conta patrimonial
            com saldo inicial totalmente zerado.
        """
        _extra = {"regra_id": self.rule_id, "competencia": context.competencia}

        cols_si = ["saldo_inicial_debito", "saldo_inicial_credito"]

        df_pat = df[
            df["conta_contabil"].astype(str).str[:1].isin(_CLASSES_PATRIMONIAIS)
        ][["conta_contabil"] + cols_si].copy()

        if df_pat.empty:
            return self.build_issues([])

        for col in cols_si:
            df_pat[col] = pd.to_numeric(df_pat[col], errors="coerce").fillna(0.0)

        totais = (
            df_pat
            .groupby("conta_contabil", as_index=False)
            .agg(
                si_d=("saldo_inicial_debito", "sum"),
                si_c=("saldo_inicial_credito", "sum"),
            )
        )

        totais["_soma_abs"] = totais["si_d"].abs() + totais["si_c"].abs()
        violacoes = totais[totais["_soma_abs"] == 0.0]

        if violacoes.empty:
            return self.build_issues([])

        logger.warning(
            "R040: %d conta(s) patrimonial(is) sem saldo inicial. competência=%s",
            len(violacoes),
            context.competencia,
            extra=_extra,
        )

        issues: list[dict[str, object]] = [
            {
                "severidade": "ALERTA",
                "conta_contabil": str(row["conta_contabil"]),
                "descricao": (
                    f"Conta patrimonial '{row['conta_contabil']}' não possui "
                    f"saldo inicial (SI_D=0 e SI_C=0)."
                ),
                "valor_esperado": "saldo_inicial ≠ 0",
                "valor_encontrado": "0",
                "competencia": context.competencia,
            }
            for _, row in violacoes.iterrows()
        ]

        return self.build_issues(issues)
