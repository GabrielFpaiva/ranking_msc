"""
Regra R051 — VPA − VPD = Resultado do Exercício.

Dimensão: Interconta
Severidade padrão: ALERTA

Lógica:
    O resultado operacional (VPA − VPD) deve ser consistente com a
    variação do grupo Resultados Acumulados (PCASP 2.1.4, prefixo "214").

    vpa_liq   = SUM(mov_C - mov_D)  para contas onde conta_contabil[0] == "4"
    vpd_liq   = SUM(mov_D - mov_C)  para contas onde conta_contabil[0] == "3"
    resultado = vpa_liq - vpd_liq

    delta_pl  = SUM(SF_C - SF_D) - SUM(SI_C - SI_D)
                para contas onde conta_contabil[:3] == "214"

    SE abs(resultado - delta_pl) > tolerancia → ALERTA

Limitação conhecida:
    Ajustes diretos no PL que não transitam por classes 3/4 (doações,
    correções monetárias) podem gerar falso ALERTA. Isso é esperado —
    por isso a severidade é ALERTA e não ERRO.

Referência:
    Portaria STN 642/2026 — Regras Gerais MSC, R051
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pandas as pd

from ranking_msc.rules.base import TOLERANCIA_CENTAVO, Rule, register_rule

if TYPE_CHECKING:
    from ranking_msc.engine.executor import EngineContext

logger = logging.getLogger("ranking_msc")


@register_rule
class R051(Rule):
    """Verifica consistência entre VPA-VPD e variação dos Resultados Acumulados (2.1.4)."""

    rule_id = "R051"
    rule_name = "VPA - VPD = Resultado"
    dimensao = "Interconta"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Compara resultado operacional com variação do grupo 2.1.4 (Resultados Acumulados).

        Args:
            df: DataFrame normalizado com colunas conta_contabil, movimento_debito,
                movimento_credito, saldo_inicial_debito, saldo_inicial_credito,
                saldo_final_debito, saldo_final_credito.
            context: metadados da execução.

        Returns:
            DataFrame de pendências — vazio se consistente ou sem dados 214;
            uma linha se divergência detectada.
        """
        _extra = {"regra_id": self.rule_id, "competencia": context.competencia}

        if df.empty:
            return self.build_issues([])

        cols_valor = [
            "movimento_debito", "movimento_credito",
            "saldo_inicial_debito", "saldo_inicial_credito",
            "saldo_final_debito", "saldo_final_credito",
        ]
        work = df.copy()
        for col in cols_valor:
            work[col] = pd.to_numeric(work[col], errors="coerce").fillna(0.0)

        grupo214 = work[work["conta_contabil"].str[:3] == "214"]

        if grupo214.empty:
            logger.info(
                "R051: nenhuma conta do grupo 2.1.4 encontrada — validação ignorada. "
                "competência=%s",
                context.competencia,
                extra=_extra,
            )
            return self.build_issues([])

        classe3 = work[work["conta_contabil"].str[:1] == "3"]
        classe4 = work[work["conta_contabil"].str[:1] == "4"]

        vpa_liq = (classe4["movimento_credito"] - classe4["movimento_debito"]).sum()
        vpd_liq = (classe3["movimento_debito"] - classe3["movimento_credito"]).sum()
        resultado = vpa_liq - vpd_liq

        pl_sf = (grupo214["saldo_final_credito"] - grupo214["saldo_final_debito"]).sum()
        pl_si = (grupo214["saldo_inicial_credito"] - grupo214["saldo_inicial_debito"]).sum()
        delta_pl = pl_sf - pl_si

        diferenca = abs(resultado - delta_pl)

        if diferenca <= TOLERANCIA_CENTAVO:
            return self.build_issues([])

        logger.warning(
            "R051: VPA-VPD (%.2f) ≠ delta PL 2.1.4 (%.2f), diferença=%.2f. competência=%s",
            resultado,
            delta_pl,
            diferenca,
            context.competencia,
            extra=_extra,
        )

        return self.build_issues([{
            "severidade": "ALERTA",
            "conta_contabil": "",
            "descricao": (
                f"Resultado operacional inconsistente com Resultados Acumulados (2.1.4): "
                f"VPA-VPD={resultado:.2f}, ΔPL(2.1.4)={delta_pl:.2f}, "
                f"diferença={diferenca:.2f}."
            ),
            "valor_esperado": f"VPA-VPD={resultado:.2f}",
            "valor_encontrado": f"delta_PL(2.1.4)={delta_pl:.2f}",
            "competencia": context.competencia,
        }])
