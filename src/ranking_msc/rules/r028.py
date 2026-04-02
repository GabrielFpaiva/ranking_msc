"""Regra R028 — FS válida: 5 dígitos (2 função + 3 subfunção).

Categoria: IC
Severidade padrão: ERRO (formato/função) | ALERTA (subfunção ausente)

Lógica:
    Quando a coluna `fs` está informada, o valor é validado em três níveis:
      1. Comprimento: deve ter exatamente 5 dígitos (verificado no valor bruto).
      2. Função (2 primeiros dígitos): deve existir na tabela FS 2026.
      3. Subfunção (3 últimos dígitos): deve existir na tabela FS 2026.
    Erros de comprimento e função geram ERRO; subfunção ausente gera ALERTA.
    Após ERRO de comprimento, os checks de função e subfunção não são executados.
    Após ERRO de função, o check de subfunção não é executado.

Referência:
    Leiaute MSC 2026 — campo FS; ref/regras_catalogo.md seção R028
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pandas as pd

from ranking_msc.io.ref_loader import load_tabela_fs
from ranking_msc.rules.base import Rule, ic_esta_informada, register_rule

if TYPE_CHECKING:
    from ranking_msc.engine.executor import EngineContext

logger = logging.getLogger("ranking_msc")


@register_rule
class R028(Rule):
    """Valida formato (5 dígitos), função (2 dígitos) e subfunção (3 dígitos) do FS."""

    rule_id = "R028"
    rule_name = "FS válida — 5 dígitos (função + subfunção)"
    dimensao = "IC"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Verifica se os valores de FS são válidos em formato, função e subfunção.

        Para cada valor de FS informado:
          - Se tiver comprimento diferente de 5 antes da normalização → ERRO e próxima conta.
          - Se os 2 primeiros dígitos (função) não existirem na tabela FS → ERRO e próxima conta.
          - Se os 3 últimos dígitos (subfunção) não existirem na tabela FS → ALERTA.

        Args:
            df: DataFrame normalizado com colunas ``fs`` e ``conta_contabil``.
            context: metadados da execução.

        Returns:
            DataFrame de pendências — uma linha por violação encontrada.
        """
        _extra = {"regra_id": self.rule_id, "competencia": context.competencia}

        if "fs" not in df.columns:
            return self.build_issues([])

        tabela = load_tabela_fs(context.settings.paths.ref_dir)
        funcoes_validas: set[str] = set(
            tabela["funcao"].astype(str).str.strip().str.zfill(2)
        )
        subfuncoes_validas: set[str] = set(
            tabela["subfuncao"].astype(str).str.strip().str.zfill(3)
        )

        df_com_fs = df[["conta_contabil", "fs"]].copy()
        df_com_fs = df_com_fs[df_com_fs["fs"].apply(ic_esta_informada)]

        if df_com_fs.empty:
            return self.build_issues([])

        issues: list[dict[str, object]] = []

        for _, row in df_com_fs.drop_duplicates().iterrows():
            conta = str(row["conta_contabil"])
            fs_raw = str(row["fs"]).strip()
            fs_val = fs_raw.zfill(5)

            if len(fs_raw) != 5:
                issues.append({
                    "severidade": "ERRO",
                    "conta_contabil": conta,
                    "descricao": (
                        f"FS '{fs_raw}' inválida para conta '{conta}': "
                        "deve ter exatamente 5 dígitos."
                    ),
                    "valor_esperado": "5 dígitos",
                    "valor_encontrado": fs_raw,
                    "competencia": context.competencia,
                })
                continue

            funcao = fs_val[:2]
            subfuncao = fs_val[2:]

            if funcao not in funcoes_validas:
                issues.append({
                    "severidade": "ERRO",
                    "conta_contabil": conta,
                    "descricao": (
                        f"FS '{fs_val}': função '{funcao}' não encontrada "
                        f"na tabela FS 2026 para conta '{conta}'."
                    ),
                    "valor_esperado": "função em tabela_fs.csv",
                    "valor_encontrado": funcao,
                    "competencia": context.competencia,
                })
                continue

            if subfuncao not in subfuncoes_validas:
                issues.append({
                    "severidade": "ALERTA",
                    "conta_contabil": conta,
                    "descricao": (
                        f"FS '{fs_val}': subfunção '{subfuncao}' não encontrada "
                        f"na tabela FS 2026 para conta '{conta}'."
                    ),
                    "valor_esperado": "subfunção em tabela_fs.csv",
                    "valor_encontrado": subfuncao,
                    "competencia": context.competencia,
                })

        if issues:
            logger.warning(
                "R028: %d pendência(s) de FS inválida. competência=%s",
                len(issues),
                context.competencia,
                extra=_extra,
            )

        return self.build_issues(issues)
