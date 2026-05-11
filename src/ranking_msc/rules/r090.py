"""
Regra R090 — Receita orçamentária sem Natureza da Receita (SIGEF V14).

Dimensão: IC
Severidade padrão: ALERTA

Lógica:
    Contas cujo id_ic exige Natureza da Receita (NR) no IC_MAP devem ter NR
    preenchida.  São as contas das classes 5 e 6 classificadas pelo PCASP com
    id_ic=6.

    SE pcasp[conta].id_ic está em {id_ics que exigem NR}
       AND nr está vazio/ausente
    → ALERTA

    Valores considerados vazios: "", "0", "nan".

    Contas sem id_ic no PCASP ou com id_ic que não exige NR são ignoradas.

Referência:
    Ranking Siconfi 2026 — verificação V14; Portaria STN 642/2026.
    Depende de R020 (IC_MAP) e R026 (NR válida).
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

_IC_ALVO = "NR"
_ID_IC_COM_NR: frozenset[str] = frozenset(
    str(k) for k, v in IC_MAP.items() if _IC_ALVO in v
)


@register_rule
class R090(Rule):
    """Detecta contas de receita orçamentária sem Natureza da Receita obrigatória."""

    rule_id = "R090"
    rule_name = "Receita sem NR"
    dimensao = "IC"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Identifica contas com id_ic exigindo NR mas NR vazio.

        Args:
            df: DataFrame normalizado com colunas ``conta_contabil`` e ``nr``.
            context: metadados da execução.

        Returns:
            DataFrame de pendências — uma linha por conta violadora.
        """
        _extra = {"regra_id": self.rule_id, "competencia": context.competencia}

        if "nr" not in df.columns:
            return self.build_issues([])

        # 1. Carregar PCASP e obter id_ic
        pcasp_raw = load_pcasp(context.settings.paths.ref_dir)
        if "id_ic" not in pcasp_raw.columns:
            logger.warning(
                "R090: coluna 'id_ic' ausente em pcasp.csv — regra desativada.",
                extra=_extra,
            )
            return self.build_issues([])

        pcasp = pcasp_raw[["conta_contabil", "id_ic"]].copy()
        pcasp["id_ic"] = pcasp["id_ic"].astype(str).str.strip()

        # 2. Join para obter id_ic de cada conta
        msc = df[["conta_contabil", "nr"]].copy()
        merged = msc.merge(pcasp, on="conta_contabil", how="left")

        # 3. Manter apenas contas cujo id_ic exige NR
        merged = merged[merged["id_ic"].isin(_ID_IC_COM_NR)]
        if merged.empty:
            return self.build_issues([])

        # 4. Identificar NR vazia/ausente (None, pd.NA, NaN, "0", "NAN" etc.)
        violacoes = merged[~ic_mask_informada(merged["nr"])].copy()

        if violacoes.empty:
            return self.build_issues([])

        logger.warning(
            "R090: %d conta(s) de receita orçamentária sem NR. competência=%s",
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
                + "): NR obrigatória não preenchida (SIGEF V14)."
            ).values,
            "valor_esperado": "NR preenchida",
            "valor_encontrado": "NR vazia",
            "competencia": context.competencia,
        })

        return self.build_issues(issues_df.to_dict("records"))
