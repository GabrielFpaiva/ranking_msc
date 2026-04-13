# F3-09: R031 — SF = SI + Movimentos — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement rule R031, which validates that every row's ending balance equals its beginning balance plus net movements (SF = SI + Mov_D − Mov_C).

**Architecture:** Single rule file `r031.py` following the established `@register_rule` pattern. Fully vectorized (no Python loop) — compute residual column on the DataFrame, then filter violations. No reference-table lookup required: the accounting identity SF_D − SF_C = (SI_D − SI_C) + (mov_D − mov_C) is universal and holds for both Devedora and Credora accounts.

**Tech Stack:** Python 3.11, pandas, pytest, ruff, mypy.

---

## File Map

| Action | Path |
|--------|------|
| Create | `src/ranking_msc/rules/r031.py` |
| Modify | `src/ranking_msc/rules/__init__.py` |
| Modify | `config/settings.yaml.example` |
| Create | `tests/test_r031.py` |

---

## Task 1: Write failing tests

**Files:**
- Create: `tests/test_r031.py`

- [ ] **Step 1.1 — Create the test file**

```python
"""Testes da regra R031 — SF = SI + Movimentos."""

from __future__ import annotations

import pandas as pd
import pytest

from ranking_msc.rules.r031 import R031


def _df(
    conta: str,
    si_d: float,
    si_c: float,
    mov_d: float,
    mov_c: float,
    sf_d: float,
    sf_c: float,
) -> pd.DataFrame:
    """Cria DataFrame mínimo para teste de R031."""
    return pd.DataFrame({
        "conta_contabil": [conta],
        "saldo_inicial_debito": [si_d],
        "saldo_inicial_credito": [si_c],
        "movimento_debito": [mov_d],
        "movimento_credito": [mov_c],
        "saldo_final_debito": [sf_d],
        "saldo_final_credito": [sf_c],
    })


class TestR031:
    def test_conta_devedora_sf_correto_nao_gera_pendencia(
        self, engine_context: object
    ) -> None:
        """Conta devedora com SF = SI + mov_D − mov_C exato não gera pendência."""
        # SI_net = 1000-0 = 1000; mov_net = 200-50 = 150; SF_net = 1150-0 = 1150
        df = _df("111110200", si_d=1000.0, si_c=0.0, mov_d=200.0, mov_c=50.0,
                 sf_d=1150.0, sf_c=0.0)
        result = R031().execute(df, engine_context)

        assert len(result) == 0

    def test_conta_credora_sf_correto_nao_gera_pendencia(
        self, engine_context: object
    ) -> None:
        """Conta credora com SF = SI + mov_C − mov_D exato não gera pendência."""
        # SI_net = 0-500 = -500; mov_net = 100-300 = -200; SF_net = 0-700 = -700
        df = _df("211000000", si_d=0.0, si_c=500.0, mov_d=300.0, mov_c=100.0,
                 sf_d=0.0, sf_c=700.0)
        result = R031().execute(df, engine_context)

        assert len(result) == 0

    def test_sf_incorreto_gera_erro(self, engine_context: object) -> None:
        """SF divergente de SI + movimentos gera pendência ERRO."""
        # SI_net = 1000; mov_net = +150; expected SF_net = 1150; actual SF_net = 2000 → diverge
        df = _df("111110200", si_d=1000.0, si_c=0.0, mov_d=200.0, mov_c=50.0,
                 sf_d=2000.0, sf_c=0.0)
        result = R031().execute(df, engine_context)

        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ERRO"
        assert result.iloc[0]["regra_id"] == "R031"
        assert "111110200" in result.iloc[0]["descricao"]

    def test_diferenca_dentro_tolerancia_nao_gera_pendencia(
        self, engine_context: object
    ) -> None:
        """Diferença residual ≤ 0.01 não gera pendência (tolerância de centavo)."""
        # SI=1000, mov=+150, SF=1150.005 → residual = 0.005 < 0.01
        df = _df("111110200", si_d=1000.0, si_c=0.0, mov_d=200.0, mov_c=50.0,
                 sf_d=1150.005, sf_c=0.0)
        result = R031().execute(df, engine_context)

        assert len(result) == 0

    def test_diferenca_acima_tolerancia_gera_erro(self, engine_context: object) -> None:
        """Diferença residual > 0.01 gera pendência ERRO."""
        # SI=1000, mov=+150, SF=1150.02 → residual = 0.02 > 0.01
        df = _df("111110200", si_d=1000.0, si_c=0.0, mov_d=200.0, mov_c=50.0,
                 sf_d=1150.02, sf_c=0.0)
        result = R031().execute(df, engine_context)

        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ERRO"

    def test_sf_zero_si_zero_mov_zero_nao_gera_pendencia(
        self, engine_context: object
    ) -> None:
        """Conta com todos os saldos zerados não gera pendência."""
        df = _df("111110200", si_d=0.0, si_c=0.0, mov_d=0.0, mov_c=0.0,
                 sf_d=0.0, sf_c=0.0)
        result = R031().execute(df, engine_context)

        assert len(result) == 0

    def test_multiplas_contas_apenas_a_incorreta_retorna(
        self, engine_context: object
    ) -> None:
        """Apenas a conta com SF errado aparece nas pendências."""
        df = pd.DataFrame({
            "conta_contabil": ["111110200", "211000000", "311000000"],
            "saldo_inicial_debito": [1000.0, 0.0, 500.0],
            "saldo_inicial_credito": [0.0, 800.0, 0.0],
            "movimento_debito": [200.0, 100.0, 50.0],
            "movimento_credito": [50.0, 50.0, 50.0],
            "saldo_final_debito": [1150.0, 0.0, 999.0],   # 311: expected 500, got 999 → ERRO
            "saldo_final_credito": [0.0, 750.0, 0.0],
        })
        result = R031().execute(df, engine_context)

        assert len(result) == 1
        assert result.iloc[0]["conta_contabil"] == "311000000"

    def test_dataframe_vazio_retorna_vazio(self, engine_context: object) -> None:
        """DataFrame sem linhas retorna DataFrame de pendências vazio."""
        df = pd.DataFrame(columns=[
            "conta_contabil",
            "saldo_inicial_debito", "saldo_inicial_credito",
            "movimento_debito", "movimento_credito",
            "saldo_final_debito", "saldo_final_credito",
        ])
        result = R031().execute(df, engine_context)

        assert len(result) == 0

    def test_valores_string_nao_numericos_sao_tratados_como_zero(
        self, engine_context: object
    ) -> None:
        """Valores não numéricos (ex: strings vazias) são convertidos para 0.0."""
        # SI_net=0, mov_net=0, SF_net=0 → sem pendência
        df = pd.DataFrame({
            "conta_contabil": ["111110200"],
            "saldo_inicial_debito": [""],
            "saldo_inicial_credito": [""],
            "movimento_debito": [""],
            "movimento_credito": [""],
            "saldo_final_debito": [""],
            "saldo_final_credito": [""],
        })
        result = R031().execute(df, engine_context)

        assert len(result) == 0

    def test_resultado_contem_valores_esperado_e_encontrado(
        self, engine_context: object
    ) -> None:
        """Pendência deve conter valor_esperado (SF_net esperado) e valor_encontrado."""
        df = _df("111110200", si_d=1000.0, si_c=0.0, mov_d=200.0, mov_c=50.0,
                 sf_d=2000.0, sf_c=0.0)
        result = R031().execute(df, engine_context)

        assert len(result) == 1
        assert result.iloc[0]["valor_esperado"] is not None
        assert result.iloc[0]["valor_encontrado"] is not None
        assert result.iloc[0]["competencia"] == "2024-01"
```

- [ ] **Step 1.2 — Run tests to confirm they fail**

```bash
cd /home/nelson/projetos/Cerebro/Claude\ \ Cerebro/psb/01\ -\ Projects/ranking_msc
.venv/bin/python -m pytest tests/test_r031.py -v 2>&1 | head -20
```

Expected: `ImportError: cannot import name 'R031' from 'ranking_msc.rules.r031'` (or ModuleNotFoundError).

---

## Task 2: Implement r031.py

**Files:**
- Create: `src/ranking_msc/rules/r031.py`

- [ ] **Step 2.1 — Create the rule file**

```python
"""Regra R031 — Saldo Final = Saldo Inicial + Movimentos.

Dimensão: Fechamento
Severidade padrão: ERRO

Lógica:
    Para cada linha (CONTA + ICs), verifica a identidade contábil fundamental:
        SF_líquido = SI_líquido + Mov_D − Mov_C

    Onde o líquido é sempre calculado como D − C:
        SI_líquido  = saldo_inicial_debito  − saldo_inicial_credito
        SF_líquido  = saldo_final_debito    − saldo_final_credito
        Mov_líquido = movimento_debito      − movimento_credito

    Resíduo = SF_líquido − (SI_líquido + Mov_líquido)
    SE abs(Resíduo) > tolerância → ERRO

    A fórmula é algebricamente idêntica para contas Devedoras e Credoras,
    portanto não é necessário consultar a NAT_SALDO do PCASP.

Referência:
    Portaria STN 642/2026 — Regras Gerais MSC, R031 (V2 SIGEF)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pandas as pd

from ranking_msc.rules.base import Rule, register_rule

if TYPE_CHECKING:
    from ranking_msc.engine.executor import EngineContext

logger = logging.getLogger("ranking_msc")

_TOLERANCIA: float = 0.01


@register_rule
class R031(Rule):
    """Verifica que SF = SI + Movimentos para cada linha CONTA+ICs."""

    rule_id = "R031"
    rule_name = "SF = SI + Movimentos"
    dimensao = "Fechamento"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Detecta linhas onde o saldo final diverge do saldo inicial + movimentos.

        Args:
            df: DataFrame normalizado com colunas ``conta_contabil``,
                ``saldo_inicial_debito``, ``saldo_inicial_credito``,
                ``movimento_debito``, ``movimento_credito``,
                ``saldo_final_debito``, ``saldo_final_credito``.
            context: metadados da execução.

        Returns:
            DataFrame de pendências — uma linha por CONTA+ICs com
            abs(SF_líq − SI_líq − Mov_líq) > 0.01.
        """
        _extra = {"regra_id": self.rule_id, "competencia": context.competencia}

        cols_valor = [
            "saldo_inicial_debito", "saldo_inicial_credito",
            "movimento_debito", "movimento_credito",
            "saldo_final_debito", "saldo_final_credito",
        ]

        work = df[["conta_contabil"] + cols_valor].copy()

        for col in cols_valor:
            work[col] = pd.to_numeric(work[col], errors="coerce").fillna(0.0)

        if work.empty:
            return self.build_issues([])

        work["_si_liq"] = work["saldo_inicial_debito"] - work["saldo_inicial_credito"]
        work["_sf_liq"] = work["saldo_final_debito"]   - work["saldo_final_credito"]
        work["_mov_liq"] = work["movimento_debito"]    - work["movimento_credito"]
        work["_residuo"] = (work["_sf_liq"] - work["_si_liq"] - work["_mov_liq"]).abs()

        violacoes = work[work["_residuo"] > _TOLERANCIA]

        if violacoes.empty:
            return self.build_issues([])

        logger.warning(
            "R031: %d linha(s) com SF ≠ SI + Movimentos. competência=%s",
            len(violacoes),
            context.competencia,
            extra=_extra,
        )

        issues: list[dict[str, object]] = [
            {
                "severidade": "ERRO",
                "conta_contabil": str(row["conta_contabil"]),
                "descricao": (
                    f"Conta '{row['conta_contabil']}': SF ≠ SI + Movimentos. "
                    f"SF_líq={row['_sf_liq']:.2f}, "
                    f"SI_líq + Mov_líq={row['_si_liq'] + row['_mov_liq']:.2f}, "
                    f"resíduo={row['_residuo']:.2f}."
                ),
                "valor_esperado": f"{row['_si_liq'] + row['_mov_liq']:.2f}",
                "valor_encontrado": f"{row['_sf_liq']:.2f}",
                "competencia": context.competencia,
            }
            for _, row in violacoes.iterrows()
        ]

        return self.build_issues(issues)
```

- [ ] **Step 2.2 — Run tests to confirm they pass**

```bash
cd /home/nelson/projetos/Cerebro/Claude\ \ Cerebro/psb/01\ -\ Projects/ranking_msc
.venv/bin/python -m pytest tests/test_r031.py -v
```

Expected: todos os 10 testes passando.

---

## Task 3: Registrar, habilitar e commitar

**Files:**
- Modify: `src/ranking_msc/rules/__init__.py`
- Modify: `config/settings.yaml.example`

- [ ] **Step 3.1 — Registrar em `__init__.py`**

Adicionar no final das importações existentes (seguindo ordem numérica):

```python
from ranking_msc.rules.r031 import R031  # noqa: F401
```

- [ ] **Step 3.2 — Habilitar em `settings.yaml.example`**

Adicionar `"R031"` na lista `rules.enabled`, após `"R030"`:

```yaml
    - "R030"
    - "R031"
```

- [ ] **Step 3.3 — Lint e tipos**

```bash
cd /home/nelson/projetos/Cerebro/Claude\ \ Cerebro/psb/01\ -\ Projects/ranking_msc
.venv/bin/python -m ruff check src/ tests/
.venv/bin/python -m mypy src/
```

Expected: sem erros.

- [ ] **Step 3.4 — Suite completa**

```bash
.venv/bin/python -m pytest -q
```

Expected: 336 passed (326 anteriores + 10 novos).

- [ ] **Step 3.5 — Criar branch e commitar**

```bash
git checkout -b feat/F3-09-rule-r031-sf-si-movimentos
git add src/ranking_msc/rules/r031.py tests/test_r031.py \
        src/ranking_msc/rules/__init__.py config/settings.yaml.example
git commit -m "F3-09: rule R031 - SF = SI + Movimentos validation"
git push -u origin feat/F3-09-rule-r031-sf-si-movimentos
```

---

## Self-Review

**Spec coverage:**
- [x] R031 lógica: SF_líq = SI_líq + Mov_líq — implementado via coluna `_residuo`
- [x] Severidade ERRO — implementado
- [x] Tolerância 0.01 — constante `_TOLERANCIA`
- [x] Testes positivos (sem pendência): devedora correta, credora correta, zeros, dentro tolerância
- [x] Testes negativos (com pendência): SF errado, acima tolerância, múltiplas contas
- [x] Valores não numéricos → coerce para 0 (teste 1.9)
- [x] `valor_esperado` e `valor_encontrado` presentes (teste 1.10)
- [x] `@register_rule`, `rule_id`, `rule_name`, `dimensao` preenchidos
- [x] Import em `__init__.py`
- [x] Habilitado em `settings.yaml.example`

**Placeholders:** nenhum.

**Consistência de tipos:** `build_issues()` recebe `list[dict[str, object]]` — correto conforme `base.py`.
