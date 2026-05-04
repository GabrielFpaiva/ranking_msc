"""
Regra R037 — Débito = Crédito — Controle (classes 7-8).

Dimensão: Fechamento
Severidade padrão: ERRO

Lógica:
    Soma o total de movimento_debito e movimento_credito de TODAS as contas
    de controle (primeiro dígito ∈ {7,8}) e verifica se a diferença
    absoluta do agregado excede TOLERANCIA_CENTAVO.

    Diferença do R030: R030 verifica D=C por conta individual; R037 verifica
    o total agregado do grupo — uma única violação possível por arquivo.

Referência:
    Doc. Validações MSC — item (e), conteúdo; Portaria STN 642/2026.
    Depende de R030.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pandas as pd

from ranking_msc.rules.base import TOLERANCIA_CENTAVO, Rule, register_rule

if TYPE_CHECKING:
    from ranking_msc.engine.executor import EngineContext

logger = logging.getLogger("ranking_msc")

_CLASSES_CONTROLE: frozenset[str] = frozenset({"7", "8"})


@register_rule
class R037(Rule):
    """Verifica equilíbrio D=C agregado das contas de controle (classes 7-8)."""

    rule_id = "R037"
    rule_name = "Débito = Crédito — Controle (classes 7-8)"
    dimensao = "Fechamento"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Soma movimentos D e C de todas as contas de controle e detecta desequilíbrio.

        Args:
            df: DataFrame normalizado com colunas ``conta_contabil``,
                ``movimento_debito`` e ``movimento_credito``.
            context: metadados da execução.

        Returns:
            DataFrame de pendências — zero ou uma linha (verificação agregada).
        """
        _extra = {"regra_id": self.rule_id, "competencia": context.competencia}

        mask = df["conta_contabil"].astype(str).str[:1].isin(_CLASSES_CONTROLE)
        df_grupo = df.loc[mask, ["movimento_debito", "movimento_credito"]].copy()

        if df_grupo.empty:
            return self.build_issues([])

        df_grupo["movimento_debito"] = pd.to_numeric(
            df_grupo["movimento_debito"], errors="coerce"
        ).fillna(0.0)
        df_grupo["movimento_credito"] = pd.to_numeric(
            df_grupo["movimento_credito"], errors="coerce"
        ).fillna(0.0)

        total_d = df_grupo["movimento_debito"].sum()
        total_c = df_grupo["movimento_credito"].sum()
        diferenca = abs(total_d - total_c)

        if diferenca <= TOLERANCIA_CENTAVO:
            return self.build_issues([])

        logger.warning(
            "R037: desequilíbrio D≠C no grupo controle (classes 7-8). "
            "Diferença=%.2f. competência=%s",
            diferenca,
            context.competencia,
            extra=_extra,
        )

        return self.build_issues([{
            "severidade": "ERRO",
            "conta_contabil": "TOTAL (classes 7-8)",
            "descricao": (
                f"Grupo controle (classes 7-8): total D≠C. "
                f"Diferença de R$ {diferenca:.2f}."
            ),
            "valor_esperado": f"{total_d:.2f}",
            "valor_encontrado": f"{total_c:.2f}",
            "competencia": context.competencia,
        }])
