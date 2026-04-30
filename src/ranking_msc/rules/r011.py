"""Regra R011 — Conta é de último nível (analítica).

Categoria: PCASP
Severidade padrão: ERRO

Lógica:
    O MSC deve conter apenas contas de último nível (analíticas).
    Contas sintéticas (nivel == "Superior" no PCASP) não devem ser
    informadas. A verificação é feita via join com a tabela PcaspEstendido2026.

Referência:
    Leiaute MSC 2026 — PcaspEstendido2026 col NIVEL; Portaria STN 642/2026
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
class R011(Rule):
    """Valida que toda conta_contabil informada é de último nível (analítica)."""

    rule_id = "R011"
    rule_name = "Conta é de último nível"
    dimensao = "PCASP"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Detecta contas sintéticas (nivel != 'Último') na MSC.

        Args:
            df: DataFrame normalizado com coluna ``conta_contabil``.
            context: metadados da execução (competência, siconfi, settings).

        Returns:
            DataFrame de pendências — uma linha por conta sintética encontrada.
        """
        _extra = {"regra_id": self.rule_id, "competencia": context.competencia}

        pcasp_df = load_pcasp(context.settings.paths.ref_dir)

        if "nivel" not in pcasp_df.columns:
            logger.warning(
                "R011: coluna 'nivel' ausente no PCASP — regra ignorada. competência=%s",
                context.competencia,
                extra=_extra,
            )
            return self.build_issues([])

        contas_unicas = (
            df[["conta_contabil"]]
            .drop_duplicates()
            .assign(conta_contabil=lambda x: x["conta_contabil"].astype(str))
        )

        # inner join: contas ausentes no PCASP são responsabilidade de R010 e
        # não devem gerar pendências duplicadas aqui.
        merged = contas_unicas.merge(
            pcasp_df[["conta_contabil", "nivel"]].assign(
                conta_contabil=lambda x: x["conta_contabil"].astype(str),
                nivel=lambda x: x["nivel"].astype(str).str.strip(),
            ),
            on="conta_contabil",
            how="inner",
        )

        sinteticas = merged[merged["nivel"] != "Último"]

        if sinteticas.empty:
            return self.build_issues([])

        logger.warning(
            "R011: %d conta(s) sintética(s) encontrada(s). competência=%s",
            len(sinteticas),
            context.competencia,
            extra=_extra,
        )

        conta_s = sinteticas["conta_contabil"].astype(str)
        issues_df = pd.DataFrame({
            "severidade": "ERRO",
            "conta_contabil": conta_s.values,
            "descricao": (
                "Conta '" + conta_s + "' é sintética (nível Superior)"
                " e não deve ser informada na MSC. Use apenas contas analíticas."
            ).values,
            "valor_esperado": "nivel == Último (conta analítica)",
            "valor_encontrado": sinteticas["nivel"].astype(str).values,
            "competencia": context.competencia,
        })

        return self.build_issues(issues_df.to_dict("records"))
