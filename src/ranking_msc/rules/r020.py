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
from typing import TYPE_CHECKING

import pandas as pd

from ranking_msc.io.ref_loader import IC_MAP, load_pcasp
from ranking_msc.rules.base import Rule, ic_mask_informada, register_rule

if TYPE_CHECKING:
    from ranking_msc.engine.executor import EngineContext

logger = logging.getLogger("ranking_msc")

# Colunas IC do DataFrame normalizado (lowercase)
IC_COLS: tuple[str, ...] = ("po", "fp", "dc", "fs", "fr", "co", "nr", "nd", "ai")


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

        if "id_ic" not in pcasp_df.columns:
            return self.build_issues([])

        # Preparar mapa PCASP: conta_contabil → id_ic (int)
        pcasp_map = pcasp_df[["conta_contabil", "id_ic"]].copy()
        pcasp_map["conta_contabil"] = pcasp_map["conta_contabil"].astype(str)
        pcasp_map["id_ic"] = pd.to_numeric(pcasp_map["id_ic"], errors="coerce")
        pcasp_map = pcasp_map.dropna(subset=["id_ic"])
        pcasp_map["id_ic"] = pcasp_map["id_ic"].astype(int)
        # Filtrar apenas id_ic válidos no IC_MAP
        pcasp_map = pcasp_map[pcasp_map["id_ic"].isin(IC_MAP)]

        # Garante que as colunas IC existem no DataFrame
        ic_cols_presentes = [col for col in IC_COLS if col in df.columns]

        # Pegar uma linha por conta (IC é igual para todas as linhas da mesma conta)
        contas_unicas = df[["conta_contabil"] + ic_cols_presentes].drop_duplicates(
            subset=["conta_contabil"]
        ).copy()
        contas_unicas["conta_contabil"] = contas_unicas["conta_contabil"].astype(str)

        # Merge com PCASP para obter id_ic
        merged = contas_unicas.merge(pcasp_map, on="conta_contabil", how="inner")

        if merged.empty:
            # Contas não encontradas no PCASP — R010 trata
            return self.build_issues([])

        # Computar conjuntos IC informados e esperados por conta (vetorizado)
        # Criar mask booleana por coluna IC
        ic_informado_masks = {}
        for col in ic_cols_presentes:
            ic_informado_masks[col.upper()] = ic_mask_informada(merged[col])

        # Construir set informado por conta — ainda precisa de apply mas sobre DF menor
        ic_informado_df = pd.DataFrame(ic_informado_masks, index=merged.index)

        # Para cada linha, computar conjunto informado e esperado
        issues: list[dict[str, object]] = []

        # Agrupar por id_ic para processar em batch
        for id_ic_val, group in merged.groupby("id_ic"):
            ic_esperado = set(IC_MAP[int(float(str(id_ic_val)))])
            group_idx = group.index

            for idx in group_idx:
                ic_informado = {
                    col_upper
                    for col_upper in ic_informado_df.columns
                    if ic_informado_df.at[idx, col_upper]
                }

                if ic_informado == ic_esperado:
                    continue

                conta = str(merged.at[idx, "conta_contabil"])
                faltantes = sorted(ic_esperado - ic_informado)
                extras = sorted(ic_informado - ic_esperado)

                partes: list[str] = []
                if faltantes:
                    partes.append(f"ICs faltantes: {', '.join(faltantes)}")
                if extras:
                    partes.append(f"ICs não esperadas: {', '.join(extras)}")

                esperado_str = (
                    ", ".join(sorted(ic_esperado)) if ic_esperado else "(nenhuma)"
                )
                informado_str = (
                    ", ".join(sorted(ic_informado)) if ic_informado else "(nenhuma)"
                )

                descricao = (
                    f"Conta '{conta}' (ID_IC={id_ic_val}): "
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
