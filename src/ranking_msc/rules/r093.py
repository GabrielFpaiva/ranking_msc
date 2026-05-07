"""
Regra R093 — Despesa (classe 3 / VPD) sem Fonte de Recurso (SIGEF V17).

Dimensão: IC
Severidade padrão: ALERTA

Lógica:
    Contas de Variação Patrimonial Diminutiva (classe 3 — VPD) cujo id_ic
    exige Fonte de Recurso (FR) no IC_MAP devem ter FR preenchido.

    SE classe(conta) == "3"
       AND ic_map[id_ic] contém "FR"
       AND fr está vazio/ausente
    → ALERTA

    Valores considerados vazios: "", "0", "nan".

    Contas sem id_ic no PCASP ou com id_ic que não exige FR são ignoradas.

Referência:
    Ranking Siconfi 2026 — verificação V17; Portaria STN 642/2026.
    Depende de R020 (IC_MAP) e R024 (FR válida).
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

_CLASSE_DESPESA = "3"
_IC_ALVO = "FR"
_ID_IC_COM_FR: frozenset[str] = frozenset(
    str(k) for k, v in IC_MAP.items() if _IC_ALVO in v
)
_IC_VAZIA: frozenset[str] = frozenset({"", "0", "nan"})


@register_rule
class R093(Rule):
    """Detecta contas de despesa (classe 3) sem Fonte de Recurso obrigatória."""

    rule_id = "R093"
    rule_name = "Despesa sem FR"
    dimensao = "IC"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Identifica contas VPD com id_ic exigindo FR mas FR vazio.

        Args:
            df: DataFrame normalizado com colunas ``conta_contabil`` e ``fr``.
            context: metadados da execução.

        Returns:
            DataFrame de pendências — uma linha por conta violadora.
        """
        _extra = {"regra_id": self.rule_id, "competencia": context.competencia}

        if "fr" not in df.columns:
            return self.build_issues([])

        # 1. Filtrar contas da classe 3 (VPD)
        msc = df[["conta_contabil", "fr"]].copy()
        msc["_classe"] = msc["conta_contabil"].astype(str).str[:1]
        msc = msc[msc["_classe"] == _CLASSE_DESPESA]

        if msc.empty:
            return self.build_issues([])

        # 2. Carregar PCASP e obter id_ic
        pcasp_raw = load_pcasp(context.settings.paths.ref_dir)
        if "id_ic" not in pcasp_raw.columns:
            logger.warning(
                "R093: coluna 'id_ic' ausente em pcasp.csv — regra desativada.",
                extra=_extra,
            )
            return self.build_issues([])

        pcasp = pcasp_raw[["conta_contabil", "id_ic"]].copy()
        pcasp["id_ic"] = pcasp["id_ic"].astype(str).str.strip()

        # 3. Join para obter id_ic de cada conta
        merged = msc.merge(pcasp, on="conta_contabil", how="left")

        # 4. Manter apenas contas cujo id_ic exige FR
        merged = merged[merged["id_ic"].isin(_ID_IC_COM_FR)]
        if merged.empty:
            return self.build_issues([])

        # 5. Identificar FR vazio/ausente
        merged["fr"] = merged["fr"].astype(str).str.strip()
        violacoes = merged[merged["fr"].isin(_IC_VAZIA)].copy()

        if violacoes.empty:
            return self.build_issues([])

        logger.warning(
            "R093: %d conta(s) de despesa (classe 3) sem FR. competência=%s",
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
                + "' (VPD/classe 3, id_ic="
                + id_ic_s
                + "): FR obrigatório não preenchido (SIGEF V17)."
            ).values,
            "valor_esperado": "FR preenchido",
            "valor_encontrado": "FR vazio",
            "competencia": context.competencia,
        })

        return self.build_issues(issues_df.to_dict("records"))
