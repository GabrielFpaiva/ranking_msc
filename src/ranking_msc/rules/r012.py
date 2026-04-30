"""Regra R012 — Conta está Ativa no PCASP.

Categoria: PCASP
Severidade padrão: ALERTA

Lógica:
    Contas com status != "Ativa" no PCASP não devem constar no MSC.
    Pode indicar uso de plano de contas desatualizado. A verificação
    é feita via join com a tabela PcaspEstendido2026.

Referência:
    Leiaute MSC 2026 — PcaspEstendido2026 col STATUS; Portaria STN 642/2026
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
class R012(Rule):
    """Valida que toda conta_contabil informada está ativa no PCASP."""

    rule_id = "R012"
    rule_name = "Conta está Ativa no PCASP"
    dimensao = "PCASP"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Detecta contas inativas (status != 'Ativa') na MSC.

        Args:
            df: DataFrame normalizado com coluna ``conta_contabil``.
            context: metadados da execução (competência, siconfi, settings).

        Returns:
            DataFrame de pendências — uma linha por conta inativa encontrada.
        """
        _extra = {"regra_id": self.rule_id, "competencia": context.competencia}

        pcasp_df = load_pcasp(context.settings.paths.ref_dir)

        if "status" not in pcasp_df.columns:
            logger.warning(
                "R012: coluna 'status' ausente no PCASP — regra ignorada. competência=%s",
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
            pcasp_df[["conta_contabil", "status"]].assign(
                conta_contabil=lambda x: x["conta_contabil"].astype(str),
                status=lambda x: x["status"].astype(str).str.strip(),
            ),
            on="conta_contabil",
            how="inner",
        )

        inativas = merged[merged["status"] != "Ativa"]

        if inativas.empty:
            return self.build_issues([])

        logger.warning(
            "R012: %d conta(s) inativa(s) encontrada(s). competência=%s",
            len(inativas),
            context.competencia,
            extra=_extra,
        )

        conta_s = inativas["conta_contabil"].astype(str)
        status_s = inativas["status"].astype(str)
        issues_df = pd.DataFrame({
            "severidade": "ALERTA",
            "conta_contabil": conta_s.values,
            "descricao": (
                "Conta '" + conta_s + "' está inativa no PCASP (status: '"
                + status_s + "') — possível plano de contas desatualizado."
            ).values,
            "valor_esperado": "status == Ativa",
            "valor_encontrado": status_s.values,
            "competencia": context.competencia,
        })

        return self.build_issues(issues_df.to_dict("records"))
