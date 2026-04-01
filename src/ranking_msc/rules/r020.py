"""Regra R020 — Conjunto de IC correto para a conta.

Categoria: IC
Severidade padrão: ERRO

Lógica:
    Para cada conta_contabil, verifica se o conjunto de ICs informadas
    (colunas não-vazias: po, fp, dc, fs, fr, co, nr, nd, ai) corresponde
    exatamente ao conjunto esperado pelo ID_IC definido no PCASP.

    Uma IC está "informada" quando seu valor NÃO é vazio/ausente:
    - Valores vazios: None, NaN, "", "nan", "0"

    IC faltante (esperada mas não informada) → ERRO
    IC extra (informada mas não esperada) → ERRO
    Ambas as situações podem ocorrer ao mesmo tempo → um único ERRO descrevendo ambas

    Contas sem ID_IC no PCASP ou com ID_IC=0 sem nenhuma IC → sem pendência.

Referência:
    Leiaute MSC 2026 — campo ID_IC; Portaria STN 642/2026
"""

from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING

import pandas as pd

from ranking_msc.io.ref_loader import IC_MAP, load_pcasp
from ranking_msc.rules.base import Rule, register_rule

if TYPE_CHECKING:
    from ranking_msc.engine.executor import EngineContext

logger = logging.getLogger("ranking_msc")

# Colunas IC do DataFrame normalizado (lowercase)
IC_COLS: tuple[str, ...] = ("po", "fp", "dc", "fs", "fr", "co", "nr", "nd", "ai")


def _ic_esta_informada(val: object) -> bool:
    """Retorna True se o valor da coluna IC está preenchido (não é vazio)."""
    if val is None:
        return False
    # Evita chamar pd.isna diretamente com type object; converte via str primeiro
    if isinstance(val, float) and math.isnan(val):
        return False
    return str(val).strip() not in ("", "0", "nan")


@register_rule
class R020(Rule):
    """Valida se o conjunto de ICs informadas corresponde ao ID_IC da conta no PCASP."""

    rule_id = "R020"
    rule_name = "Conjunto de IC correto para a conta"
    dimensao = "IC"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Verifica se as ICs informadas batem com o ID_IC definido no PCASP.

        Args:
            df: DataFrame normalizado com colunas de FACT_MSC_COLUMNS.
            context: metadados da execução (competência, siconfi, settings).

        Returns:
            DataFrame de pendências — uma linha por conta com conjunto de IC incorreto.
        """
        _extra = {"regra_id": self.rule_id, "competencia": context.competencia}

        pcasp_df = load_pcasp(context.settings.paths.ref_dir)

        # Mapeia conta_contabil → id_ic (string)
        id_ic_map: dict[str, str] = {}
        if "id_ic" in pcasp_df.columns:
            id_ic_map = dict(
                zip(
                    pcasp_df["conta_contabil"].astype(str),
                    pcasp_df["id_ic"].astype(str),
                    strict=False,
                )
            )

        # Garante que as colunas IC existem no DataFrame
        ic_cols_presentes = [col for col in IC_COLS if col in df.columns]

        # Agrupa por conta_contabil — IC é igual para todas as linhas da mesma conta
        contas_unicas = df[["conta_contabil"] + ic_cols_presentes].drop_duplicates(
            subset=["conta_contabil"]
        )

        issues: list[dict[str, object]] = []

        for _, row in contas_unicas.iterrows():
            conta = str(row["conta_contabil"])

            # Conta sem ID_IC no PCASP → skip com warning
            if conta not in id_ic_map:
                logger.warning(
                    "R020: conta '%s' não encontrada no PCASP, verificação de ID_IC ignorada."
                    " competência=%s",
                    conta,
                    context.competencia,
                    extra=_extra,
                )
                continue

            id_ic_str = str(id_ic_map[conta]).strip()

            # ID_IC ausente/nulo → skip com warning
            if id_ic_str in ("", "nan", "None"):
                logger.warning(
                    "R020: conta '%s' com ID_IC nulo/ausente no PCASP, ignorada."
                    " competência=%s",
                    conta,
                    context.competencia,
                    extra=_extra,
                )
                continue

            # ID_IC fora do IC_MAP → skip com warning
            try:
                id_ic_int = int(id_ic_str)
            except ValueError:
                logger.warning(
                    "R020: conta '%s' com ID_IC='%s' não numérico, ignorada."
                    " competência=%s",
                    conta,
                    id_ic_str,
                    context.competencia,
                    extra=_extra,
                )
                continue

            if id_ic_int not in IC_MAP:
                logger.warning(
                    "R020: conta '%s' com ID_IC=%d fora do IC_MAP, ignorada."
                    " competência=%s",
                    conta,
                    id_ic_int,
                    context.competencia,
                    extra=_extra,
                )
                continue

            # Conjunto esperado (UPPERCASE) e informado (UPPERCASE)
            ic_esperado_upper: set[str] = set(IC_MAP[id_ic_int])
            ic_informado_upper: set[str] = {
                col.upper()
                for col in ic_cols_presentes
                if _ic_esta_informada(row[col])
            }

            if ic_informado_upper == ic_esperado_upper:
                continue

            # Calcula faltantes e extras
            faltantes = sorted(ic_esperado_upper - ic_informado_upper)
            extras = sorted(ic_informado_upper - ic_esperado_upper)

            partes: list[str] = []
            if faltantes:
                partes.append(f"ICs faltantes: {', '.join(faltantes)}")
            if extras:
                partes.append(f"ICs não esperadas: {', '.join(extras)}")

            esperado_str = (
                ", ".join(sorted(ic_esperado_upper)) if ic_esperado_upper else "(nenhuma)"
            )
            informado_str = (
                ", ".join(sorted(ic_informado_upper)) if ic_informado_upper else "(nenhuma)"
            )

            descricao = (
                f"Conta '{conta}' (ID_IC={id_ic_int}): "
                + ". ".join(partes)
                + f". Esperado: {esperado_str}. Informado: {informado_str}."
            )

            issues.append({
                "severidade": "ERRO",
                "conta_contabil": conta,
                "descricao": descricao,
                "valor_esperado": esperado_str,
                "valor_encontrado": informado_str,
                "competencia": context.competencia,
            })

        if issues:
            logger.warning(
                "R020: %d conta(s) com conjunto de IC incorreto. competência=%s",
                len(issues),
                context.competencia,
                extra=_extra,
            )

        return self.build_issues(issues)
