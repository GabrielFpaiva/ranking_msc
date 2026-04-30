"""Regra R027 — ND válida: 8 dígitos e existente na tabela ND.

Categoria: IC
Severidade padrão: ERRO (formato) | ALERTA (código ausente na tabela)

Lógica:
    Quando a coluna `nd` está informada, o valor é validado em três níveis:
      1. Comprimento: deve ter exatamente 8 caracteres (verificado no valor bruto).
      2. Formato: deve conter apenas dígitos (0–9) — valores como "33A0B600" são ERRO.
      3. Existência: deve existir na tabela ND 2026.
    Checks de comprimento e formato geram ERRO; ausência na tabela gera ALERTA.
    Após ERRO de comprimento ou formato, o check de existência não é executado.

Referência:
    Leiaute MSC 2026 — campo ND; ref/regras_catalogo.md seção R027
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pandas as pd

from ranking_msc.io.ref_loader import load_tabela_nd
from ranking_msc.rules.base import Rule, ic_mask_informada, register_rule

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
          - Se contiver caractere não-dígito (ex: "33A0B600") → ERRO e próxima conta.
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
        df_com_nd = df_com_nd[ic_mask_informada(df_com_nd["nd"])]

        if df_com_nd.empty:
            return self.build_issues([])

        df_unica = df_com_nd.drop_duplicates(subset=["conta_contabil", "nd"]).copy()
        df_unica["nd_raw"] = df_unica["nd"].astype(str).str.strip()
        df_unica["nd_val"] = df_unica["nd_raw"].str.zfill(8)

        mask_len = df_unica["nd_raw"].str.len() != 8
        mask_digit = (~mask_len) & (~df_unica["nd_raw"].str.isdigit())
        mask_tabela = (~mask_len) & (~mask_digit) & (~df_unica["nd_val"].isin(codigos_validos))

        dfs_issues = []

        if mask_len.any():
            viol = df_unica[mask_len]
            dfs_issues.append(pd.DataFrame({
                "severidade": "ERRO",
                "conta_contabil": viol["conta_contabil"].astype(str),
                "descricao": (
                    "ND '" + viol["nd_raw"] + "' inválida para conta '"
                    + viol["conta_contabil"].astype(str) + "': deve ter exatamente 8 dígitos."
                ),
                "valor_esperado": "8 dígitos",
                "valor_encontrado": viol["nd_raw"],
                "competencia": context.competencia,
            }))

        if mask_digit.any():
            viol = df_unica[mask_digit]
            dfs_issues.append(pd.DataFrame({
                "severidade": "ERRO",
                "conta_contabil": viol["conta_contabil"].astype(str),
                "descricao": (
                    "ND '" + viol["nd_raw"] + "' inválida para conta '"
                    + viol["conta_contabil"].astype(str) + "': deve conter apenas dígitos (0–9)."
                ),
                "valor_esperado": "apenas dígitos (0-9)",
                "valor_encontrado": viol["nd_raw"],
                "competencia": context.competencia,
            }))

        if mask_tabela.any():
            viol = df_unica[mask_tabela]
            dfs_issues.append(pd.DataFrame({
                "severidade": "ALERTA",
                "conta_contabil": viol["conta_contabil"].astype(str),
                "descricao": (
                    "ND '" + viol["nd_val"]
                    + "' não encontrada na tabela ND 2026 para conta '"
                    + viol["conta_contabil"].astype(str) + "'."
                ),
                "valor_esperado": "código em tabela_nd.csv",
                "valor_encontrado": viol["nd_val"],
                "competencia": context.competencia,
            }))

        if dfs_issues:
            issues_df = pd.concat(dfs_issues, ignore_index=True)
            logger.warning(
                "R027: %d pendência(s) de ND inválida. competência=%s",
                len(issues_df),
                context.competencia,
                extra=_extra,
            )
            return self.build_issues(issues_df.to_dict("records"))

        return self.build_issues([])
