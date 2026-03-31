---
name: schema-column
description: Add or modify columns in schemas.py (FACT_MSC_COLUMNS or FACT_RESULTADO_REGRAS_COLUMNS). Use when the CSV has a new column, a rule needs a new output column, or a column name changes. Always update reader and tests too.
---

# Add or Modify Schema Column

Safely adds or modifies a column in `schemas.py` and propagates the change to reader and tests.

## When to Use

- A new CSV column must be processed
- A new output column is needed in rule results
- A column name is being renamed

## When NOT to Use

- Adding a reference table (not a MSC CSV column) → use `/ref-table`
- Changing engine logic without column changes → edit executor directly

## Key Constraint

`schemas.py` is the **contract**. Never add a column to the reader or tests without first adding it to the schema. The schema defines the source of truth for all column names.

## Files Affected

1. `src/ranking_msc/schemas.py` — primary change
2. `src/ranking_msc/io/reader_msc.py` — map CSV column → schema column
3. `tests/test_reader.py` — update column assertions
4. `ref/layout_msc.md` — document the column (if MSC input column)

## Process

### Step 1: Add to schemas.py

```python
# src/ranking_msc/schemas.py
# Columns of the normalized MSC fact table
FACT_MSC_COLUMNS: list[str] = [
    "competencia",
    "siconfi",
    "conta_contabil",
    # ... existing columns ...
    "nova_coluna",   # <-- add here with a comment explaining its purpose
]
```

For output columns (rule results), add to `FACT_RESULTADO_REGRAS_COLUMNS`.

### Step 2: Update reader_msc.py

If the column comes from the CSV (rename or new):

```python
# src/ranking_msc/io/reader_msc.py
COLUMN_MAP = {
    # csv_name: schema_name
    "CONTA_CONTABIL": "conta_contabil",
    "NOVA_COLUNA_CSV": "nova_coluna",   # <-- add mapping
}
```

If the column is derived/computed, add the derivation logic after reading.

### Step 3: Update tests

```python
# tests/test_reader.py
def test_read_csv_contem_nova_coluna(tmp_path):
    """CSV com nova_coluna → presente no resultado."""
    csv_path = tmp_path / "msc.csv"
    pd.DataFrame({
        "CONTA_CONTABIL": ["1.1.1.1.1.01.00"],
        "NOVA_COLUNA_CSV": ["valor"],
    }).to_csv(csv_path, index=False)

    result = read_msc_csv(str(csv_path))
    assert "nova_coluna" in result.df.columns
```

Also update any test that checks `FACT_MSC_COLUMNS` directly.

### Step 4: Document in layout_msc.md (if input column)

Add a row to the column table in `ref/layout_msc.md`:

```markdown
| nova_coluna | NOVA_COLUNA_CSV | string | Descrição do campo |
```

### Step 5: Run checks

```bash
pytest tests/test_reader.py -v
ruff check src/ tests/
mypy src/
```

## Checklist

- [ ] Column added to correct constant in `schemas.py` with comment
- [ ] `reader_msc.py` updated if column comes from CSV
- [ ] Tests in `test_reader.py` updated or added
- [ ] `ref/layout_msc.md` updated (if input column)
- [ ] `pytest`, `ruff`, `mypy` all pass

## References

- `CLAUDE.md §4.2` — Schema column pattern
- `src/ranking_msc/schemas.py` — FACT_MSC_COLUMNS, FACT_RESULTADO_REGRAS_COLUMNS
- `src/ranking_msc/io/reader_msc.py` — Column mapping
- `ref/layout_msc.md` — Column documentation
