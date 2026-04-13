"""
app/web_app.py
~~~~~~~~~~~~~~

Aplicação web Panel — Sistema SAMID.

Para rodar localmente:
    panel serve app/web_app.py --show --autoreload

Para rodar no servidor (multiusuário):
    panel serve app/web_app.py --address 0.0.0.0 --port 5006 \\
        --allow-websocket-origin=* --num-procs 2
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

import pandas as pd
import panel as pn

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "src"))

import ranking_msc.rules  # noqa: E402, F401
from ranking_msc.config.settings import load_settings  # noqa: E402
from ranking_msc.engine.executor import EngineContext, run_engine  # noqa: E402
from ranking_msc.io.reader_msc import read_msc_csv  # noqa: E402
from ranking_msc.outputs.logs import setup_logging  # noqa: E402
from ranking_msc.schemas import FACT_RESULTADO_REGRAS_COLUMNS  # noqa: E402
from ranking_msc.transform.ic_normalize import normalize_ic  # noqa: E402

# ---------------------------------------------------------------------------
# Inicialização
# ---------------------------------------------------------------------------
pn.extension("plotly", "tabulator", sizing_mode="stretch_width")

try:
    settings = load_settings(_PROJECT_ROOT / "config" / "settings.yaml")
except Exception as exc:
    from ranking_msc.config.settings import Settings
    settings = Settings()

logger = setup_logging(log_dir=settings.paths.logs_dir)
logger.info("Aplicação web iniciada.")

# ---------------------------------------------------------------------------
# Constantes de exibição
# ---------------------------------------------------------------------------

_PEND_COLS = [
    "regra_id", "severidade", "conta_contabil",
    "descricao", "valor_esperado", "valor_encontrado",
    "regra_nome", "dimensao",
]

_PEND_TITLES = {
    "regra_id": "Regra",
    "severidade": "Severidade",
    "conta_contabil": "Conta Contábil",
    "descricao": "Descrição",
    "valor_esperado": "Esperado",
    "valor_encontrado": "Encontrado",
    "regra_nome": "Nome da Regra",
    "dimensao": "Dimensão",
}

_PEND_WIDTHS = {
    "regra_id": 70,
    "severidade": 90,
    "conta_contabil": 155,
    "descricao": 340,
    "valor_esperado": 110,
    "valor_encontrado": 120,
    "regra_nome": 170,
    "dimensao": 100,
}

_STATUS_COLOR = {"OK": "#28a745", "PARCIAL": "#e67e00", "ERRO": "#dc3545"}

# ---------------------------------------------------------------------------
# Estado global
# ---------------------------------------------------------------------------
_all_pendencias: pd.DataFrame = pd.DataFrame(columns=_PEND_COLS)

# ---------------------------------------------------------------------------
# Header — importar MSC (onde ficava o botão de tema)
# ---------------------------------------------------------------------------

file_upload = pn.widgets.FileInput(accept=".csv", multiple=False, width=220)

btn_processar = pn.widgets.Button(
    name="▶ Processar", button_type="success", width=130,
)

status_indicator = pn.pane.Alert("Pronto.", alert_type="info", height=50, margin=(0, 0))

header_controls = pn.Row(
    pn.pane.HTML("<span style='color:white;font-weight:600;white-space:nowrap;'>Importar MSC:</span>"),
    file_upload,
    btn_processar,
    status_indicator,
    align="center",
    sizing_mode="stretch_width",
    margin=(4, 12),
)

# ---------------------------------------------------------------------------
# Conteúdo das seções
# ---------------------------------------------------------------------------

# — Status Geral —
_stats_html = pn.pane.HTML(
    "<p style='color:#aaa;padding:32px;font-size:15px;'>Aguardando processamento...</p>"
)
section_status = pn.Column(
    pn.pane.HTML("<h2 style='margin:0 0 16px'>📊 Status Geral</h2>"),
    _stats_html,
    sizing_mode="stretch_width",
)

# — Controle por Regras —
_controle_table = pn.widgets.Tabulator(
    pd.DataFrame(columns=["regra_id", "regra_nome", "dimensao", "pendencias"]),
    selectable=True,
    editors={},
    pagination="local",
    page_size=30,
    sizing_mode="stretch_width",
    show_index=False,
    titles={"regra_id": "Regra", "regra_nome": "Nome", "dimensao": "Dimensão", "pendencias": "Pendências"},
    widths={"regra_id": 70, "regra_nome": 220, "dimensao": 140, "pendencias": 100},
)

section_regras = pn.Column(
    pn.pane.HTML("<h2 style='margin:0 0 8px'>📋 Regras</h2>"),
    pn.pane.HTML(
        "<p style='color:#888;font-size:13px;margin:0 0 12px;'>"
        "💡 Clique em uma linha para ver as pendências daquela regra."
        "</p>"
    ),
    _controle_table,
    sizing_mode="stretch_width",
)

# — Pendências —
_pendencias_table = pn.widgets.Tabulator(
    pd.DataFrame(columns=_PEND_COLS),
    selectable=False,
    editors={},
    pagination="local",
    page_size=25,
    sizing_mode="stretch_width",
    show_index=False,
    titles=_PEND_TITLES,
    widths=_PEND_WIDTHS,
)

_filter_banner = pn.pane.HTML("")
btn_limpar_filtro = pn.widgets.Button(name="✕ Ver todas", button_type="light", width=120, visible=False)

section_pendencias = pn.Column(
    pn.pane.HTML("<h2 style='margin:0 0 8px'>⚠ Pendências</h2>"),
    pn.Row(_filter_banner, btn_limpar_filtro, align="center"),
    _pendencias_table,
    sizing_mode="stretch_width",
)

# — Seções futuras —
def _future(label: str) -> pn.Column:
    return pn.Column(
        pn.pane.HTML(f"<p style='color:#aaa;padding:40px;font-size:15px;'>{label} — implementação na Fase 5.</p>")
    )

section_caixa    = _future("💰 Meu Caixa")
section_passivos = _future("📑 Passivos")
section_superavit = _future("📈 Superávit")
section_auditoria = _future("🔍 Auditoria")

# ---------------------------------------------------------------------------
# Área principal — troca de seção via nav
# ---------------------------------------------------------------------------

_main_pane = pn.Column(section_status, sizing_mode="stretch_both", min_height=600)


def _switch_to(section: pn.viewable.Viewable) -> None:
    _main_pane.clear()
    _main_pane.append(section)


# ---------------------------------------------------------------------------
# Sidebar — navegação
# ---------------------------------------------------------------------------

_NAV_ITEMS = [
    ("📊  Status Geral",  section_status),
    ("📋  Regras",        section_regras),
    ("⚠   Pendências",   section_pendencias),
    ("💰  Meu Caixa",    section_caixa),
    ("📑  Passivos",      section_passivos),
    ("📈  Superávit",     section_superavit),
    ("🔍  Auditoria",     section_auditoria),
]

_nav_buttons: list[pn.widgets.Button] = []
for _label, _section in _NAV_ITEMS:
    _btn = pn.widgets.Button(
        name=_label,
        button_type="light",
        sizing_mode="stretch_width",
        margin=(2, 0),
    )
    _btn.on_click(lambda e, s=_section: _switch_to(s))
    _nav_buttons.append(_btn)

sidebar_nav = pn.Column(
    pn.pane.HTML("<p style='color:#aaa;font-size:11px;margin:0 0 6px;letter-spacing:1px;'>MENU</p>"),
    *_nav_buttons,
    sizing_mode="stretch_width",
)

# ---------------------------------------------------------------------------
# Interação: clique em regra → filtra pendências
# ---------------------------------------------------------------------------

def _reset_pendencias_filter() -> None:
    _pendencias_table.value = (
        _all_pendencias[_PEND_COLS] if not _all_pendencias.empty
        else pd.DataFrame(columns=_PEND_COLS)
    )
    _filter_banner.object = ""
    btn_limpar_filtro.visible = False
    _controle_table.selection = []


def _on_rule_select(event: object) -> None:
    sel = _controle_table.selection
    if not sel or _all_pendencias.empty:
        _reset_pendencias_filter()
        return

    row = _controle_table.value.iloc[sel[0]]
    rule_id   = row["regra_id"]
    rule_name = row["regra_nome"]
    filtered  = _all_pendencias[_all_pendencias["regra_id"] == rule_id]

    _pendencias_table.value = (
        filtered[_PEND_COLS] if not filtered.empty
        else pd.DataFrame(columns=_PEND_COLS)
    )
    _filter_banner.object = (
        f"<span style='background:#e9f0ff;border:1px solid #b0c4de;"
        f"border-radius:6px;padding:5px 12px;font-size:13px;'>"
        f"Filtrando: <strong>{rule_id} — {rule_name}</strong>"
        f" ({len(filtered)} pendência(s))</span>"
    )
    btn_limpar_filtro.visible = True
    _switch_to(section_pendencias)


btn_limpar_filtro.on_click(lambda e: _reset_pendencias_filter())
_controle_table.param.watch(_on_rule_select, "selection")

# ---------------------------------------------------------------------------
# Helpers de UI
# ---------------------------------------------------------------------------

def _build_stats_html(raw: object, result: object, counts: dict) -> str:  # type: ignore[type-arg]
    n_err = counts.get("ERRO", 0)
    n_alt = counts.get("ALERTA", 0)
    n_inf = counts.get("INFO", 0)
    sc = _STATUS_COLOR.get(result.status, "#6c757d")  # type: ignore[union-attr]

    def card(label: str, val: int, color: str) -> str:
        return (
            f"<div style='background:{color};color:white;border-radius:10px;"
            f"padding:18px 28px;text-align:center;min-width:110px;'>"
            f"<div style='font-size:36px;font-weight:700;line-height:1'>{val}</div>"
            f"<div style='font-size:11px;margin-top:6px;opacity:.9;letter-spacing:.5px'>{label}</div>"
            f"</div>"
        )

    return (
        f"<div style='font-family:sans-serif;padding:8px 0;'>"
        f"<p style='margin:0 0 8px;font-size:16px;color:#333;'>"
        f"<strong>{raw.competencia}</strong> &nbsp;·&nbsp; {raw.siconfi}</p>"  # type: ignore[union-attr]
        f"<div style='margin-bottom:20px;'>"
        f"<span style='background:{sc};color:white;padding:5px 18px;"
        f"border-radius:20px;font-weight:600;font-size:14px;'>{result.status}</span>"  # type: ignore[union-attr]
        f"<span style='margin-left:10px;color:#666;font-size:13px;'>"
        f"{result.regras_executadas} regras executadas"  # type: ignore[union-attr]
        f"{'&nbsp;·&nbsp;' + str(result.regras_com_erro) + ' com erro' if result.regras_com_erro else ''}"  # type: ignore[union-attr]
        f"</span></div>"
        f"<div style='display:flex;gap:12px;flex-wrap:wrap;'>"
        f"{card('ERRO', n_err, '#dc3545')}"
        f"{card('ALERTA', n_alt, '#e67e00')}"
        f"{card('INFO', n_inf, '#0d6efd')}"
        f"{card('TOTAL', result.total_pendencias, '#495057')}"  # type: ignore[union-attr]
        f"</div>"
        f"<p style='margin:16px 0 0;font-size:13px;color:#888;'>"
        f"Clique em uma regra no menu <strong>Regras</strong> para ver as pendências detalhadas."
        f"</p></div>"
    )

# ---------------------------------------------------------------------------
# Callback principal — Processar
# ---------------------------------------------------------------------------

_ENGINE_STATUS_TO_ALERT = {"OK": "success", "PARCIAL": "warning", "ERRO": "danger"}


def _on_processar(event: object) -> None:
    global _all_pendencias

    if not file_upload.value:
        status_indicator.object = "⚠ Selecione um CSV."
        status_indicator.alert_type = "warning"
        return

    status_indicator.object = "⏳ Processando..."
    status_indicator.alert_type = "info"

    try:
        raw = read_msc_csv(io.BytesIO(file_upload.value))
    except Exception as exc:
        logger.error("Falha ao ler CSV MSC: %s", exc, exc_info=True)
        status_indicator.object = f"❌ Erro ao ler: {exc}"
        status_indicator.alert_type = "danger"
        return

    try:
        df = normalize_ic(raw.df)
    except Exception as exc:
        logger.error("Falha ao normalizar IC: %s", exc, exc_info=True)
        status_indicator.object = f"❌ Erro ao normalizar: {exc}"
        status_indicator.alert_type = "danger"
        return

    context = EngineContext(
        competencia=raw.competencia,
        siconfi=raw.siconfi,
        settings=settings,
        pre_pivot_issues=raw.pre_pivot_issues,
    )

    try:
        result = run_engine(df, context)
    except Exception as exc:
        logger.error("Falha crítica no motor: %s", exc, exc_info=True)
        status_indicator.object = f"❌ Erro no motor: {exc}"
        status_indicator.alert_type = "danger"
        return

    # Banner
    icons = {"OK": "✅", "PARCIAL": "⚠️", "ERRO": "❌"}
    icon  = icons.get(result.status, "❓")
    alert_type = _ENGINE_STATUS_TO_ALERT.get(result.status, "warning")

    if result.status == "OK":
        msg = f"{icon} {raw.competencia} — {result.total_pendencias} pendência(s) · {result.regras_executadas} regras."
    elif result.status == "PARCIAL":
        msg = f"{icon} Parcial: {result.regras_com_erro} erro(s) · {result.total_pendencias} pendência(s)."
    else:
        msg = f"{icon} Falha: {result.regras_com_erro} erro(s) fatal(is)."

    status_indicator.object = msg
    status_indicator.alert_type = alert_type

    # Status Geral
    counts = result.pendencias.groupby("severidade").size().to_dict() if not result.pendencias.empty else {}
    _stats_html.object = _build_stats_html(raw, result, counts)

    # Controle por Regras
    if not result.pendencias.empty:
        controle_df = (
            result.pendencias
            .groupby(["regra_id", "regra_nome", "dimensao"])
            .size()
            .reset_index(name="pendencias")
            .sort_values("pendencias", ascending=False)
            .reset_index(drop=True)
        )
    else:
        controle_df = pd.DataFrame(columns=["regra_id", "regra_nome", "dimensao", "pendencias"])
    _controle_table.value = controle_df
    _controle_table.selection = []

    # Pendências
    cols = [c for c in _PEND_COLS if c in result.pendencias.columns]
    _all_pendencias = result.pendencias[cols].copy() if not result.pendencias.empty else pd.DataFrame(columns=_PEND_COLS)
    _pendencias_table.value = _all_pendencias
    _filter_banner.object = ""
    btn_limpar_filtro.visible = False

    # Vai para Status Geral após processar
    _switch_to(section_status)

    logger.info(
        "Execução concluída: status=%s, regras=%d, erros=%d, pendencias=%d",
        result.status, result.regras_executadas, result.regras_com_erro, result.total_pendencias,
        extra={"execucao_id": context.execucao_id, "competencia": raw.competencia},
    )


btn_processar.on_click(_on_processar)

# ---------------------------------------------------------------------------
# Template
# ---------------------------------------------------------------------------

template = pn.template.FastListTemplate(
    title="Sistema SAMID",
    header=[header_controls],
    sidebar=[sidebar_nav],
    main=[_main_pane],
    theme_toggle=False,
    accent_base_color="#1f77b4",
    header_background="#1f77b4",
)

template.servable()
