"""
Regra R071 — Valores com mais de 2 casas decimais.

Dimensão: Qualidade
Severidade padrão: INFO

Lógica:
    Valores monetários devem estar na escala de R$ (2 casas decimais).
    Mais de 2 decimais pode indicar erro de conversão de unidade.

    SE abs(valor - round(valor, 2)) > 1e-9 → INFO

Referência:
    ref/regras_catalogo.md — R071; Portaria STN 642/2026
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

import pandas as pd

from ranking_msc.rules.base import Rule, register_rule

if TYPE_CHECKING:
    from ranking_msc.engine.executor import EngineContext

_COLS_VALOR = (
    "saldo_inicial_debito",
    "saldo_inicial_credito",
    "movimento_debito",
    "movimento_credito",
    "saldo_final_debito",
    "saldo_final_credito",
)
_DECIMAL_TOL = 1e-9


@register_rule
class R071(Rule):
    """Detecta valores com mais de 2 casas decimais na MSC."""

    rule_id = "R071"
    rule_name = "Valores com > 2 decimais"
    dimensao = "Qualidade"
    is_scoring: ClassVar[bool] = False

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Identifica linhas com valores monetários além de 2 casas decimais.

        Args:
            df: DataFrame normalizado com colunas de saldo e movimentação.
            context: metadados da execução.

        Returns:
            DataFrame de pendências — uma linha por coluna/linha com >2 decimais.
        """
        if df.empty:
            return self.build_issues([])

        issues: list[dict[str, object]] = []

        for col in _COLS_VALOR:
            serie = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
            # |v - round(v, 2)| > tol indica mais de 2 casas decimais
            mask = (serie - serie.round(2)).abs() > _DECIMAL_TOL
            violacoes = df[mask]
            for idx, row in violacoes.iterrows():
                val = float(serie.loc[idx])  # type: ignore[index]
                issues.append({
                    "severidade": "INFO",
                    "conta_contabil": str(row["conta_contabil"]),
                    "descricao": (
                        f"Coluna '{col}' com mais de 2 casas decimais: {val}."
                    ),
                    "valor_esperado": f"{round(val, 2):.2f}",
                    "valor_encontrado": str(val),
                    "competencia": context.competencia,
                })

        return self.build_issues(issues)
