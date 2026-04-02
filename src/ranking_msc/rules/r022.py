"""Regra R022 — FP (Financeiro/Permanente) válido.

Categoria: IC
Severidade padrão: ERRO

Lógica:
    Quando a coluna `fp` está informada, o valor deve ser "1" (Financeiro)
    ou "2" (Permanente). Qualquer outro valor é inválido.

Referência:
    Leiaute MSC 2026 — campo FP; Portaria STN 642/2026
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pandas as pd

from ranking_msc.io.ref_loader import FP_DOMAIN
from ranking_msc.rules.base import Rule, ic_esta_informada, register_rule

if TYPE_CHECKING:
    from ranking_msc.engine.executor import EngineContext

logger = logging.getLogger("ranking_msc")


@register_rule
class R022(Rule):
    """Valida se o valor de FP é "1" (Financeiro) ou "2" (Permanente)."""

    rule_id = "R022"
    rule_name = "FP válido — 1 ou 2"
    dimensao = "IC"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Verifica se os valores de FP estão no domínio permitido {1, 2}.

        Args:
            df: DataFrame normalizado com colunas ``fp`` e ``conta_contabil``.
            context: metadados da execução.

        Returns:
            DataFrame de pendências — uma linha por combinação
            conta/FP inválida encontrada.
        """
        _extra = {"regra_id": self.rule_id, "competencia": context.competencia}

        if "fp" not in df.columns:
            return self.build_issues([])

        df_com_fp = df[["conta_contabil", "fp"]].copy()
        df_com_fp = df_com_fp[df_com_fp["fp"].apply(ic_esta_informada)]
        df_com_fp["fp"] = df_com_fp["fp"].astype(str).str.strip()

        if df_com_fp.empty:
            return self.build_issues([])

        issues: list[dict[str, object]] = []

        for _, row in df_com_fp.drop_duplicates().iterrows():
            fp_valor = str(row["fp"])
            conta = str(row["conta_contabil"])

            if fp_valor not in FP_DOMAIN:
                issues.append({
                    "severidade": "ERRO",
                    "conta_contabil": conta,
                    "descricao": (
                        f"FP '{fp_valor}' inválido para conta '{conta}': "
                        "esperado '1' (Financeiro) ou '2' (Permanente)."
                    ),
                    "valor_esperado": "1 ou 2",
                    "valor_encontrado": fp_valor,
                    "competencia": context.competencia,
                })

        if issues:
            logger.warning(
                "R022: %d pendência(s) de FP inválido. competência=%s",
                len(issues),
                context.competencia,
                extra=_extra,
            )

        return self.build_issues(issues)
