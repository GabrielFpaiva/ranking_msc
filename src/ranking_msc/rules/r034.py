"""
Regra R034 — Todos os registros devem ter PO preenchido.

Dimensão: IC
Severidade padrão: ERRO

Lógica:
    O Poder/Órgão (PO) é obrigatório para 100% dos registros da MSC.
    Toda conta que não possui o IC de tipo PO preenchido gera ERRO.

    Verifica a coluna ``po`` no DataFrame normalizado (FACT_MSC), após
    a transformação IC → named columns.  Valores vazios, "0", "nan"
    e NaN são considerados "sem PO".

Referência:
    Leiaute MSC Siconfi — campo PO obrigatório em todos os registros.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pandas as pd

from ranking_msc.rules.base import Rule, ic_mask_informada, register_rule

if TYPE_CHECKING:
    from ranking_msc.engine.executor import EngineContext

logger = logging.getLogger("ranking_msc")


@register_rule
class R034(Rule):
    """Verifica que todo registro possui IC de tipo PO preenchido."""

    rule_id = "R034"
    rule_name = "PO obrigatório"
    dimensao = "IC"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Detecta registros sem PO no DataFrame normalizado.

        Args:
            df: DataFrame normalizado com colunas de FACT_MSC_COLUMNS.
            context: metadados da execução.

        Returns:
            DataFrame de pendências — uma linha por conta sem PO.
        """
        _extra = {"regra_id": self.rule_id, "competencia": context.competencia}

        if df.empty or "po" not in df.columns:
            return self.build_issues([])

        sem_po = ~ic_mask_informada(df["po"])

        if not sem_po.any():
            return self.build_issues([])

        contas_sem_po = (
            df.loc[sem_po, "conta_contabil"].astype(str).unique()
        )

        logger.warning(
            "R034: %d conta(s) sem PO. competencia=%s",
            len(contas_sem_po),
            context.competencia,
            extra=_extra,
        )

        issues = [
            {
                "severidade": "ERRO",
                "conta_contabil": conta,
                "descricao": (
                    f"Conta '{conta}' não possui IC de tipo PO "
                    "(obrigatório para todos os registros)."
                ),
                "valor_esperado": "PO preenchido",
                "valor_encontrado": "PO ausente",
                "competencia": context.competencia,
            }
            for conta in contas_sem_po
        ]

        return self.build_issues(issues)
