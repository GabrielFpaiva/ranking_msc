"""
Regra R089 — Receita orçamentária sem Fonte de Recurso (SIGEF V13).

Dimensão: IC
Severidade padrão: ALERTA

Lógica:
    Contas cujo id_ic é 6 (leiaute de receita orçamentária e deduções)
    devem ter FR preenchido.  São as contas das classes 5 e 6 que o PCASP
    classifica como receita orçamentária.

    SE pcasp[conta].id_ic == 6
       AND fr está vazio/ausente
    → ALERTA

    Valores considerados vazios: "", "0", "nan".

    Contas sem id_ic no PCASP ou com id_ic ≠ 6 são ignoradas.

Referência:
    Ranking Siconfi 2026 — verificação V13; Portaria STN 642/2026.
    Depende de R020 (IC_MAP) e R024 (FR válido).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pandas as pd

from ranking_msc.io.ref_loader import load_pcasp
from ranking_msc.rules.base import Rule, register_rule

if TYPE_CHECKING:
    from ranking_msc.engine.executor import EngineContext

logger = logging.getLogger("ranking_msc")

_ID_IC_RECEITA: frozenset[str] = frozenset({"6"})
_IC_VAZIA: frozenset[str] = frozenset({"", "0", "nan"})


@register_rule
class R089(Rule):
    """Detecta contas de receita orçamentária (id_ic=6) sem Fonte de Recurso."""

    rule_id = "R089"
    rule_name = "Receita sem FR"
    dimensao = "IC"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Identifica contas com id_ic=6 que exigem FR mas FR está vazio.

        Args:
            df: DataFrame normalizado com colunas ``conta_contabil`` e ``fr``.
            context: metadados da execução.

        Returns:
            DataFrame de pendências — uma linha por conta violadora.
        """
        _extra = {"regra_id": self.rule_id, "competencia": context.competencia}

        if "fr" not in df.columns:
            return self.build_issues([])

        # 1. Carregar PCASP e obter id_ic
        pcasp_raw = load_pcasp(context.settings.paths.ref_dir)
        if "id_ic" not in pcasp_raw.columns:
            logger.warning(
                "R089: coluna 'id_ic' ausente em pcasp.csv — regra desativada.",
                extra=_extra,
            )
            return self.build_issues([])

        pcasp = pcasp_raw[["conta_contabil", "id_ic"]].copy()
        pcasp["id_ic"] = pcasp["id_ic"].astype(str).str.strip()

        # 2. Join para obter id_ic de cada conta
        msc = df[["conta_contabil", "fr"]].copy()
        merged = msc.merge(pcasp, on="conta_contabil", how="left")

        # 3. Manter apenas contas cujo id_ic é de receita orçamentária (6)
        merged = merged[merged["id_ic"].isin(_ID_IC_RECEITA)]
        if merged.empty:
            return self.build_issues([])

        # 4. Identificar FR vazio/ausente
        merged["fr"] = merged["fr"].astype(str).str.strip()
        violacoes = merged[merged["fr"].isin(_IC_VAZIA)].copy()

        if violacoes.empty:
            return self.build_issues([])

        logger.warning(
            "R089: %d conta(s) de receita orçamentária (id_ic=6) sem FR. competência=%s",
            len(violacoes),
            context.competencia,
            extra=_extra,
        )

        conta_s = violacoes["conta_contabil"].astype(str)
        id_ic_s = violacoes["id_ic"].astype(str)

        issues_df = pd.DataFrame({
            "severidade": "ALERTA",
            "conta_contabil": conta_s.values,
            "descricao": (
                "Conta '"
                + conta_s
                + "' (receita orçamentária, id_ic="
                + id_ic_s
                + "): FR obrigatório não preenchido (SIGEF V13)."
            ).values,
            "valor_esperado": "FR preenchido",
            "valor_encontrado": "FR vazio",
            "competencia": context.competencia,
        })

        return self.build_issues(issues_df.to_dict("records"))
