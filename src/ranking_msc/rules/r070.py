"""
Regra R070 — Sem registros duplicados.

Dimensão: Estrutura
Severidade padrão: ERRO

Lógica:
    Após a normalização das ICs, cada linha do FACT_MSC deve ser
    identificada de forma única pela chave composta:
        (conta_contabil, po, fp, dc, fs, fr, co, nr, nd, ai)
    Se dois ou mais registros compartilham exatamente a mesma chave,
    reporta ERRO por grupo de duplicatas.

    Limitação conhecida: duplicatas exatas no CSV original
    (mesma CONTA + ICs + Tipo_valor + Natureza_valor) são colapsadas
    pelo pivot_table(aggfunc="sum") no reader antes desta regra rodar.
    Essa regra detecta duplicatas introduzidas por IC-position-swap
    (mesmos valores de IC em posições diferentes → mesma chave após
    normalize_ic).

Referência:
    Catálogo de Regras MSC — R070, Prioridade P1 (Crítica), depende R001.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pandas as pd

from ranking_msc.rules.base import Rule, register_rule

if TYPE_CHECKING:
    from ranking_msc.engine.executor import EngineContext

logger = logging.getLogger("ranking_msc")

# Colunas que formam a chave de unicidade em FACT_MSC_COLUMNS
_KEY_COLS: list[str] = [
    "conta_contabil",
    "po", "fp", "dc", "fs", "fr", "co", "nr", "nd", "ai",
]


@register_rule
class R070(Rule):
    """Detecta registros duplicados por chave composta CONTA + ICs normalizadas."""

    rule_id = "R070"
    rule_name = "Sem registros duplicados"
    dimensao = "Estrutura"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Verifica unicidade da chave composta conta_contabil + colunas IC.

        Args:
            df: DataFrame normalizado com colunas de FACT_MSC_COLUMNS.
            context: metadados da execução.

        Returns:
            DataFrame de pendências — uma linha por grupo de duplicatas.
        """
        _extra = {"regra_id": self.rule_id, "competencia": context.competencia}

        # Usar apenas colunas da chave que existem no DataFrame
        key_cols = [c for c in _KEY_COLS if c in df.columns]
        if not key_cols:
            return self.build_issues([])

        # Normalizar NaN → "" para que o groupby compare corretamente
        work = df[key_cols].fillna("")

        mask = work.duplicated(subset=key_cols, keep=False)
        if not mask.any():
            return self.build_issues([])

        issues: list[dict[str, object]] = []

        for key_vals, group_idx in work[mask].groupby(key_cols, sort=False).groups.items():
            n = len(group_idx)
            # Proteger contra NaN em conta_contabil no DataFrame original
            if "conta_contabil" in df.columns:
                conta_raw = df.loc[group_idx[0], "conta_contabil"]
                conta = "" if pd.isna(conta_raw) else str(conta_raw)
            else:
                conta = ""

            # Montar descrição das ICs afetadas para diagnóstico
            # key_vals é tuple em groupby multi-coluna, scalar em groupby single-coluna
            ic_vals = key_vals[1:] if isinstance(key_vals, tuple) else []
            ic_info = ", ".join(
                f"{col}={val}"
                for col, val in zip(key_cols[1:], ic_vals, strict=True)
                if val
            )
            descricao = (
                f"Registro duplicado: conta '{conta}' com a combinação de ICs "
                f"[{ic_info}] aparece {n} vezes. "
                "Duplicidade indica erro de geração do arquivo."
            )

            issues.append({
                "severidade": "ERRO",
                "conta_contabil": conta,
                "descricao": descricao,
                "valor_esperado": "1 ocorrência por combinação CONTA+ICs",
                "valor_encontrado": f"{n} ocorrências",
                "competencia": context.competencia,
            })

        if issues:
            logger.warning(
                "R070: %d grupo(s) de registros duplicados. competência=%s",
                len(issues),
                context.competencia,
                extra=_extra,
            )

        return self.build_issues(issues)
