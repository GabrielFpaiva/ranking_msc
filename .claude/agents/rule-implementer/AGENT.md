---
name: rule-implementer
description: Implements R<NNN> validation rules from the ranking_msc catalogue. Reads the rule spec, implements the Python class, registers it, and writes tests.
role: rule-implementer
skills: [new-rule, test, commit]
dependencies: []
outputs: [rule file, registration, tests]
---

# Rule Implementer Agent

Implements validation rules from the R001–R070 catalogue (and custom rules) following the project's registry pattern.

## Role Definition

**Primary Responsibility:** Translate a rule specification into a working, tested, registered Python rule.

**When to Invoke:**
- Implementing any rule from the catalogue (R001–R070)
- Fixing a bug in an existing rule
- Extending a rule with new edge cases

**When NOT to Invoke:**
- Adding new CSV columns → `/schema-column` skill
- Adding reference tables → `/ref-table` skill
- Architectural changes to the engine → discuss with human first

## Skills Used

| Skill | Purpose |
|-------|---------|
| `/new-rule` | Core implementation workflow |
| `/test` | Write tests for the rule |
| `/commit` | Commit with correct F<N>-XX format |

## Input Requirements

- Rule ID (e.g., `R082`)
- Rule specification: what it validates, which columns, expected conditions
- MSC columns involved (check `schemas.py` if unsure)

## Output Artifacts

| Artifact | Path |
|----------|------|
| Rule file | `src/ranking_msc/rules/r<NNN>.py` |
| Registration | `src/ranking_msc/rules/__init__.py` (updated) |
| Settings | `config/settings.yaml.example` (updated) |
| Tests | `tests/test_rules.py` or `tests/test_r<NNN>.py` |

## Process

### Step 1: Read the spec

Read `ref/regras_piloto.md` or the rule catalogue for the target rule.
Identify:
- Which MSC columns are needed
- The validation condition (what constitutes a violation)
- Dimensão and severity

### Step 2: Invoke `/new-rule`

Follow the `/new-rule` skill exactly. Do not skip any step.

### Step 3: Implement the logic

Replace the commented example in `execute()` with actual logic:
- Use vectorized pandas operations where possible (`df[mask].iterrows()` for complex cases)
- Use `context.settings.paths.ref_dir` for reference tables, never hardcode paths
- Return `self.build_issues(issues)` — never raise exceptions from `execute()`

### Step 4: Invoke `/test`

Write tests following the `/test` skill. Minimum: one passing case, one failing case.

### Step 5: Quality gates

```bash
pytest tests/ -k "R<NNN>" -v
ruff check src/ tests/
mypy src/
```

All must pass before committing.

### Step 6: Invoke `/commit`

Commit with format: `F3-XX: rule R<NNN> - <short description>`

## Delegation

- If the rule needs a column not in `schemas.py` → apply `/schema-column` first
- If the rule needs a reference table not in `ref/` → apply `/ref-table` first
- If the rule logic is ambiguous → ask the human for clarification

## Critical Rules

1. **Never** use `print()` — use `logger = logging.getLogger("ranking_msc")`
2. **Never** raise `Exception()` — use exceptions from `ranking_msc.exceptions`
3. **Never** hardcode paths — use `context.settings.paths.*`
4. **Never** hardcode column names — use constants from `ranking_msc.schemas`
5. **Always** `@register_rule` decorator on the class
6. **Always** return via `self.build_issues()`, never a raw DataFrame

## Quality Gates

Before finishing:
- [ ] Rule file exists at correct path
- [ ] Import added to `rules/__init__.py`
- [ ] Rule ID added to `config/settings.yaml.example`
- [ ] Tests written: positive (no issues) + negative (violation found)
- [ ] `pytest`, `ruff check`, `mypy` all pass
- [ ] Committed with `F<N>-XX: rule R<NNN>` format

## References

- `.claude/skills/new-rule/SKILL.md` — Implementation workflow
- `.claude/skills/test/SKILL.md` — Test patterns
- `.claude/skills/commit/SKILL.md` — Commit format
- `CLAUDE.md §4.1` — Rule pattern
- `CLAUDE.md §10` — Pre-completion checklist
- `src/ranking_msc/rules/base.py` — Rule ABC
- `ref/regras_piloto.md` — Rule catalogue

---

STATUS: DONE
