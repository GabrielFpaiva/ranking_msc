"""Regra R030 — Débito = Crédito por conta (fechamento patrimonial).

Categoria: Fechamento
Severidade padrão: ERRO
Lógica:
    Para cada conta das classes patrimoniais (1, 2, 3, 4 — primeiro
    dígito da conta), a soma de movimento_debito deve ser igual à soma
    de movimento_credito. Diferença acima de tolerância indica lançamento
    contábil incompleto ou incorreto.
Referência:
    Regras Gerais MSC 2026 (Anexo I); Portaria STN 642/2026
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pandas as pd

from ranking_msc.rules.base import TOLERANCIA_CENTAVO, Rule, register_rule

if TYPE_CHECKING:
    from ranking_msc.engine.executor import EngineContext

logger = logging.getLogger("ranking_msc")

_CLASSES_PATRIMONIAIS: frozenset[str] = frozenset({"1", "2", "3", "4"})


@register_rule
class R030(Rule):
    """Verifica equilíbrio D=C nos movimentos de contas patrimoniais."""

    rule_id = "R030"
    rule_name = "Débito = Crédito por conta (fechamento patrimonial)"
    dimensao = "Fechamento"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Soma movimentos D e C por conta e detecta desequilíbrios.

        Args:
            df: DataFrame normalizado com colunas ``conta_contabil``,
                ``movimento_debito`` e ``movimento_credito``.
            context: metadados da execução.

        Returns:
            DataFrame de pendências — uma linha por conta com
            mov_D ≠ mov_C acima da tolerância.
        """
        _extra = {"regra_id": self.rule_id, "competencia": context.competencia}

        df_patrimonial = df[
            df["conta_contabil"].astype(str).str[:1].isin(_CLASSES_PATRIMONIAIS)
        ][["conta_contabil", "movimento_debito", "movimento_credito"]].copy()

        if df_patrimonial.empty:
            return self.build_issues([])

        df_patrimonial["movimento_debito"] = pd.to_numeric(
            df_patrimonial["movimento_debito"], errors="coerce"
        ).fillna(0.0)
        df_patrimonial["movimento_credito"] = pd.to_numeric(
            df_patrimonial["movimento_credito"], errors="coerce"
        ).fillna(0.0)

        totais = (
            df_patrimonial
            .groupby("conta_contabil", as_index=False)
            .agg(
                mov_d=("movimento_debito", "sum"),
                mov_c=("movimento_credito", "sum"),
            )
        )

        totais["diferenca"] = (totais["mov_d"] - totais["mov_c"]).abs()
        violacoes = totais[totais["diferenca"] > TOLERANCIA_CENTAVO]

        if violacoes.empty:
            return self.build_issues([])

        logger.warning(
            "R030: %d conta(s) com D≠C. competência=%s",
            len(violacoes),
            context.competencia,
            extra=_extra,
        )

        issues: list[dict[str, object]] = [
            {
                "severidade": "ERRO",
                "conta_contabil": row["conta_contabil"],
                "descricao": (
                    f"Conta '{row['conta_contabil']}': movimento D≠C. "
                    f"Diferença de R$ {row['diferenca']:.2f}."
                ),
                "valor_esperado": f"{row['mov_d']:.2f}",
                "valor_encontrado": f"{row['mov_c']:.2f}",
                "competencia": context.competencia,
            }
            for _, row in violacoes.iterrows()
        ]

        return self.build_issues(issues)
