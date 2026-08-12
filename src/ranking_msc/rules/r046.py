"""Regra R046 — ND classificada como genérica (informativo).

Dimensão: IC
Severidade padrão: INFO — fora da pontuação (is_scoring=False)

Lógica:
    Marca as NDs cujo nome na tabela ND contém "Genéric". A verificação nasceu de
    uma tabela De-Para e não tem respaldo no leiaute: as 77 NDs que ela apontava
    estão todas classificadas como último nível na tabela oficial da STN, ou seja,
    todas são de uso válido. Fica como sinal informativo.

Referência:
    doc/calibracao_regras_respostas_rodrigo.md, pergunta 4.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, ClassVar

import pandas as pd

from ranking_msc.io.ref_loader import load_tabela_nd
from ranking_msc.rules.base import Rule, ic_mask_informada, register_rule

if TYPE_CHECKING:
    from ranking_msc.engine.executor import EngineContext

logger = logging.getLogger("ranking_msc")


@register_rule
class R046(Rule):
    """Sinaliza ND classificada como genérica — informativo, fora da pontuação."""

    rule_id = "R046"
    rule_name = "ND genérica (informativo)"
    dimensao = "IC"
    is_scoring: ClassVar[bool] = False

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Verifica se cada ND informada não tem 'Genéric' no nome da tabela ND.

        Args:
            df: DataFrame normalizado com colunas ``nd`` e ``conta_contabil``.
            context: metadados da execução.

        Returns:
            DataFrame de pendências — uma linha por ND genérica encontrada.
        """
        _extra = {"regra_id": self.rule_id, "competencia": context.competencia}

        if "nd" not in df.columns:
            return self.build_issues([])

        tabela = load_tabela_nd(context.settings.paths.ref_dir)
        nd_genericas: set[str] = set(
            tabela.loc[
                tabela["nome"].str.strip().str.contains("Genéric", na=False, case=False),
                "codigo",
            ]
            .astype(str)
            .str.strip()
            .str.zfill(8)
        )

        df_com_nd = df[["conta_contabil", "nd"]].copy()
        df_com_nd = df_com_nd[ic_mask_informada(df_com_nd["nd"])]

        if df_com_nd.empty:
            return self.build_issues([])

        df_unica = df_com_nd.drop_duplicates(subset=["conta_contabil", "nd"]).copy()
        df_unica["nd_val"] = df_unica["nd"].astype(str).str.strip().str.zfill(8)

        mask_generica = df_unica["nd_val"].isin(nd_genericas)
        df_viol = df_unica[mask_generica]

        if df_viol.empty:
            return self.build_issues([])

        conta_s = df_viol["conta_contabil"].astype(str)
        nd_s = df_viol["nd_val"]

        issues_df = pd.DataFrame({
            "severidade": "INFO",
            "conta_contabil": conta_s.values,
            "descricao": (
                "ND '" + nd_s + "' é classificada como genérica (De-Para) para conta '"
                + conta_s + "' — sinal informativo, uso legítimo confirmado na tabela STN."
            ).values,
            "valor_esperado": "ND de uso legítimo (informativo)",
            "valor_encontrado": nd_s.values,
            "competencia": context.competencia,
        })

        logger.info(
            "R046: %d ND(s) genérica(s) sinalizada(s) (informativo). competência=%s",
            len(issues_df),
            context.competencia,
            extra=_extra,
        )

        return self.build_issues(issues_df.to_dict("records"))
