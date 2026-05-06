"""Regra R088 — Patrimônio Líquido (grupo 2.3) com saldo devedor invertido (SIGEF V10).

Dimensão: PCASP
Severidade padrão: ALERTA

Lógica:
    Contas de PL (classe 2, grupo "23") cuja NAT_SALDO no PCASP é "Credora"
    não devem apresentar saldo final devedor positivo.

    Exceção aceita (sem pendência):
    - NAT_SALDO == "Credora/Devedora" → contas como Ajustes de Avaliação
      Patrimonial, Superávits/Déficits Acumulados aceitam ambas as naturezas.

    O grupo é determinado pelos 2 primeiros dígitos de conta_contabil.

    SE classe(conta) == "2"
       AND grupo(conta) == "23"
       AND pcasp[conta].nat_saldo == "Credora"
       AND saldo_final_debito > 0
    → ALERTA

Referência:
    Ranking Siconfi 2026 — verificação V10; Portaria STN 642/2026; R032 (geral)
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

_CLASSE_PASSIVO = "2"
_GRUPO_PL = "23"
_NAT_CREDORA = "Credora"
_NAT_CREDORA_DEVEDORA = "Credora/Devedora"


@register_rule
class R088(Rule):
    """Detecta contas de PL (grupo 2.3) com saldo devedor anômalo."""

    rule_id = "R088"
    rule_name = "PL invertido"
    dimensao = "PCASP"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Identifica linhas de PL (grupo 23) com saldo_final_debito > 0
        e NAT_SALDO=Credora.

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
                "R088: coluna 'nat_saldo' ausente em pcasp.csv — regra desativada. "
                "Verifique se o PCASP está atualizado (PcaspEstendido2026).",
                extra=_extra,
            )
            return self.build_issues([])

        pcasp = pcasp_raw[["conta_contabil", "nat_saldo"]].copy()
        pcasp["nat_saldo"] = pcasp["nat_saldo"].str.strip()

        # 2. Filtrar apenas contas de PL (classe 2, grupo 23)
        cols = ["conta_contabil", "saldo_final_debito", "saldo_final_credito"]
        msc = df[cols].copy()
        msc["_classe"] = msc["conta_contabil"].astype(str).str[:1]
        msc["_grupo"] = msc["conta_contabil"].astype(str).str[:2]
        msc = msc[
            (msc["_classe"] == _CLASSE_PASSIVO)
            & (msc["_grupo"] == _GRUPO_PL)
        ]

        if msc.empty:
            return self.build_issues([])

        # 3. Join com PCASP para obter nat_saldo
        merged = msc.merge(pcasp, on="conta_contabil", how="left")

        # 4. Manter apenas contas Credoras (Credora/Devedora é exceção aceita)
        merged = merged[
            merged["nat_saldo"].notna()
            & (merged["nat_saldo"] == _NAT_CREDORA)
        ]

        if merged.empty:
            return self.build_issues([])

        # 5. Converter saldo para numérico e filtrar violações
        merged["saldo_final_debito"] = pd.to_numeric(
            merged["saldo_final_debito"], errors="coerce"
        ).fillna(0.0)

        violacoes = merged[merged["saldo_final_debito"] > 0].copy()

        if violacoes.empty:
            return self.build_issues([])

        logger.warning(
            "R088: %d conta(s) de PL com saldo invertido. competência=%s",
            len(violacoes),
            context.competencia,
            extra=_extra,
        )

        # 6. Construção vetorizada de issues
        conta_s = violacoes["conta_contabil"].astype(str)
        saldo_s = violacoes["saldo_final_debito"].map(lambda x: f"{x:.2f}")

        issues_df = pd.DataFrame({
            "severidade": "ALERTA",
            "conta_contabil": conta_s.values,
            "descricao": (
                "Conta '"
                + conta_s
                + "' (PL/grupo 2.3): NAT_SALDO=Credora mas saldo devedor de "
                + saldo_s
                + " (SIGEF V10)."
            ).values,
            "valor_esperado": "saldo_final_debito = 0",
            "valor_encontrado": ("saldo_final_debito = " + saldo_s).values,
            "competencia": context.competencia,
        })

        return self.build_issues(issues_df.to_dict("records"))
