"""Regra R030 — Débito = Crédito no razão (fechamento patrimonial).

Categoria: Fechamento
Severidade padrão: ERRO
Lógica:
    Método das partidas dobradas: no razão patrimonial (classes 1, 2, 3, 4 —
    primeiro dígito da conta), a soma de TODOS os movimentos devedores deve
    igualar a soma de TODOS os movimentos credores. Este é um invariante do
    razão como um todo, NÃO de cada conta isolada — a diferença D−C de uma
    conta é a variação de saldo dela no período, e por si só não é erro.
    Diferença global acima da tolerância indica que o razão não fecha
    (lançamento incompleto/inconsistente em algum ponto).
Referência:
    Regras Gerais MSC 2026 (Anexo I); Portaria STN 642/2026; MCASP —
    método das partidas dobradas.
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
    rule_name = "Débito = Crédito no razão (fechamento patrimonial)"
    dimensao = "Fechamento"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Soma todos os movimentos D e C do razão patrimonial e detecta
        desequilíbrio global das partidas dobradas.

        Args:
            df: DataFrame normalizado com colunas ``conta_contabil``,
                ``movimento_debito`` e ``movimento_credito``.
            context: metadados da execução.

        Returns:
            DataFrame de pendências — uma única linha ERRO quando o total de
            débitos difere do total de créditos no razão patrimonial acima da
            tolerância; vazio caso o razão feche.
        """
        _extra = {"regra_id": self.rule_id, "competencia": context.competencia}

        df_patrimonial = df[
            df["conta_contabil"].astype(str).str[:1].isin(_CLASSES_PATRIMONIAIS)
        ][["movimento_debito", "movimento_credito"]].copy()

        if df_patrimonial.empty:
            return self.build_issues([])

        total_d = pd.to_numeric(
            df_patrimonial["movimento_debito"], errors="coerce"
        ).fillna(0.0).sum()
        total_c = pd.to_numeric(
            df_patrimonial["movimento_credito"], errors="coerce"
        ).fillna(0.0).sum()

        diferenca = abs(total_d - total_c)
        if diferenca <= TOLERANCIA_CENTAVO:
            return self.build_issues([])

        logger.warning(
            "R030: razão patrimonial não fecha — ∑D=%.2f ∑C=%.2f dif=%.2f. "
            "competência=%s",
            total_d,
            total_c,
            diferenca,
            context.competencia,
            extra=_extra,
        )

        issue = {
            "severidade": "ERRO",
            "conta_contabil": "",
            "descricao": (
                "Razão patrimonial (classes 1–4) não fecha: soma dos movimentos "
                f"devedores (R$ {total_d:.2f}) ≠ soma dos credores "
                f"(R$ {total_c:.2f}). Diferença de R$ {diferenca:.2f}."
            ),
            "valor_esperado": f"{total_d:.2f}",
            "valor_encontrado": f"{total_c:.2f}",
            "competencia": context.competencia,
        }

        return self.build_issues([issue])
