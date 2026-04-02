"""Regra R026 — NR válida: 8 dígitos e existente na tabela NR.

Categoria: IC
Severidade padrão: ERRO (formato) | ALERTA (código ausente na tabela)

Lógica:
    Quando a coluna `nr` está informada, o valor é validado em dois níveis:
      1. Comprimento: deve ter exatamente 8 dígitos (verificado no valor bruto).
      2. Existência: deve existir na tabela NR 2026.
    Check de comprimento gera ERRO; ausência na tabela gera ALERTA.
    Após ERRO de comprimento, o check de existência não é executado.

Referência:
    Leiaute MSC 2026 — campo NR; ref/regras_catalogo.md seção R026
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pandas as pd

from ranking_msc.io.ref_loader import load_tabela_nr
from ranking_msc.rules.base import Rule, ic_esta_informada, register_rule

if TYPE_CHECKING:
    from ranking_msc.engine.executor import EngineContext

logger = logging.getLogger("ranking_msc")


@register_rule
class R026(Rule):
    """Valida formato (8 dígitos) e existência do NR na tabela oficial."""

    rule_id = "R026"
    rule_name = "NR válida — 8 dígitos e existente na tabela NR 2026"
    dimensao = "IC"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Verifica se os valores de NR são válidos em formato e domínio.

        Para cada valor de NR informado:
          - Se tiver comprimento diferente de 8 antes da normalização → ERRO e próxima conta.
          - Se o código não existir na tabela NR → ALERTA.

        Args:
            df: DataFrame normalizado com colunas ``nr`` e ``conta_contabil``.
            context: metadados da execução.

        Returns:
            DataFrame de pendências — uma linha por violação encontrada.
        """
        _extra = {"regra_id": self.rule_id, "competencia": context.competencia}

        if "nr" not in df.columns:
            return self.build_issues([])

        tabela = load_tabela_nr(context.settings.paths.ref_dir)
        codigos_validos: set[str] = set(
            tabela["codigo"].astype(str).str.strip().str.zfill(8)
        )

        df_com_nr = df[["conta_contabil", "nr"]].copy()
        df_com_nr = df_com_nr[df_com_nr["nr"].apply(ic_esta_informada)]

        if df_com_nr.empty:
            return self.build_issues([])

        issues: list[dict[str, object]] = []

        for _, row in df_com_nr.drop_duplicates().iterrows():
            conta = str(row["conta_contabil"])
            nr_raw = str(row["nr"]).strip()
            nr_val = nr_raw.zfill(8)

            if len(nr_raw) != 8:
                issues.append({
                    "severidade": "ERRO",
                    "conta_contabil": conta,
                    "descricao": (
                        f"NR '{nr_raw}' inválida para conta '{conta}': "
                        "deve ter exatamente 8 dígitos."
                    ),
                    "valor_esperado": "8 dígitos",
                    "valor_encontrado": nr_raw,
                    "competencia": context.competencia,
                })
                continue

            if nr_val not in codigos_validos:
                issues.append({
                    "severidade": "ALERTA",
                    "conta_contabil": conta,
                    "descricao": (
                        f"NR '{nr_val}' não encontrada na tabela NR 2026 "
                        f"para conta '{conta}'."
                    ),
                    "valor_esperado": "código em tabela_nr.csv",
                    "valor_encontrado": nr_val,
                    "competencia": context.competencia,
                })

        if issues:
            logger.warning(
                "R026: %d pendência(s) de NR inválida. competência=%s",
                len(issues),
                context.competencia,
                extra=_extra,
            )

        return self.build_issues(issues)
