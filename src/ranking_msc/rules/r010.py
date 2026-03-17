"""Regra R010 — Conta existe no PCASP Estendido 2026.

Categoria: PCASP
Severidade padrão: ERRO
Lógica:
    Toda conta_contabil informada na MSC deve existir na tabela
    PcaspEstendido2026. Contas ausentes indicam erro de digitação
    ou uso de versão desatualizada do PCASP.
Referência:
    Leiaute MSC 2026 — PcaspEstendido2026; Portaria STN 642/2026
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


@register_rule
class R010(Rule):
    """Valida existência de conta_contabil no PCASP Estendido 2026."""

    rule_id = "R010"
    rule_name = "Conta existe no PCASP Estendido 2026"
    dimensao = "PCASP"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Verifica se todas as contas informadas existem no PCASP.

        Args:
            df: DataFrame normalizado com coluna ``conta_contabil``.
            context: metadados da execução (competência, siconfi, settings).

        Returns:
            DataFrame de pendências — uma linha por conta inválida encontrada.
        """
        pcasp_df = load_pcasp(context.settings.paths.ref_dir)
        contas_validas: set[str] = set(pcasp_df["conta_contabil"].astype(str))

        contas_invalidas = (
            df[["conta_contabil"]]
            .drop_duplicates()
            .loc[lambda x: ~x["conta_contabil"].astype(str).isin(contas_validas)]
        )

        if contas_invalidas.empty:
            return self.build_issues([])

        logger.warning(
            "R010: %d conta(s) não encontrada(s) no PCASP. competencia=%s",
            len(contas_invalidas),
            context.competencia,
        )

        issues: list[dict[str, object]] = [
            {
                "severidade": "ERRO",
                "conta_contabil": row["conta_contabil"],
                "descricao": (
                    f"Conta '{row['conta_contabil']}' não encontrada "
                    "no PCASP Estendido 2026."
                ),
                "valor_esperado": "Conta existente no PCASP",
                "valor_encontrado": str(row["conta_contabil"]),
                "competencia": context.competencia,
            }
            for _, row in contas_invalidas.iterrows()
        ]

        return self.build_issues(issues)
