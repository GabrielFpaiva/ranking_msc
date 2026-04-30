"""Regra R026 — NR válida: 8 dígitos e existente na tabela NR.

Categoria: IC
Severidade padrão: ERRO (formato) | ALERTA (código ausente na tabela)

Lógica:
    Quando a coluna `nr` está informada, o valor é validado em três níveis:
      1. Comprimento: deve ter exatamente 8 caracteres (verificado no valor bruto).
      2. Formato: deve conter apenas dígitos (0–9) — valores como "12AB5678" são ERRO.
      3. Existência: deve existir na tabela NR 2026.
    Checks de comprimento e formato geram ERRO; ausência na tabela gera ALERTA.
    Após ERRO de comprimento ou formato, o check de existência não é executado.

Referência:
    Leiaute MSC 2026 — campo NR; ref/regras_catalogo.md seção R026
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pandas as pd

from ranking_msc.io.ref_loader import load_tabela_nr
from ranking_msc.rules.base import Rule, ic_mask_informada, register_rule

if TYPE_CHECKING:
    from ranking_msc.engine.executor import EngineContext

logger = logging.getLogger("ranking_msc")


@register_rule
class R026(Rule):
    """Valida formato (8 dígitos) e existência do NR na tabela oficial."""

    rule_id = "R026"
    rule_name = "NR válida — 8 dígitos e existente na tabela NR 2026"
    dimensao = "IC"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Verifica se os valores de NR são válidos em formato e domínio.

        Para cada valor de NR informado:
          - Se tiver comprimento diferente de 8 antes da normalização → ERRO e próxima conta.
          - Se contiver caractere não-dígito (ex: "12AB5678") → ERRO e próxima conta.
          - Se o código não existir na tabela NR → ALERTA.

        Args:
            df: DataFrame normalizado com colunas ``nr`` e ``conta_contabil``.
            context: metadados da execução.

        Returns:
            DataFrame de pendências — uma linha por violação encontrada.
        """
        _extra = {"regra_id": self.rule_id, "competencia": context.competencia}

        if "nr" not in df.columns:
            return self.build_issues([])

        tabela = load_tabela_nr(context.settings.paths.ref_dir)
        codigos_validos: set[str] = set(
            tabela["codigo"].astype(str).str.strip().str.zfill(8)
        )

        df_com_nr = df[["conta_contabil", "nr"]].copy()
        df_com_nr = df_com_nr[ic_mask_informada(df_com_nr["nr"])]

        if df_com_nr.empty:
            return self.build_issues([])

        df_unica = df_com_nr.drop_duplicates(subset=["conta_contabil", "nr"]).copy()
        df_unica["nr_raw"] = df_unica["nr"].astype(str).str.strip()
        df_unica["nr_val"] = df_unica["nr_raw"].str.zfill(8)

        mask_len = df_unica["nr_raw"].str.len() != 8
        mask_digit = (~mask_len) & (~df_unica["nr_raw"].str.isdigit())
        mask_tabela = (~mask_len) & (~mask_digit) & (~df_unica["nr_val"].isin(codigos_validos))

        dfs_issues = []

        if mask_len.any():
            viol = df_unica[mask_len]
            dfs_issues.append(pd.DataFrame({
                "severidade": "ERRO",
                "conta_contabil": viol["conta_contabil"].astype(str),
                "descricao": "NR '" + viol["nr_raw"] + "' inválida para conta '" + viol["conta_contabil"].astype(str) + "': deve ter exatamente 8 dígitos.",
                "valor_esperado": "8 dígitos",
                "valor_encontrado": viol["nr_raw"],
                "competencia": context.competencia,
            }))

        if mask_digit.any():
            viol = df_unica[mask_digit]
            dfs_issues.append(pd.DataFrame({
                "severidade": "ERRO",
                "conta_contabil": viol["conta_contabil"].astype(str),
                "descricao": "NR '" + viol["nr_raw"] + "' inválida para conta '" + viol["conta_contabil"].astype(str) + "': deve conter apenas dígitos (0–9).",
                "valor_esperado": "apenas dígitos (0-9)",
                "valor_encontrado": viol["nr_raw"],
                "competencia": context.competencia,
            }))

        if mask_tabela.any():
            viol = df_unica[mask_tabela]
            dfs_issues.append(pd.DataFrame({
                "severidade": "ALERTA",
                "conta_contabil": viol["conta_contabil"].astype(str),
                "descricao": "NR '" + viol["nr_val"] + "' não encontrada na tabela NR 2026 para conta '" + viol["conta_contabil"].astype(str) + "'.",
                "valor_esperado": "código em tabela_nr.csv",
                "valor_encontrado": viol["nr_val"],
                "competencia": context.competencia,
            }))

        if dfs_issues:
            issues_df = pd.concat(dfs_issues, ignore_index=True)
            logger.warning(
                "R026: %d pendência(s) de NR inválida. competência=%s",
                len(issues_df),
                context.competencia,
                extra=_extra,
            )
            return self.build_issues(issues_df.to_dict("records"))

        return self.build_issues([])
