"""
Regra R090 — Receita (classe 4 / VPA) sem Natureza da Receita (SIGEF V14).

Dimensão: IC
Severidade padrão: ALERTA

Lógica:
    Contas de Variação Patrimonial Aumentativa (classe 4 — VPA) cujo id_ic
    exige Natureza da Receita (NR) no IC_MAP devem ter NR preenchido.

    SE classe(conta) == "4"
       AND ic_map[id_ic] contém "NR"
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
from ranking_msc.rules.base import Rule, register_rule

if TYPE_CHECKING:
    from ranking_msc.engine.executor import EngineContext

logger = logging.getLogger("ranking_msc")

_CLASSE_RECEITA = "4"
_IC_ALVO = "NR"
_ID_IC_COM_NR: frozenset[str] = frozenset(
    str(k) for k, v in IC_MAP.items() if _IC_ALVO in v
)
_IC_VAZIA: frozenset[str] = frozenset({"", "0", "nan"})


@register_rule
class R090(Rule):
    """Detecta contas de receita (classe 4) sem Natureza da Receita obrigatória."""

    rule_id = "R090"
    rule_name = "Receita sem NR"
    dimensao = "IC"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Identifica contas VPA com id_ic exigindo NR mas NR vazio.

        Args:
            df: DataFrame normalizado com colunas ``conta_contabil`` e ``nr``.
            context: metadados da execução.

        Returns:
            DataFrame de pendências — uma linha por conta violadora.
        """
        _extra = {"regra_id": self.rule_id, "competencia": context.competencia}

        if "nr" not in df.columns:
            return self.build_issues([])

        # 1. Filtrar contas da classe 4 (VPA)
        msc = df[["conta_contabil", "nr"]].copy()
        msc["_classe"] = msc["conta_contabil"].astype(str).str[:1]
        msc = msc[msc["_classe"] == _CLASSE_RECEITA]

        if msc.empty:
            return self.build_issues([])

        # 2. Carregar PCASP e obter id_ic
        pcasp_raw = load_pcasp(context.settings.paths.ref_dir)
        if "id_ic" not in pcasp_raw.columns:
            logger.warning(
                "R090: coluna 'id_ic' ausente em pcasp.csv — regra desativada.",
                extra=_extra,
            )
            return self.build_issues([])

        pcasp = pcasp_raw[["conta_contabil", "id_ic"]].copy()
        pcasp["id_ic"] = pcasp["id_ic"].astype(str).str.strip()

        # 3. Join para obter id_ic de cada conta
        merged = msc.merge(pcasp, on="conta_contabil", how="left")

        # 4. Manter apenas contas cujo id_ic exige NR
        merged = merged[merged["id_ic"].isin(_ID_IC_COM_NR)]
        if merged.empty:
            return self.build_issues([])

        # 5. Identificar NR vazia/ausente
        merged["nr"] = merged["nr"].astype(str).str.strip()
        violacoes = merged[merged["nr"].isin(_IC_VAZIA)].copy()

        if violacoes.empty:
            return self.build_issues([])

        logger.warning(
            "R090: %d conta(s) de receita (classe 4) sem NR. competência=%s",
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
                + "' (VPA/classe 4, id_ic="
                + id_ic_s
                + "): NR obrigatória não preenchida (SIGEF V14)."
            ).values,
            "valor_esperado": "NR preenchida",
            "valor_encontrado": "NR vazia",
            "competencia": context.competencia,
        })

        return self.build_issues(issues_df.to_dict("records"))
