"""
Regra R038 — IC informada não permitida para a conta (Conta × IC do leiaute).

Dimensão: IC
Severidade padrão: ERRO

Lógica:
    Para cada conta, verifica se algum tipo de IC informado não está no
    conjunto de tipos permitidos pelo leiaute MSC para aquela conta.

    Usa o ID_IC do PCASP + IC_MAP (ref_loader) para determinar o conjunto
    de tipos permitidos.  Se tipos_informados ⊄ tipos_permitidos → ERRO.

    Complementa R020 (que verifica igualdade completa IC_informado == IC_esperado).
    R038 foca especificamente em ICs presentes mas não permitidas para a conta.
    Contas sem ID_IC no PCASP ou com ID_IC=0 são ignoradas.

Referência:
    Leiaute MSC 2026 — campo ID_IC; Portaria STN 642/2026.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pandas as pd

from ranking_msc.io.ref_loader import IC_MAP, load_pcasp
from ranking_msc.rules.base import Rule, ic_mask_informada, register_rule

if TYPE_CHECKING:
    from ranking_msc.engine.executor import EngineContext

logger = logging.getLogger("ranking_msc")

# Colunas IC do DataFrame normalizado (lowercase)
_IC_COLS: tuple[str, ...] = ("po", "fp", "dc", "fs", "fr", "co", "nr", "nd", "ai")


@register_rule
class R038(Rule):
    """Verifica que os tipos de IC informados são permitidos para a conta."""

    rule_id = "R038"
    rule_name = "IC associada à conta correta"
    dimensao = "IC"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Detecta contas com tipos de IC não permitidos pelo leiaute.

        Args:
            df: DataFrame normalizado com colunas de FACT_MSC_COLUMNS.
            context: metadados da execução (competência, siconfi, settings).

        Returns:
            DataFrame de pendências — uma linha por conta com IC não permitida.
        """
        _extra = {"regra_id": self.rule_id, "competencia": context.competencia}

        if df.empty:
            return self.build_issues([])

        pcasp_df = load_pcasp(context.settings.paths.ref_dir)

        if "id_ic" not in pcasp_df.columns:
            return self.build_issues([])

        # Preparar mapa PCASP: conta_contabil → id_ic (int)
        pcasp_map = pcasp_df[["conta_contabil", "id_ic"]].copy()
        pcasp_map["conta_contabil"] = pcasp_map["conta_contabil"].astype(str)
        pcasp_map["id_ic"] = pd.to_numeric(pcasp_map["id_ic"], errors="coerce")
        pcasp_map = pcasp_map.dropna(subset=["id_ic"])
        pcasp_map["id_ic"] = pcasp_map["id_ic"].astype(int)
        pcasp_map = pcasp_map[pcasp_map["id_ic"].isin(IC_MAP)]

        ic_cols_presentes = [col for col in _IC_COLS if col in df.columns]
        if not ic_cols_presentes:
            return self.build_issues([])

        contas_unicas = df[["conta_contabil"] + ic_cols_presentes].drop_duplicates(
            subset=["conta_contabil"]
        ).copy()
        contas_unicas["conta_contabil"] = contas_unicas["conta_contabil"].astype(str)

        merged = contas_unicas.merge(pcasp_map, on="conta_contabil", how="inner")

        if merged.empty:
            return self.build_issues([])

        # Calcular máscara de IC informada por coluna (vetorizado)
        ic_informado_masks: dict[str, pd.Series] = {
            col.upper(): ic_mask_informada(merged[col])
            for col in ic_cols_presentes
        }
        ic_informado_df = pd.DataFrame(ic_informado_masks, index=merged.index)

        issues: list[dict[str, object]] = []

        for id_ic_val, group in merged.groupby("id_ic"):
            tipos_permitidos = set(IC_MAP[int(str(id_ic_val))])

            for idx in group.index:
                tipos_informados = {
                    col_upper
                    for col_upper in ic_informado_df.columns
                    if ic_informado_df.at[idx, col_upper]
                }

                tipos_invalidos = sorted(tipos_informados - tipos_permitidos)
                if not tipos_invalidos:
                    continue

                conta = str(merged.at[idx, "conta_contabil"])
                permitidos_str = (
                    ", ".join(sorted(tipos_permitidos)) if tipos_permitidos else "(nenhuma)"
                )
                issues.append({
                    "severidade": "ERRO",
                    "conta_contabil": conta,
                    "descricao": (
                        f"Conta '{conta}' (ID_IC={id_ic_val}): IC(s) não permitida(s) "
                        f"para esta conta: {', '.join(tipos_invalidos)}. "
                        f"Tipos permitidos: {permitidos_str}."
                    ),
                    "valor_esperado": permitidos_str,
                    "valor_encontrado": ", ".join(tipos_invalidos),
                    "competencia": context.competencia,
                })

        if issues:
            logger.warning(
                "R038: %d conta(s) com IC(s) não permitida(s). competencia=%s",
                len(issues),
                context.competencia,
                extra=_extra,
            )

        return self.build_issues(issues)
