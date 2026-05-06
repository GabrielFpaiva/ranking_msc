"""Regra R086 — Ativo (classe 1) com saldo credor invertido (SIGEF V5).

Dimensão: PCASP
Severidade padrão: ALERTA

Lógica:
    Contas do Ativo (classe 1) cuja NAT_SALDO no PCASP é "Devedora" não
    devem apresentar saldo final credor positivo.

    Exceções aceitas (sem pendência):
    - NAT_SALDO == "Credora" → conta retificadora (ex: (-) Provisão), saldo
      credor é esperado.
    - NAT_SALDO == "Credora/Devedora" → aceita ambas as naturezas.

    SE classe(conta) == "1"
       AND pcasp[conta].nat_saldo == "Devedora"
       AND saldo_final_credito > 0
    → ALERTA

    A classe é determinada pelo 1.º dígito de conta_contabil.

Referência:
    Ranking Siconfi 2026 — verificação V5; Portaria STN 642/2026; R032 (geral)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pandas as pd

from ranking_msc.io.ref_loader import load_pcasp
from ranking_msc.rules.base import Rule, register_rule

if TYPE_CHECKING:
    from ranking_msc.engine.executor import EngineContext

logger = logging.getLogger("ranking_msc")

_CLASSE_ATIVO = "1"
_NAT_DEVEDORA = "Devedora"
_NAT_CREDORA_DEVEDORA = "Credora/Devedora"


@register_rule
class R086(Rule):
    """Detecta contas de Ativo (classe 1) com saldo credor anômalo."""

    rule_id = "R086"
    rule_name = "Ativo credor invertido"
    dimensao = "PCASP"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Identifica linhas de Ativo com saldo_final_credito > 0 e NAT_SALDO=Devedora.

        Args:
            df: DataFrame normalizado com colunas ``conta_contabil``,
                ``saldo_final_debito`` e ``saldo_final_credito``.
            context: metadados da execução (competência, siconfi, settings).

        Returns:
            DataFrame de pendências — uma linha por conta violadora.
        """
        _extra = {"regra_id": self.rule_id, "competencia": context.competencia}

        # 1. Carregar PCASP com nat_saldo
        pcasp_raw = load_pcasp(context.settings.paths.ref_dir)
        if "nat_saldo" not in pcasp_raw.columns:
            logger.warning(
                "R086: coluna 'nat_saldo' ausente em pcasp.csv — regra desativada. "
                "Verifique se o PCASP está atualizado (PcaspEstendido2026).",
                extra=_extra,
            )
            return self.build_issues([])

        pcasp = pcasp_raw[["conta_contabil", "nat_saldo"]].copy()
        pcasp["nat_saldo"] = pcasp["nat_saldo"].str.strip()

        # 2. Filtrar apenas contas de Ativo (classe 1)
        cols = ["conta_contabil", "saldo_final_debito", "saldo_final_credito"]
        msc = df[cols].copy()
        msc["_classe"] = msc["conta_contabil"].astype(str).str[:1]
        msc = msc[msc["_classe"] == _CLASSE_ATIVO]

        if msc.empty:
            return self.build_issues([])

        # 3. Join com PCASP para obter nat_saldo
        merged = msc.merge(pcasp, on="conta_contabil", how="left")

        # 4. Manter apenas contas Devedoras (retificadoras e Credora/Devedora são aceitas)
        merged = merged[
            merged["nat_saldo"].notna()
            & (merged["nat_saldo"] == _NAT_DEVEDORA)
        ]

        if merged.empty:
            return self.build_issues([])

        # 5. Converter saldo para numérico e filtrar violações
        merged["saldo_final_credito"] = pd.to_numeric(
            merged["saldo_final_credito"], errors="coerce"
        ).fillna(0.0)

        violacoes = merged[merged["saldo_final_credito"] > 0].copy()

        if violacoes.empty:
            return self.build_issues([])

        logger.warning(
            "R086: %d conta(s) de Ativo com saldo credor invertido. competência=%s",
            len(violacoes),
            context.competencia,
            extra=_extra,
        )

        # 6. Construção vetorizada de issues
        conta_s = violacoes["conta_contabil"].astype(str)
        saldo_s = violacoes["saldo_final_credito"].map(lambda x: f"{x:.2f}")

        issues_df = pd.DataFrame({
            "severidade": "ALERTA",
            "conta_contabil": conta_s.values,
            "descricao": (
                "Conta '"
                + conta_s
                + "' (Ativo/classe 1): NAT_SALDO=Devedora mas saldo credor de "
                + saldo_s
                + " (SIGEF V5)."
            ).values,
            "valor_esperado": "saldo_final_credito = 0",
            "valor_encontrado": ("saldo_final_credito = " + saldo_s).values,
            "competencia": context.competencia,
        })

        return self.build_issues(issues_df.to_dict("records"))
