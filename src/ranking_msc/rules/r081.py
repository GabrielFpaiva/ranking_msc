"""Regra R081 — IC tem dígitos no formato correto.

Categoria: Formato
Severidade padrão: ERRO
Prioridade: P1-Crítica
Dependência: R001

Lógica:
    Para cada IC informada (não-vazia), o valor deve ter o número exato
    de dígitos esperado pelo seu tipo E ser totalmente numérico.

    Mapa de dígitos esperados por tipo de IC:
      po=5, fp=1, dc=1, fr=4, co=4, nr=8, nd=8, fs=5, ai=4

Referência:
    Leiaute MSC 2026 — Portaria STN 642/2026, Anexo II (campos IC/TIPO)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pandas as pd

from ranking_msc.rules.base import Rule, ic_mask_informada, register_rule

if TYPE_CHECKING:
    from ranking_msc.engine.executor import EngineContext

logger = logging.getLogger("ranking_msc")

# Mapa de colunas IC para número de dígitos esperados.
# Nota: R023 valida o domínio de DC (valor "1"); R081 valida o formato (1 dígito numérico).
# As duas regras são complementares — não há sobreposição de responsabilidade.
IC_DIGITOS: dict[str, int] = {
    "po": 5,
    "fp": 1,
    "dc": 1,
    "fr": 4,
    "co": 4,
    "nr": 8,
    "nd": 8,
    "fs": 5,
    "ai": 4,
}


@register_rule
class R081(Rule):
    """Valida que cada IC informada tem o número correto de dígitos numéricos."""

    rule_id = "R081"
    rule_name = "Formato de IC — dígitos por tipo"
    dimensao = "Formato"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Verifica se cada IC informada tem o número exato de dígitos numéricos.

        Args:
            df: DataFrame normalizado com colunas de IC (po, fp, dc, fr, co, nr, nd, fs, ai).
            context: metadados da execução.

        Returns:
            DataFrame de pendências — uma linha por IC inválida encontrada.
        """
        _extra = {"regra_id": self.rule_id, "competencia": context.competencia}

        dfs_violacoes: list[pd.DataFrame] = []

        for col, digitos_esperados in IC_DIGITOS.items():
            if col not in df.columns:
                continue

            # Mask vetorizada — substitui .apply(ic_esta_informada)
            mask_informada = ic_mask_informada(df[col])
            df_com_ic = df.loc[mask_informada, ["conta_contabil", col]].copy()

            if df_com_ic.empty:
                continue

            # Vetorizar a validação de formato
            df_com_ic[col] = df_com_ic[col].astype(str).str.strip()
            mask_invalido = ~(
                (df_com_ic[col].str.len() == digitos_esperados)
                & df_com_ic[col].str.isdigit()
            )
            violacoes = df_com_ic[mask_invalido]

            if violacoes.empty:
                continue

            # Construção vetorizada de issues — substitui iterrows()
            col_upper = col.upper()
            conta_s = violacoes["conta_contabil"].astype(str)
            val_s = violacoes[col].astype(str)
            len_s = val_s.str.len().astype(str)

            issue_df = pd.DataFrame({
                "severidade": "ERRO",
                "conta_contabil": conta_s.values,
                "descricao": (
                    "IC '" + col_upper + "' com valor '" + val_s
                    + "' inválido para conta '" + conta_s
                    + "': esperado " + str(digitos_esperados)
                    + " dígito(s) numérico(s), encontrado " + len_s + "."
                ).values,
                "valor_esperado": f"{digitos_esperados} dígito(s) numérico(s)",
                "valor_encontrado": val_s.values,
                "competencia": context.competencia,
            })
            dfs_violacoes.append(issue_df)

        if not dfs_violacoes:
            return self.build_issues([])

        all_issues = pd.concat(dfs_violacoes, ignore_index=True)

        logger.warning(
            "R081: %d IC(s) com formato inválido. competência=%s",
            len(all_issues),
            context.competencia,
            extra=_extra,
        )

        return self.build_issues(all_issues.to_dict("records"))
