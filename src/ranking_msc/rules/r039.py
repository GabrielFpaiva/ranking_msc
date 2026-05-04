"""Regra R039 — PO compatível com esfera do ente.

Dimensão: PO
Severidade padrão: ALERTA

Lógica:
    O PO informado deve ser compatível com a esfera do ente configurada
    em settings.app.esfera. Para um ente municipal, o PO deve iniciar com
    o dígito "3" (esfera Municipal). PO iniciando com "1" (Federal) ou "2"
    (Estadual) é incompatível e gera ALERTA.

    Mapeamento esfera → prefixo esperado do PO:
        "municipal"  → "3"
        "estadual"   → "2"
        "federal"    → "1"

Referência:
    Leiaute MSC 2026 — campo PO; Portaria STN 642/2026; ref/regras_catalogo.md R039
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pandas as pd

from ranking_msc.rules.base import Rule, ic_mask_informada, register_rule

if TYPE_CHECKING:
    from ranking_msc.engine.executor import EngineContext

logger = logging.getLogger("ranking_msc")

_ESFERA_PREFIXO: dict[str, str] = {
    "municipal": "3",
    "estadual": "2",
    "federal": "1",
}


@register_rule
class R039(Rule):
    """Valida se o PO informado é compatível com a esfera do ente configurada."""

    rule_id = "R039"
    rule_name = "PO compatível com esfera do ente"
    dimensao = "PO"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Verifica se o 1º dígito do PO corresponde à esfera do ente.

        Args:
            df: DataFrame normalizado com colunas ``po`` e ``conta_contabil``.
            context: metadados da execução (inclui settings.app.esfera).

        Returns:
            DataFrame de pendências — uma linha por combinação conta/PO inválida.
        """
        _extra = {"regra_id": self.rule_id, "competencia": context.competencia}

        if "po" not in df.columns:
            return self.build_issues([])

        esfera = getattr(context.settings.app, "esfera", "municipal").lower()
        prefixo_esperado = _ESFERA_PREFIXO.get(esfera)
        if prefixo_esperado is None:
            logger.warning(
                "R039: esfera '%s' não reconhecida, regra ignorada. competência=%s",
                esfera,
                context.competencia,
                extra=_extra,
            )
            return self.build_issues([])

        df_com_po = df[["conta_contabil", "po"]].copy()
        df_com_po = df_com_po[ic_mask_informada(df_com_po["po"])]

        if df_com_po.empty:
            return self.build_issues([])

        df_unica = df_com_po.drop_duplicates(subset=["conta_contabil", "po"]).copy()
        df_unica["po_raw"] = df_unica["po"].astype(str).str.strip().str.zfill(5)

        mask_esfera = ~df_unica["po_raw"].str.startswith(prefixo_esperado)
        df_viol = df_unica[mask_esfera]

        if df_viol.empty:
            return self.build_issues([])

        conta_s = df_viol["conta_contabil"].astype(str)
        po_s = df_viol["po_raw"]

        issues_df = pd.DataFrame({
            "severidade": "ALERTA",
            "conta_contabil": conta_s.values,
            "descricao": (
                "PO '" + po_s + "' incompatível com esfera '" + esfera
                + "' (esperado prefixo '" + prefixo_esperado + "') para conta '"
                + conta_s + "'."
            ).values,
            "valor_esperado": "PO com prefixo '" + prefixo_esperado + "' (esfera " + esfera + ")",
            "valor_encontrado": po_s.values,
            "competencia": context.competencia,
        })

        logger.warning(
            "R039: %d pendência(s) de PO incompatível com esfera '%s'. competência=%s",
            len(issues_df),
            esfera,
            context.competencia,
            extra=_extra,
        )

        return self.build_issues(issues_df.to_dict("records"))
