"""
app/web_app.py
~~~~~~~~~~~~~~

Aplicação web Panel — interface principal do Ranking MSC.

Orquestrador fino: carrega Tab Registry, conecta o engine real,
serve com BootstrapTemplate.

Para rodar localmente:
    panel serve app/web_app.py --show --autoreload

Para rodar no servidor (multiusuário):
    panel serve app/web_app.py --address 0.0.0.0 --port 5006 \\
        --allow-websocket-origin=* --num-procs 2

Para adicionar nova aba: criar app/tabs/<nome>.py e importar em app/tabs/__init__.py.
Não é necessário alterar este arquivo.
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

import panel as pn

# --- Ajuste de path para importar o pacote src/ ---
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "src"))
sys.path.insert(0, str(_PROJECT_ROOT))  # para importar app.tabs

import app.tabs  # noqa: F401, E402 — dispara registro de todas as abas
from app.tabs.base import TAB_REGISTRY  # noqa: E402
from ranking_msc.config.settings import load_settings  # noqa: E402
from ranking_msc.engine.executor import EngineContext, run_engine  # noqa: E402
from ranking_msc.io.reader_msc import read_msc_csv  # noqa: E402
from ranking_msc.outputs.logs import setup_logging  # noqa: E402
from ranking_msc.transform.ic_normalize import normalize_ic  # noqa: E402

# ---------------------------------------------------------------------------
# Inicialização
# ---------------------------------------------------------------------------
pn.extension(sizing_mode="stretch_width")

try:
    settings = load_settings(_PROJECT_ROOT / "config" / "settings.yaml")
except Exception as exc:
    from ranking_msc.config.settings import Settings
    settings = Settings()
    print(f"⚠ Config não encontrado, usando defaults: {exc}")  # noqa: T201

logger = setup_logging(log_dir=settings.paths.logs_dir)
logger.info("Aplicação web iniciada.")


# ---------------------------------------------------------------------------
# Containers das abas (atualizados após cada processamento)
# ---------------------------------------------------------------------------
_sorted_tabs = sorted(TAB_REGISTRY.values(), key=lambda t: t.order)

_tab_containers: dict[str, pn.Column] = {
    tab.tab_id: pn.Column(tab.render(None), sizing_mode="stretch_width")
    for tab in _sorted_tabs
}

tabs = pn.Tabs(
    *[(tab.tab_name, _tab_containers[tab.tab_id]) for tab in _sorted_tabs],
    dynamic=True,
    sizing_mode="stretch_width",
)


# ---------------------------------------------------------------------------
# Widgets de controle (sidebar)
# ---------------------------------------------------------------------------
file_upload = pn.widgets.FileInput(
    accept=".csv",
    multiple=False,
    name="Arquivo CSV MSC",
)

btn_processar = pn.widgets.Button(
    name="▶ Processar",
    button_type="primary",
    width=200,
)

status_indicator = pn.pane.Alert(
    "Nenhum arquivo processado ainda.",
    alert_type="info",
)


def _on_processar(event: object) -> None:
    """Callback do botão Processar.

    Fluxo:
        1. Valida que arquivo foi selecionado.
        2. Lê CSV via read_msc_csv().
        3. Normaliza IC via normalize_ic().
        4. Monta EngineContext com competência, siconfi e settings.
        5. Executa run_engine() → EngineResult.
        6. Atualiza containers de cada aba registrada.
    """
    if file_upload.value is None:
        status_indicator.object = "⚠ Selecione um arquivo CSV antes de processar."
        status_indicator.alert_type = "warning"
        return

    btn_processar.disabled = True
    status_indicator.object = "⏳ Processando…"
    status_indicator.alert_type = "info"

    try:
        raw = read_msc_csv(io.BytesIO(file_upload.value))
        df = normalize_ic(raw.df)

        context = EngineContext(
            competencia=raw.competencia,
            siconfi=raw.siconfi,
            settings=settings,
            pre_pivot_issues=raw.pre_pivot_issues,
            snapshots_dir=Path(settings.paths.snapshots_dir),
        )

        result = run_engine(df, context)

        for tab in _sorted_tabs:
            _tab_containers[tab.tab_id].objects = [tab.render(result)]

        total = result.total_pendencias
        erros = int((result.pendencias["severidade"] == "ERRO").sum()) if total else 0
        status_indicator.object = (
            f"✅ Processado: competência `{raw.competencia}` | "
            f"{total} pendência(s) | {erros} ERRO(s)"
        )
        status_indicator.alert_type = "success" if erros == 0 else "danger"

    except Exception as exc:  # noqa: BLE001
        logger.error("Erro no processamento via web: %s", exc, exc_info=True)
        status_indicator.object = f"❌ Erro: {exc}"
        status_indicator.alert_type = "danger"

    finally:
        btn_processar.disabled = False


btn_processar.on_click(_on_processar)

sidebar = pn.Column(
    "## 📂 Importar MSC",
    file_upload,
    btn_processar,
    pn.layout.Divider(),
    status_indicator,
    width=320,
)


# ---------------------------------------------------------------------------
# Layout principal — BootstrapTemplate
# ---------------------------------------------------------------------------

template = pn.template.BootstrapTemplate(
    title=settings.app.title,
    sidebar=[sidebar],
    main=[tabs],
    header_background="#1a5276",
)

template.servable()
