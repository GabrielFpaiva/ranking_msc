"""
Regra R084 — Conta Financeira (FP=1) sem FR detalhada (SIGEF V11).

Dimensão: PCASP
Severidade padrão: ERRO

Lógica:
    Contas com FP=1 (Financeiro) devem ter Fonte de Recursos (FR) preenchida
    quando o ID_IC da conta no PCASP inclui FR como campo obrigatório (ID_IC
    em {4, 5, 6, 7, 8, 9}).

    Contas financeiras sem FR impede identificação da origem dos recursos.
    Vai além de R020 pois verifica o cruzamento FP×FR independente do layout.

    PARA CADA registro WHERE fp == "1":
        SE fr não está informada:
            id_ic = pcasp[conta_contabil].id_ic
            SE id_ic IN {"4","5","6","7","8","9"} → ALERTA

Referência:
    Ranking Siconfi 2026 — verificação V11; R022, R024; R084
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pandas as pd

from ranking_msc.io.ref_loader import load_pcasp
from ranking_msc.rules.base import Rule, ic_mask_informada, register_rule

if TYPE_CHECKING:
    from ranking_msc.engine.executor import EngineContext

logger = logging.getLogger("ranking_msc")

# ID_IC que exigem FR como campo obrigatório (conforme IC_MAP em ref_loader)
_ID_IC_COM_FR: frozenset[str] = frozenset({"4", "5", "6", "7", "8", "9"})

_FP_FINANCEIRO = "1"


@register_rule
class R084(Rule):
    """Detecta contas Financeiras (FP=1) sem Fonte de Recursos preenchida."""

    rule_id = "R084"
    rule_name = "Conta Financeira sem FR"
    dimensao = "PCASP"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Identifica linhas com FP=1 sem FR quando id_ic obriga FR.

        Args:
            df: DataFrame normalizado com colunas ``conta_contabil``, ``fp`` e ``fr``.
            context: metadados da execução (competência, siconfi, settings).

        Returns:
            DataFrame de pendências — uma linha por registro violador.
        """
        _extra = {"regra_id": self.rule_id, "competencia": context.competencia}

        # Colunas obrigatórias no df
        for col in ("fp", "fr", "conta_contabil"):
            if col not in df.columns:
                logger.warning(
                    "R084: coluna '%s' ausente no DataFrame — regra desativada.",
                    col,
                    extra=_extra,
                )
                return self.build_issues([])

        # Carrega PCASP para obter id_ic
        pcasp_raw = load_pcasp(context.settings.paths.ref_dir)
        if "id_ic" not in pcasp_raw.columns:
            logger.warning(
                "R084: coluna 'id_ic' ausente em pcasp.csv — regra desativada. "
                "Verifique se o PCASP está atualizado (PcaspEstendido2026).",
                extra=_extra,
            )
            return self.build_issues([])

        pcasp = pcasp_raw[["conta_contabil", "id_ic"]].copy()
        pcasp["id_ic"] = pcasp["id_ic"].astype(str).str.strip()

        # Filtra linhas com FP=1 (Financeiro)
        msc = df[["conta_contabil", "fp", "fr"]].copy()
        msc["fp"] = msc["fp"].fillna("").astype(str).str.strip()
        financeiras = msc[msc["fp"] == _FP_FINANCEIRO]

        if financeiras.empty:
            return self.build_issues([])

        # Identifica linhas sem FR (usando ic_mask_informada vetorizado)
        fr_col = financeiras["fr"].fillna("").astype(str).str.lower()
        sem_fr = financeiras[~ic_mask_informada(fr_col)]

        if sem_fr.empty:
            return self.build_issues([])

        # Join com PCASP para obter id_ic
        merged = sem_fr.merge(pcasp, on="conta_contabil", how="left")
        merged["id_ic"] = merged["id_ic"].fillna("").astype(str).str.strip()

        # Filtra apenas contas onde id_ic exige FR
        violacoes = merged[merged["id_ic"].isin(_ID_IC_COM_FR)].copy()

        if violacoes.empty:
            return self.build_issues([])

        logger.warning(
            "R084: %d linha(s) com FP=1 sem FR onde id_ic obriga FR. competência=%s",
            len(violacoes),
            context.competencia,
            extra=_extra,
        )

        conta_s = violacoes["conta_contabil"].astype(str)
        id_ic_s = violacoes["id_ic"].astype(str)

        issues_df = pd.DataFrame({
            "severidade": "ERRO",
            "conta_contabil": conta_s.values,
            "descricao": (
                "Conta '"
                + conta_s
                + "' (FP=1/Financeiro, ID_IC="
                + id_ic_s
                + "): FR não preenchida — conta financeira sem Fonte de Recursos (SIGEF V11)."
            ).values,
            "valor_esperado": "fr preenchida",
            "valor_encontrado": "fr vazia",
            "competencia": context.competencia,
        })

        return self.build_issues(issues_df.to_dict("records"))
