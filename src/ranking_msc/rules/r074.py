"""
Regra R074 — Cada conta/IC deve ter ending_balance OU period_change.

Dimensão: Completude
Severidade padrão: ALERTA

Lógica:
    Registros com apenas saldo inicial (sem saldo final nem movimentação)
    são inúteis para análise — indicam exportação incompleta.

    PARA CADA chave (conta + ICs):
      SE saldo_inicial > 0 E saldo_final == 0 E movimento == 0 → ALERTA

Referência:
    ref/regras_catalogo.md — R074; Portaria STN 642/2026
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

from ranking_msc.rules.base import Rule, register_rule

if TYPE_CHECKING:
    from ranking_msc.engine.executor import EngineContext

_COLS_SF = ("saldo_final_debito", "saldo_final_credito")
_COLS_MOV = ("movimento_debito", "movimento_credito")
_COLS_SI = ("saldo_inicial_debito", "saldo_inicial_credito")


@register_rule
class R074(Rule):
    """Verifica se toda chave conta/IC tem saldo final ou movimentação."""

    rule_id = "R074"
    rule_name = "Chave com SF ou PC"
    dimensao = "Completude"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Detecta linhas com saldo inicial mas sem SF nem movimentação.

        Args:
            df: DataFrame normalizado com colunas de saldo e movimentação.
            context: metadados da execução.

        Returns:
            DataFrame de pendências — uma linha por chave conta/IC incompleta.
        """
        if df.empty:
            return self.build_issues([])

        work = df.copy()
        for col in (*_COLS_SF, *_COLS_MOV, *_COLS_SI):
            work[col] = pd.to_numeric(work[col], errors="coerce").fillna(0.0)

        has_si = (work[list(_COLS_SI)] != 0).any(axis=1)
        has_sf = (work[list(_COLS_SF)] != 0).any(axis=1)
        has_mov = (work[list(_COLS_MOV)] != 0).any(axis=1)

        violacoes = work[has_si & ~has_sf & ~has_mov]

        if violacoes.empty:
            return self.build_issues([])

        si_d = work.loc[violacoes.index, "saldo_inicial_debito"]
        si_c = work.loc[violacoes.index, "saldo_inicial_credito"]

        issues = [
            {
                "severidade": "ALERTA",
                "conta_contabil": str(row["conta_contabil"]),
                "descricao": (
                    "Conta/IC com saldo inicial mas sem saldo final nem movimentação."
                ),
                "valor_esperado": "SF ≠ 0 ou movimentação ≠ 0",
                "valor_encontrado": (
                    f"SI_D={si_d.loc[idx]:.2f}, SI_C={si_c.loc[idx]:.2f}; "
                    "SF=0, MOV=0"
                ),
                "competencia": context.competencia,
            }
            for idx, row in violacoes.iterrows()
        ]
        return self.build_issues(issues)
