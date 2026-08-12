"""Regra R040 — Contas patrimoniais têm saldo inicial.

Dimensão: Completude
Severidade padrão: INFO — fora da pontuação (is_scoring=False)

Lógica:
    Marca conta patrimonial (primeiro dígito em {1, 2, 5, 6}) sem nenhuma linha
    beginning_balance no CSV original. Conta aberta no meio do período ou conta
    zerada pode legitimamente não ter a entrada, então o sinal é informativo.

Referência:
    doc/calibracao_regras_respostas_rodrigo.md, pergunta 9.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, ClassVar

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
    is_scoring: ClassVar[bool] = False

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Detecta contas patrimoniais sem nenhuma entrada de saldo inicial.

        Agrega por conta_contabil antes de validar: uma conta pode estar
        representada em múltiplas linhas (ICs diferentes). Reporta INFO
        apenas se nenhuma linha beginning_balance existia no CSV original
        (indicado por _has_saldo_inicial=False em todas as linhas da conta).
        Conta aberta no meio do período ou conta zerada pode legitimamente
        não ter a entrada — o sinal é informativo, fora da pontuação.

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

        logger.info(
            "R040: %d conta(s) patrimonial(is) sem saldo inicial (informativo). competência=%s",
            len(violacoes),
            context.competencia,
            extra=_extra,
        )

        conta_s = violacoes["conta_contabil"].astype(str)
        issues_df = pd.DataFrame({
            "severidade": "INFO",
            "conta_contabil": conta_s.values,
            "descricao": (
                "Conta patrimonial '" + conta_s
                + "' não possui nenhuma entrada de saldo inicial (beginning_balance ausente) —"
                " sinal informativo, pode ser conta nova ou zerada."
            ).values,
            "valor_esperado": "COUNT(beginning_balance) > 0",
            "valor_encontrado": "0",
            "competencia": context.competencia,
        })

        return self.build_issues(issues_df.to_dict("records"))
