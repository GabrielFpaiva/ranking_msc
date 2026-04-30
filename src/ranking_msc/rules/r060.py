"""
Regra R060 — FP coerente com indicador de superávit financeiro do PCASP.

Dimensão: PCASP
Severidade padrão: ALERTA

Lógica:
    Para cada conta contábil na MSC, verifica se o valor de FP é compatível
    com o indicador IND_SF definido no PCASP:
    - IND_SF == "Financeiro"           → FP deve ser "1"
    - IND_SF == "Permanente"           → FP deve ser "2"
    - IND_SF == "Financeiro/Permanente"→ aceita "1" ou "2" (sem ALERTA)
    Contas sem IND_SF definido no PCASP (NaN ou vazio) são ignoradas.

Referência:
    Leiaute MSC 2026 — PcaspEstendido2026 (IND_SF); Portaria STN 642/2026
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from ranking_msc.io.ref_loader import load_pcasp
from ranking_msc.rules.base import Rule, register_rule

if TYPE_CHECKING:
    from ranking_msc.engine.executor import EngineContext

logger = logging.getLogger("ranking_msc")

_IND_SF_FINANCEIRO = "Financeiro"
_IND_SF_PERMANENTE = "Permanente"
_IND_SF_AMBOS = "Financeiro/Permanente"
_FP_FINANCEIRO = "1"
_FP_PERMANENTE = "2"


@register_rule
class R060(Rule):
    """Verifica compatibilidade entre FP informado na MSC e IND_SF definido no PCASP."""

    rule_id = "R060"
    rule_name = "FP coerente com indicador PCASP"
    dimensao = "PCASP"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Detecta divergências entre FP da MSC e IND_SF do PCASP.

        Args:
            df: DataFrame normalizado com colunas ``conta_contabil`` e ``fp``.
            context: metadados da execução (competência, siconfi, settings).

        Returns:
            DataFrame de pendências — uma linha por combinação conta/FP divergente.
        """
        _extra = {"regra_id": self.rule_id, "competencia": context.competencia}

        # 1. Carregar PCASP e verificar presença de ind_sf (coluna opcional no loader)
        pcasp_raw = load_pcasp(context.settings.paths.ref_dir)
        if "ind_sf" not in pcasp_raw.columns:
            logger.warning(
                "R060: coluna 'ind_sf' ausente em pcasp.csv — regra desativada para esta execução. "
                "Verifique se o arquivo PCASP está atualizado (PcaspEstendido2026).",
                extra=_extra,
            )
            return self.build_issues([])

        pcasp = pcasp_raw[["conta_contabil", "ind_sf"]].copy()
        pcasp["ind_sf"] = pcasp["ind_sf"].str.strip()

        # 2. Left join para obter ind_sf por linha da MSC
        # Incluir po e fr quando disponíveis para identificar a linha nas issues
        _key_cols = ["conta_contabil", "po", "fr", "fp"]
        select_cols = [c for c in _key_cols if c in df.columns]
        merged = df[select_cols].merge(pcasp, on="conta_contabil", how="left")

        # 3. Ignorar contas sem match no PCASP (R010 trata) e ind_sf vazio
        merged = merged[merged["ind_sf"].notna() & (merged["ind_sf"] != "")]

        if merged.empty:
            return self.build_issues([])

        # 4. Normalizar fp — normalize_ic usa "" para IC ausente, mas DataFrames
        #    externos podem conter NaN; NaN != "1" seria True gerando "nan" na issue
        merged["fp"] = merged["fp"].fillna("")

        # 5. Ignorar ind_sf == "Financeiro/Permanente" (aceita FP=1 ou FP=2)
        merged = merged[merged["ind_sf"] != _IND_SF_AMBOS]

        if merged.empty:
            return self.build_issues([])

        # 6. Detectar violações via masks vetorizadas
        mask_financeiro = (
            (merged["ind_sf"] == _IND_SF_FINANCEIRO)
            & (merged["fp"] != _FP_FINANCEIRO)
        )
        mask_permanente = (
            (merged["ind_sf"] == _IND_SF_PERMANENTE)
            & (merged["fp"] != _FP_PERMANENTE)
        )
        violacoes = merged[mask_financeiro | mask_permanente].copy()

        if violacoes.empty:
            return self.build_issues([])

        logger.warning(
            "R060: %d linha(s) com FP incompatível com IND_SF do PCASP. competência=%s",
            len(violacoes),
            context.competencia,
            extra=_extra,
        )

        # 7. Construção vetorizada de issues — substitui iterrows()
        conta_s = violacoes["conta_contabil"].astype(str)
        ind_s = violacoes["ind_sf"].astype(str)
        fp_s = violacoes["fp"].astype(str)
        fp_esp_s = pd.Series(
            np.where(
                violacoes["ind_sf"] == _IND_SF_FINANCEIRO,
                _FP_FINANCEIRO,
                _FP_PERMANENTE,
            ),
            index=violacoes.index,
        )

        # Construir info contextual de po/fr quando disponíveis
        po_info = pd.Series("", index=violacoes.index)
        if "po" in violacoes.columns:
            po_info = ", po=" + violacoes["po"].astype(str)
        fr_info = pd.Series("", index=violacoes.index)
        if "fr" in violacoes.columns:
            fr_info = ", fr=" + violacoes["fr"].astype(str)

        issues_df = pd.DataFrame({
            "severidade": "ALERTA",
            "conta_contabil": conta_s.values,
            "descricao": (
                "Conta '" + conta_s + "'" + po_info + fr_info
                + ": IND_SF=" + ind_s + " mas FP='" + fp_s
                + "' (esperado: '" + fp_esp_s + "')."
            ).values,
            "valor_esperado": fp_esp_s.values,
            "valor_encontrado": fp_s.values,
            "competencia": context.competencia,
        })

        return self.build_issues(issues_df.to_dict("records"))
