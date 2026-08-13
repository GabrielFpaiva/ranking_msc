"""Regra R042 — Contas de resultado zeradas no encerramento.

Dimensão: Completude
Severidade padrão: INFO — fora da pontuação (is_scoring=False)

Lógica:
    Contas de resultado (primeiro dígito em {3, 4}) acumulam saldo ao longo do
    exercício e são zeradas no encerramento, em confronto com Resultados
    Acumulados. Durante o exercício, portanto, saldo em conta de resultado é
    normal e não gera pendência.

    Na competência de encerramento (mês 13):
        SE abs(saldo_final_debito - saldo_final_credito) > tolerância → INFO

Pontuação:
    R069 ("Resultado zerado no encerramento", dimensão Temporal) já verificava
    exatamente esta condição — classes 3 e 4 com saldo final não-zero no mês 13 —
    e continua sendo a dona da pontuação. R042 mantém a detecção como sinal
    informativo, mas sai da nota (``is_scoring = False``) para que um único
    defeito não gere duas pendências pontuadas em duas dimensões distintas
    (Completude e Temporal).

Referência:
    doc/calibracao_regras_respostas_rodrigo.md, pergunta 10;
    ref/IPC_Encerramento_STN.pdf, p. 9.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, ClassVar

import pandas as pd

from ranking_msc.rules.base import (
    TOLERANCIA_CENTAVO,
    Rule,
    competencia_de_encerramento,
    register_rule,
)

if TYPE_CHECKING:
    from ranking_msc.engine.executor import EngineContext

logger = logging.getLogger("ranking_msc")

_CLASSES_RESULTADO: frozenset[str] = frozenset({"3", "4"})

_COLS_SALDO_FINAL = ["saldo_final_debito", "saldo_final_credito"]


@register_rule
class R042(Rule):
    """Verifica que contas de resultado zeram no encerramento do exercício."""

    rule_id = "R042"
    rule_name = "Contas de resultado zeradas no encerramento"
    dimensao = "Completude"
    is_scoring: ClassVar[bool] = False  # condição pontuada por R069 — evita dupla penalização

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Detecta conta de resultado com saldo final diferente de zero no mês 13.

        Args:
            df: DataFrame normalizado com colunas ``conta_contabil``,
                ``saldo_final_debito`` e ``saldo_final_credito``.
            context: metadados da execução.

        Returns:
            DataFrame de pendências — uma linha por conta de resultado que não
            zerou. Vazio fora da competência de encerramento.
        """
        _extra = {"regra_id": self.rule_id, "competencia": context.competencia}

        if not competencia_de_encerramento(context.competencia):
            return self.build_issues([])

        if df.empty or "conta_contabil" not in df.columns:
            return self.build_issues([])

        df_res = df[
            df["conta_contabil"].astype(str).str[:1].isin(_CLASSES_RESULTADO)
        ][["conta_contabil"] + [c for c in _COLS_SALDO_FINAL if c in df.columns]].copy()

        if df_res.empty:
            return self.build_issues([])

        for col in _COLS_SALDO_FINAL:
            if col in df_res.columns:
                df_res[col] = pd.to_numeric(df_res[col], errors="coerce").fillna(0.0)
            else:
                df_res[col] = 0.0

        totais = (
            df_res
            .groupby("conta_contabil", as_index=False)
            .agg(
                sf_d=("saldo_final_debito", "sum"),
                sf_c=("saldo_final_credito", "sum"),
            )
        )
        totais["saldo_liquido"] = totais["sf_d"] - totais["sf_c"]

        violacoes = totais[totais["saldo_liquido"].abs() > TOLERANCIA_CENTAVO]

        if violacoes.empty:
            return self.build_issues([])

        logger.info(
            "R042: %d conta(s) de resultado sem zerar no encerramento "
            "(informativo; a condição é pontuada por R069). competência=%s",
            len(violacoes),
            context.competencia,
            extra=_extra,
        )

        conta_s = violacoes["conta_contabil"].astype(str)
        saldo_s = violacoes["saldo_liquido"].map(lambda x: f"{x:.2f}")

        issues_df = pd.DataFrame({
            "severidade": "INFO",
            "conta_contabil": conta_s.values,
            "descricao": (
                "Conta de resultado '" + conta_s + "' não zerou no encerramento: "
                "saldo final líquido de " + saldo_s + " — sinal informativo, "
                "a condição é pontuada por R069."
            ).values,
            "valor_esperado": "0.00",
            "valor_encontrado": saldo_s.values,
            "competencia": context.competencia,
        })

        return self.build_issues(issues_df.to_dict("records"))
