"""Regra R042 — Contas de resultado sem saldo (apenas movimentos).

Dimensão: Completude
Severidade padrão: ALERTA

Lógica:
    Para cada conta de resultado (primeiro dígito em {3, 4}),
    verifica se existe ao menos uma linha beginning_balance ou ending_balance
    no CSV original. A verificação é baseada em presença de entradas (EXISTS),
    não em valor não-zero: uma entrada com valor zero também é violação.

    SE _has_saldo_inicial == True OU _has_saldo_final == True → ALERTA

    Contas de resultado (variação patrimonial) devem acumular apenas
    movimentos do exercício; entradas de saldo indicam erro de encerramento.

Referência:
    Catálogo de Regras MSC — R042 (Completude)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pandas as pd

from ranking_msc.rules.base import Rule, register_rule

if TYPE_CHECKING:
    from ranking_msc.engine.executor import EngineContext

logger = logging.getLogger("ranking_msc")

_CLASSES_RESULTADO: frozenset[str] = frozenset({"3", "4"})

_COLS_SALDO = [
    "saldo_inicial_debito",
    "saldo_inicial_credito",
    "saldo_final_debito",
    "saldo_final_credito",
]

_COLS_PRESENCE = ["_has_saldo_inicial", "_has_saldo_final"]


@register_rule
class R042(Rule):
    """Verifica que contas de resultado não possuem saldo (apenas movimentos)."""

    rule_id = "R042"
    rule_name = "Contas de resultado sem saldo (apenas movimentos)"
    dimensao = "Completude"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Detecta contas de resultado com entradas de saldo inicial ou final.

        A verificação é baseada em presença de entradas (EXISTS), não em valor
        não-zero: um beginning_balance ou ending_balance com valor zero também
        é violação — contas de resultado não devem ter esses tipos de lançamento.

        Agrega por conta_contabil antes de validar: uma conta pode estar
        representada em múltiplas linhas (ICs diferentes). Reporta ALERTA
        se qualquer linha _has_saldo_inicial ou _has_saldo_final for True.

        Args:
            df: DataFrame normalizado com colunas ``conta_contabil``,
                ``_has_saldo_inicial``, ``_has_saldo_final`` e colunas
                de saldo (usadas apenas para a mensagem descritiva).
            context: metadados da execução.

        Returns:
            DataFrame de pendências — uma linha por conta de resultado
            com pelo menos uma entrada beginning_balance ou ending_balance.
        """
        _extra = {"regra_id": self.rule_id, "competencia": context.competencia}

        cols_saldo_presentes = [c for c in _COLS_SALDO if c in df.columns]
        df_res = df[
            df["conta_contabil"].astype(str).str[:1].isin(_CLASSES_RESULTADO)
        ][["conta_contabil"] + _COLS_PRESENCE + cols_saldo_presentes].copy()

        if df_res.empty:
            return self.build_issues([])

        # Garantir todas as 4 colunas de saldo (usadas na descrição); preenche 0.0 se ausentes
        for col in _COLS_SALDO:
            if col in df_res.columns:
                df_res[col] = pd.to_numeric(df_res[col], errors="coerce").fillna(0.0)
            else:
                df_res[col] = 0.0

        totais = (
            df_res
            .groupby("conta_contabil", as_index=False)
            .agg(
                tem_si=("_has_saldo_inicial", "any"),
                tem_sf=("_has_saldo_final", "any"),
                si_d=("saldo_inicial_debito", "sum"),
                si_c=("saldo_inicial_credito", "sum"),
                sf_d=("saldo_final_debito", "sum"),
                sf_c=("saldo_final_credito", "sum"),
            )
        )

        violacoes = totais[totais["tem_si"] | totais["tem_sf"]]

        if violacoes.empty:
            return self.build_issues([])

        logger.warning(
            "R042: %d conta(s) de resultado com saldo. competência=%s",
            len(violacoes),
            context.competencia,
            extra=_extra,
        )

        issues: list[dict[str, object]] = []
        for _, row in violacoes.iterrows():
            tipos: list[str] = []
            if row["tem_si"]:
                tipos.append("saldo inicial")
            if row["tem_sf"]:
                tipos.append("saldo final")
            tipos_str = " e ".join(tipos)
            issues.append({
                "severidade": "ALERTA",
                "conta_contabil": str(row["conta_contabil"]),
                "descricao": (
                    f"Conta de resultado '{row['conta_contabil']}' possui {tipos_str} "
                    f"(SI_D={row['si_d']:.2f}, SI_C={row['si_c']:.2f}, "
                    f"SF_D={row['sf_d']:.2f}, SF_C={row['sf_c']:.2f}). "
                    f"Contas de resultado devem ter apenas movimentos."
                ),
                "valor_esperado": "COUNT(beginning_balance) = 0 e COUNT(ending_balance) = 0",
                "valor_encontrado": tipos_str,
                "competencia": context.competencia,
            })

        return self.build_issues(issues)
