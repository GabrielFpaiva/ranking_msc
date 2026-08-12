"""Regra R045 — ND deve ser de último nível.

Dimensão: IC
Severidade padrão: ALERTA

Lógica:
    NDs informadas devem ser passíveis de envio. Níveis de agregação acima de
    elemento (Classe, Grupo e Modalidade marcados como "Superior" na tabela ND
    2026) existem apenas para "De-Para" e não devem aparecer na execução. O
    elemento com subelemento 00 é envio válido, mesmo marcado como
    "Superior 4º Nível - Elemento".

Referência:
    Leiaute MSC 2026 — campo ND; ref/regras_catalogo.md R045
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

# Único nível "Superior" liberado: o leiaute admite o envio do elemento com
# subelemento 00 (resposta da contabilidade em 11/08/2026). Qualquer outro
# nível "Superior" — inclusive um que ainda não exista na tabela ND hoje —
# continua sendo agregação acima de elemento e, portanto, pendência.
_NIVEL_ELEMENTO_LIBERADO = "Superior 4º Nível - Elemento"


@register_rule
class R045(Rule):
    """Valida se a ND informada não está em nível de agregação acima de elemento."""

    rule_id = "R045"
    rule_name = "ND deve ser de último nível"
    dimensao = "IC"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Verifica se a ND informada está em nível de agregação acima de elemento.

        Níveis "Superior" na tabela ND são agregação e não devem aparecer em
        execução — exceto `_NIVEL_ELEMENTO_LIBERADO`, cujo envio no subelemento
        00 é válido para o Siconfi.

        Args:
            df: DataFrame normalizado com colunas ``nd`` e ``conta_contabil``.
            context: metadados da execução.

        Returns:
            DataFrame de pendências — uma linha por ND em nível de agregação
            acima de elemento encontrada.
        """
        _extra = {"regra_id": self.rule_id, "competencia": context.competencia}

        if "nd" not in df.columns:
            return self.build_issues([])

        tabela = load_tabela_nd(context.settings.paths.ref_dir)
        nivel_col = tabela["nivel"].str.strip()
        mask_acima_elemento = nivel_col.str.startswith("Superior") & (
            nivel_col != _NIVEL_ELEMENTO_LIBERADO
        )
        nds_acima_elemento: set[str] = set(
            tabela.loc[mask_acima_elemento, "codigo"]
            .astype(str)
            .str.strip()
            .str.zfill(8)
        )

        df_com_nd = df[["conta_contabil", "nd"]].copy()
        df_com_nd = df_com_nd[ic_mask_informada(df_com_nd["nd"])]

        if df_com_nd.empty:
            return self.build_issues([])

        df_unica = df_com_nd.drop_duplicates(subset=["conta_contabil", "nd"]).copy()
        df_unica["nd_val"] = df_unica["nd"].astype(str).str.strip().str.zfill(8)

        mask_pendencia = df_unica["nd_val"].isin(nds_acima_elemento)
        df_viol = df_unica[mask_pendencia]

        if df_viol.empty:
            return self.build_issues([])

        conta_s = df_viol["conta_contabil"].astype(str)
        nd_s = df_viol["nd_val"]

        issues_df = pd.DataFrame({
            "severidade": "ALERTA",
            "conta_contabil": conta_s.values,
            "descricao": (
                "ND '" + nd_s + "' está em nível de agregação acima de elemento "
                "para conta '" + conta_s + "': usar ND passível de envio."
            ).values,
            "valor_esperado": "ND passível de envio (nível elemento ou inferior)",
            "valor_encontrado": nd_s.values,
            "competencia": context.competencia,
        })

        logger.warning(
            "R045: %d pendência(s) de ND em nível de agregação acima de elemento. "
            "competência=%s",
            len(issues_df),
            context.competencia,
            extra=_extra,
        )

        return self.build_issues(issues_df.to_dict("records"))
