"""Regra R041 — Contas patrimoniais têm saldo final.

Dimensão: Completude
Severidade padrão: ALERTA

Lógica:
    Para cada conta patrimonial (primeiro dígito em {1, 2, 5, 6}),
    verifica se existe ao menos uma linha ending_balance no CSV original.
    A verificação é baseada em presença de entradas (COUNT > 0), não em
    valor não-zero: saldo zero legítimo não deve gerar ALERTA.

    SE _has_saldo_final == False (nenhuma entrada ending_balance) → ALERTA

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
        """Detecta contas patrimoniais sem nenhuma entrada de saldo final.

        Agrega por conta_contabil antes de validar: uma conta pode estar
        representada em múltiplas linhas (ICs diferentes). Reporta ALERTA
        apenas se nenhuma linha ending_balance existia no CSV original
        (indicado por _has_saldo_final=False em todas as linhas da conta).
        Saldo zero legítimo não gera ALERTA — a verificação é baseada em
        presença de entradas (COUNT > 0), não em valor não-zero.

        Args:
            df: DataFrame normalizado com colunas ``conta_contabil`` e
                ``_has_saldo_final``.
            context: metadados da execução.

        Returns:
            DataFrame de pendências — uma linha por conta patrimonial
            sem nenhuma entrada ending_balance no CSV original.
        """
        _extra = {"regra_id": self.rule_id, "competencia": context.competencia}

        df_pat = df[
            df["conta_contabil"].astype(str).str[:1].isin(_CLASSES_PATRIMONIAIS)
        ][["conta_contabil", "_has_saldo_final"]].copy()

        if df_pat.empty:
            return self.build_issues([])

        totais = (
            df_pat
            .groupby("conta_contabil", as_index=False)
            .agg(tem_sf=("_has_saldo_final", "any"))
        )

        violacoes = totais[~totais["tem_sf"]]

        if violacoes.empty:
            return self.build_issues([])

        logger.warning(
            "R041: %d conta(s) patrimonial(is) sem saldo final. competência=%s",
            len(violacoes),
            context.competencia,
            extra=_extra,
        )

        conta_s = violacoes["conta_contabil"].astype(str)
        issues_df = pd.DataFrame({
            "severidade": "ALERTA",
            "conta_contabil": conta_s.values,
            "descricao": (
                "Conta patrimonial '" + conta_s
                + "' não possui nenhuma entrada de saldo final (ending_balance ausente)."
            ).values,
            "valor_esperado": "COUNT(ending_balance) > 0",
            "valor_encontrado": "0",
            "competencia": context.competencia,
        })

        return self.build_issues(issues_df.to_dict("records"))
