"""Regra R080 — CONTA tem 9 dígitos numéricos.

Categoria: Formato
Severidade padrão: ERRO
Prioridade: P0-Blocker
Dependência: R001

Lógica:
    O campo `conta_contabil` deve ter exatamente 9 dígitos numéricos.
    Se len(conta_contabil) != 9 ou não for totalmente numérico, é ERRO.

Referência:
    Leiaute MSC 2026 — Portaria STN 642/2026, Anexo II (campo CONTA)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pandas as pd

from ranking_msc.rules.base import Rule, register_rule

if TYPE_CHECKING:
    from ranking_msc.engine.executor import EngineContext

logger = logging.getLogger("ranking_msc")


@register_rule
class R080(Rule):
    """Valida que o campo conta_contabil tem exatamente 9 dígitos numéricos."""

    rule_id = "R080"
    rule_name = "Formato de conta — 9 dígitos numéricos"
    dimensao = "Formato"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Verifica se conta_contabil tem exatamente 9 dígitos numéricos.

        Args:
            df: DataFrame normalizado com coluna ``conta_contabil``.
            context: metadados da execução.

        Returns:
            DataFrame de pendências — uma linha por conta com formato inválido.
        """
        _extra = {"regra_id": self.rule_id, "competencia": context.competencia}

        if "conta_contabil" not in df.columns:
            return self.build_issues([])

        # Filtrar linhas onde conta_contabil não é NaN/None
        contas = df["conta_contabil"].dropna().astype(str).str.strip()
        contas_invalidas = contas[~(contas.str.len() == 9) | ~(contas.str.isdigit())]

        # Uma pendência por conta distinta com formato inválido
        contas_invalidas_unicas = contas_invalidas.unique()

        issues: list[dict[str, object]] = []

        for conta in contas_invalidas_unicas:
            issues.append({
                "severidade": "ERRO",
                "conta_contabil": conta,
                "descricao": (
                    f"Conta '{conta}' tem formato inválido: esperado 9 dígitos numéricos, "
                    f"encontrado '{conta}' ({len(conta)} caractere(s))."
                ),
                "valor_esperado": "9 dígitos numéricos (ex: 111110200)",
                "valor_encontrado": conta,
                "competencia": context.competencia,
            })

        if issues:
            logger.warning(
                "R080: %d conta(s) com formato inválido. competência=%s",
                len(issues),
                context.competencia,
                extra=_extra,
            )

        return self.build_issues(issues)
