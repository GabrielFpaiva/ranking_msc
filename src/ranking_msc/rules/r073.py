"""
Regra R073 — Valor muito grande (outlier absoluto).

Dimensão: Qualidade
Severidade padrão: INFO

Lógica:
    Valores extremamente altos podem indicar erro de escala na exportação
    (ex: valores em centavos ao invés de reais).

    p99 = percentil_99(todos_valores_nao_zero)
    SE valor > p99 * 10 → INFO

    Guarda: se < 10 valores não-zero ou p99 == 0, não há threshold útil.

Referência:
    ref/regras_catalogo.md — R073; Portaria STN 642/2026
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
_MULTIPLICADOR_P99 = 10


@register_rule
class R073(Rule):
    """Detecta valores monetários com magnitude outlier absoluto (> p99 × 10)."""

    rule_id = "R073"
    rule_name = "Valores outliers extremos"
    dimensao = "Qualidade"
    is_scoring: ClassVar[bool] = False

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Identifica linhas com valores muito acima do percentil 99 da MSC.

        Args:
            df: DataFrame normalizado com colunas de saldo e movimentação.
            context: metadados da execução.

        Returns:
            DataFrame de pendências — uma linha por valor outlier detectado.
        """
        if df.empty:
            return self.build_issues([])

        work = df.copy()
        for col in _COLS_VALOR:
            work[col] = pd.to_numeric(work[col], errors="coerce").fillna(0.0)

        # Coletar todos os valores absolutos não-zero para calcular p99
        todos = pd.concat([work[col].abs() for col in _COLS_VALOR])
        todos_nz = todos[todos > 0]

        if len(todos_nz) < 10:
            return self.build_issues([])

        p99 = float(todos_nz.quantile(0.99))
        if p99 == 0:
            return self.build_issues([])

        limiar = p99 * _MULTIPLICADOR_P99

        issues: list[dict[str, object]] = []
        for col in _COLS_VALOR:
            mask = work[col].abs() > limiar
            for idx, row in work[mask].iterrows():
                val = float(work.loc[idx, col])  # type: ignore[index]
                issues.append({
                    "severidade": "INFO",
                    "conta_contabil": str(row["conta_contabil"]),
                    "descricao": (
                        f"Coluna '{col}' com valor outlier: {val:.2f} "
                        f"(limiar p99×{_MULTIPLICADOR_P99} = {limiar:.2f})."
                    ),
                    "valor_esperado": f"≤ {limiar:.2f}",
                    "valor_encontrado": f"{val:.2f}",
                    "competencia": context.competencia,
                })

        return self.build_issues(issues)
