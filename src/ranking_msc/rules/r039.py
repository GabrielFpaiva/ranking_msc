"""Regra R039 — PO compatível com esfera do ente.

Dimensão: PO
Severidade padrão: ALERTA

Lógica:
    O PO informado deve ser compatível com a esfera do ente configurada em
    settings.app.esfera. Cada esfera tem um conjunto explícito de códigos PO
    permitidos, derivado da tabela_po.csv mais exceções documentadas:

    Municipal:
        - Todos os códigos com prefixo "3" (esfera municipal própria).
        - Códigos cross-esfera documentados como municipais:
          {10131, 10132} (Município Executivo/Legislativo no range Federal),
          {20231, 20232} (Município Executivo/Legislativo no range Estadual).
        - Estes códigos cross-esfera aparecem em arquivos MSC reais de
          municípios (ver ref/amostras/msc_2026-01.csv e ref/regras_catalogo.md
          R039/R083).

    Estadual:
        - Códigos com prefixo "2", exceto {20231, 20232} (que são municipais).

    Federal:
        - Códigos com prefixo "1", exceto {10131, 10132} (que são municipais).

Referência:
    Leiaute MSC 2026 — campo PO; Portaria STN 642/2026;
    ref/regras_catalogo.md R039 e R083 (PO=10131 para município).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pandas as pd

from ranking_msc.io.ref_loader import load_tabela_po
from ranking_msc.rules.base import Rule, ic_mask_informada, register_rule

if TYPE_CHECKING:
    from ranking_msc.engine.executor import EngineContext

logger = logging.getLogger("ranking_msc")

# Códigos PO que representam o Município (Executivo/Legislativo) mesmo
# aparecendo em ranges nominalmente Federal (1xxxx) ou Estadual (2xxxx).
_PO_CROSS_MUNICIPAL: frozenset[str] = frozenset({"10131", "10132", "20231", "20232"})


def _allowed_po_codes(esfera: str, todos_pos: set[str]) -> set[str]:
    """Calcula o conjunto de códigos PO válidos para uma dada esfera.

    Args:
        esfera: "municipal", "estadual" ou "federal".
        todos_pos: conjunto de todos os códigos PO da tabela oficial (zfill 5).

    Returns:
        Conjunto de códigos PO permitidos para a esfera informada.
    """
    if esfera == "municipal":
        return {c for c in todos_pos if c.startswith("3")} | _PO_CROSS_MUNICIPAL
    if esfera == "estadual":
        return {c for c in todos_pos if c.startswith("2")} - _PO_CROSS_MUNICIPAL
    if esfera == "federal":
        return {c for c in todos_pos if c.startswith("1")} - _PO_CROSS_MUNICIPAL
    return set()


@register_rule
class R039(Rule):
    """Valida se o PO informado é compatível com a esfera do ente configurada."""

    rule_id = "R039"
    rule_name = "PO compatível com esfera do ente"
    dimensao = "PO"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Verifica se cada PO está no conjunto permitido para a esfera.

        Args:
            df: DataFrame normalizado com colunas ``po`` e ``conta_contabil``.
            context: metadados da execução (inclui settings.app.esfera).

        Returns:
            DataFrame de pendências — uma linha por combinação conta/PO inválida.
        """
        _extra = {"regra_id": self.rule_id, "competencia": context.competencia}

        if "po" not in df.columns:
            return self.build_issues([])

        esfera_raw = getattr(context.settings.app, "esfera", "municipal")
        if not isinstance(esfera_raw, str):
            logger.warning(
                "R039: esfera não-string em settings (%r), regra ignorada. competência=%s",
                esfera_raw,
                context.competencia,
                extra=_extra,
            )
            return self.build_issues([])
        esfera = esfera_raw.strip().lower()
        if esfera not in {"municipal", "estadual", "federal"}:
            logger.warning(
                "R039: esfera '%s' não reconhecida, regra ignorada. competência=%s",
                esfera,
                context.competencia,
                extra=_extra,
            )
            return self.build_issues([])

        tabela_po = load_tabela_po(context.settings.paths.ref_dir)
        todos_pos: set[str] = set(
            tabela_po["codigo"].astype(str).str.strip().str.zfill(5)
        )
        permitidos = _allowed_po_codes(esfera, todos_pos)

        df_com_po = df[["conta_contabil", "po"]].copy()
        df_com_po = df_com_po[ic_mask_informada(df_com_po["po"])]

        if df_com_po.empty:
            return self.build_issues([])

        df_unica = df_com_po.drop_duplicates(subset=["conta_contabil", "po"]).copy()
        df_unica["po_raw"] = df_unica["po"].astype(str).str.strip().str.zfill(5)

        # Apenas POs que existem na tabela mas estão fora da esfera —
        # POs ausentes da tabela são tratados por R021.
        mask_na_tabela = df_unica["po_raw"].isin(todos_pos)
        mask_fora_esfera = ~df_unica["po_raw"].isin(permitidos)
        df_viol = df_unica[mask_na_tabela & mask_fora_esfera]

        if df_viol.empty:
            return self.build_issues([])

        conta_s = df_viol["conta_contabil"].astype(str)
        po_s = df_viol["po_raw"]

        issues_df = pd.DataFrame({
            "severidade": "ALERTA",
            "conta_contabil": conta_s.values,
            "descricao": (
                "PO '" + po_s + "' incompatível com esfera '" + esfera
                + "' para conta '" + conta_s + "'."
            ).values,
            "valor_esperado": "PO permitido para esfera " + esfera,
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
