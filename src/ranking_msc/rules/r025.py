"""Regra R025 — CO válido: 4 dígitos e existente na tabela CO.

Categoria: IC
Severidade padrão: ERRO

Lógica:
    Quando a coluna `co` está informada, o valor é normalizado para 4 dígitos
    via zfill(4) e validado em dois níveis independentes:
      1. Comprimento: deve ter exatamente 4 dígitos após normalização.
      2. Existência: o código deve existir na tabela oficial de CO 2026.
    Ambos os checks geram ERRO. Após ERRO de comprimento, o check de existência
    não é executado.

Referência:
    Leiaute MSC 2026 — campo CO; Portaria STN 642/2026
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pandas as pd

from ranking_msc.io.ref_loader import load_tabela_co
from ranking_msc.rules.base import Rule, ic_esta_informada, register_rule

if TYPE_CHECKING:
    from ranking_msc.engine.executor import EngineContext

logger = logging.getLogger("ranking_msc")


@register_rule
class R025(Rule):
    """Valida formato (4 dígitos) e existência do CO na tabela oficial."""

    rule_id = "R025"
    rule_name = "CO válido — 4 dígitos e existente na tabela CO 2026"
    dimensao = "IC"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Verifica se os valores de CO são válidos em formato e domínio.

        Para cada valor de CO informado:
          - Se tiver comprimento diferente de 4 após normalização → ERRO e próxima conta.
          - Se o código não existir na tabela CO → ERRO.

        Args:
            df: DataFrame normalizado com colunas ``co`` e ``conta_contabil``.
            context: metadados da execução.

        Returns:
            DataFrame de pendências — uma linha por violação encontrada.
        """
        _extra = {"regra_id": self.rule_id, "competencia": context.competencia}

        if "co" not in df.columns:
            return self.build_issues([])

        tabela = load_tabela_co(context.settings.paths.ref_dir)
        codigos_validos_co: set[str] = set(
            tabela["codigo"].astype(str).str.strip().str.zfill(4)
        )

        df_com_co = df[["conta_contabil", "co"]].copy()
        df_com_co = df_com_co[df_com_co["co"].apply(ic_esta_informada)]

        if df_com_co.empty:
            return self.build_issues([])

        issues: list[dict[str, object]] = []

        for _, row in df_com_co.drop_duplicates().iterrows():
            co_raw = str(row["co"]).strip()
            co_val = co_raw.zfill(4)
            conta = str(row["conta_contabil"])

            if len(co_raw) != 4:
                issues.append({
                    "severidade": "ERRO",
                    "conta_contabil": conta,
                    "descricao": (
                        f"CO '{co_val}' inválido para conta '{conta}': "
                        "deve ter exatamente 4 dígitos."
                    ),
                    "valor_esperado": "4 dígitos",
                    "valor_encontrado": co_val,
                    "competencia": context.competencia,
                })
                continue

            if co_val not in codigos_validos_co:
                issues.append({
                    "severidade": "ERRO",
                    "conta_contabil": conta,
                    "descricao": (
                        f"CO '{co_val}' não encontrado na tabela CO 2026 "
                        f"para conta '{conta}'."
                    ),
                    "valor_esperado": "Código CO existente na tabela",
                    "valor_encontrado": co_val,
                    "competencia": context.competencia,
                })

        if issues:
            logger.warning(
                "R025: %d pendência(s) de CO inválido. competência=%s",
                len(issues),
                context.competencia,
                extra=_extra,
            )

        return self.build_issues(issues)
