"""Regra R024 — FR válido: 4 dígitos, prefixo {1, 2, 9} e código-raiz na tabela.

Categoria: IC
Severidade padrão: ERRO / ALERTA

Lógica:
    Quando a coluna `fr` está informada, o valor é normalizado para 4 dígitos
    via zfill(4) e validado em três níveis independentes:
      1. Comprimento: deve ter exatamente 4 caracteres (verificado no valor bruto, antes do zfill).
      2. Formato: deve conter apenas dígitos (0–9) — valores alfanuméricos como "1A00" são ERRO.
      3. Prefixo: o 1º dígito deve ser "1" (atual), "2" (anterior) ou "9" (condicionado).
      4. Código-raiz: os últimos 3 dígitos devem existir na tabela FR 2026.
    Os checks de comprimento, formato e prefixo geram ERRO; o check de código-raiz gera ALERTA.
    Após ERRO de comprimento, formato ou prefixo, o check de código-raiz não é executado.

Referência:
    Leiaute MSC 2026 — campo FR; Portaria STN 642/2026
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pandas as pd

from ranking_msc.io.ref_loader import load_tabela_fr
from ranking_msc.rules.base import Rule, ic_mask_informada, register_rule

if TYPE_CHECKING:
    from ranking_msc.engine.executor import EngineContext

logger = logging.getLogger("ranking_msc")

_PREFIXOS_VALIDOS: frozenset[str] = frozenset({"1", "2", "9"})


@register_rule
class R024(Rule):
    """Valida formato (4 dígitos), prefixo e código-raiz do campo FR."""

    rule_id = "R024"
    rule_name = "FR válido — 4 dígitos, prefixo e tabela FR 2026"
    dimensao = "IC"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Verifica se os valores de FR são válidos em formato, prefixo e domínio.

        Para cada valor de FR informado:
          - Se tiver comprimento diferente de 4 antes da normalização → ERRO e próxima conta.
          - Se contiver caractere não-dígito (ex: "1A00") → ERRO e próxima conta.
          - Se o 1º dígito não for "1", "2" ou "9" → ERRO e próxima conta.
          - Se os 3 dígitos restantes não existirem na tabela FR → ALERTA.

        Args:
            df: DataFrame normalizado com colunas ``fr`` e ``conta_contabil``.
            context: metadados da execução.

        Returns:
            DataFrame de pendências — uma linha por violação encontrada.
        """
        _extra = {"regra_id": self.rule_id, "competencia": context.competencia}

        if "fr" not in df.columns:
            return self.build_issues([])

        tabela = load_tabela_fr(context.settings.paths.ref_dir)
        codigos_validos_fr: set[str] = set(
            tabela["codigo_base"].astype(str).str.strip().str.zfill(3)
        )

        df_com_fr = df[["conta_contabil", "fr"]].copy()
        df_com_fr = df_com_fr[ic_mask_informada(df_com_fr["fr"])]

        if df_com_fr.empty:
            return self.build_issues([])

        # Remover duplicatas para validação
        df_unica = df_com_fr.drop_duplicates(subset=["conta_contabil", "fr"]).copy()
        df_unica["fr_raw"] = df_unica["fr"].astype(str).str.strip()
        df_unica["fr_val"] = df_unica["fr_raw"].str.zfill(4)

        # 1. Comprimento != 4
        mask_len = df_unica["fr_raw"].str.len() != 4
        # 2. Não dígito (aplicado apenas onde len é válido para evitar falhas em cascata)
        mask_digit = (~mask_len) & (~df_unica["fr_raw"].str.isdigit())
        # 3. Prefixo inválido
        mask_prefix = (~mask_len) & (~mask_digit) & (~df_unica["fr_val"].str[0].isin(_PREFIXOS_VALIDOS))
        # 4. Tabela
        mask_tabela = (~mask_len) & (~mask_digit) & (~mask_prefix) & (~df_unica["fr_val"].str[1:].isin(codigos_validos_fr))

        dfs_issues = []

        if mask_len.any():
            viol = df_unica[mask_len]
            dfs_issues.append(pd.DataFrame({
                "severidade": "ERRO",
                "conta_contabil": viol["conta_contabil"].astype(str),
                "descricao": "FR '" + viol["fr_raw"] + "' inválido para conta '" + viol["conta_contabil"].astype(str) + "': deve ter exatamente 4 dígitos.",
                "valor_esperado": "4 dígitos",
                "valor_encontrado": viol["fr_raw"],
                "competencia": context.competencia,
            }))

        if mask_digit.any():
            viol = df_unica[mask_digit]
            dfs_issues.append(pd.DataFrame({
                "severidade": "ERRO",
                "conta_contabil": viol["conta_contabil"].astype(str),
                "descricao": "FR '" + viol["fr_raw"] + "' inválido para conta '" + viol["conta_contabil"].astype(str) + "': deve conter apenas dígitos (0–9).",
                "valor_esperado": "apenas dígitos (0-9)",
                "valor_encontrado": viol["fr_raw"],
                "competencia": context.competencia,
            }))

        if mask_prefix.any():
            viol = df_unica[mask_prefix]
            dfs_issues.append(pd.DataFrame({
                "severidade": "ERRO",
                "conta_contabil": viol["conta_contabil"].astype(str),
                "descricao": "FR '" + viol["fr_val"] + "': 1º dígito '" + viol["fr_val"].str[0] + "' inválido — esperado 1 (atual), 2 (anterior) ou 9 (condicionado).",
                "valor_esperado": "1, 2 ou 9",
                "valor_encontrado": viol["fr_val"].str[0],
                "competencia": context.competencia,
            }))

        if mask_tabela.any():
            viol = df_unica[mask_tabela]
            dfs_issues.append(pd.DataFrame({
                "severidade": "ALERTA",
                "conta_contabil": viol["conta_contabil"].astype(str),
                "descricao": "FR '" + viol["fr_val"] + "': código-raiz '" + viol["fr_val"].str[1:] + "' não encontrado na tabela FR 2026.",
                "valor_esperado": "Código-raiz FR existente na tabela",
                "valor_encontrado": viol["fr_val"].str[1:],
                "competencia": context.competencia,
            }))

        if dfs_issues:
            issues_df = pd.concat(dfs_issues, ignore_index=True)
            logger.warning(
                "R024: %d pendência(s) de FR inválida. competência=%s",
                len(issues_df),
                context.competencia,
                extra=_extra,
            )
            return self.build_issues(issues_df.to_dict("records"))

        return self.build_issues([])
