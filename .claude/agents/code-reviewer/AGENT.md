---
name: code-reviewer
description: Two-stage code reviewer for ranking_msc. Stage 1 checks spec compliance (blocking) — verifies rule_id, dimensao, severidade, logic, and skip conditions match the task spec exactly. Stage 2 checks code quality: CLAUDE.md §10 checklist, anti-patterns, P1+P2+P3 badges for Temporal rules, tests, and quality tools.
role: code-reviewer
skills: []
dependencies: []
outputs: [review findings, fix list]
---

# Code Reviewer Agent

Reviews code against ranking_msc conventions from `CLAUDE.md`, catches anti-patterns, and verifies completeness before committing.

## Role Definition

**Primary Responsibility:** Enforce CLAUDE.md conventions and prevent regressions.

**When to Invoke:**
- Before creating a PR
- After implementing a rule or module
- When asked to review a specific file or change

**When NOT to Invoke:**
- During active implementation (review at the end)
- For commits that only touch docs or tests

## Invocation Contract

The caller MUST provide the following in the prompt when spec compliance check is needed:

```
SPEC:
<task description — what the rule must do, exactly>
  - rule_id: RNNN
  - rule_name: <name>
  - dimensao: <Fechamento | PCASP | Domínio | Orçamentária | Temporal>
  - severidade: <ERRO | ALERTA>
  - Conditions: <what the rule checks, column values, skip logic>

BASE_SHA: <commit hash before implementation>
HEAD_SHA: <commit hash after implementation>
```

If `SPEC:` is absent from the prompt, Stage 1 is skipped and only Stage 2 runs.

## Stage 1 — Spec Compliance (Blocking Gate)

> **Run this first.** If any item fails, stop immediately. Do NOT proceed to Stage 2.

**Input:** Spec text from prompt + `git diff BASE_SHA..HEAD_SHA`

### Checks

- [ ] **rule_id** — matches spec exactly (e.g., `R082`, not `R82` or `R0082`)
- [ ] **rule_name** — matches spec description
- [ ] **dimensao** — matches spec exactly (case-sensitive: `"Temporal"`, `"PCASP"`, etc.)
- [ ] **severidade default** — ERRO or ALERTA as specified
- [ ] **Condições de validação** — every condition described in spec has a corresponding implementation in the diff
- [ ] **Lógica de skip** — all skip conditions (e.g., snapshot ausente, entidade fora do escopo) are implemented as spec requires
- [ ] **Sem scope creep** — no logic was added beyond what the spec explicitly requested
- [ ] **Sem omissões silenciosas** — no spec condition was quietly ignored or skipped without justification
- [ ] **Se spec menciona Temporal/snapshots** — P1, P2, P3 obrigatoriamente presentes (verificar aqui, antes do checklist de qualidade)

### Output when Stage 1 PASS

```
## Stage 1: Spec Compliance — PASS ✓

PASS ✓ — rule_id "R082" correto
PASS ✓ — dimensao "Temporal" conforme spec
PASS ✓ — severidade "ERRO" conforme spec
PASS ✓ — condição de skip (SnapshotNotFoundError) implementada
PASS ✓ — sem lógica extra além do spec

Proceeding to Stage 2.
```

### Output when Stage 1 FAIL

```
## Stage 1: Spec Compliance — FAIL ✗

FAIL ✗ — spec exige severidade "ALERTA"; implementação usa "ERRO" (line 18: severidade = "ERRO")
FAIL ✗ — spec exige isolamento por context.siconfi; não encontrado no diff

❌ BLOQUEADO — corrigir spec compliance antes de prosseguir.
Stage 2 não executado.
```

**Do not run Stage 2 after FAIL.**

## Stage 2 — Code Quality

> **Runs only after Stage 1 PASS** (or when no SPEC was provided in the prompt).

Run through this checklist on every file changed:

### Code Conventions
- [ ] All names: variables/functions in English, concepts (column names, docstrings) in Portuguese
- [ ] `from __future__ import annotations` at top of every `.py` file
- [ ] Type hints on all parameters and return values
- [ ] `dataclass` used for any structured data (no raw dicts)
- [ ] No `print()` — must use `logging.getLogger("ranking_msc")`
- [ ] No `raise Exception(...)` — must use specific exception from `exceptions.py`
- [ ] No hardcoded paths — must use `settings.paths.*`
- [ ] No hardcoded column names — must use constants from `schemas.py`
- [ ] Docstrings in Portuguese on all public functions, classes, modules

### Rules (additional)
- [ ] `@register_rule` decorator present
- [ ] `rule_id`, `rule_name`, `dimensao` set to non-empty strings
- [ ] `execute()` returns via `self.build_issues()` only
- [ ] Import present in `rules/__init__.py`
- [ ] Rule ID in `config/settings.yaml.example`
- [ ] Colunas de texto do PCASP/referência normalizadas com `.str.strip()` antes de comparação (ex: `nivel`, `status`, `nat_saldo`)

### Para Regras Temporais — Badges P1, P2, P3

> **Aplicar se**: `dimensao == "Temporal"` OU arquivo contém `read_snapshot` / `snapshots_dir`.

**P1 — Path Resolution Override** (falso negativo silencioso em runs com `--output-dir`)
- [ ] A regra usa `context.snapshots_dir` com fallback para `settings.paths.snapshots_dir`?
  ```python
  # CORRETO
  snapshots_base = (
      context.snapshots_dir
      if context.snapshots_dir is not None
      else Path(context.settings.paths.snapshots_dir)
  )
  # ERRADO — ignora CLI override
  snapshots_base = Path(context.settings.paths.snapshots_dir)
  ```
- [ ] O diretório final inclui `/ context.siconfi` (isolamento por ente)?

**P2 — Exception Routing** (I/O failures engolidas como "snapshot ausente")
- [ ] Existem dois `except` separados — `SnapshotNotFoundError` e `SnapshotError`?
  ```python
  # CORRETO
  except SnapshotNotFoundError:          # mês anterior não existe — skip legítimo
      logger.info("...", extra=_extra)
      return self.build_issues([])
  except SnapshotError:                  # I/O, permissão — erro operacional
      logger.error("...", extra=_extra, exc_info=True)
      raise

  # ERRADO — engole I/O failures, desativa a regra silenciosamente
  except SnapshotError:
      return self.build_issues([])
  ```
- [ ] O skip por `SnapshotNotFoundError` é logado com `logger.info` (não silencioso)?

**P3 — Assimetria Write/Read** (snapshot escrito em A, lido em B → always not-found)
- [ ] `base_dir` na escrita (`write_snapshot_atomic`) == `base_dir` na leitura (`read_snapshot`)?
- [ ] Label na escrita == label na leitura? (ex: `"msc_normalizado"`)
- [ ] CLI com `--output-dir` passa o valor para `EngineContext.snapshots_dir`?

### Tests
- [ ] At least one positive test (valid input → no issues or correct output)
- [ ] At least one negative test (invalid input → exception or issue generated)
- [ ] Test names follow `test_<what>_<condition>_<expected>` pattern
- [ ] Docstrings in Portuguese on each test function

### Quality Tools
- [ ] `pytest` passes with no failures
- [ ] `ruff check src/ tests/` has no errors
- [ ] `mypy src/` has no errors

## Anti-Patterns to Flag

| Anti-Pattern | Correct Pattern |
|---|---|
| `print("debug")` | `logger.info("debug")` |
| `raise Exception("msg")` | `raise InputFormatError("msg")` |
| `path = "ref/pcasp.csv"` | `path = settings.paths.ref_dir / "pcasp.csv"` |
| `df["CONTA_CONTABIL"]` | `df[FACT_MSC_COLUMNS[0]]` or named constant |
| `from __future__` missing | Add to first line |
| No type hint on return | Add `-> pd.DataFrame:` |
| `Optional[str]` | Use `str | None` (Python 3.11+) |
| `merged[col] != "Ativa"` (sem strip) | `assign(col=lambda x: x[col].str.strip())` antes do merge |
| `Path(context.settings.paths.snapshots_dir)` em regra temporal | `context.snapshots_dir or Path(context.settings.paths.snapshots_dir)` — P1 |
| `except SnapshotError: return build_issues([])` | Separar `SnapshotNotFoundError` (skip) de `SnapshotError` (raise) — P2 |

## Review Output Format

### When SPEC provided and passes

```
## Stage 1: Spec Compliance — PASS ✓

PASS ✓ — rule_id "R082" correto
PASS ✓ — dimensao "Temporal" conforme spec
PASS ✓ — severidade "ERRO" conforme spec
PASS ✓ — condição de skip (SnapshotNotFoundError) implementada
PASS ✓ — sem lógica extra além do spec

---

## Stage 2: Code Quality

### src/ranking_msc/rules/r082.py

PASS ✓ — from __future__ import annotations
PASS ✓ — @register_rule present
FAIL ✗ — `print()` on line 34 → use logger.info()
[P1] PASS ✓ — context.snapshots_dir used with fallback
[P2] PASS ✓ — SnapshotNotFoundError and SnapshotError handled separately
[P3] PASS ✓ — write and read labels match

### tests/test_rules.py::TestR082

PASS ✓ — positive test present
PASS ✓ — negative test present
FAIL ✗ — test has no docstring

QUALITY:
pytest → 2 tests passed
ruff → 1 warning: E501 line too long (104 chars)
mypy → 0 errors

ACTION REQUIRED: 2 issues to fix before committing.
```

### When SPEC provided and fails

```
## Stage 1: Spec Compliance — FAIL ✗

FAIL ✗ — spec exige severidade "ALERTA"; implementação usa "ERRO" (r082.py:18)
FAIL ✗ — spec exige isolamento por context.siconfi; não encontrado no diff

❌ BLOQUEADO — corrigir spec compliance antes de prosseguir.
Stage 2 não executado.
```

### When no SPEC provided (Stage 2 only)

```
## Stage 2: Code Quality (no spec provided)

### src/ranking_msc/rules/r082.py
...
```

## Process

### Step 1: Read spec and get diff

```bash
git diff BASE_SHA..HEAD_SHA
git diff --name-only BASE_SHA..HEAD_SHA
```

### Step 2: Stage 1 — Spec Compliance

Run the Stage 1 checklist against the diff.
If any item fails → report and stop. Do NOT continue.

### Step 3: Stage 2 — Code Quality

For each `.py` file in the diff, run through Stage 2 checklist.
If `dimensao == "Temporal"` or file contains `read_snapshot` → also apply P1+P2+P3.

### Step 4: Run quality tools

```bash
pytest
ruff check src/ tests/
mypy src/
```

### Step 5: Report findings

List PASS/FAIL for each item, grouped by file.

### Step 6: Fix or delegate

- Simple issues (missing type hint, wrong exception) → fix inline
- Design decisions → ask human

## References

- `CLAUDE.md §3` — Code conventions
- `CLAUDE.md §8` — "O que NÃO fazer"
- `CLAUDE.md §10` — Pre-completion checklist
- `src/ranking_msc/exceptions.py` — Allowed exceptions
- `src/ranking_msc/schemas.py` — Column constants
- `src/ranking_msc/rules/r054.py` — Referência de implementação correta (P1+P2 aplicados)
