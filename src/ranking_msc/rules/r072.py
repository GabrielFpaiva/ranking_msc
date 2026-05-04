"""
Regra R072 — Conta com muitos registros (outlier estatístico).

Dimensão: Qualidade
Severidade padrão: INFO

Lógica:
    Conta com quantidade de registros acima de média + 3 desvios padrão
    pode indicar duplicação parcial na exportação.

    contagem = df.groupby("conta_contabil").size()
    SE contagem[conta] > media + 3 * std → INFO

    Guarda: se < 2 contas distintas ou std == 0, não há outliers possíveis.

Referência:
    ref/regras_catalogo.md — R072; Portaria STN 642/2026
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

import pandas as pd

from ranking_msc.rules.base import Rule, register_rule

if TYPE_CHECKING:
    from ranking_msc.engine.executor import EngineContext


@register_rule
class R072(Rule):
    """Detecta contas com contagem de registros estatisticamente atípica."""

    rule_id = "R072"
    rule_name = "Registros atípicos por conta"
    dimensao = "Qualidade"
    is_scoring: ClassVar[bool] = False

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Identifica contas cujo número de registros excede média + 3σ.

        Args:
            df: DataFrame normalizado com coluna ``conta_contabil``.
            context: metadados da execução.

        Returns:
            DataFrame de pendências — uma linha por conta atípica.
        """
        if df.empty:
            return self.build_issues([])

        contagem = df.groupby("conta_contabil").size()

        if len(contagem) < 2:
            return self.build_issues([])

        media = contagem.mean()
        desvio = contagem.std(ddof=1)

        if desvio == 0:
            return self.build_issues([])

        limiar = media + 3 * desvio
        outliers = contagem[contagem > limiar]

        if outliers.empty:
            return self.build_issues([])

        issues = [
            {
                "severidade": "INFO",
                "conta_contabil": str(conta),
                "descricao": (
                    f"Conta {conta} tem {qtd} registros — acima de "
                    f"média ({media:.1f}) + 3σ ({desvio:.1f}) = {limiar:.1f}."
                ),
                "valor_esperado": f"≤ {limiar:.1f}",
                "valor_encontrado": str(qtd),
                "competencia": context.competencia,
            }
            for conta, qtd in outliers.items()
        ]
        return self.build_issues(issues)
