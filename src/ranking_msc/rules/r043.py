"""Regra R043 — Conta totalmente zerada.

Dimensão: Completude
Severidade padrão: INFO

Lógica:
    Para cada conta (qualquer classe), agrega a soma de abs de todas as
    6 colunas de valor (SI_D, SI_C, Mov_D, Mov_C, SF_D, SF_C) por conta.
    Se a soma for zero → a conta existe no arquivo mas não tem nenhum valor
    informado → INFO.

    Contas zeradas podem indicar placeholders, erros de extração ou contas
    encerradas que não deveriam aparecer no arquivo.

Referência:
    Catálogo de Regras MSC — R043 (Completude)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pandas as pd

from ranking_msc.rules.base import Rule, register_rule

if TYPE_CHECKING:
    from ranking_msc.engine.executor import EngineContext

logger = logging.getLogger("ranking_msc")

_COLS_VALOR = [
    "saldo_inicial_debito",
    "saldo_inicial_credito",
    "movimento_debito",
    "movimento_credito",
    "saldo_final_debito",
    "saldo_final_credito",
]


@register_rule
class R043(Rule):
    """Detecta contas com todas as colunas de valor zeradas."""

    rule_id = "R043"
    rule_name = "Conta totalmente zerada"
    dimensao = "Completude"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Detecta contas onde a soma de abs de todos os valores é zero.

        Agrega por conta_contabil antes de validar: uma conta pode estar
        representada em múltiplas linhas (ICs diferentes). Usa apenas as
        colunas de valor presentes no DataFrame para robustez em testes
        com DataFrames mínimos.

        Args:
            df: DataFrame normalizado com colunas ``conta_contabil`` e
                opcionalmente as 6 colunas de valor.
            context: metadados da execução.

        Returns:
            DataFrame de pendências — uma linha por conta com todas
            as colunas de valor zeradas.
        """
        _extra = {"regra_id": self.rule_id, "competencia": context.competencia}

        # Usa apenas as colunas presentes — robustez para DFs mínimos de teste
        cols_presentes = [c for c in _COLS_VALOR if c in df.columns]

        work = df[["conta_contabil"] + cols_presentes].copy()

        if work.empty:
            return self.build_issues([])

        for col in cols_presentes:
            work[col] = pd.to_numeric(work[col], errors="coerce").fillna(0.0)

        if cols_presentes:
            agg_dict = {col: "sum" for col in cols_presentes}
            totais = work.groupby("conta_contabil", as_index=False).agg(agg_dict)
            totais["_soma_abs"] = sum(totais[col].abs() for col in cols_presentes)
        else:
            # Nenhuma coluna de valor presente — todas as contas são zeradas por definição
            totais = work[["conta_contabil"]].drop_duplicates().copy()
            totais["_soma_abs"] = 0.0

        violacoes = totais[totais["_soma_abs"] == 0.0]

        if violacoes.empty:
            return self.build_issues([])

        logger.info(
            "R043: %d conta(s) totalmente zerada(s). competência=%s",
            len(violacoes),
            context.competencia,
            extra=_extra,
        )

        conta_s = violacoes["conta_contabil"].astype(str)
        issues_df = pd.DataFrame({
            "severidade": "INFO",
            "conta_contabil": conta_s.values,
            "descricao": ("Conta '" + conta_s + "' está totalmente zerada (SI=0, Mov=0, SF=0).").values,
            "valor_esperado": "ao menos um valor ≠ 0",
            "valor_encontrado": "0",
            "competencia": context.competencia,
        })

        return self.build_issues(issues_df.to_dict("records"))
