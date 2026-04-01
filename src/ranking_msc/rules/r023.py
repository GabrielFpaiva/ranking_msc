"""Regra R023 — DC (Dívida Consolidada) válido.

Categoria: IC
Severidade padrão: ERRO

Lógica:
    Quando a coluna `dc` está informada, o valor deve ser "1"
    (não compõe Dívida Consolidada). Qualquer outro valor é inválido.

Referência:
    Leiaute MSC 2026 — campo DC; Portaria STN 642/2026
"""

from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING

import pandas as pd

from ranking_msc.rules.base import Rule, register_rule

if TYPE_CHECKING:
    from ranking_msc.engine.executor import EngineContext

logger = logging.getLogger("ranking_msc")

_IC_VAZIA: frozenset[str] = frozenset({"", "0", "nan"})
_DC_DOMAIN: frozenset[str] = frozenset({"1"})


def _dc_esta_informado(val: object) -> bool:
    """Retorna True se o valor da coluna DC está preenchido (não é vazio)."""
    if val is None:
        return False
    if isinstance(val, float) and math.isnan(val):
        return False
    return str(val).strip() not in _IC_VAZIA


@register_rule
class R023(Rule):
    """Valida se o valor de DC é "1" (não compõe Dívida Consolidada)."""

    rule_id = "R023"
    rule_name = "DC válido — valor 1"
    dimensao = "IC"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Verifica se os valores de DC estão no domínio permitido {"1"}.

        Args:
            df: DataFrame normalizado com colunas ``dc`` e ``conta_contabil``.
            context: metadados da execução.

        Returns:
            DataFrame de pendências — uma linha por combinação
            conta/DC inválida encontrada.
        """
        _extra = {"regra_id": self.rule_id, "competencia": context.competencia}

        if "dc" not in df.columns:
            return self.build_issues([])

        df_com_dc = df[["conta_contabil", "dc"]].copy()
        df_com_dc = df_com_dc[df_com_dc["dc"].apply(_dc_esta_informado)]
        df_com_dc["dc"] = df_com_dc["dc"].astype(str).str.strip()

        if df_com_dc.empty:
            return self.build_issues([])

        issues: list[dict[str, object]] = []

        for _, row in df_com_dc.drop_duplicates().iterrows():
            dc_valor = str(row["dc"])
            conta = str(row["conta_contabil"])

            if dc_valor not in _DC_DOMAIN:
                issues.append({
                    "severidade": "ERRO",
                    "conta_contabil": conta,
                    "descricao": (
                        f"DC '{dc_valor}' inválido para conta '{conta}': "
                        "esperado '1' (não compõe DC)."
                    ),
                    "valor_esperado": "1",
                    "valor_encontrado": dc_valor,
                    "competencia": context.competencia,
                })

        if issues:
            logger.warning(
                "R023: %d pendência(s) de DC inválido. competência=%s",
                len(issues),
                context.competencia,
                extra=_extra,
            )

        return self.build_issues(issues)
