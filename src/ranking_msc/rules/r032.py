"""Regra R032 — Natureza do saldo compatível com conta.

Dimensão: PCASP
Severidade padrão: ALERTA

Lógica:
    O saldo ending_balance deve ter Natureza_valor compatível com a natureza
    da conta no PCASP. Conta Devedora não pode ter saldo credor; conta Credora
    não pode ter saldo devedor. Contas Credora/Devedora aceitam ambos.

Referência:
    Leiaute MSC 2026 — PcaspEstendido2026 (NAT_SALDO); Portaria STN 642/2026
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pandas as pd

from ranking_msc.exceptions import ConfigError
from ranking_msc.io.ref_loader import load_pcasp
from ranking_msc.rules.base import Rule, register_rule

if TYPE_CHECKING:
    from ranking_msc.engine.executor import EngineContext

logger = logging.getLogger("ranking_msc")

_NAT_CREDORA_DEVEDORA = "Credora/Devedora"


@register_rule
class R032(Rule):
    """Verifica compatibilidade entre Natureza_valor do saldo e NAT_SALDO do PCASP."""

    rule_id = "R032"
    rule_name = "Natureza do saldo compatível com conta"
    dimensao = "PCASP"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Detecta saldos com natureza invertida em relação ao PCASP.

        Para cada linha da MSC:
        - nat_saldo == "Devedora" e saldo_final_credito > 0 → ALERTA
        - nat_saldo == "Credora" e saldo_final_debito > 0  → ALERTA
        - nat_saldo == "Credora/Devedora" → aceito (sem pendência)
        - conta ausente no PCASP → ignorado (R010 trata)

        Args:
            df: DataFrame normalizado com colunas ``conta_contabil``,
                ``saldo_final_debito`` e ``saldo_final_credito``.
            context: metadados da execução (competência, siconfi, settings).

        Returns:
            DataFrame de pendências — uma linha por saldo com natureza invertida.
        """
        _extra = {"regra_id": self.rule_id, "competencia": context.competencia}

        # 1. Carregar PCASP e normalizar nat_saldo
        pcasp_raw = load_pcasp(context.settings.paths.ref_dir)
        if "nat_saldo" not in pcasp_raw.columns:
            raise ConfigError(
                "R032 requer a coluna 'nat_saldo' em pcasp.csv, mas ela não foi encontrada. "
                f"Colunas presentes: {sorted(pcasp_raw.columns.tolist())}. "
                "Verifique se o arquivo de referência PCASP está atualizado (PcaspEstendido2026)."
            )

        pcasp = pcasp_raw[["conta_contabil", "nat_saldo"]].copy()
        pcasp["nat_saldo"] = pcasp["nat_saldo"].str.strip()

        # 2. Left join para obter nat_saldo por linha da MSC
        cols = ["conta_contabil", "saldo_final_debito", "saldo_final_credito"]
        merged = df[cols].merge(pcasp, on="conta_contabil", how="left")

        # 3. Ignorar contas sem match no PCASP (R010 já sinaliza) e Credora/Devedora
        merged = merged[merged["nat_saldo"].notna()]
        merged = merged[merged["nat_saldo"] != _NAT_CREDORA_DEVEDORA]

        if merged.empty:
            return self.build_issues([])

        # 4. Converter saldos para numérico
        merged["saldo_final_debito"] = pd.to_numeric(
            merged["saldo_final_debito"], errors="coerce"
        ).fillna(0.0)
        merged["saldo_final_credito"] = pd.to_numeric(
            merged["saldo_final_credito"], errors="coerce"
        ).fillna(0.0)

        # 5. Detectar violações (operações vetorizadas)
        mask_devedora = (merged["nat_saldo"] == "Devedora") & (
            merged["saldo_final_credito"] > 0
        )
        mask_credora = (merged["nat_saldo"] == "Credora") & (
            merged["saldo_final_debito"] > 0
        )
        violacoes = merged[mask_devedora | mask_credora]

        if violacoes.empty:
            return self.build_issues([])

        logger.warning(
            "R032: %d linha(s) com natureza de saldo incompatível. competência=%s",
            len(violacoes),
            context.competencia,
            extra=_extra,
        )

        # 6. Gerar issues
        issues: list[dict[str, object]] = []
        for _, row in violacoes.iterrows():
            conta = row["conta_contabil"]
            nat = row["nat_saldo"]
            if nat == "Devedora":
                saldo_inv = float(row["saldo_final_credito"])
                descricao = (
                    f"Conta '{conta}': nat_saldo=Devedora mas possui "
                    f"saldo credor de {saldo_inv:.2f}."
                )
                valor_esperado = "Natureza D (saldo devedor)"
                valor_encontrado = f"C (saldo_final_credito={saldo_inv:.2f})"
            else:
                saldo_inv = float(row["saldo_final_debito"])
                descricao = (
                    f"Conta '{conta}': nat_saldo=Credora mas possui "
                    f"saldo devedor de {saldo_inv:.2f}."
                )
                valor_esperado = "Natureza C (saldo credor)"
                valor_encontrado = f"D (saldo_final_debito={saldo_inv:.2f})"

            issues.append(
                {
                    "severidade": "ALERTA",
                    "conta_contabil": conta,
                    "descricao": descricao,
                    "valor_esperado": valor_esperado,
                    "valor_encontrado": valor_encontrado,
                    "competencia": context.competencia,
                }
            )

        return self.build_issues(issues)
