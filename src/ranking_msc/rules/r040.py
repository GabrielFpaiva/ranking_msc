"""Regra R040 — Contas patrimoniais têm saldo inicial.

Dimensão: Completude
Severidade padrão: ALERTA

Lógica:
    Para cada conta patrimonial (primeiro dígito em {1, 2, 5, 6}),
    verifica se existe ao menos uma linha beginning_balance no CSV original.
    A verificação é baseada em presença de entradas (COUNT > 0), não em
    valor não-zero: saldo zero legítimo não deve gerar ALERTA.

    SE _has_saldo_inicial == False (nenhuma entrada beginning_balance) → ALERTA

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
        """Detecta contas patrimoniais sem nenhuma entrada de saldo inicial.

        Agrega por conta_contabil antes de validar: uma conta pode estar
        representada em múltiplas linhas (ICs diferentes). Reporta ALERTA
        apenas se nenhuma linha beginning_balance existia no CSV original
        (indicado por _has_saldo_inicial=False em todas as linhas da conta).

        Args:
            df: DataFrame normalizado com colunas ``conta_contabil`` e
                ``_has_saldo_inicial``.
            context: metadados da execução.

        Returns:
            DataFrame de pendências — uma linha por conta patrimonial
            sem nenhuma entrada beginning_balance no CSV original.
        """
        _extra = {"regra_id": self.rule_id, "competencia": context.competencia}

        df_pat = df[
            df["conta_contabil"].astype(str).str[:1].isin(_CLASSES_PATRIMONIAIS)
        ][["conta_contabil", "_has_saldo_inicial"]].copy()

        if df_pat.empty:
            return self.build_issues([])

        totais = (
            df_pat
            .groupby("conta_contabil", as_index=False)
            .agg(tem_si=("_has_saldo_inicial", "any"))
        )

        violacoes = totais[~totais["tem_si"]]

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
                    f"nenhuma entrada de saldo inicial (beginning_balance ausente)."
                ),
                "valor_esperado": "COUNT(beginning_balance) > 0",
                "valor_encontrado": "0",
                "competencia": context.competencia,
            }
            for _, row in violacoes.iterrows()
        ]

        return self.build_issues(issues)
