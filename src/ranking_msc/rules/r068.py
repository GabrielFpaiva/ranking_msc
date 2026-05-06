"""
Regra R068 — Existem contas de todas as 8 classes contábeis.

Dimensão: Completude
Severidade padrão: ALERTA

Lógica:
    A MSC de um ente deve conter registros de todas as 8 classes do PCASP
    (1=Ativo, 2=Passivo, 3=VPD, 4=VPA, 5..8=Controles).
    Ausência de uma classe inteira pode indicar problema sistêmico.

    classes_presentes = set(conta_contabil.str[0])
    faltantes = {"1","2","3","4","5","6","7","8"} - classes_presentes
    SE faltantes → ALERTA(classes ausentes)

Referência:
    ref/regras_catalogo.md — R068; Portaria STN 642/2026
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

from ranking_msc.rules.base import Rule, register_rule

if TYPE_CHECKING:
    from ranking_msc.engine.executor import EngineContext

_CLASSES_ESPERADAS: frozenset[str] = frozenset("12345678")


@register_rule
class R068(Rule):
    """Verifica se todas as 8 classes contábeis estão presentes na MSC."""

    rule_id = "R068"
    rule_name = "8 classes presentes"
    dimensao = "Completude"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Detecta classes contábeis ausentes na MSC.

        Args:
            df: DataFrame normalizado com coluna ``conta_contabil``.
            context: metadados da execução.

        Returns:
            DataFrame de pendências — uma linha por classe ausente.
        """
        if df.empty:
            return self.build_issues([])

        classes_presentes = set(
            df["conta_contabil"].astype(str).str.strip().str[:1].unique()
        )
        faltantes = sorted(_CLASSES_ESPERADAS - classes_presentes)

        if not faltantes:
            return self.build_issues([])

        issues = [
            {
                "severidade": "ALERTA",
                "conta_contabil": f"Classe {c}",
                "descricao": (
                    f"Classe contábil {c} ausente na MSC. "
                    f"Classes presentes: {sorted(classes_presentes)}."
                ),
                "valor_esperado": f"Classe {c} com ≥ 1 registro",
                "valor_encontrado": "0 registros",
                "competencia": context.competencia,
            }
            for c in faltantes
        ]
        return self.build_issues(issues)
