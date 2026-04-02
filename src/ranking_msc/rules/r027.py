"""Regra R027 — ND válida: 8 dígitos e existente na tabela ND.

Categoria: IC
Severidade padrão: ERRO (formato) | ALERTA (código ausente na tabela)

Lógica:
    Quando a coluna `nd` está informada, o valor é validado em dois níveis:
      1. Comprimento: deve ter exatamente 8 dígitos (verificado no valor bruto).
      2. Existência: deve existir na tabela ND 2026.
    Check de comprimento gera ERRO; ausência na tabela gera ALERTA.
    Após ERRO de comprimento, o check de existência não é executado.

Referência:
    Leiaute MSC 2026 — campo ND; ref/regras_catalogo.md seção R027
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pandas as pd

from ranking_msc.io.ref_loader import load_tabela_nd
from ranking_msc.rules.base import Rule, ic_esta_informada, register_rule

if TYPE_CHECKING:
    from ranking_msc.engine.executor import EngineContext

logger = logging.getLogger("ranking_msc")


@register_rule
class R027(Rule):
    """Valida formato (8 dígitos) e existência do ND na tabela oficial."""

    rule_id = "R027"
    rule_name = "ND válida — 8 dígitos e existente na tabela ND 2026"
    dimensao = "IC"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Verifica se os valores de ND são válidos em formato e domínio.

        Para cada valor de ND informado:
          - Se tiver comprimento diferente de 8 antes da normalização → ERRO e próxima conta.
          - Se o código não existir na tabela ND → ALERTA.

        Args:
            df: DataFrame normalizado com colunas ``nd`` e ``conta_contabil``.
            context: metadados da execução.

        Returns:
            DataFrame de pendências — uma linha por violação encontrada.
        """
        _extra = {"regra_id": self.rule_id, "competencia": context.competencia}

        if "nd" not in df.columns:
            return self.build_issues([])

        tabela = load_tabela_nd(context.settings.paths.ref_dir)
        codigos_validos: set[str] = set(
            tabela["codigo"].astype(str).str.strip().str.zfill(8)
        )

        df_com_nd = df[["conta_contabil", "nd"]].copy()
        df_com_nd = df_com_nd[df_com_nd["nd"].apply(ic_esta_informada)]

        if df_com_nd.empty:
            return self.build_issues([])

        issues: list[dict[str, object]] = []

        for _, row in df_com_nd.drop_duplicates().iterrows():
            conta = str(row["conta_contabil"])
            nd_raw = str(row["nd"]).strip()
            nd_val = nd_raw.zfill(8)

            if len(nd_raw) != 8:
                issues.append({
                    "severidade": "ERRO",
                    "conta_contabil": conta,
                    "descricao": (
                        f"ND '{nd_raw}' inválida para conta '{conta}': "
                        "deve ter exatamente 8 dígitos."
                    ),
                    "valor_esperado": "8 dígitos",
                    "valor_encontrado": nd_raw,
                    "competencia": context.competencia,
                })
                continue

            if nd_val not in codigos_validos:
                issues.append({
                    "severidade": "ALERTA",
                    "conta_contabil": conta,
                    "descricao": (
                        f"ND '{nd_val}' não encontrada na tabela ND 2026 "
                        f"para conta '{conta}'."
                    ),
                    "valor_esperado": "código em tabela_nd.csv",
                    "valor_encontrado": nd_val,
                    "competencia": context.competencia,
                })

        if issues:
            logger.warning(
                "R027: %d pendência(s) de ND inválida. competência=%s",
                len(issues),
                context.competencia,
                extra=_extra,
            )

        return self.build_issues(issues)
