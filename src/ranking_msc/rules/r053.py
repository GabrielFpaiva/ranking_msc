"""
Regra R053 — Contas INTRA OFSS com contrapartida balanceada.

Dimensão: Interconta
Severidade padrão: ALERTA

Lógica:
    Contas cujo título no PCASP contém "INTRA" representam transferências
    intra-OFSS e devem ter contrapartida. O total de saldo_final_debito das
    contas INTRA deve igualar o total de saldo_final_credito.

    contas_intra = pcasp WHERE titulo_desc CONTAINS "INTRA"
    total_d = SUM(saldo_final_debito)  para contas INTRA na MSC
    total_c = SUM(saldo_final_credito) para contas INTRA na MSC
    SE abs(total_d - total_c) > tolerancia → ALERTA

    Se a coluna ``titulo_desc`` não existir no PCASP, a regra é desativada
    com warning (sem falso negativo por ausência de dados).

Referência:
    Portaria STN 642/2026 — Regras Gerais MSC, R053; INTRA OFSS
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pandas as pd

from ranking_msc.io.ref_loader import load_pcasp
from ranking_msc.rules.base import TOLERANCIA_CENTAVO, Rule, register_rule

if TYPE_CHECKING:
    from ranking_msc.engine.executor import EngineContext

logger = logging.getLogger("ranking_msc")


@register_rule
class R053(Rule):
    """Verifica que as contas INTRA OFSS estão balanceadas (D = C)."""

    rule_id = "R053"
    rule_name = "INTRA OFSS com contrapartida"
    dimensao = "Interconta"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Detecta desequilíbrio entre saldos finais D e C das contas INTRA.

        Args:
            df: DataFrame normalizado com colunas ``conta_contabil``,
                ``saldo_final_debito`` e ``saldo_final_credito``.
            context: metadados da execução (competência, siconfi, settings).

        Returns:
            DataFrame de pendências — vazio se balanceado ou sem contas INTRA;
            uma linha se desequilíbrio detectado.
        """
        _extra = {"regra_id": self.rule_id, "competencia": context.competencia}

        if df.empty:
            return self.build_issues([])

        # 1. Carregar PCASP e verificar presença de titulo_desc
        pcasp_raw = load_pcasp(context.settings.paths.ref_dir)
        if "titulo_desc" not in pcasp_raw.columns:
            logger.warning(
                "R053: coluna 'titulo_desc' ausente em pcasp.csv — regra desativada "
                "para esta execução. Atualize o PCASP com a coluna de descrição.",
                extra=_extra,
            )
            return self.build_issues([])

        # 2. Identificar contas INTRA pelo título
        titulo = pcasp_raw["titulo_desc"].astype(str).str.strip()
        intra_contas = set(
            pcasp_raw.loc[titulo.str.contains("INTRA", case=False, na=False), "conta_contabil"]
        )

        if not intra_contas:
            logger.info(
                "R053: nenhuma conta com 'INTRA' no título encontrada no PCASP. "
                "competência=%s",
                context.competencia,
                extra=_extra,
            )
            return self.build_issues([])

        # 3. Filtrar MSC para contas INTRA
        intra_df = df[df["conta_contabil"].isin(intra_contas)].copy()

        if intra_df.empty:
            return self.build_issues([])

        # 4. Converter saldos e calcular totais
        for col in ("saldo_final_debito", "saldo_final_credito"):
            intra_df[col] = pd.to_numeric(intra_df[col], errors="coerce").fillna(0.0)

        total_d = intra_df["saldo_final_debito"].sum()
        total_c = intra_df["saldo_final_credito"].sum()
        diferenca = abs(total_d - total_c)

        if diferenca <= TOLERANCIA_CENTAVO:
            return self.build_issues([])

        logger.warning(
            "R053: contas INTRA OFSS desequilibradas: D=%.2f, C=%.2f, "
            "diferença=%.2f. competência=%s",
            total_d,
            total_c,
            diferenca,
            context.competencia,
            extra=_extra,
        )

        return self.build_issues([{
            "severidade": "ALERTA",
            "conta_contabil": "INTRA OFSS",
            "descricao": (
                f"Contas INTRA OFSS sem contrapartida balanceada: "
                f"D={total_d:.2f}, C={total_c:.2f}, diferença={diferenca:.2f}."
            ),
            "valor_esperado": f"D={total_d:.2f}",
            "valor_encontrado": f"C={total_c:.2f}",
            "competencia": context.competencia,
        }])
