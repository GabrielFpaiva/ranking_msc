---
name: commit
description: Create a git commit following ranking_msc format. Use when ready to commit. Format is "F<N>-XX: short description in English" — single line, no body, no Co-Authored-By.
---

# Create Git Commit

Creates a well-formatted git commit following ranking_msc conventions.

## Commit Format

```
F<N>-XX: short description in English
```

- `F<N>` = current phase number (e.g., `F3` for Fase 3)
- `XX` = task number from the backlog (e.g., `03`, `12`)
- Description: English, imperative, lowercase, max ~72 chars, no period
- **Single line only** — no body, no Co-Authored-By, no footer

## Examples

```bash
# Feature
git commit -m "F3-03: implement read_msc_csv() with real CSV"

# Rule implementation
git commit -m "F3-12: rule R082 - debit = credit closing check"

# Tests
git commit -m "F3-18: end-to-end pipeline integration test"

# Fix
git commit -m "F3-07: fix ref_loader cache reset between tests"

# Refactor
git commit -m "F3-15: extract build_issues helper to Rule base class"

# Documentation
git commit -m "F3-01: fill CODEX.md agent guide with F3 patterns"
```

## Process

### Step 1: Pre-commit checks

```bash
pytest                    # all tests must pass
ruff check src/ tests/    # no lint errors
mypy src/                 # no type errors
```

Only commit when all three pass.

### Step 2: Review staged changes

```bash
git status
git diff --staged
```

Stage only relevant files. Never stage:
- `config/settings.yaml` (gitignored, contains local paths)
- `data/` directory (gitignored)
- `.venv/` (gitignored)

### Step 3: Stage files

```bash
# Prefer explicit staging
git add src/ranking_msc/rules/r082.py
git add src/ranking_msc/rules/__init__.py
git add tests/test_rules.py

# For entire directories when the change is focused
git add src/ranking_msc/rules/
```

### Step 4: Commit

```bash
git commit -m "F3-12: rule R082 - debit = credit closing check"
```

### Step 5: Verify

```bash
git log -1 --oneline
```

Expected: shows the commit with the correct format.

## Task Number Reference

If you don't know the exact task number, use the closest one and note it's approximate. The format must always start with `F<N>-`.

Current phase (as of 2026-03-31): **F3** — full rule catalogue R001–R070.

## Branches

- `main` — always stable, tests passing
- `feat/F3-XX-descricao` — one branch per backlog task
- Merge via PR (no direct push to main)

## Checklist

- [ ] `pytest` passes
- [ ] `ruff check src/ tests/` clean
- [ ] `mypy src/` clean
- [ ] Only relevant files staged
- [ ] No secrets, no `data/`, no `.venv/`
- [ ] Message format: `F<N>-XX: description`
- [ ] Single line, English, imperative, no period
- [ ] Verified with `git log -1`

## References

- `CLAUDE.md §6` — Git workflow
