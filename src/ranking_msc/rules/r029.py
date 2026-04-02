"""Regra R029 — AI (Ano Inscrição RP) válido.

Categoria: IC
Severidade: ERRO (formato inválido) | ALERTA (ano implausível)

Lógica:
    Quando uma conta possui IC do tipo AI (Ano de Inscrição em Restos a Pagar),
    o valor deve:
    1. Ter exatamente 4 dígitos numéricos → ERRO se violado.
    2. Ser um ano plausível: >= 2000 e <= ano corrente → ALERTA se violado.

    Linhas sem AI (ic_esta_informada retorna False) são ignoradas.

Referência:
    Leiaute MSC 2026 — IC tipo AI; Portaria STN 642/2026
"""

from __future__ import annotations

import datetime
import logging
from typing import TYPE_CHECKING

import pandas as pd

from ranking_msc.rules.base import Rule, ic_esta_informada, register_rule

if TYPE_CHECKING:
    from ranking_msc.engine.executor import EngineContext

logger = logging.getLogger("ranking_msc")


@register_rule
class R029(Rule):
    """Valida formato (4 dígitos) e plausibilidade do Ano Inscrição RP."""

    rule_id = "R029"
    rule_name = "AI — Ano Inscrição RP válido"
    dimensao = "IC"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Verifica formato e plausibilidade do campo ai.

        Args:
            df: DataFrame normalizado com colunas ``conta_contabil`` e ``ai``.
            context: metadados da execução (competência, siconfi, settings).

        Returns:
            DataFrame de pendências — ERRO para formato inválido,
            ALERTA para ano fora do intervalo [2000, ano_corrente].
        """
        _extra = {"regra_id": self.rule_id, "competencia": context.competencia}

        ano_corrente = datetime.date.today().year

        df_com_ai = (
            df[df["ai"].apply(ic_esta_informada)][["conta_contabil", "ai"]]
            .drop_duplicates()
            .copy()
        )
        df_com_ai["ai"] = df_com_ai["ai"].astype(str).str.strip()

        if df_com_ai.empty:
            return self.build_issues([])

        issues: list[dict[str, object]] = []

        for _, row in df_com_ai.iterrows():
            ai_val = str(row["ai"])
            conta = str(row["conta_contabil"])

            # Validação 1 — formato: exatamente 4 dígitos numéricos
            if len(ai_val) != 4 or not ai_val.isdigit():
                issues.append({
                    "severidade": "ERRO",
                    "conta_contabil": conta,
                    "descricao": (
                        f"AI '{ai_val}' fora do formato: "
                        f"esperado exatamente 4 dígitos numéricos, "
                        f"encontrado '{ai_val}'. Conta: {conta}."
                    ),
                    "valor_esperado": "4 dígitos numéricos (ex: '2023')",
                    "valor_encontrado": ai_val,
                    "competencia": context.competencia,
                })
                continue  # formato errado → não verifica plausibilidade

            # Validação 2 — plausibilidade: 2000 <= ano <= ano_corrente
            ano = int(ai_val)
            if ano < 2000 or ano > ano_corrente:
                issues.append({
                    "severidade": "ALERTA",
                    "conta_contabil": conta,
                    "descricao": (
                        f"AI '{ai_val}' implausível: "
                        f"esperado ano entre 2000 e {ano_corrente}, "
                        f"encontrado {ano}."
                    ),
                    "valor_esperado": f"2000 ≤ ano ≤ {ano_corrente}",
                    "valor_encontrado": ai_val,
                    "competencia": context.competencia,
                })

        if issues:
            logger.warning(
                "R029: %d pendência(s) de AI inválido. competência=%s",
                len(issues),
                context.competencia,
                extra=_extra,
            )

        return self.build_issues(issues)
