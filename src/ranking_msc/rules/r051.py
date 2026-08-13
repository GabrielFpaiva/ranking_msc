"""
Regra R051 — VPA − VPD = Resultado do Exercício (encerramento).

Dimensão: Interconta
Severidade padrão: ALERTA

Lógica:
    No encerramento do exercício (mês 13), o resultado operacional (VPA − VPD)
    deve corresponder à variação do grupo Resultados Acumulados (PCASP 2.3.7),
    contra o qual as contas de resultado são zeradas. Nas demais competências a
    regra não se aplica e não gera pendência.

    vpa_liq   = SUM(mov_D - mov_C)  para contas onde conta_contabil[0] == "4"
    vpd_liq   = SUM(mov_C - mov_D)  para contas onde conta_contabil[0] == "3"
    resultado = vpa_liq - vpd_liq

    delta_pl  = SUM(SF_C - SF_D) - SUM(SI_C - SI_D)
                para contas onde conta_contabil[:3] == "237"

    SE abs(resultado - delta_pl) > tolerancia → ALERTA

ATENÇÃO ao sinal dos movimentos (armadilha desta regra):
    Durante o exercício (meses 1..12) o movimento de uma conta de VPA (classe 4,
    natureza credora) é *a crédito* e o de uma conta de VPD (classe 3, natureza
    devedora) é *a débito* — a VPA líquida seria SUM(mov_C - mov_D).

    No mês 13, porém, os únicos movimentos das classes 3 e 4 são os **lançamentos
    de encerramento**, que zeram essas contas: a VPA acumulada é baixada *a débito*
    e a VPD acumulada é baixada *a crédito*. Os sinais, portanto, se invertem em
    relação ao exercício corrente, e é por isso que aqui vpa_liq usa
    ``mov_D - mov_C`` e vpd_liq usa ``mov_C - mov_D``. Assim ``resultado`` volta a
    ser o resultado do exercício com o sinal econômico usual (positivo = superávit),
    diretamente comparável com ``delta_pl``, que é positivo quando o superávit foi
    incorporado a 2.3.7.

    Usar a fórmula do exercício corrente aqui produziria ``resultado`` com o sinal
    trocado e uma diferença de exatamente ``2 × |resultado|`` em *todo* arquivo
    corretamente encerrado — falso ALERTA garantido. Equivalentemente: no
    encerramento, os movimentos de zeramento e a variação de 2.3.7 se anulam.

Limitação conhecida:
    Ajustes diretos no PL que não transitam por classes 3/4 (doações, correções
    monetárias) podem gerar falso ALERTA. Por isso a severidade é ALERTA, não ERRO.

Referência:
    doc/calibracao_regras_respostas_rodrigo.md, pergunta 2;
    ref/IPC_Encerramento_STN.pdf, p. 9.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pandas as pd

from ranking_msc.rules.base import (
    TOLERANCIA_CENTAVO,
    Rule,
    competencia_de_encerramento,
    register_rule,
)

if TYPE_CHECKING:
    from ranking_msc.engine.executor import EngineContext

logger = logging.getLogger("ranking_msc")


@register_rule
class R051(Rule):
    """Verifica consistência entre VPA-VPD e variação dos Resultados Acumulados (2.3.7)."""

    rule_id = "R051"
    rule_name = "VPA - VPD = Resultado"
    dimensao = "Interconta"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Compara resultado operacional com variação do grupo 2.3.7 (Resultados Acumulados).

        Args:
            df: DataFrame normalizado com colunas conta_contabil, movimento_debito,
                movimento_credito, saldo_inicial_debito, saldo_inicial_credito,
                saldo_final_debito, saldo_final_credito.
            context: metadados da execução.

        Returns:
            DataFrame de pendências — vazio se consistente, sem dados 237 ou fora
            do encerramento; uma linha se divergência detectada no encerramento.
        """
        _extra = {"regra_id": self.rule_id, "competencia": context.competencia}

        if df.empty:
            return self.build_issues([])

        if not competencia_de_encerramento(context.competencia):
            logger.info(
                "R051: competência %s não é de encerramento — confronto VPA-VPD "
                "não se aplica.",
                context.competencia,
                extra=_extra,
            )
            return self.build_issues([])

        cols_valor = [
            "movimento_debito", "movimento_credito",
            "saldo_inicial_debito", "saldo_inicial_credito",
            "saldo_final_debito", "saldo_final_credito",
        ]
        work = df.copy()
        for col in cols_valor:
            work[col] = pd.to_numeric(work[col], errors="coerce").fillna(0.0)

        grupo237 = work[work["conta_contabil"].str[:3] == "237"]

        if grupo237.empty:
            logger.info(
                "R051: nenhuma conta do grupo 2.3.7 encontrada — validação ignorada. "
                "competência=%s",
                context.competencia,
                extra=_extra,
            )
            return self.build_issues([])

        classe3 = work[work["conta_contabil"].str[:1] == "3"]
        classe4 = work[work["conta_contabil"].str[:1] == "4"]

        # Sinais invertidos em relação ao exercício corrente: no mês 13 os
        # movimentos das classes 3 e 4 são os lançamentos de zeramento (VPA baixada
        # a débito, VPD baixada a crédito). Ver nota no docstring do módulo.
        vpa_liq = (classe4["movimento_debito"] - classe4["movimento_credito"]).sum()
        vpd_liq = (classe3["movimento_credito"] - classe3["movimento_debito"]).sum()
        resultado = vpa_liq - vpd_liq

        pl_sf = (grupo237["saldo_final_credito"] - grupo237["saldo_final_debito"]).sum()
        pl_si = (grupo237["saldo_inicial_credito"] - grupo237["saldo_inicial_debito"]).sum()
        delta_pl = pl_sf - pl_si

        diferenca = abs(resultado - delta_pl)

        if diferenca <= TOLERANCIA_CENTAVO:
            return self.build_issues([])

        logger.warning(
            "R051: VPA-VPD (%.2f) ≠ delta PL 2.3.7 (%.2f), diferença=%.2f. competência=%s",
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
                f"Resultado do exercício inconsistente com Resultados Acumulados (2.3.7): "
                f"VPA-VPD={resultado:.2f}, ΔPL(2.3.7)={delta_pl:.2f}, "
                f"diferença={diferenca:.2f}."
            ),
            "valor_esperado": f"VPA-VPD={resultado:.2f}",
            "valor_encontrado": f"delta_PL(2.3.7)={delta_pl:.2f}",
            "competencia": context.competencia,
        }])
