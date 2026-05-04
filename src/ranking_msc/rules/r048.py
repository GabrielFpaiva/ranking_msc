"""Regra R048 — FR: 1º dígito deve estar em {1, 2, 9}.

Dimensão: IC
Severidade padrão: ALERTA
Pontuação: is_scoring=False — sinal complementar (não entra no score)

Lógica:
    O 1º dígito da Fonte de Recurso indica o exercício:
      1 = corrente (exercício atual)
      2 = anterior (saldos de exercício anterior)
      9 = condicionado
    Qualquer outro valor no 1º dígito indica FR semanticamente inválida.

    Complementa R024 (que já trata o mesmo problema com severidade ERRO).
    Como a condição checada aqui é subset estrito de R024.mask_prefix,
    a regra é marcada como is_scoring=False para não penalizar o score
    duas vezes pelo mesmo defeito subjacente. Permanece emitindo ALERTA
    para evidenciar o problema em relatórios de pendências.

Referência:
    Leiaute MSC 2026 — campo FR; ref/regras_catalogo.md R048; R024
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pandas as pd

from ranking_msc.rules.base import Rule, ic_mask_informada, register_rule

if TYPE_CHECKING:
    from ranking_msc.engine.executor import EngineContext

logger = logging.getLogger("ranking_msc")

_PREFIXOS_VALIDOS: frozenset[str] = frozenset({"1", "2", "9"})


@register_rule
class R048(Rule):
    """Valida se o 1º dígito da FR indica exercício válido."""

    rule_id = "R048"
    rule_name = "FR — 1º dígito deve ser 1 (corrente), 2 (anterior) ou 9 (condicionado)"
    dimensao = "IC"
    is_scoring = False  # condição já penalizada por R024 — evita double-penalty no score

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Verifica se o 1º dígito de cada FR está em {1, 2, 9}.

        Args:
            df: DataFrame normalizado com colunas ``fr`` e ``conta_contabil``.
            context: metadados da execução.

        Returns:
            DataFrame de pendências — uma linha por FR com 1º dígito inválido.
        """
        _extra = {"regra_id": self.rule_id, "competencia": context.competencia}

        if "fr" not in df.columns:
            return self.build_issues([])

        df_com_fr = df[["conta_contabil", "fr"]].copy()
        df_com_fr = df_com_fr[ic_mask_informada(df_com_fr["fr"])]

        if df_com_fr.empty:
            return self.build_issues([])

        df_unica = df_com_fr.drop_duplicates(subset=["conta_contabil", "fr"]).copy()
        df_unica["fr_raw"] = df_unica["fr"].astype(str).str.strip()
        df_unica["fr_val"] = df_unica["fr_raw"].str.zfill(4)

        mask_curto = df_unica["fr_raw"].str.len() < 1
        df_unica_valida = df_unica[~mask_curto].copy()

        mask_prefixo = ~df_unica_valida["fr_val"].str[0].isin(_PREFIXOS_VALIDOS)
        df_viol = df_unica_valida[mask_prefixo]

        if df_viol.empty:
            return self.build_issues([])

        conta_s = df_viol["conta_contabil"].astype(str)
        fr_s = df_viol["fr_val"]
        prefixo_s = df_viol["fr_val"].str[0]

        issues_df = pd.DataFrame({
            "severidade": "ALERTA",
            "conta_contabil": conta_s.values,
            "descricao": (
                "FR '" + fr_s + "': 1º dígito '" + prefixo_s
                + "' inválido para conta '" + conta_s
                + "' — esperado 1 (corrente), 2 (anterior) ou 9 (condicionado)."
            ).values,
            "valor_esperado": "1, 2 ou 9",
            "valor_encontrado": prefixo_s.values,
            "competencia": context.competencia,
        })

        logger.warning(
            "R048: %d pendência(s) de FR com 1º dígito inválido. competência=%s",
            len(issues_df),
            context.competencia,
            extra=_extra,
        )

        return self.build_issues(issues_df.to_dict("records"))
