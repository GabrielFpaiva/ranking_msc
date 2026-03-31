---
name: new-rule
description: Implement a new validation rule R<NNN> following the project's registry pattern. Use when adding any rule from the R001-R070 catalogue or a new custom rule. Covers file creation, registration, settings config, and tests.
---

# Implement New Validation Rule

Creates a new rule file, registers it in the RULE_REGISTRY, enables it in settings, and writes tests.

## When to Use

- Adding any rule from the R001–R070 catalogue
- Adding a custom validation rule not in the catalogue
- Fixing or extending an existing rule file

## When NOT to Use

- Modifying the engine itself → edit `engine/executor.py` directly
- Adding a reference table used by rules → use `/ref-table` skill
- Modifying the schema → use `/schema-column` skill

## Prerequisites

- Know the rule ID (e.g., `R082`), name, and dimensão
- Understand what MSC columns it validates (check `schemas.py`)
- Rule logic documented in `ref/regras_piloto.md` or the catalogue

## Process

### Step 1: Create rule file

Create `src/ranking_msc/rules/r<NNN>.py` with this exact structure:

```python
"""
Regra R<NNN> — <Nome descritivo>.

Dimensão: <Fechamento | PCASP | Domínio | Orçamentária | Temporal>
Severidade padrão: <ERRO | ALERTA>

Lógica:
    <Descrever em 2-3 linhas o que a regra verifica.>

Referência:
    <Manual STN página X / documentação SICONFI>
"""

from __future__ import annotations

import pandas as pd

from ranking_msc.engine.executor import EngineContext
from ranking_msc.rules.base import Rule, register_rule


@register_rule
class R<NNN>(Rule):
    rule_id = "R<NNN>"
    rule_name = "<Nome curto>"
    dimensao = "<Dimensão>"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """<Uma linha descrevendo o que verifica>."""
        issues: list[dict[str, object]] = []

        # --- LÓGICA DA REGRA ---
        # Exemplo:
        # mask = df["debito"] != df["credito"]
        # for _, row in df[mask].iterrows():
        #     issues.append({
        #         "severidade": "ERRO",
        #         "conta_contabil": row["conta_contabil"],
        #         "descricao": "Débito ≠ Crédito",
        #         "valor_esperado": str(row["debito"]),
        #         "valor_encontrado": str(row["credito"]),
        #         "competencia": context.competencia,
        #     })

        return self.build_issues(issues)
```

### Step 2: Register in `__init__.py`

Open `src/ranking_msc/rules/__init__.py` and add the import:

```python
from ranking_msc.rules.r<NNN> import R<NNN>  # noqa: F401
```

Keep imports sorted by rule number.

### Step 3: Enable in settings

Add to `config/settings.yaml` under `rules.enabled`:

```yaml
rules:
  enabled:
    - "R<NNN>"
```

**Note:** `config/settings.yaml` is gitignored. Update `config/settings.yaml.example` too so the example stays in sync.

### Step 4: Write tests

Add to `tests/test_rules.py` (or create `tests/test_r<NNN>.py` if logic is complex):

```python
import pytest
import pandas as pd
from ranking_msc.rules.r<NNN> import R<NNN>


class TestR<NNN>:
    def test_dados_corretos_sem_pendencia(self, engine_context):
        """Dados válidos → nenhuma pendência."""
        df = pd.DataFrame({
            # minimal valid DataFrame for this rule
        })
        rule = R<NNN>()
        result = rule.execute(df, engine_context)
        assert len(result) == 0

    def test_dados_incorretos_gera_pendencia(self, engine_context):
        """Dados com violação → pendência com severidade ERRO."""
        df = pd.DataFrame({
            # DataFrame with the violation condition
        })
        rule = R<NNN>()
        result = rule.execute(df, engine_context)
        assert len(result) > 0
        assert result.iloc[0]["severidade"] == "ERRO"
        assert result.iloc[0]["regra_id"] == "R<NNN>"
```

### Step 5: Run quality checks

```bash
pytest tests/ -k "R<NNN>" -v
ruff check src/ tests/
mypy src/
```

Expected: all pass with no errors.

## Checklist

- [ ] `@register_rule` decorator applied
- [ ] `rule_id`, `rule_name`, `dimensao` set
- [ ] `execute()` returns via `self.build_issues()`
- [ ] Module-level docstring with Dimensão, Severidade, Lógica, Referência
- [ ] Import added to `rules/__init__.py`
- [ ] Rule ID added to `config/settings.yaml` (and `.example`)
- [ ] At least 2 tests: positive (no issues) + negative (with violation)
- [ ] `pytest`, `ruff check`, `mypy` all pass

## Key Patterns

### build_issues() auto-injects metadata

`self.build_issues(rows)` automatically fills `regra_id`, `regra_nome`, `dimensao`.
You only need these keys in each row dict:
- `severidade` — `"ERRO"` or `"ALERTA"`
- `conta_contabil` — the account that violated the rule
- `descricao` — human-readable explanation in Portuguese
- `valor_esperado` — what was expected (as string)
- `valor_encontrado` — what was found (as string)
- `competencia` — from `context.competencia`

### Never raise exceptions in execute()

Rules should never raise exceptions. If data is missing or malformed, return an empty DataFrame or log a warning. The engine wraps `execute()` in a try/except.

### Use context for metadata

```python
issues.append({
    "competencia": context.competencia,   # "2024-01"
    # context.siconfi, context.settings also available
})
```

## References

- `CLAUDE.md §4.1` — Rule implementation pattern
- `src/ranking_msc/rules/base.py` — Rule ABC and register_rule decorator
- `src/ranking_msc/schemas.py` — FACT_MSC_COLUMNS, FACT_RESULTADO_REGRAS_COLUMNS
- `src/ranking_msc/engine/executor.py` — EngineContext definition
- `ref/regras_piloto.md` — Rule catalogue documentation
