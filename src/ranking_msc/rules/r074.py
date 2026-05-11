"""
Regra R074 — Cada conta/IC deve ter ending_balance OU period_change.

Dimensão: Completude
Severidade padrão: ALERTA

Lógica:
    Registros com apenas saldo inicial (sem saldo final nem movimentação)
    são inúteis para análise — indicam exportação incompleta.

    A condição é baseada em *presença de tipos* (set(Tipo_valor)), não em
    magnitude de valor.  Um ending_balance com valor zero é válido — o ente
    encerrou a conta zerada; já a ausência da linha ending_balance no CSV é
    que indica exportação incompleta.  O mesmo vale para period_change: uma
    linha com valor zero significa que o tipo foi exportado (sem movimento),
    não que a chave está incompleta.

    O reader_msc._pivot_values adiciona três flags booleanos ao DataFrame:
        _has_saldo_inicial  — True se havia ao menos uma linha beginning_balance
        _has_saldo_final    — True se havia ao menos uma linha ending_balance
        _has_period_change  — True se havia ao menos uma linha period_change

    PARA CADA chave (conta + ICs):
      SE _has_saldo_inicial
         E NÃO _has_saldo_final
         E NÃO _has_period_change → ALERTA

    Fallback para DataFrames sem os flags (ex: testes unitários sem pivot
    real): usa != 0 nos valores — mantém comportamento conservador nesses
    casos.

Referência:
    ref/regras_catalogo.md — R074; Portaria STN 642/2026
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

from ranking_msc.rules.base import Rule, register_rule

if TYPE_CHECKING:
    from ranking_msc.engine.executor import EngineContext

_COLS_SF = ("saldo_final_debito", "saldo_final_credito")
_COLS_MOV = ("movimento_debito", "movimento_credito")
_COLS_SI = ("saldo_inicial_debito", "saldo_inicial_credito")

_FLAG_SI = "_has_saldo_inicial"
_FLAG_SF = "_has_saldo_final"
_FLAG_PC = "_has_period_change"


def _parse_flag(series: pd.Series) -> pd.Series:
    """Converte uma coluna de flag de presença em Series booleana.

    Os flags _has_* são gerados como ``bool`` pelo reader, mas a passagem
    de normalização de strings em ``_pivot_values`` pode convertê-los para
    as strings ``"True"`` / ``"False"``.  ``astype(bool)`` trataria a
    string ``"False"`` como ``True`` (string não-vazia é truthy), o que
    suprimiria alertas legítimos.

    Esta função aceita ambos os formatos:
    - ``bool``/``np.bool_`` nativos → passagem direta.
    - strings ``"True"``/``"1"``/``"yes"`` (case-insensitive) → True;
      qualquer outro valor (``"False"``, ``"0"``, ``"no"``, vazio, NaN) → False.
    - NaN/None → False.

    Args:
        series: coluna do DataFrame contendo o flag de presença.

    Returns:
        ``pd.Series`` de dtype ``bool``.
    """
    if pd.api.types.is_bool_dtype(series):
        return series.astype(bool)
    # String path: conjunto de valores considerados truthy (case-insensitive).
    # Inclui "1"/"0" para round-trips CSV/export que serializam bool como inteiro.
    _truthy = frozenset({"true", "1", "yes"})
    return series.astype(str).str.strip().str.lower().isin(_truthy)


@register_rule
class R074(Rule):
    """Verifica se toda chave conta/IC tem saldo final ou movimentação."""

    rule_id = "R074"
    rule_name = "Chave com SF ou PC"
    dimensao = "Completude"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Detecta linhas com saldo inicial mas sem SF nem movimentação.

        Usa os flags de presença (_has_saldo_inicial, _has_saldo_final,
        _has_period_change) adicionados pelo reader_msc._pivot_values para
        distinguir 'tipo ausente no CSV' de 'tipo presente com valor zero'.
        Quando os flags não estão presentes (ex: DataFrames sintéticos em
        testes de outras regras), recai em comparação de valor != 0 como
        fallback.

        Args:
            df: DataFrame normalizado com colunas de saldo e movimentação.
            context: metadados da execução.

        Returns:
            DataFrame de pendências — uma linha por chave conta/IC incompleta.
        """
        if df.empty:
            return self.build_issues([])

        work = df.copy()
        for col in (*_COLS_SF, *_COLS_MOV, *_COLS_SI):
            work[col] = pd.to_numeric(work[col], errors="coerce").fillna(0.0)

        # --- Presença de saldo inicial ---
        # Flag preferencial: _has_saldo_inicial (True = linha beginning_balance existia)
        # Fallback: qualquer valor != 0 nas colunas de SI.
        if _FLAG_SI in work.columns:
            has_si = _parse_flag(work[_FLAG_SI])
        else:
            has_si = (work[list(_COLS_SI)] != 0).any(axis=1)

        # --- Presença de saldo final ---
        # Flag preferencial: _has_saldo_final (True = linha ending_balance existia,
        # mesmo que o valor seja zero — ex: conta encerrada zerada).
        # Fallback: qualquer valor != 0 nas colunas de SF.
        if _FLAG_SF in work.columns:
            has_sf = _parse_flag(work[_FLAG_SF])
        else:
            has_sf = (work[list(_COLS_SF)] != 0).any(axis=1)

        # --- Presença de movimentação ---
        # Flag preferencial: _has_period_change (True = linha period_change existia
        # no CSV, mesmo que o valor seja zero — ex: conta sem movimentação no período).
        # Fallback: qualquer valor != 0 nas colunas de movimento.
        if _FLAG_PC in work.columns:
            has_mov = _parse_flag(work[_FLAG_PC])
        else:
            has_mov = (work[list(_COLS_MOV)] != 0).any(axis=1)


        violacoes = work[has_si & ~has_sf & ~has_mov]

        if violacoes.empty:
            return self.build_issues([])

        si_d = work.loc[violacoes.index, "saldo_inicial_debito"]
        si_c = work.loc[violacoes.index, "saldo_inicial_credito"]

        issues = [
            {
                "severidade": "ALERTA",
                "conta_contabil": str(row["conta_contabil"]),
                "descricao": (
                    "Conta/IC com saldo inicial mas sem saldo final nem movimentação."
                ),
                "valor_esperado": "linhas ending_balance ou period_change presentes no CSV",
                "valor_encontrado": (
                    f"SI_D={si_d.loc[idx]:.2f}, SI_C={si_c.loc[idx]:.2f}; "
                    "SF ausente, period_change ausente"
                ),
                "competencia": context.competencia,
            }
            for idx, row in violacoes.iterrows()
        ]
        return self.build_issues(issues)
