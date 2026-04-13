# F3-08: R029 — AI Ano Inscrição RP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar a regra R029 que valida o campo `ai` (Ano de Inscrição de Restos a Pagar): formato 4 dígitos numéricos (ERRO) e ano plausível entre 2000 e o ano corrente (ALERTA).

**Architecture:** R029 é uma regra de IC pura — sem lookup em tabela de referência. Lê a coluna `ai` do DataFrame normalizado (já extraída pelo `normalize_ic()`), usa o helper `ic_esta_informada()` de `base.py` para ignorar linhas sem AI, e aplica duas validações sequenciais: formato (ERRO se não são 4 dígitos numéricos) e plausibilidade (ALERTA se fora do intervalo 2000–ano_corrente). Segue o padrão de R021.

**Tech Stack:** Python 3.11+, pandas, `datetime.date`, pytest, ruff, mypy.

---

## Mapa de arquivos

| Arquivo | Ação | Responsabilidade |
|---|---|---|
| `src/ranking_msc/rules/r029.py` | Criar | Regra R029 — formato e plausibilidade do AI |
| `tests/test_r029.py` | Criar | Testes unitários de R029 (6 casos) |
| `src/ranking_msc/rules/__init__.py` | Modificar | Registrar R029 |
| `config/settings.yaml.example` | Modificar | Habilitar `"R029"` em `rules.enabled` |

**Não alterar:** `schemas.py` (coluna `ai` já existe em `FACT_MSC_COLUMNS`), `base.py` (`ic_esta_informada` já existe), `io/ref_loader.py` (sem tabela de referência).

---

## Task 1: Criar branch

**Files:** nenhum arquivo alterado.

- [ ] **Step 1: Criar e entrar na branch**

```bash
cd "$(git rev-parse --show-toplevel)"
git checkout -b feat/F3-08-rule-r029-ai-ano-inscricao-rp
```

Esperado: `Switched to a new branch 'feat/F3-08-rule-r029-ai-ano-inscricao-rp'`

---

## Task 2: Escrever os testes com TDD

**Files:**
- Create: `tests/test_r029.py`

- [ ] **Step 1: Criar `tests/test_r029.py` com os 6 testes**

```python
"""Testes da regra R029 — AI: Ano Inscrição RP válido."""

from __future__ import annotations

import datetime

import pandas as pd

from ranking_msc.rules.r029 import R029


def _df_ai(conta: str, ai: object) -> pd.DataFrame:
    """DataFrame mínimo com uma linha e colunas conta_contabil + ai."""
    return pd.DataFrame({"conta_contabil": [conta], "ai": [ai]})


class TestR029:
    def test_ai_ausente_nao_gera_pendencia(self, engine_context: object) -> None:
        """Linha sem AI (coluna vazia) não gera pendência."""
        df = _df_ai("111110200", "")
        result = R029().execute(df, engine_context)
        assert len(result) == 0

    def test_ai_ausente_nan_nao_gera_pendencia(self, engine_context: object) -> None:
        """Linha com AI None/NaN não gera pendência."""
        df = _df_ai("111110200", None)
        result = R029().execute(df, engine_context)
        assert len(result) == 0

    def test_ai_4_digitos_ano_plausivel_nao_gera_pendencia(
        self, engine_context: object
    ) -> None:
        """AI com 4 dígitos e ano plausível (ex: 2023) não gera pendência."""
        df = _df_ai("111110200", "2023")
        result = R029().execute(df, engine_context)
        assert len(result) == 0

    def test_ai_formato_invalido_3_digitos_gera_erro(
        self, engine_context: object
    ) -> None:
        """AI com 3 dígitos gera pendência ERRO."""
        df = _df_ai("111110200", "202")
        result = R029().execute(df, engine_context)

        assert len(result) == 1
        assert result.iloc[0]["regra_id"] == "R029"
        assert result.iloc[0]["severidade"] == "ERRO"
        assert "202" in result.iloc[0]["descricao"]
        assert result.iloc[0]["competencia"] == "2024-01"

    def test_ai_formato_nao_numerico_gera_erro(self, engine_context: object) -> None:
        """AI com 4 caracteres não numéricos gera pendência ERRO."""
        df = _df_ai("111110200", "ABCD")
        result = R029().execute(df, engine_context)

        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ERRO"
        assert result.iloc[0]["regra_id"] == "R029"

    def test_ai_ano_abaixo_de_2000_gera_alerta(self, engine_context: object) -> None:
        """AI com ano < 2000 (ex: '1999') gera pendência ALERTA."""
        df = _df_ai("111110200", "1999")
        result = R029().execute(df, engine_context)

        assert len(result) == 1
        assert result.iloc[0]["regra_id"] == "R029"
        assert result.iloc[0]["severidade"] == "ALERTA"
        assert "1999" in result.iloc[0]["descricao"]

    def test_ai_ano_acima_do_corrente_gera_alerta(
        self, engine_context: object
    ) -> None:
        """AI com ano > ano corrente gera pendência ALERTA."""
        ano_futuro = str(datetime.date.today().year + 1)
        df = _df_ai("111110200", ano_futuro)
        result = R029().execute(df, engine_context)

        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ALERTA"
        assert ano_futuro in result.iloc[0]["descricao"]

    def test_multiplas_linhas_cada_uma_com_ai_invalido(
        self, engine_context: object
    ) -> None:
        """Múltiplas linhas com AI inválido geram uma pendência por combinação conta/AI."""
        df = pd.DataFrame({
            "conta_contabil": ["111110200", "211000000", "311000000"],
            "ai": ["2023", "1999", "ABCD"],  # válido, implausível, formato errado
        })
        result = R029().execute(df, engine_context)

        assert len(result) == 2
        severidades = set(result["severidade"].tolist())
        assert severidades == {"ALERTA", "ERRO"}
```

- [ ] **Step 2: Rodar os testes para confirmar que falham por `ImportError`**

```bash
cd "$(git rev-parse --show-toplevel)"
pytest tests/test_r029.py -v
```

Esperado: ERRO com `ModuleNotFoundError: No module named 'ranking_msc.rules.r029'`.

---

## Task 3: Implementar R029

**Files:**
- Create: `src/ranking_msc/rules/r029.py`

- [ ] **Step 1: Criar `src/ranking_msc/rules/r029.py`**

```python
"""Regra R029 — AI (Ano Inscrição RP) válido.

Categoria: IC
Severidade: ERRO (formato inválido) | ALERTA (ano implausível)

Lógica:
    Quando uma conta possui IC do tipo AI (Ano de Inscrição em Restos a Pagar),
    o valor deve:
    1. Ter exatamente 4 dígitos numéricos → ERRO se violado.
    2. Ser um ano plausível: >= 2000 e <= ano corrente → ALERTA se violado.

    Linhas sem AI (ic_esta_informada retorna False) são ignoradas.

Referência:
    Leiaute MSC 2026 — IC tipo AI; Portaria STN 642/2026
"""

from __future__ import annotations

import datetime
import logging
from typing import TYPE_CHECKING

import pandas as pd

from ranking_msc.rules.base import Rule, ic_esta_informada, register_rule

if TYPE_CHECKING:
    from ranking_msc.engine.executor import EngineContext

logger = logging.getLogger("ranking_msc")


@register_rule
class R029(Rule):
    """Valida formato (4 dígitos) e plausibilidade do Ano Inscrição RP."""

    rule_id = "R029"
    rule_name = "AI — Ano Inscrição RP válido"
    dimensao = "IC"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Verifica formato e plausibilidade do campo ai.

        Args:
            df: DataFrame normalizado com colunas ``conta_contabil`` e ``ai``.
            context: metadados da execução (competência, siconfi, settings).

        Returns:
            DataFrame de pendências — ERRO para formato inválido,
            ALERTA para ano fora do intervalo [2000, ano_corrente].
        """
        _extra = {"regra_id": self.rule_id, "competencia": context.competencia}

        ano_corrente = datetime.date.today().year

        df_com_ai = (
            df[df["ai"].apply(ic_esta_informada)][["conta_contabil", "ai"]]
            .drop_duplicates()
            .copy()
        )
        df_com_ai["ai"] = df_com_ai["ai"].astype(str).str.strip()

        if df_com_ai.empty:
            return self.build_issues([])

        issues: list[dict[str, object]] = []

        for _, row in df_com_ai.iterrows():
            ai_val = str(row["ai"])
            conta = str(row["conta_contabil"])

            # Validação 1 — formato: exatamente 4 dígitos numéricos
            if len(ai_val) != 4 or not ai_val.isdigit():
                issues.append({
                    "severidade": "ERRO",
                    "conta_contabil": conta,
                    "descricao": (
                        f"AI '{ai_val}' fora do formato: "
                        f"esperado exatamente 4 dígitos numéricos, "
                        f"encontrado '{ai_val}'."
                    ),
                    "valor_esperado": "4 dígitos numéricos (ex: '2023')",
                    "valor_encontrado": ai_val,
                    "competencia": context.competencia,
                })
                continue  # formato errado → não verifica plausibilidade

            # Validação 2 — plausibilidade: 2000 <= ano <= ano_corrente
            ano = int(ai_val)
            if ano < 2000 or ano > ano_corrente:
                issues.append({
                    "severidade": "ALERTA",
                    "conta_contabil": conta,
                    "descricao": (
                        f"AI '{ai_val}' implausível: "
                        f"esperado ano entre 2000 e {ano_corrente}, "
                        f"encontrado {ano}."
                    ),
                    "valor_esperado": f"2000 ≤ ano ≤ {ano_corrente}",
                    "valor_encontrado": ai_val,
                    "competencia": context.competencia,
                })

        if issues:
            logger.warning(
                "R029: %d pendência(s) de AI inválido. competência=%s",
                len(issues),
                context.competencia,
                extra=_extra,
            )

        return self.build_issues(issues)
```

- [ ] **Step 2: Rodar os testes de R029**

```bash
cd "$(git rev-parse --show-toplevel)"
pytest tests/test_r029.py -v
```

Esperado: todos os 8 testes PASSED.

- [ ] **Step 3: Lint e tipos**

```bash
ruff check src/ranking_msc/rules/r029.py
mypy src/ranking_msc/rules/r029.py
```

Esperado: saída limpa, sem erros.

- [ ] **Step 4: Commit**

```bash
git add src/ranking_msc/rules/r029.py tests/test_r029.py
git commit -m "F3-08: implement R029 AI year format and plausibility validation"
```

---

## Task 4: Registrar R029 e habilitar nas settings

**Files:**
- Modify: `src/ranking_msc/rules/__init__.py`
- Modify: `config/settings.yaml.example`

- [ ] **Step 1: Adicionar import em `src/ranking_msc/rules/__init__.py`**

Adicionar após a linha `from ranking_msc.rules.r023 import R023  # noqa: F401`
(mantendo ordem numérica):

```python
from ranking_msc.rules.r029 import R029  # noqa: F401
```

O bloco completo de imports deve ficar:

```python
from ranking_msc.rules.r001 import R001  # noqa: F401
from ranking_msc.rules.r002 import R002  # noqa: F401
from ranking_msc.rules.r003 import R003  # noqa: F401
from ranking_msc.rules.r004 import R004  # noqa: F401
from ranking_msc.rules.r005 import R005  # noqa: F401
from ranking_msc.rules.r010 import R010  # noqa: F401
from ranking_msc.rules.r011 import R011  # noqa: F401
from ranking_msc.rules.r012 import R012  # noqa: F401
from ranking_msc.rules.r020 import R020  # noqa: F401
from ranking_msc.rules.r021 import R021  # noqa: F401
from ranking_msc.rules.r022 import R022  # noqa: F401
from ranking_msc.rules.r023 import R023  # noqa: F401
from ranking_msc.rules.r029 import R029  # noqa: F401
from ranking_msc.rules.r030 import R030  # noqa: F401
from ranking_msc.rules.r080 import R080  # noqa: F401
from ranking_msc.rules.r081 import R081  # noqa: F401
```

- [ ] **Step 2: Habilitar em `config/settings.yaml.example`**

Adicionar `"R029"` após `"R023"` (mantendo ordem numérica):

```yaml
rules:
  enabled:
    - "R001"
    - "R002"
    - "R003"
    - "R004"
    - "R005"
    - "R010"
    - "R011"
    - "R012"
    - "R020"
    - "R021"
    - "R022"
    - "R023"
    - "R029"
    - "R030"
    - "R080"
    - "R081"
  fail_fast: false
```

- [ ] **Step 3: Verificar que RULE_REGISTRY contém R029**

```bash
cd "$(git rev-parse --show-toplevel)"
.venv/bin/python -c "
import ranking_msc.rules
from ranking_msc.rules.base import RULE_REGISTRY
print(sorted(RULE_REGISTRY.keys()))
"
```

Esperado: lista inclui `'R029'`.

- [ ] **Step 4: Suite completa de testes**

```bash
pytest -v
```

Esperado: todos PASSED, sem regressões.

- [ ] **Step 5: Lint e tipos — suite completa**

```bash
ruff check src/ tests/
mypy src/
```

Esperado: saída limpa, sem erros.

- [ ] **Step 6: Commit final**

```bash
git add src/ranking_msc/rules/__init__.py config/settings.yaml.example
git commit -m "F3-08: register R029 in rules module and enable in settings"
```

---

## Self-Review

**Cobertura da spec:**
- [x] AI ausente/vazio → sem pendência ✓ (test_ai_ausente_*, test_ai_ausente_nan_*)
- [x] AI com 4 dígitos + ano plausível → sem pendência ✓ (test_ai_4_digitos_ano_plausivel_*)
- [x] AI com != 4 dígitos → ERRO ✓ (test_ai_formato_invalido_3_digitos_*)
- [x] AI não numérico → ERRO ✓ (test_ai_formato_nao_numerico_*)
- [x] AI com ano < 2000 → ALERTA ✓ (test_ai_ano_abaixo_de_2000_*)
- [x] AI com ano > ano_corrente → ALERTA ✓ (test_ai_ano_acima_do_corrente_*)
- [x] Múltiplas linhas com falhas distintas → pendências individuais ✓ (test_multiplas_linhas_*)
- [x] Registro em `__init__.py` ✓ (Task 4)
- [x] Habilitação em `settings.yaml.example` ✓ (Task 4)

**Riscos e pontos de atenção:**
- `continue` após ERRO de formato evita falso ALERTA de plausibilidade na mesma linha.
- `drop_duplicates()` garante que a mesma combinação conta/AI inválida não gere pendências duplicadas.
- O `ano_corrente` é calculado em `execute()` a cada chamada — correto para produção (o ano pode mudar entre execuções).
- `ic_esta_informada()` já trata None, NaN, string vazia e "0" — sem lógica extra necessária.
- Não há tabela de referência → sem risco de arquivo ausente em produção.
