"""Regra R065 — FS com combinação função×subfunção atípica.

Dimensão: IC
Severidade padrão: INFO

Lógica:
    Conforme Portaria MOG 42/99, subfunções podem ser vinculadas a qualquer
    função. Porém, certas combinações são consideradas "típicas" e estão
    listadas na tabela FS. Combinações onde função e subfunção são válidas
    individualmente (R028 passa) mas o PAR (funcao, subfuncao) não consta
    na tabela FS são consideradas atípicas e merecem revisão.

    Severidade INFO: não impede a execução, apenas sinaliza para revisão humana.

Referência:
    Portaria MOG 42/99; Leiaute MSC 2026 — campo FS; ref/regras_catalogo.md R065
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pandas as pd

from ranking_msc.io.ref_loader import load_tabela_fs
from ranking_msc.rules.base import Rule, ic_mask_informada, register_rule

if TYPE_CHECKING:
    from ranking_msc.engine.executor import EngineContext

logger = logging.getLogger("ranking_msc")


@register_rule
class R065(Rule):
    """Sinaliza combinações função×subfunção de FS que fogem do padrão típico."""

    rule_id = "R065"
    rule_name = "FS — combinação função×subfunção atípica"
    dimensao = "IC"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Verifica se cada par (funcao, subfuncao) de FS consta na tabela típica.

        Apenas gera pendências para combinações onde ambos função e subfunção
        são individualmente válidos mas o PAR não está na tabela FS —
        casos onde um ou ambos são inválidos já são cobertos por R028.

        Args:
            df: DataFrame normalizado com colunas ``fs`` e ``conta_contabil``.
            context: metadados da execução.

        Returns:
            DataFrame de pendências INFO — uma linha por combinação atípica.
        """
        _extra = {"regra_id": self.rule_id, "competencia": context.competencia}

        if "fs" not in df.columns:
            return self.build_issues([])

        tabela = load_tabela_fs(context.settings.paths.ref_dir)
        funcoes_validas: set[str] = set(
            tabela["funcao"].astype(str).str.strip().str.zfill(2)
        )
        subfuncoes_validas: set[str] = set(
            tabela["subfuncao"].astype(str).str.strip().str.zfill(3)
        )
        pares_tipicos: set[tuple[str, str]] = {
            (row["funcao"], row["subfuncao"])
            for _, row in tabela[["funcao", "subfuncao"]].iterrows()
        }

        df_com_fs = df[["conta_contabil", "fs"]].copy()
        df_com_fs = df_com_fs[ic_mask_informada(df_com_fs["fs"])]

        if df_com_fs.empty:
            return self.build_issues([])

        df_unica = df_com_fs.drop_duplicates(subset=["conta_contabil", "fs"]).copy()
        df_unica["fs_raw"] = df_unica["fs"].astype(str).str.strip()
        df_unica["fs_val"] = df_unica["fs_raw"].str.zfill(5)
        df_unica["funcao"] = df_unica["fs_val"].str[:2]
        df_unica["subfuncao"] = df_unica["fs_val"].str[2:]

        mask_len_ok = df_unica["fs_raw"].str.len() == 5
        mask_funcao_ok = df_unica["funcao"].isin(funcoes_validas)
        mask_sub_ok = df_unica["subfuncao"].isin(subfuncoes_validas)

        df_candidatos = df_unica[mask_len_ok & mask_funcao_ok & mask_sub_ok].copy()

        if df_candidatos.empty:
            return self.build_issues([])

        mask_atipica = ~df_candidatos.apply(
            lambda r: (r["funcao"], r["subfuncao"]) in pares_tipicos, axis=1
        )
        df_viol = df_candidatos[mask_atipica]

        if df_viol.empty:
            return self.build_issues([])

        conta_s = df_viol["conta_contabil"].astype(str)
        fs_s = df_viol["fs_val"]
        funcao_s = df_viol["funcao"]
        sub_s = df_viol["subfuncao"]

        issues_df = pd.DataFrame({
            "severidade": "INFO",
            "conta_contabil": conta_s.values,
            "descricao": (
                "FS '" + fs_s + "' (função '" + funcao_s + "' + subfunção '"
                + sub_s + "') é uma combinação atípica para conta '"
                + conta_s + "' — verificar se é intencional."
            ).values,
            "valor_esperado": "combinação típica da tabela FS",
            "valor_encontrado": fs_s.values,
            "competencia": context.competencia,
        })

        logger.info(
            "R065: %d combinação(ões) FS atípica(s). competência=%s",
            len(issues_df),
            context.competencia,
            extra=_extra,
        )

        return self.build_issues(issues_df.to_dict("records"))
