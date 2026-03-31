---
name: test
description: Write pytest tests for any ranking_msc module. Use when adding tests for rules, io, transform, engine, or outputs modules. Covers naming conventions, fixture usage, conftest patterns, and quality commands.
---

# Write Tests

Writes pytest tests following project conventions for any module in ranking_msc.

## When to Use

- Adding tests for a new rule (`/new-rule` always pairs with this)
- Adding tests for a new module or function
- Increasing coverage for an existing module

## File Structure

One test file per module:

| Module | Test File |
|--------|-----------|
| `io/reader_msc.py` | `tests/test_reader.py` |
| `transform/ic_normalize.py` | `tests/test_normalize.py` |
| `engine/executor.py` | `tests/test_engine.py` |
| `outputs/snapshot.py` | `tests/test_snapshot.py` |
| `outputs/reports.py` | `tests/test_reports.py` |
| `rules/r<NNN>.py` | `tests/test_rules.py` or `tests/test_r<NNN>.py` |
| Full pipeline | `tests/test_integration.py` |

## Naming Convention

```
def test_<what>_<condition>_<expected>():
    """Docstring curta em português."""
```

Examples:
- `test_read_csv_valido_retorna_rawmsc()`
- `test_read_csv_sem_coluna_obrigatoria_levanta_inputformaterror()`
- `test_normalize_ic_desconhecido_loga_warning()`
- `test_r082_debito_igual_credito_sem_pendencia()`
- `test_r082_debito_diferente_credito_gera_erro()`

## Standard Fixtures (from conftest.py)

Always use these fixtures — never re-create them inline:

```python
def test_algo(engine_context, sample_msc_df):
    # engine_context: EngineContext with competencia="2024-01", siconfi="250400"
    # sample_msc_df: minimal valid MSC DataFrame
```

Available fixtures:
- `settings` — default Settings object
- `engine_context` — EngineContext for rule tests
- `sample_msc_df` — minimal valid MSC DataFrame

## Adding New Fixtures to conftest.py

When you need a fixture used by multiple test files:

```python
# tests/conftest.py
@pytest.fixture
def sample_msc_df_with_error() -> pd.DataFrame:
    """DataFrame MSC com violação de débito ≠ crédito."""
    return pd.DataFrame({
        "competencia": ["2024-01"],
        "siconfi": ["250400"],
        "conta_contabil": ["1.1.1.1.1.01.00"],
        "debito": [100.0],
        "credito": [200.0],  # mismatched
    })
```

If the fixture is only used in one file, define it locally in that file.

## Test Structure — Three Parts

Every test should follow: **Arrange → Act → Assert**

```python
def test_read_csv_valido_retorna_rawmsc(tmp_path):
    """CSV válido → RawMSC com colunas corretas."""
    # Arrange: create a minimal valid CSV
    csv_path = tmp_path / "msc.csv"
    pd.DataFrame({
        "competencia": ["2024-01"],
        "siconfi": ["250400"],
        "conta_contabil": ["1.1.1.1.1.01.00"],
    }).to_csv(csv_path, index=False)

    # Act
    result = read_msc_csv(str(csv_path))

    # Assert
    assert result is not None
    assert "conta_contabil" in result.df.columns
```

## Testing Exceptions

```python
import pytest
from ranking_msc.exceptions import InputFormatError

def test_read_csv_sem_coluna_obrigatoria_levanta_inputformaterror(tmp_path):
    """CSV sem coluna 'conta_contabil' → InputFormatError."""
    csv_path = tmp_path / "bad.csv"
    pd.DataFrame({"coluna_errada": [1]}).to_csv(csv_path, index=False)

    with pytest.raises(InputFormatError, match="conta_contabil"):
        read_msc_csv(str(csv_path))
```

## Running Tests

```bash
pytest                            # all tests
pytest tests/test_rules.py -v    # single file
pytest -k "test_r082"            # by name pattern
pytest --cov=ranking_msc         # with coverage
pytest tests/test_reader.py -v --tb=short  # with short traceback
```

## Checklist

- [ ] Test file follows naming convention (`test_<module>.py`)
- [ ] Each test name follows `test_<what>_<condition>_<expected>` pattern
- [ ] Docstring in Portuguese on every test
- [ ] Using fixtures from conftest.py where available
- [ ] At least one positive test (valid input → expected output)
- [ ] At least one negative test (invalid/edge case → exception or empty result)
- [ ] No `print()` in tests
- [ ] No `import *`
- [ ] `pytest` passes

## References

- `CLAUDE.md §5` — Test patterns
- `tests/conftest.py` — Available fixtures
- `src/ranking_msc/exceptions.py` — Exception types for `pytest.raises`
- `src/ranking_msc/schemas.py` — Column constants for test data setup
