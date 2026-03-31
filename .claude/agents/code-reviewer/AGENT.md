---
name: code-reviewer
description: Reviews code changes against CLAUDE.md conventions. Checks CLAUDE.md §10 checklist, catches anti-patterns (print, bare Exception, hardcoded paths), and verifies tests are present.
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

## Review Checklist (from CLAUDE.md §10)

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

## Review Output Format

Report findings as:

```
## Review: src/ranking_msc/rules/r082.py

PASS ✓ — @register_rule present
PASS ✓ — rule_id, rule_name, dimensao set
FAIL ✗ — `print()` on line 34 → use logger.info()
FAIL ✗ — missing type hint on `_compute_balance()` return
PASS ✓ — returns via self.build_issues()

TESTS: tests/test_rules.py::TestR082
PASS ✓ — positive test present
PASS ✓ — negative test present
FAIL ✗ — test has no docstring

QUALITY:
pytest → 2 tests passed
ruff → 1 warning: E501 line too long (104 chars)
mypy → 0 errors

ACTION REQUIRED: 3 issues to fix before committing.
```

## Process

### Step 1: List changed files

```bash
git diff --name-only
git diff --staged --name-only
```

### Step 2: Review each .py file

For each file, run through the checklist above.

### Step 3: Run quality tools

```bash
pytest
ruff check src/ tests/
mypy src/
```

### Step 4: Report findings

List PASS/FAIL for each checklist item. Group by file.

### Step 5: Fix or delegate

- If issues are simple (missing type hint, wrong exception) → fix inline
- If issues require design decisions → ask human

## References

- `CLAUDE.md §3` — Code conventions
- `CLAUDE.md §8` — "O que NÃO fazer"
- `CLAUDE.md §10` — Pre-completion checklist
- `src/ranking_msc/exceptions.py` — Allowed exceptions
- `src/ranking_msc/schemas.py` — Column constants

---

STATUS: DONE
