# Sistema SAMID — Dashboard Redesign + Backend Persistence

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite `app/web_app.py` to match the Figma design (dark sidebar, metric cards, charts, filters) AND wire up the missing backend persistence (snapshot, Excel report, execution log) so data survives page refreshes.

**Architecture:** Panel `FastListTemplate` with dark theme/sidebar. Each screen is a `pn.Column` swapped into a single `_main_pane` via sidebar icon-button navigation. Backend persistence mirrors `scripts/run_pipeline.py` (which already works correctly): `write_snapshot_atomic()` + `export_issues_excel()` + `log_execucao()` are called after `run_engine()`. On app load, existing snapshots are detected and offered for reload.

**Tech Stack:** Python 3.12, Panel 1.x (Bokeh 3.9), Plotly (charts), Tabulator (tables), openpyxl (Excel), pyarrow (Parquet snapshots)

**Figma reference:** `/home/nelson/Downloads/Untitled/` (7 PNGs)

**Branch:** Create `feat/F5-01-samid-dashboard` from `main`

---

## Scope

**Phase 1 (Tasks 1-4): Foundation** — Backend persistence, dark layout shell, sidebar navigation
**Phase 2 (Tasks 5-8): Core Screens** — Upload/Home, Execution Dashboard, Regras, Pendencias
**Phase 3 (Tasks 9-11): Analytical Screens** — Caixa, Passivos, Superavit (layout + stub data)
**Phase 4 (Task 12): Polish** — Lint, tests, final integration

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `app/web_app.py` | **Rewrite** | Main Panel app — layout shell, sidebar nav, screen switching |
| `app/screens/__init__.py` | **Create** | Screen package |
| `app/screens/home.py` | **Create** | Upload + overview metrics + top 10 regras + evolucao chart |
| `app/screens/execucao.py` | **Create** | Pipeline progress, processing details, execution log |
| `app/screens/regras.py` | **Create** | Rules heatmap matrix + detail table |
| `app/screens/pendencias.py` | **Create** | Sidebar filters + pendencias table |
| `app/screens/caixa.py` | **Create** | Cash control cards + charts + table |
| `app/screens/passivos.py` | **Create** | Liabilities cards + charts + table |
| `app/screens/superavit.py` | **Create** | Surplus cards + charts + table |
| `app/styles.py` | **Create** | Shared HTML/CSS constants (colors, card builder, dark theme) |
| `app/persistence.py` | **Create** | Thin wrapper: persist results, load last snapshot, list available months |
| `tests/test_web_persistence.py` | **Create** | Tests for persistence layer |

---

## Task 1: Backend Persistence Layer

**Files:**
- Create: `app/persistence.py`
- Create: `tests/test_web_persistence.py`

This wires up `write_snapshot_atomic`, `export_issues_excel`, and `log_execucao` for the web entrypoint — exactly like `scripts/run_pipeline.py` does, but callable from the Panel callback.

- [ ] **Step 1: Write failing tests for persist_result()**

```python
# tests/test_web_persistence.py
"""Testes da camada de persistência do web_app."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from ranking_msc.config.settings import Settings
from ranking_msc.engine.executor import EngineContext, EngineResult
from ranking_msc.schemas import FACT_RESULTADO_REGRAS_COLUMNS


@pytest.fixture
def tmp_output(tmp_path: Path) -> Path:
    """Diretório temporário para outputs."""
    return tmp_path


@pytest.fixture
def dummy_result() -> EngineResult:
    """EngineResult com uma pendência para teste."""
    settings = Settings()
    ctx = EngineContext(
        competencia="2024-01", siconfi="250400",
        settings=settings, usuario="teste",
    )
    result = EngineResult(context=ctx)
    result.pendencias = pd.DataFrame([{
        "regra_id": "R030",
        "regra_nome": "Fechamento D=C",
        "dimensao": "Fechamento",
        "severidade": "ERRO",
        "conta_contabil": "1.1.1.1.1.01.00",
        "descricao": "Débito ≠ Crédito",
        "valor_esperado": "0.00",
        "valor_encontrado": "100.00",
        "competencia": "2024-01",
    }])
    result.regras_executadas = 1
    return result


class TestPersistResult:
    def test_persist_creates_snapshot_parquet(
        self, tmp_output: Path, dummy_result: EngineResult,
    ) -> None:
        """Persistir resultado cria snapshot Parquet no caminho correto."""
        from app.persistence import persist_result

        paths = persist_result(
            result=dummy_result,
            normalized_df=pd.DataFrame(),
            competencia="2024-01",
            siconfi="250400",
            base_dir=tmp_output,
        )
        assert paths.snapshot.exists()
        assert paths.snapshot.suffix == ".parquet"

    def test_persist_creates_excel_report(
        self, tmp_output: Path, dummy_result: EngineResult,
    ) -> None:
        """Persistir resultado cria relatório Excel."""
        from app.persistence import persist_result

        paths = persist_result(
            result=dummy_result,
            normalized_df=pd.DataFrame(),
            competencia="2024-01",
            siconfi="250400",
            base_dir=tmp_output,
        )
        assert paths.report.exists()
        assert paths.report.suffix == ".xlsx"

    def test_persist_creates_normalized_snapshot(
        self, tmp_output: Path, dummy_result: EngineResult,
    ) -> None:
        """Persistir resultado cria snapshot do DF normalizado."""
        from app.persistence import persist_result

        norm_df = pd.DataFrame({"conta_contabil": ["1.1.1"]})
        paths = persist_result(
            result=dummy_result,
            normalized_df=norm_df,
            competencia="2024-01",
            siconfi="250400",
            base_dir=tmp_output,
        )
        assert paths.normalized_snapshot.exists()


class TestLoadLastResult:
    def test_load_returns_none_when_no_snapshot(self, tmp_output: Path) -> None:
        """Sem snapshot salvo, retorna None."""
        from app.persistence import load_last_result

        result = load_last_result(
            competencia="2024-01", siconfi="250400", base_dir=tmp_output,
        )
        assert result is None

    def test_load_returns_dataframe_after_persist(
        self, tmp_output: Path, dummy_result: EngineResult,
    ) -> None:
        """Após persistir, load retorna o DataFrame de pendências."""
        from app.persistence import persist_result, load_last_result

        persist_result(
            result=dummy_result,
            normalized_df=pd.DataFrame(),
            competencia="2024-01",
            siconfi="250400",
            base_dir=tmp_output,
        )
        loaded = load_last_result(
            competencia="2024-01", siconfi="250400", base_dir=tmp_output,
        )
        assert loaded is not None
        assert len(loaded) == 1
        assert loaded.iloc[0]["regra_id"] == "R030"
```

- [ ] **Step 2: Run tests — expect FAIL (module not found)**

```bash
cd "/home/nelson/projetos/Cerebro/Claude  Cerebro/psb/01 - Projects/ranking_msc"
pytest tests/test_web_persistence.py -v
```

- [ ] **Step 3: Implement persistence.py**

```python
# app/persistence.py
"""Camada de persistência para o web_app.

Encapsula snapshot Parquet + relatório Excel + log de execução.
Espelha o que scripts/run_pipeline.py faz, porém sem dependência do CLI.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from ranking_msc.engine.executor import EngineResult
from ranking_msc.exceptions import SnapshotNotFoundError
from ranking_msc.outputs.logs import log_execucao
from ranking_msc.outputs.reports import export_issues_excel
from ranking_msc.outputs.snapshot import read_snapshot, write_snapshot_atomic

logger = logging.getLogger("ranking_msc")


@dataclass(frozen=True)
class PersistedPaths:
    """Caminhos dos artefatos gravados após uma execução."""
    snapshot: Path
    normalized_snapshot: Path
    report: Path


def persist_result(
    *,
    result: EngineResult,
    normalized_df: pd.DataFrame,
    competencia: str,
    siconfi: str,
    base_dir: str | Path,
) -> PersistedPaths:
    """Persiste todos os artefatos de uma execução.

    Grava: snapshot normalizado, snapshot de resultado, Excel e log.

    Args:
        result: EngineResult com pendências.
        normalized_df: DataFrame normalizado (antes das regras).
        competencia: "YYYY-MM".
        siconfi: código do ente.
        base_dir: diretório raiz de dados (ex: ./data).

    Returns:
        PersistedPaths com os caminhos dos arquivos criados.
    """
    base = Path(base_dir)
    snap_dir = base / "snapshots" / siconfi

    normalized_path = write_snapshot_atomic(
        normalized_df, competencia,
        base_dir=snap_dir, label="msc_normalizado",
    )

    snapshot_path = write_snapshot_atomic(
        result.pendencias, competencia,
        base_dir=snap_dir, label="resultado_regras",
    )

    report_path = export_issues_excel(
        result.pendencias, competencia,
        output_dir=base / "reports",
    )

    log_execucao(
        logger,
        execucao_id=result.context.execucao_id,
        competencia=competencia,
        status=result.status,
        message="Execução web concluída",
        siconfi=siconfi,
        usuario=result.context.usuario,
    )

    return PersistedPaths(
        snapshot=snapshot_path,
        normalized_snapshot=normalized_path,
        report=report_path,
    )


def load_last_result(
    *,
    competencia: str,
    siconfi: str,
    base_dir: str | Path,
) -> pd.DataFrame | None:
    """Carrega o último resultado salvo para um ente/competência.

    Returns:
        DataFrame de pendências ou None se não houver snapshot.
    """
    snap_dir = Path(base_dir) / "snapshots" / siconfi
    try:
        return read_snapshot(
            competencia, base_dir=snap_dir, label="resultado_regras",
        )
    except SnapshotNotFoundError:
        return None


def list_available_months(
    *,
    siconfi: str,
    base_dir: str | Path,
) -> list[str]:
    """Lista competências com snapshot salvo para um ente.

    Returns:
        Lista de strings "YYYY-MM" ordenada decrescente.
    """
    snap_dir = Path(base_dir) / "snapshots" / siconfi
    if not snap_dir.exists():
        return []
    months = [
        d.name for d in snap_dir.iterdir()
        if d.is_dir() and (d / "resultado_regras.parquet").exists()
    ]
    return sorted(months, reverse=True)
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
pytest tests/test_web_persistence.py -v
```

- [ ] **Step 5: Commit**

```bash
git add app/persistence.py tests/test_web_persistence.py
git commit -m "F5-01: add web persistence layer (snapshot + excel + log)"
```

---

## Task 2: Shared Styles Module

**Files:**
- Create: `app/styles.py`

Dark theme constants, card builder, and shared CSS matching the Figma design. All screens import from here.

- [ ] **Step 1: Create styles.py**

```python
# app/styles.py
"""Constantes de estilo compartilhadas — tema escuro SAMID.

Todas as telas importam cores, builders de card e CSS daqui.
"""

from __future__ import annotations

# --- Paleta ---
BG_SIDEBAR = "#1a1a2e"
BG_HEADER = "#16213e"
BG_MAIN = "#f8f9fa"
TEXT_LIGHT = "#e0e0e0"
TEXT_DARK = "#212529"
ACCENT = "#0f3460"

COLOR_OK = "#28a745"
COLOR_ERRO = "#dc3545"
COLOR_ALERTA = "#e67e00"
COLOR_INFO = "#0d6efd"
COLOR_NEUTRAL = "#495057"
COLOR_PASSIVO = "#e6b422"

STATUS_COLORS: dict[str, str] = {
    "OK": COLOR_OK,
    "PARCIAL": COLOR_ALERTA,
    "ERRO": COLOR_ERRO,
}

# --- CSS global injetado via pn.config.raw_css ---
GLOBAL_CSS = """
.bk-root .bk-tab {
    font-size: 13px !important;
}
.sidenav-btn .bk-btn {
    text-align: left !important;
    padding: 10px 16px !important;
    border: none !important;
    border-radius: 8px !important;
    color: #ccc !important;
    background: transparent !important;
    font-size: 14px !important;
    transition: background 0.15s !important;
}
.sidenav-btn .bk-btn:hover {
    background: rgba(255,255,255,0.08) !important;
    color: #fff !important;
}
.sidenav-btn-active .bk-btn {
    background: rgba(255,255,255,0.12) !important;
    color: #fff !important;
    font-weight: 600 !important;
}
"""


def metric_card(label: str, value: str, sub: str = "", bg: str = COLOR_NEUTRAL) -> str:
    """Retorna HTML de um card de métrica no estilo Figma."""
    sub_html = f"<div style='font-size:11px;margin-top:4px;opacity:.7;'>{sub}</div>" if sub else ""
    return (
        f"<div style='background:#fff;border-radius:12px;padding:20px 24px;"
        f"min-width:140px;flex:1;box-shadow:0 1px 3px rgba(0,0,0,.08);'>"
        f"<div style='font-size:12px;color:#888;margin-bottom:8px;'>{label}</div>"
        f"<div style='font-size:28px;font-weight:700;color:{bg};line-height:1;'>{value}</div>"
        f"{sub_html}"
        f"</div>"
    )


def status_badge(status: str) -> str:
    """Retorna HTML de badge colorido para status OK/PARCIAL/ERRO."""
    bg = STATUS_COLORS.get(status, COLOR_NEUTRAL)
    return (
        f"<span style='background:{bg};color:#fff;padding:4px 14px;"
        f"border-radius:16px;font-weight:600;font-size:13px;'>{status}</span>"
    )


def section_title(text: str) -> str:
    """Retorna HTML de título de seção padronizado."""
    return f"<h3 style='margin:0 0 12px;font-weight:600;color:{TEXT_DARK};'>{text}</h3>"


def pipeline_step(label: str, done: bool = False) -> str:
    """Retorna HTML de um passo do pipeline (Figma: barra de progresso)."""
    icon = "✅" if done else "⬜"
    color = COLOR_OK if done else "#ccc"
    return (
        f"<div style='text-align:center;flex:1;'>"
        f"<div style='font-size:22px;'>{icon}</div>"
        f"<div style='font-size:11px;color:{color};margin-top:4px;'>{label}</div>"
        f"</div>"
    )
```

- [ ] **Step 2: Commit**

```bash
git add app/styles.py
git commit -m "F5-01: add shared styles module (dark theme, card builders)"
```

---

## Task 3: Layout Shell + Sidebar Navigation

**Files:**
- Rewrite: `app/web_app.py`
- Create: `app/screens/__init__.py`

The main layout: dark sidebar with icon navigation, header with title, main content pane that swaps per screen. No business logic here — just the shell.

- [ ] **Step 1: Create screens package**

```python
# app/screens/__init__.py
"""Submódulo de telas do dashboard SAMID."""
```

- [ ] **Step 2: Rewrite web_app.py as layout shell**

```python
# app/web_app.py
"""Sistema SAMID — Dashboard de Validação Contábil MSC.

    panel serve app/web_app.py --show
"""

from __future__ import annotations

import sys
from pathlib import Path

import panel as pn

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "src"))
sys.path.insert(0, str(_PROJECT_ROOT))

import ranking_msc.rules  # noqa: E402, F401
from app.screens.home import build_home_screen  # noqa: E402
from app.screens.execucao import build_execucao_screen  # noqa: E402
from app.screens.regras import build_regras_screen  # noqa: E402
from app.screens.pendencias import build_pendencias_screen  # noqa: E402
from app.screens.caixa import build_caixa_screen  # noqa: E402
from app.screens.passivos import build_passivos_screen  # noqa: E402
from app.screens.superavit import build_superavit_screen  # noqa: E402
from app.styles import BG_SIDEBAR, GLOBAL_CSS  # noqa: E402
from ranking_msc.config.settings import load_settings  # noqa: E402
from ranking_msc.outputs.logs import setup_logging  # noqa: E402

# --- Init ---
pn.extension("plotly", "tabulator", sizing_mode="stretch_width")
pn.config.raw_css.append(GLOBAL_CSS)

try:
    settings = load_settings(_PROJECT_ROOT / "config" / "settings.yaml")
except Exception:
    from ranking_msc.config.settings import Settings
    settings = Settings()

logger = setup_logging(log_dir=settings.paths.logs_dir)
logger.info("Sistema SAMID iniciado.")

# --- State shared across screens ---
# Dicionário mutável que os screens leem/escrevem.
# Evita variáveis globais espalhadas — um único ponto de estado.
app_state: dict = {
    "settings": settings,
    "project_root": _PROJECT_ROOT,
    "last_result": None,       # EngineResult mais recente
    "last_raw": None,          # RawMSC mais recente
    "last_normalized": None,   # DataFrame normalizado
}

# --- Build screens ---
screens = {
    "home": build_home_screen(app_state),
    "execucao": build_execucao_screen(app_state),
    "regras": build_regras_screen(app_state),
    "pendencias": build_pendencias_screen(app_state),
    "caixa": build_caixa_screen(app_state),
    "passivos": build_passivos_screen(app_state),
    "superavit": build_superavit_screen(app_state),
}

# --- Main pane ---
_main_pane = pn.Column(
    screens["home"]["panel"],
    sizing_mode="stretch_both",
    min_height=700,
)


def _switch(name: str) -> None:
    _main_pane.clear()
    _main_pane.append(screens[name]["panel"])


# --- Sidebar ---
_NAV = [
    ("🏠", "Início",        "home"),
    ("⚙", "Execução",      "execucao"),
    ("📋", "Regras",        "regras"),
    ("🔍", "Pendências",    "pendencias"),
    ("💰", "Caixa",         "caixa"),
    ("📑", "Passivos",      "passivos"),
    ("📈", "Superávit",     "superavit"),
]

nav_buttons = []
for icon, label, key in _NAV:
    btn = pn.widgets.Button(
        name=f"{icon}  {label}",
        button_type="light",
        sizing_mode="stretch_width",
        margin=(2, 8),
        css_classes=["sidenav-btn"],
    )
    btn.on_click(lambda e, k=key: _switch(k))
    nav_buttons.append(btn)

sidebar = pn.Column(
    pn.pane.HTML(
        f"<div style='padding:16px 12px 24px;text-align:center;'>"
        f"<span style='font-size:18px;font-weight:700;color:#fff;'>SAMID</span>"
        f"</div>"
    ),
    *nav_buttons,
    sizing_mode="stretch_width",
    styles={"background": BG_SIDEBAR},
)

# --- Template ---
template = pn.template.FastListTemplate(
    title="Sistema SAMID — Ranking da Qualidade da Informação Contábil",
    sidebar=[sidebar],
    main=[_main_pane],
    theme_toggle=False,
    accent_base_color="#1a1a2e",
    header_background="#16213e",
    sidebar_width=220,
)
template.servable()
```

Note: This will NOT run yet — it imports screens that don't exist. Tasks 4-10 create them one at a time, each producing a working intermediate state.

- [ ] **Step 3: Commit**

```bash
git add app/web_app.py app/screens/__init__.py
git commit -m "F5-01: layout shell with dark sidebar navigation"
```

---

## Task 4: Home Screen (Upload + Overview)

**Files:**
- Create: `app/screens/home.py`

**Figma reference:** `Investigação de Pendências Contábeis (2).png`

Upload area with cloud icon + "PROCESSAR ARQUIVO" button. After processing: 4 metric cards (conformidade, regras violadas, pendencias, contas analisadas), top-10 rules table. Calls `persist_result()` after engine completes.

- [ ] **Step 1: Create home.py**

The implementation should:
1. Build the upload area (FileInput + Processar button)
2. Build 4 metric cards (updated after processing)
3. Build top-10 rules table (Tabulator, read-only, updated after processing)
4. Wire `_on_processar` callback that runs the full pipeline:
   - `read_msc_csv()` → `normalize_ic()` → `run_engine()`
   - `persist_result()` (Task 1)
   - Update all widgets
5. Return `{"panel": pn.Column(...), "update": update_fn}` so other screens can refresh

Key details:
- `FileInput` widget with `.accept=".csv"`
- After processing, store result in `app_state["last_result"]`, `app_state["last_raw"]`, `app_state["last_normalized"]`
- Metric cards use `styles.metric_card()` from Task 2
- `EngineContext.snapshots_dir` MUST be set (copy from `run_pipeline.py` line 208) so R054 works
- Top-10 table: group pendencias by `regra_id`, sort descending, take first 10
- Compute conformidade as `(1 - regras_com_pendencia / regras_executadas) * 100`

- [ ] **Step 2: Create stub screens so app boots**

Create minimal stubs for ALL other screens (`execucao.py`, `regras.py`, `pendencias.py`, `caixa.py`, `passivos.py`, `superavit.py`) that return `{"panel": pn.Column(pn.pane.HTML("Em construção"))}`. This lets the app run while we build screens one at a time.

- [ ] **Step 3: Test manually** — `panel serve app/web_app.py --show`

Upload a CSV, click Processar. Verify:
- Metric cards update
- Top-10 table populates
- Check `data/snapshots/` — Parquet files created
- Check `data/reports/` — Excel file created
- Refresh page — data gone (expected for now; Task 5 adds reload)

- [ ] **Step 4: Commit**

```bash
git add app/screens/
git commit -m "F5-01: home screen with upload, metrics, persistence"
```

---

## Task 5: Execution Dashboard Screen

**Files:**
- Create: `app/screens/execucao.py`

**Figma reference:** `Painel de Execução Técnica.png`

Pipeline progress bar (Importação → Normalização → Validação → Consolidação), processing details (competência, siconfi, timestamps), execution log (last N log entries). This screen reads from `app_state["last_result"]` — no new backend logic needed.

- [ ] **Step 1: Implement execucao.py**

Key elements:
- Pipeline progress: 4 steps using `styles.pipeline_step()`, shown as `pn.Row`
- 4 metric cards: Linhas processadas (`len(raw.df)`), Tempo de execução (`result.fim - result.context.inicio`), Taxa de validação (`regras_executadas / total enabled`), Versão do motor (`ranking_msc.__version__`)
- Processing details: `pn.pane.HTML` with competência, siconfi, execucao_id, timestamps
- Log: read last 20 lines from `data/logs/ranking_msc.jsonl` and display in a table

- [ ] **Step 2: Test manually**

- [ ] **Step 3: Commit**

```bash
git add app/screens/execucao.py
git commit -m "F5-01: execution dashboard with pipeline progress and log"
```

---

## Task 6: Rules Analysis Screen

**Files:**
- Create: `app/screens/regras.py`

**Figma reference:** `Análise de Desempenho por Regra.png`

Two sections:
1. **Heatmap matrix** — rules × last 12 months. Color = pendencia count. Requires loading snapshots from multiple months (use `list_available_months()` from Task 1).
2. **Detail table** — one row per rule: código, dimensão, severidade, % falha, qtd ocorrências.

Click on a rule → navigate to Pendências filtered by that rule (like we had before, but via `_switch("pendencias")` + state).

- [ ] **Step 1: Implement regras.py**

For the heatmap:
- Use `plotly.graph_objects.Heatmap` rendered via `pn.pane.Plotly`
- Load available month snapshots: `list_available_months(siconfi, base_dir)`
- For each month, `read_snapshot(month, ...)` and count by `regra_id`
- If only current month exists, show single-column heatmap (still useful)

For the detail table:
- `pn.widgets.Tabulator`, `editors={}`, `selectable=True`
- Columns: Código, Nome, Dimensão, Severidade, % Falha, Pendências, Tendência
- Click → store selected rule_id in `app_state["filter_rule"]`, call `_switch("pendencias")`

- [ ] **Step 2: Test manually**

- [ ] **Step 3: Commit**

```bash
git add app/screens/regras.py
git commit -m "F5-01: rules analysis screen with heatmap and detail table"
```

---

## Task 7: Pendências Screen

**Files:**
- Create: `app/screens/pendencias.py`

**Figma reference:** `Investigação de Pendências Contábeis.png`

Left sidebar with filters (checkboxes for regra, severidade, dimensão, conta contábil). Main area is the full pendências table. Filters are built from the data after processing.

- [ ] **Step 1: Implement pendencias.py**

Key elements:
- **Filter sidebar** (inside the screen, not the app sidebar): `pn.Column` with:
  - `pn.widgets.CheckBoxGroup` for Código Regra (populated from unique `regra_id`)
  - `pn.widgets.CheckBoxGroup` for Severidade (`["ERRO", "ALERTA", "INFO"]`)
  - `pn.widgets.CheckBoxGroup` for Dimensão (populated from unique `dimensao`)
  - `pn.widgets.TextInput` for Conta Contábil (free text search)
- **Table**: `pn.widgets.Tabulator`, `editors={}`, `pagination="local"`, `page_size=30`
- All filter widgets use `param.watch` to filter the DataFrame reactively
- If `app_state["filter_rule"]` is set (from Rules click-through), pre-select it
- Status icons: red/orange/green circles via HTML in severidade column

- [ ] **Step 2: Test manually**

- [ ] **Step 3: Commit**

```bash
git add app/screens/pendencias.py
git commit -m "F5-01: pendencias screen with sidebar filters"
```

---

## Task 8: Wire Up Screen Refresh After Processing

**Files:**
- Modify: `app/screens/home.py`
- Modify: `app/web_app.py`

After processing in the Home screen, ALL other screens need to refresh their data. The `_on_processar` callback should trigger each screen's `update()` function.

- [ ] **Step 1: Add update protocol**

Each `build_*_screen(app_state)` returns `{"panel": ..., "update": callable}`. After processing, `home.py` calls:

```python
for screen in screens.values():
    if "update" in screen and screen["update"] is not None:
        screen["update"]()
```

- [ ] **Step 2: Wire in web_app.py**

Pass `screens` dict to `build_home_screen()` so it can trigger updates.

- [ ] **Step 3: Test manually** — process a CSV, then navigate to Regras, Pendências, Execução. Data should be populated without needing to re-process.

- [ ] **Step 4: Commit**

```bash
git add app/screens/home.py app/web_app.py
git commit -m "F5-01: wire screen refresh after processing"
```

---

## Task 9: Caixa Screen

**Files:**
- Create: `app/screens/caixa.py`

**Figma reference:** `Controle e Conciliação de Caixa.png`

4 metric cards (Saldo Inicial, Movimento Líquido, Saldo Final, Superávit/Déficit). Line chart of daily balance evolution. Donut chart of PO composition. Detail table by conta + PO.

Data source: the normalized MSC DataFrame (`app_state["last_normalized"]`). Filter by class 1 accounts (Ativo → Caixa).

- [ ] **Step 1: Implement caixa.py**

Key calculations from the normalized DataFrame:
- Filter `conta_contabil` starting with `1.1.1` (Caixa e Equivalentes)
- Saldo Inicial = sum of `saldo_inicial_debito - saldo_inicial_credito`
- Saldo Final = sum of `saldo_final_debito - saldo_final_credito`
- Movimento Líquido = Saldo Final - Saldo Inicial
- Group by PO (column `ic1` after normalize) for the donut chart
- Detail table: group by `conta_contabil` × PO, show saldo_inicial, movimento, saldo_final

Charts: Plotly `go.Scatter` (line) and `go.Pie` (donut).

- [ ] **Step 2: Test manually**

- [ ] **Step 3: Commit**

```bash
git add app/screens/caixa.py
git commit -m "F5-01: caixa screen with balance cards and charts"
```

---

## Task 10: Passivos Screen

**Files:**
- Create: `app/screens/passivos.py`

**Figma reference:** `Monitoramento de Passivos e Dívida.png`

4 metric cards. Bar chart (Circulante vs Não Circulante). Detail table by conta contábil.

- [ ] **Step 1: Implement passivos.py**

Data source: normalized DataFrame. Filter by class 2 accounts:
- `2.1` = Passivo Circulante
- `2.2` = Passivo Não Circulante
- Sum `saldo_final_credito - saldo_final_debito` per group
- Bar chart: `go.Bar` with month comparison (if multiple snapshots exist)
- Detail table: group by conta_contabil with FR, saldo_inicial, saldo_final, variação %

- [ ] **Step 2: Test manually**

- [ ] **Step 3: Commit**

```bash
git add app/screens/passivos.py
git commit -m "F5-01: passivos screen with liability breakdown"
```

---

## Task 11: Superávit Screen

**Files:**
- Create: `app/screens/superavit.py`

**Figma reference:** `Análise de Superávit Financeiro.png`

4 metric cards (Resultado Financeiro Total, Superávit Confirmado SIM/NÃO, Recursos Vinculados, Inconsistências). Horizontal bar chart by PO × Fonte. Detail table.

- [ ] **Step 1: Implement superavit.py**

Data source: normalized DataFrame.
- Resultado Financeiro = Ativo Financeiro (1.x) - Passivo Financeiro (2.x) filtered by Atributo Financeiro
- Superávit Confirmado = "SIM" if Resultado > 0
- Group by PO + FR for the bar chart
- Detail table with conta_contabil, descrição, saldo

- [ ] **Step 2: Test manually**

- [ ] **Step 3: Commit**

```bash
git add app/screens/superavit.py
git commit -m "F5-01: superavit screen with financial surplus analysis"
```

---

## Task 12: Polish — Lint, Type Check, Final Test

**Files:**
- Modify: all `app/` files as needed

- [ ] **Step 1: Run ruff and fix**

```bash
ruff check app/ --fix
ruff check app/
```

- [ ] **Step 2: Run full test suite**

```bash
pytest --tb=short -q
```
Expected: 471+ tests pass (original 471 + new persistence tests).

- [ ] **Step 3: Manual smoke test**

1. Start app: `panel serve app/web_app.py --show`
2. Upload CSV → verify all screens populate
3. Refresh page → verify data is gone (no auto-reload yet, but snapshots exist on disk)
4. Navigate between ALL 7 screens
5. Click rule in Regras → verify Pendências filters
6. Check `data/snapshots/`, `data/reports/`, `data/logs/`

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "F5-01: polish — lint, tests, smoke test pass"
```

---

## Out of Scope (Future Tasks)

- **Auto-reload snapshots on page refresh** (F5-02): detect existing snapshots on app init, offer dropdown to load previous months
- **Evolução Mensal chart** (F5-03): line chart comparing conformidade % across months (needs multiple months of data)
- **Heatmap with real 12-month data** (F5-03): needs historical snapshots
- **Auditoria tab** (F5-04): read `ranking_msc.jsonl` and display structured execution log with filters
- **Export Excel from web** (F5-05): download button that serves the already-generated Excel file
- **Multiusuário** (F5-06): concurrent job control, user identification
