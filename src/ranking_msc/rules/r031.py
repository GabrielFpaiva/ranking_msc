"""Regra R031 — Saldo Final = Saldo Inicial + Movimentos.

Dimensão: Fechamento
Severidade padrão: ERRO

Lógica:
    Para cada linha (CONTA + ICs), verifica a identidade contábil fundamental:
        SF_líquido = SI_líquido + Mov_D − Mov_C

    Onde o líquido é sempre calculado como D − C:
        SI_líquido  = saldo_inicial_debito  − saldo_inicial_credito
        SF_líquido  = saldo_final_debito    − saldo_final_credito
        Mov_líquido = movimento_debito      − movimento_credito

    Resíduo = SF_líquido − (SI_líquido + Mov_líquido)
    SE abs(Resíduo) > tolerância → ERRO

    A fórmula é algebricamente idêntica para contas Devedoras e Credoras,
    portanto não é necessário consultar a NAT_SALDO do PCASP.

Referência:
    Portaria STN 642/2026 — Regras Gerais MSC, R031 (V2 SIGEF)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pandas as pd

from ranking_msc.rules.base import TOLERANCIA_CENTAVO, Rule, register_rule

if TYPE_CHECKING:
    from ranking_msc.engine.executor import EngineContext

logger = logging.getLogger("ranking_msc")


@register_rule
class R031(Rule):
    """Verifica que SF = SI + Movimentos para cada linha CONTA+ICs."""

    rule_id = "R031"
    rule_name = "SF = SI + Movimentos"
    dimensao = "Fechamento"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Detecta combos CONTA+ICs onde o saldo final diverge de SI + movimentos.

        Agrega os valores por combo normalizado antes de validar: o pipeline pode
        representar um mesmo combo CONTA+ICs em múltiplas linhas quando layouts
        de IC diferentes (ex: PO;FR vs PO;;FR) normalizam para o mesmo conjunto.
        Sem agregação, valores divididos causariam falsos ERROs.

        Args:
            df: DataFrame normalizado com colunas ``conta_contabil``, colunas IC
                (``po``, ``fp``, ``dc``, ``fs``, ``fr``, ``co``, ``nr``, ``nd``,
                ``ai``) e colunas de valor (saldo_inicial/movimento/saldo_final D e C).
            context: metadados da execução.

        Returns:
            DataFrame de pendências — uma linha por combo CONTA+ICs agregado com
            abs(SF_líq − SI_líq − Mov_líq) > 0.01.
        """
        _extra = {"regra_id": self.rule_id, "competencia": context.competencia}

        ic_cols = ["po", "fp", "dc", "fs", "fr", "co", "nr", "nd", "ai"]
        cols_valor = [
            "saldo_inicial_debito", "saldo_inicial_credito",
            "movimento_debito", "movimento_credito",
            "saldo_final_debito", "saldo_final_credito",
        ]

        # Inclui apenas as colunas IC presentes no DataFrame (testes usam DFs mínimos)
        ic_keys = [c for c in ic_cols if c in df.columns]
        group_keys = ["conta_contabil"] + ic_keys

        work = df[group_keys + cols_valor].copy()

        if work.empty:
            return self.build_issues([])

        for col in cols_valor:
            work[col] = pd.to_numeric(work[col], errors="coerce").fillna(0.0)

        # Agrega por combo normalizado CONTA+ICs antes de validar
        work = work.groupby(group_keys, as_index=False, dropna=False)[cols_valor].sum()

        work["_si_liq"] = work["saldo_inicial_debito"] - work["saldo_inicial_credito"]
        work["_sf_liq"] = work["saldo_final_debito"]   - work["saldo_final_credito"]
        work["_mov_liq"] = work["movimento_debito"] - work["movimento_credito"]
        work["_residuo"] = (work["_sf_liq"] - work["_si_liq"] - work["_mov_liq"]).abs()

        violacoes = work[work["_residuo"] > TOLERANCIA_CENTAVO]

        if violacoes.empty:
            return self.build_issues([])

        logger.warning(
            "R031: %d linha(s) com SF ≠ SI + Movimentos. competência=%s",
            len(violacoes),
            context.competencia,
            extra=_extra,
        )

        issues: list[dict[str, object]] = [
            {
                "severidade": "ERRO",
                "conta_contabil": str(row["conta_contabil"]),
                "descricao": (
                    f"Conta '{row['conta_contabil']}': SF ≠ SI + Movimentos. "
                    f"SF_líq={row['_sf_liq']:.2f}, "
                    f"SI_líq + Mov_líq={row['_si_liq'] + row['_mov_liq']:.2f}, "
                    f"resíduo={row['_residuo']:.2f}."
                ),
                "valor_esperado": f"{row['_si_liq'] + row['_mov_liq']:.2f}",
                "valor_encontrado": f"{row['_sf_liq']:.2f}",
                "competencia": context.competencia,
            }
            for _, row in violacoes.iterrows()
        ]

        return self.build_issues(issues)
