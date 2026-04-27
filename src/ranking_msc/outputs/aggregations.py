"""
ranking_msc.outputs.aggregations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Agregações derivadas dos snapshots persistidos pelo motor.

Centraliza as transformações que são puras — recebem DataFrames já lidos do disco
e devolvem estruturas prontas para o frontend MCRA PMJP. As rotas FastAPI em
``app/api/routes/`` consomem estas funções; assim a camada API não duplica lógica
de pandas.

A leitura de disco (snapshots Parquet, scoring_metadata.json) continua em
``ranking_msc.outputs.snapshot`` — este módulo só transforma o que já foi lido.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import pandas as pd

from ranking_msc.rules.base import RULE_REGISTRY

logger = logging.getLogger("ranking_msc")


_SEVERIDADE_RANK: dict[str, int] = {"ERRO": 3, "ALERTA": 2, "INFO": 1}


@dataclass(frozen=True)
class TopRule:
    """Linha do ranking de regras violadas em uma competência."""

    regra_id: str
    regra_nome: str
    dimensao: str
    severidade_max: str
    pendencias: int


def top_violated_rules(
    pendencias: pd.DataFrame,
    *,
    limit: int = 8,
) -> list[TopRule]:
    """Lista as ``limit`` regras com mais pendências em uma execução.

    Args:
        pendencias: DataFrame de pendências (FACT_RESULTADO_REGRAS_COLUMNS).
        limit: número máximo de linhas a retornar.

    Returns:
        Lista ordenada decrescente por pendencias e severidade máxima.
    """
    if pendencias.empty:
        return []

    grouped = (
        pendencias.assign(
            _sev_rank=pendencias["severidade"].map(_SEVERIDADE_RANK).fillna(0),
        )
        .groupby(["regra_id", "regra_nome", "dimensao"], as_index=False)
        .agg(pendencias=("severidade", "size"), _sev_rank_max=("_sev_rank", "max"))
        .sort_values(
            by=["pendencias", "_sev_rank_max"],
            ascending=[False, False],
        )
        .head(limit)
    )

    inv_rank = {v: k for k, v in _SEVERIDADE_RANK.items()}
    return [
        TopRule(
            regra_id=str(row["regra_id"]),
            regra_nome=str(row["regra_nome"]) or _registry_name(str(row["regra_id"])),
            dimensao=str(row["dimensao"]),
            severidade_max=inv_rank.get(int(row["_sev_rank_max"]), "INFO"),
            pendencias=int(row["pendencias"]),
        )
        for _, row in grouped.iterrows()
    ]


def filter_pendencias(
    pendencias: pd.DataFrame,
    *,
    regra_id: str | None = None,
    severidade: str | None = None,
    conta_contabil_prefix: str | None = None,
) -> pd.DataFrame:
    """Aplica filtros usuais da tela Pendências sobre o DataFrame de pendências.

    Args:
        pendencias: DataFrame da execução (pode ser vazio).
        regra_id: filtra por regra exata (ex: ``"R054"``).
        severidade: filtra por severidade exata (``ERRO``/``ALERTA``/``INFO``).
        conta_contabil_prefix: filtra contas que começam com este prefixo (ex: ``"1.1.1"``).

    Returns:
        DataFrame filtrado (cópia rasa).
    """
    if pendencias.empty:
        return pendencias

    df = pendencias
    if regra_id:
        df = df[df["regra_id"] == regra_id]
    if severidade:
        df = df[df["severidade"] == severidade]
    if conta_contabil_prefix:
        df = df[df["conta_contabil"].astype(str).str.startswith(conta_contabil_prefix)]
    return df.reset_index(drop=True)


def _registry_name(rule_id: str) -> str:
    """Retorna o nome da regra olhando o RULE_REGISTRY (fallback ao id)."""
    rule_class = RULE_REGISTRY.get(rule_id)
    return rule_class.rule_name if rule_class else rule_id
