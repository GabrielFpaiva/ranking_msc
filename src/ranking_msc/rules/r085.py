"""
Regra R085 — Depreciação/amortização/exaustão sem movimentação mensal (SIGEF V19).

Dimensão: Completude
Severidade padrão: ALERTA

Lógica:
    Contas patrimoniais de depreciação acumulada, exaustão ou amortização acumulada
    devem ter period_change todo mês. Ausência indica que o ente não está registrando
    depreciação conforme MCASP.

    Contas de depreciação são identificadas pelo título no PCASP (contém "DEPRECIA",
    "AMORTIZA" ou "EXAUST") e natureza Credora.

    PARA CADA conta_deprec:
        SE conta não aparece no df com _has_period_change = True → ALERTA

    Implementação condicional: se 'titulo_desc' não estiver em pcasp.csv, a regra
    é desativada com aviso (graceful degradation — coluna não disponível na versão
    atual do PCASP).

Referência:
    Ranking Siconfi 2026 — verificação V19; MCASP; R010, R040; R085
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

_DEPREC_PATTERN = r"DEPRECIA|AMORTIZA|EXAUST"
_NAT_CREDORA = "Credora"
_FLAG_PC = "_has_period_change"


def _parse_flag(series: pd.Series) -> pd.Series:
    """Converte coluna de flag de presença em Series booleana.

    Handles bool, int (0/1) e string ("True"/"False"/"1"/"0").
    """
    if pd.api.types.is_bool_dtype(series):
        return series
    s = series.astype(str).str.strip().str.lower()
    return s.isin({"true", "1"})


@register_rule
class R085(Rule):
    """Detecta contas de depreciação sem movimentação no mês."""

    rule_id = "R085"
    rule_name = "Depreciação sem movimentação"
    dimensao = "Completude"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Identifica contas de depreciação sem period_change no mês.

        Requer coluna 'titulo_desc' em pcasp.csv. Se ausente, a regra é
        desativada com logger.warning (graceful degradation — coluna não
        disponível na versão atual do PcaspEstendido2026).

        Args:
            df: DataFrame normalizado com colunas ``conta_contabil`` e
                ``_has_period_change``.
            context: metadados da execução (competência, siconfi, settings).

        Returns:
            DataFrame de pendências — uma linha por conta de depreciação sem
            movimentação. Retorna vazio se titulo_desc ausente no PCASP.
        """
        _extra = {"regra_id": self.rule_id, "competencia": context.competencia}

        pcasp_raw = load_pcasp(context.settings.paths.ref_dir)

        # Graceful degradation: titulo_desc ausente no pcasp.csv atual
        if "titulo_desc" not in pcasp_raw.columns:
            logger.warning(
                "R085: coluna 'titulo_desc' ausente em pcasp.csv — regra desativada. "
                "Disponível apenas com PcaspEstendido2026 completo (SIGEF V19).",
                extra=_extra,
            )
            return self.build_issues([])

        if "nat_saldo" not in pcasp_raw.columns:
            logger.warning(
                "R085: coluna 'nat_saldo' ausente em pcasp.csv — regra desativada.",
                extra=_extra,
            )
            return self.build_issues([])

        # Identifica contas de depreciação/amortização/exaustão com NAT_SALDO=Credora
        pcasp = pcasp_raw[["conta_contabil", "titulo_desc", "nat_saldo"]].copy()
        pcasp["titulo_desc"] = pcasp["titulo_desc"].astype(str).str.strip()
        pcasp["nat_saldo"] = pcasp["nat_saldo"].astype(str).str.strip()

        contas_deprec = pcasp[
            pcasp["titulo_desc"].str.contains(_DEPREC_PATTERN, case=False, na=False)
            & (pcasp["nat_saldo"] == _NAT_CREDORA)
        ]["conta_contabil"].unique()

        if len(contas_deprec) == 0:
            return self.build_issues([])

        if "conta_contabil" not in df.columns:
            return self.build_issues([])

        # Para cada conta de depreciação, verifica se tem period_change
        if _FLAG_PC in df.columns:
            df_flags = df[["conta_contabil", _FLAG_PC]].copy()
            df_flags["_pc_bool"] = _parse_flag(df_flags[_FLAG_PC])
            # Agrega por conta: True se QUALQUER linha da conta tem period_change
            has_pc = (
                df_flags.groupby("conta_contabil")["_pc_bool"]
                .any()
                .reset_index()
                .rename(columns={"_pc_bool": "_tem_pc"})
            )
        else:
            # Sem flag: não há como verificar — retorna vazio conservador
            logger.warning(
                "R085: coluna '_has_period_change' ausente — regra desativada.",
                extra=_extra,
            )
            return self.build_issues([])

        # Cria DataFrame das contas de depreciação e faz merge com flags
        deprec_df = pd.DataFrame({"conta_contabil": contas_deprec})
        merged = deprec_df.merge(has_pc, on="conta_contabil", how="left")
        merged["_tem_pc"] = merged["_tem_pc"].fillna(False).astype(bool)

        violacoes = merged[~merged["_tem_pc"]].copy()

        if violacoes.empty:
            return self.build_issues([])

        logger.warning(
            "R085: %d conta(s) de depreciação sem movimentação no mês. competência=%s",
            len(violacoes),
            context.competencia,
            extra=_extra,
        )

        conta_s = violacoes["conta_contabil"].astype(str)

        issues_df = pd.DataFrame({
            "severidade": "ALERTA",
            "conta_contabil": conta_s.values,
            "descricao": (
                "Conta '"
                + conta_s
                + "': depreciação/amortização/exaustão sem movimentação "
                "(period_change ausente). Registro de depreciação conforme MCASP "
                "obrigatório todo mês (SIGEF V19)."
            ).values,
            "valor_esperado": "period_change presente",
            "valor_encontrado": "period_change ausente",
            "competencia": context.competencia,
        })

        return self.build_issues(issues_df.to_dict("records"))
