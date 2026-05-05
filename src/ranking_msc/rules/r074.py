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
    que indica exportação incompleta.

    O reader_msc._pivot_values adiciona dois flags booleanos ao DataFrame:
        _has_saldo_inicial  — True se havia ao menos uma linha beginning_balance
        _has_saldo_final    — True se havia ao menos uma linha ending_balance

    Para period_change não há flag dedicado, pois sua presença pode ser
    inferida dos valores: movimento ≠ 0 implica que a linha existia.  Mas
    se ambas as colunas de movimento são zero, a linha pode ter existido com
    valor zero (ex: encerramento sem movimento); esse cenário não é
    penalizado por R074 — a regra exige SF *ou* MOV, então a ausência de
    ambos (flags e valores) é suficiente para flagrar.

    PARA CADA chave (conta + ICs):
      SE _has_saldo_inicial E NÃO _has_saldo_final E movimento == 0 → ALERTA

    Fallback para DataFrames sem os flags (ex: testes unitários sem pivot
    real): usa != 0 nos valores — mantém comportamento anterior nesses casos.

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


@register_rule
class R074(Rule):
    """Verifica se toda chave conta/IC tem saldo final ou movimentação."""

    rule_id = "R074"
    rule_name = "Chave com SF ou PC"
    dimensao = "Completude"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Detecta linhas com saldo inicial mas sem SF nem movimentação.

        Usa os flags de presença (_has_saldo_inicial, _has_saldo_final)
        adicionados pelo reader_msc._pivot_values para distinguir
        'saldo zero legítimo' de 'tipo ausente no CSV'.  Quando os flags
        não estão presentes (ex: DataFrames sintéticos em testes de outras
        regras), recai em comparação de valor != 0 como fallback.

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
            has_si = work[_FLAG_SI].astype(bool)
        else:
            has_si = (work[list(_COLS_SI)] != 0).any(axis=1)

        # --- Presença de saldo final ---
        # Flag preferencial: _has_saldo_final (True = linha ending_balance existia,
        # mesmo que o valor seja zero — ex: conta encerrada zerada).
        # Fallback: qualquer valor != 0 nas colunas de SF.
        if _FLAG_SF in work.columns:
            has_sf = work[_FLAG_SF].astype(bool)
        else:
            has_sf = (work[list(_COLS_SF)] != 0).any(axis=1)

        # --- Presença de movimentação ---
        # Não há flag dedicado para period_change.  Valor != 0 é suficiente:
        # se a linha period_change existia com valor zero, a regra não dispara
        # porque a ausência de SF é que determina o alerta — e nesse caso
        # o ente tem um saldo inicial + movimento zero + sem SF, cenário que
        # merece alerta independentemente.
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
                "valor_esperado": "linha ending_balance presente no CSV",
                "valor_encontrado": (
                    f"SI_D={si_d.loc[idx]:.2f}, SI_C={si_c.loc[idx]:.2f}; "
                    "SF ausente, MOV=0"
                ),
                "competencia": context.competencia,
            }
            for idx, row in violacoes.iterrows()
        ]
        return self.build_issues(issues)
