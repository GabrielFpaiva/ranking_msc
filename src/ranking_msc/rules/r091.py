"""
Regra R091 — Despesa orçamentária sem Natureza da Despesa (SIGEF V15).

Dimensão: IC
Severidade padrão: ALERTA

Lógica:
    Contas cujo id_ic exige Natureza da Despesa (ND) no IC_MAP devem ter ND
    preenchida.  São as contas das classes 5, 6, 7 e 8 classificadas pelo PCASP
    com id_ic=7 ou 9.

    SE pcasp[conta].id_ic está em {id_ics que exigem ND}
       AND nd está vazio/ausente
    → ALERTA

    Valores considerados vazios: "", "0", "nan".

    Contas sem id_ic no PCASP ou com id_ic que não exige ND são ignoradas.

Referência:
    Ranking Siconfi 2026 — verificação V15; Portaria STN 642/2026.
    Depende de R020 (IC_MAP) e R027 (ND válida).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pandas as pd

from ranking_msc.io.ref_loader import IC_MAP, load_pcasp
from ranking_msc.rules.base import Rule, register_rule

if TYPE_CHECKING:
    from ranking_msc.engine.executor import EngineContext

logger = logging.getLogger("ranking_msc")

_IC_ALVO = "ND"
_ID_IC_COM_ND: frozenset[str] = frozenset(
    str(k) for k, v in IC_MAP.items() if _IC_ALVO in v
)
_IC_VAZIA: frozenset[str] = frozenset({"", "0", "nan"})


@register_rule
class R091(Rule):
    """Detecta contas de despesa orçamentária sem Natureza da Despesa obrigatória."""

    rule_id = "R091"
    rule_name = "Despesa sem ND"
    dimensao = "IC"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Identifica contas com id_ic exigindo ND mas ND vazia.

        Args:
            df: DataFrame normalizado com colunas ``conta_contabil`` e ``nd``.
            context: metadados da execução.

        Returns:
            DataFrame de pendências — uma linha por conta violadora.
        """
        _extra = {"regra_id": self.rule_id, "competencia": context.competencia}

        if "nd" not in df.columns:
            return self.build_issues([])

        # 1. Carregar PCASP e obter id_ic
        pcasp_raw = load_pcasp(context.settings.paths.ref_dir)
        if "id_ic" not in pcasp_raw.columns:
            logger.warning(
                "R091: coluna 'id_ic' ausente em pcasp.csv — regra desativada.",
                extra=_extra,
            )
            return self.build_issues([])

        pcasp = pcasp_raw[["conta_contabil", "id_ic"]].copy()
        pcasp["id_ic"] = pcasp["id_ic"].astype(str).str.strip()

        # 2. Join para obter id_ic de cada conta
        msc = df[["conta_contabil", "nd"]].copy()
        merged = msc.merge(pcasp, on="conta_contabil", how="left")

        # 3. Manter apenas contas cujo id_ic exige ND
        merged = merged[merged["id_ic"].isin(_ID_IC_COM_ND)]
        if merged.empty:
            return self.build_issues([])

        # 4. Identificar ND vazia/ausente
        merged["nd"] = merged["nd"].astype(str).str.strip()
        violacoes = merged[merged["nd"].isin(_IC_VAZIA)].copy()

        if violacoes.empty:
            return self.build_issues([])

        logger.warning(
            "R091: %d conta(s) de despesa orçamentária sem ND. competência=%s",
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
                + "' (despesa orçamentária, id_ic="
                + id_ic_s
                + "): ND obrigatória não preenchida (SIGEF V15)."
            ).values,
            "valor_esperado": "ND preenchida",
            "valor_encontrado": "ND vazia",
            "competencia": context.competencia,
        })

        return self.build_issues(issues_df.to_dict("records"))
