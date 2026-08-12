"""Regra R047 — Confronto entre elemento de despesa e seus subelementos (informativo).

Dimensão: IC
Severidade padrão: INFO — fora da pontuação (is_scoring=False)

Lógica:
    Compara a soma dos subelementos com o valor do elemento pai (subelemento 00).
    Não existe relação aritmética exigível entre os dois: parte da despesa pode ser
    enviada sem detalhamento em subelemento. O confronto continua no relatório como
    sinal informativo.

Referência:
    doc/calibracao_regras_respostas_rodrigo.md, pergunta 6.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, ClassVar

import pandas as pd

from ranking_msc.rules.base import Rule, ic_mask_informada, register_rule

if TYPE_CHECKING:
    from ranking_msc.engine.executor import EngineContext

logger = logging.getLogger("ranking_msc")

_TOLERANCIA: float = 0.01


@register_rule
class R047(Rule):
    """Confronta a soma dos subelementos de ND com o elemento pai — informativo."""

    rule_id = "R047"
    rule_name = "Confronto elemento x subelementos (informativo)"
    dimensao = "IC"
    is_scoring: ClassVar[bool] = False

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Confronta elemento ND e seus subelementos — informativo.

        Para cada prefixo de 6 dígitos de ND que possui tanto o elemento pai
        (últimos 2 dígitos == "00") quanto subelementos (últimos 2 dígitos != "00"),
        compara as somas do saldo_final líquido. Não há relação aritmética
        exigível entre os dois valores; o confronto é apenas informativo.

        Args:
            df: DataFrame normalizado com colunas ``nd``, ``saldo_final_debito``
                e ``saldo_final_credito``.
            context: metadados da execução.

        Returns:
            DataFrame de pendências INFO — uma linha por prefixo ND com
            diferença entre elemento e subelementos.
        """
        _extra = {"regra_id": self.rule_id, "competencia": context.competencia}

        required = {"nd", "saldo_final_debito", "saldo_final_credito"}
        if not required.issubset(df.columns):
            return self.build_issues([])

        df_nd = df[list(required)].copy()
        df_nd = df_nd[ic_mask_informada(df_nd["nd"])]

        if df_nd.empty:
            return self.build_issues([])

        df_nd["nd_val"] = df_nd["nd"].astype(str).str.strip().str.zfill(8)
        df_nd["saldo_final_debito"] = pd.to_numeric(
            df_nd["saldo_final_debito"], errors="coerce"
        ).fillna(0.0)
        df_nd["saldo_final_credito"] = pd.to_numeric(
            df_nd["saldo_final_credito"], errors="coerce"
        ).fillna(0.0)
        df_nd["net"] = df_nd["saldo_final_debito"] - df_nd["saldo_final_credito"]

        df_nd["prefixo6"] = df_nd["nd_val"].str[:6]
        df_nd["sufixo2"] = df_nd["nd_val"].str[6:]

        mask_elemento = df_nd["sufixo2"] == "00"
        mask_subelemento = df_nd["sufixo2"] != "00"

        elementos = (
            df_nd[mask_elemento]
            .groupby("prefixo6")["net"]
            .sum()
            .rename("valor_elemento")
        )
        subelementos = (
            df_nd[mask_subelemento]
            .groupby("prefixo6")["net"]
            .sum()
            .rename("valor_subs")
        )

        comparacao = pd.concat([elementos, subelementos], axis=1).dropna()
        if comparacao.empty:
            return self.build_issues([])

        mask_diverge = (comparacao["valor_elemento"] - comparacao["valor_subs"]).abs() > _TOLERANCIA
        divergentes = comparacao[mask_diverge].reset_index()

        if divergentes.empty:
            return self.build_issues([])

        issues = []
        for _, row in divergentes.iterrows():
            issues.append({
                "severidade": "INFO",
                "conta_contabil": f"ND:{row['prefixo6']}xx",
                "descricao": (
                    f"ND prefixo '{row['prefixo6']}': soma dos subelementos "
                    f"({row['valor_subs']:.2f}) difere do elemento pai "
                    f"({row['valor_elemento']:.2f}) — diferença de "
                    f"{abs(row['valor_elemento'] - row['valor_subs']):.2f} "
                    f"— sinal informativo, sem relação aritmética exigível."
                ),
                "valor_esperado": f"{row['valor_elemento']:.2f}",
                "valor_encontrado": f"{row['valor_subs']:.2f}",
                "competencia": context.competencia,
            })

        logger.info(
            "R047: %d prefixo(s) ND com diferença entre elemento e subelementos "
            "(informativo). competência=%s",
            len(issues),
            context.competencia,
            extra=_extra,
        )

        return self.build_issues(issues)
