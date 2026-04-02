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
import math
from typing import TYPE_CHECKING

import pandas as pd

from ranking_msc.rules.base import Rule, register_rule

if TYPE_CHECKING:
    from ranking_msc.engine.executor import EngineContext

logger = logging.getLogger("ranking_msc")

# Mapa de colunas IC para número de dígitos esperados
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

_IC_VAZIA: frozenset[str] = frozenset({"", "0", "nan"})


def _ic_esta_informada(val: object) -> bool:
    """Retorna True se o valor da coluna IC está preenchido (não é vazio).

    Args:
        val: valor bruto da célula da coluna IC.

    Returns:
        True se a IC está informada, False caso contrário.
    """
    if val is None:
        return False
    if isinstance(val, float) and math.isnan(val):
        return False
    return str(val).strip() not in _IC_VAZIA


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

        issues: list[dict[str, object]] = []

        for col, digitos_esperados in IC_DIGITOS.items():
            if col not in df.columns:
                continue

            # Filtrar linhas onde IC está informada
            df_com_ic = df[["conta_contabil", col]].copy()
            df_com_ic = df_com_ic[df_com_ic[col].apply(_ic_esta_informada)]

            if df_com_ic.empty:
                continue

            for _, row in df_com_ic.iterrows():
                val = str(row[col]).strip()
                conta = str(row["conta_contabil"])

                if len(val) != digitos_esperados or not val.isdigit():
                    issues.append({
                        "severidade": "ERRO",
                        "conta_contabil": conta,
                        "descricao": (
                            f"IC '{col.upper()}' com valor '{val}' inválido para conta '{conta}': "
                            f"esperado {digitos_esperados} dígito(s) numérico(s), "
                            f"encontrado {len(val)}."
                        ),
                        "valor_esperado": f"{digitos_esperados} dígito(s) numérico(s)",
                        "valor_encontrado": val,
                        "competencia": context.competencia,
                    })

        if issues:
            logger.warning(
                "R081: %d IC(s) com formato inválido. competência=%s",
                len(issues),
                context.competencia,
                extra=_extra,
            )

        return self.build_issues(issues)
