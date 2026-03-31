---
name: ref-table
description: Add a new reference table (PCASP, domínios, fontes) to io/ref_loader.py. Use when a rule needs to look up values from an external CSV in the ref/ directory. Covers loader function, caching pattern, and tests.
---

# Add Reference Table

Adds a new loader function to `io/ref_loader.py` for a CSV reference table in `ref/`.

## When to Use

- A new rule needs to validate accounts against PCASP or another catalogue
- A new domain mapping CSV is added to `ref/`
- An existing loader needs a filter parameter or an extra column

## File Structure

```
ref/
├── pcasp.csv              # PCASP account plan
├── dominios_fr.csv        # Domain reference (exists)
├── mapeamento_ic_tipo.csv # IC×TIPO mapping (exists)
└── nova_tabela.csv        # Your new table
```

## Loader Pattern (mandatory)

Always follow this exact pattern in `io/ref_loader.py`:

```python
# src/ranking_msc/io/ref_loader.py
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from ranking_msc.exceptions import ConfigError

logger = logging.getLogger("ranking_msc")

# ---------------------------------------------------------------------------
# Nova tabela de referência
# ---------------------------------------------------------------------------

_CACHE_NOVA_TABELA: pd.DataFrame | None = None


def load_nova_tabela(ref_dir: str = "ref") -> pd.DataFrame:
    """Carrega nova_tabela.csv com cache em memória.

    Args:
        ref_dir: diretório das tabelas de referência.

    Returns:
        DataFrame com colunas X, Y, Z.

    Raises:
        ConfigError: se o arquivo não for encontrado.
    """
    global _CACHE_NOVA_TABELA
    if _CACHE_NOVA_TABELA is not None:
        return _CACHE_NOVA_TABELA

    path = Path(ref_dir) / "nova_tabela.csv"
    if not path.exists():
        raise ConfigError(f"Tabela nova_tabela não encontrada: {path}")

    _CACHE_NOVA_TABELA = pd.read_csv(path, dtype=str)
    logger.debug("nova_tabela carregada: %d registros", len(_CACHE_NOVA_TABELA))
    return _CACHE_NOVA_TABELA
```

**Rules:**
- Always `dtype=str` — codes like `001` must not become `1`
- Cache in module-level variable `_CACHE_<NAME>`
- Raise `ConfigError` (not `FileNotFoundError`) if file missing
- Log at DEBUG level after loading

## Using in a Rule

```python
# src/ranking_msc/rules/r<NNN>.py
from ranking_msc.io.ref_loader import load_nova_tabela

class R<NNN>(Rule):
    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        ref = load_nova_tabela(context.settings.paths.ref_dir)
        valid_codes = set(ref["codigo"])
        mask = ~df["conta_contabil"].isin(valid_codes)
        # ...
```

## Tests

```python
# tests/test_ref_loader.py (or add to existing)
import pytest
from pathlib import Path
import pandas as pd
from ranking_msc.io.ref_loader import load_nova_tabela
from ranking_msc.exceptions import ConfigError


def test_load_nova_tabela_retorna_dataframe(tmp_path):
    """CSV presente → DataFrame com colunas corretas."""
    csv = tmp_path / "nova_tabela.csv"
    pd.DataFrame({"codigo": ["001", "002"], "descricao": ["A", "B"]}).to_csv(
        csv, index=False
    )
    result = load_nova_tabela(str(tmp_path))
    assert "codigo" in result.columns
    assert result["codigo"].tolist() == ["001", "002"]


def test_load_nova_tabela_arquivo_ausente_levanta_config_error(tmp_path):
    """Arquivo ausente → ConfigError."""
    with pytest.raises(ConfigError, match="nova_tabela"):
        load_nova_tabela(str(tmp_path))


def test_load_nova_tabela_codigo_com_zeros_preservado(tmp_path):
    """dtype=str → código '001' não vira 1."""
    csv = tmp_path / "nova_tabela.csv"
    pd.DataFrame({"codigo": ["001"]}).to_csv(csv, index=False)
    result = load_nova_tabela(str(tmp_path))
    assert result["codigo"].iloc[0] == "001"  # not "1"
```

**Important:** reset the cache between tests if needed:

```python
import ranking_msc.io.ref_loader as ref_loader

@pytest.fixture(autouse=True)
def reset_cache():
    ref_loader._CACHE_NOVA_TABELA = None
    yield
    ref_loader._CACHE_NOVA_TABELA = None
```

## Checklist

- [ ] CSV placed in `ref/` directory
- [ ] Loader function added to `io/ref_loader.py`
- [ ] `dtype=str` in `pd.read_csv`
- [ ] `_CACHE_<NAME>` module-level variable
- [ ] Raises `ConfigError` if file missing
- [ ] DEBUG log after loading
- [ ] Tests: valid CSV, missing file, zero-preserving dtype
- [ ] Cache reset fixture in tests
- [ ] `pytest`, `ruff`, `mypy` pass

## References

- `CLAUDE.md §4.4` — Reference table pattern
- `src/ranking_msc/io/ref_loader.py` — Existing loaders (use as examples)
- `src/ranking_msc/exceptions.py` — ConfigError
- `ref/dominios_fr.csv` — Example existing reference table
