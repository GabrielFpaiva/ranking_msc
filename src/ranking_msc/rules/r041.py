"""Regra R041 — Contas patrimoniais têm saldo final.

Dimensão: Completude
Severidade padrão: ALERTA

Lógica:
    Para cada conta patrimonial (primeiro dígito em {1, 2, 5, 6}),
    agrega abs(saldo_final_debito) + abs(saldo_final_credito) por conta.
    Se a soma for zero → a conta não possui saldo final → ALERTA.

Referência:
    Catálogo de Regras MSC — R041 (Completude)
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
class R041(Rule):
    """Verifica que contas patrimoniais possuem saldo final informado."""

    rule_id = "R041"
    rule_name = "Contas patrimoniais têm saldo final"
    dimensao = "Completude"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Detecta contas patrimoniais com saldo final zerado.

        Agrega por conta_contabil antes de validar: uma conta pode estar
        representada em múltiplas linhas (ICs diferentes). Só reporta ALERTA
        se a soma de abs(SF_D) + abs(SF_C) for zero para o total da conta.

        Args:
            df: DataFrame normalizado com colunas ``conta_contabil``,
                ``saldo_final_debito`` e ``saldo_final_credito``.
            context: metadados da execução.

        Returns:
            DataFrame de pendências — uma linha por conta patrimonial
            com saldo final totalmente zerado.
        """
        _extra = {"regra_id": self.rule_id, "competencia": context.competencia}

        cols_sf = ["saldo_final_debito", "saldo_final_credito"]

        df_pat = df[
            df["conta_contabil"].astype(str).str[:1].isin(_CLASSES_PATRIMONIAIS)
        ][["conta_contabil"] + cols_sf].copy()

        if df_pat.empty:
            return self.build_issues([])

        for col in cols_sf:
            df_pat[col] = pd.to_numeric(df_pat[col], errors="coerce").fillna(0.0)

        totais = (
            df_pat
            .groupby("conta_contabil", as_index=False)
            .agg(
                sf_d=("saldo_final_debito", "sum"),
                sf_c=("saldo_final_credito", "sum"),
            )
        )

        totais["_soma_abs"] = totais["sf_d"].abs() + totais["sf_c"].abs()
        violacoes = totais[totais["_soma_abs"] == 0.0]

        if violacoes.empty:
            return self.build_issues([])

        logger.warning(
            "R041: %d conta(s) patrimonial(is) sem saldo final. competência=%s",
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
                    f"saldo final (SF_D=0 e SF_C=0)."
                ),
                "valor_esperado": "saldo_final ≠ 0",
                "valor_encontrado": "0",
                "competencia": context.competencia,
            }
            for _, row in violacoes.iterrows()
        ]

        return self.build_issues(issues)
