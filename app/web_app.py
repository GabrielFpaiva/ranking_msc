"""
app/web_app.py — Sistema SAMID

    panel serve app/web_app.py --show --autoreload
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
# Init
# ---------------------------------------------------------------------------
pn.extension("plotly", "tabulator", sizing_mode="stretch_width")

try:
    settings = load_settings(_PROJECT_ROOT / "config" / "settings.yaml")
except Exception:
    from ranking_msc.config.settings import Settings
    settings = Settings()

logger = setup_logging(log_dir=settings.paths.logs_dir)
logger.info("Aplicação web iniciada.")

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------
_PEND_COLS = [
    "regra_id", "severidade", "conta_contabil",
    "descricao", "valor_esperado", "valor_encontrado",
    "regra_nome", "dimensao",
]

_STATUS_COLOR = {"OK": "#28a745", "PARCIAL": "#e67e00", "ERRO": "#dc3545"}
_all_pendencias: pd.DataFrame = pd.DataFrame(columns=_PEND_COLS)

# ---------------------------------------------------------------------------
# Upload (topo da página)
# ---------------------------------------------------------------------------
file_upload = pn.widgets.FileInput(accept=".csv", multiple=False, width=280)
btn_processar = pn.widgets.Button(name="▶ Processar", button_type="primary", width=140)
status_indicator = pn.pane.Alert("Selecione um CSV e clique em Processar.", alert_type="info")

upload_bar = pn.Card(
    pn.Row(file_upload, btn_processar, align="center", margin=(0, 10)),
    status_indicator,
    title="📂 Importar MSC",
    collapsed=False,
    sizing_mode="stretch_width",
    margin=(0, 0, 10, 0),
)

# ---------------------------------------------------------------------------
# Tab: Status Geral
# ---------------------------------------------------------------------------
_stats_html = pn.pane.HTML(
    "<p style='color:#999;padding:20px;'>Nenhum arquivo processado.</p>",
    sizing_mode="stretch_width",
)

# ---------------------------------------------------------------------------
# Tab: Regras
# ---------------------------------------------------------------------------
_controle_table = pn.widgets.Tabulator(
    pd.DataFrame(columns=["regra_id", "regra_nome", "dimensao", "pendencias"]),
    editors={},
    selectable=True,
    pagination="local",
    page_size=35,
    sizing_mode="stretch_width",
    show_index=False,
    titles={"regra_id": "Regra", "regra_nome": "Nome", "dimensao": "Dimensão", "pendencias": "Qtd"},
    widths={"regra_id": 70, "regra_nome": 250, "dimensao": 140, "pendencias": 80},
    text_align={"pendencias": "center"},
)
_regras_hint = pn.pane.HTML(
    "<p style='color:#777;font-size:13px;margin:4px 0 8px;'>"
    "Clique em uma regra para ver suas pendências.</p>"
)

# ---------------------------------------------------------------------------
# Tab: Pendências
# ---------------------------------------------------------------------------
_pendencias_table = pn.widgets.Tabulator(
    pd.DataFrame(columns=_PEND_COLS),
    editors={},
    selectable=False,
    pagination="local",
    page_size=30,
    sizing_mode="stretch_width",
    show_index=False,
    titles={
        "regra_id": "Regra", "severidade": "Sev.",
        "conta_contabil": "Conta", "descricao": "Descrição",
        "valor_esperado": "Esperado", "valor_encontrado": "Encontrado",
        "regra_nome": "Nome Regra", "dimensao": "Dimensão",
    },
    widths={
        "regra_id": 65, "severidade": 75, "conta_contabil": 150,
        "descricao": 320, "valor_esperado": 105, "valor_encontrado": 115,
        "regra_nome": 160, "dimensao": 95,
    },
)

_filter_banner = pn.pane.HTML("")
btn_limpar = pn.widgets.Button(name="✕ Limpar filtro", button_type="light", width=130, visible=False)

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tabs = pn.Tabs(
    ("📊 Status Geral", pn.Column(_stats_html)),
    ("📋 Regras", pn.Column(_regras_hint, _controle_table)),
    ("⚠ Pendências", pn.Column(pn.Row(_filter_banner, btn_limpar), _pendencias_table)),
    ("💰 Meu Caixa", pn.pane.HTML("<p style='color:#aaa;padding:30px;'>Fase 5</p>")),
    ("📑 Passivos", pn.pane.HTML("<p style='color:#aaa;padding:30px;'>Fase 5</p>")),
    ("📈 Superávit", pn.pane.HTML("<p style='color:#aaa;padding:30px;'>Fase 5</p>")),
    ("🔍 Auditoria", pn.pane.HTML("<p style='color:#aaa;padding:30px;'>Fase 5</p>")),
    dynamic=True,
    sizing_mode="stretch_width",
)

# ---------------------------------------------------------------------------
# Interação: clique regra → pendências filtradas
# ---------------------------------------------------------------------------

def _reset_filter() -> None:
    _pendencias_table.value = (
        _all_pendencias if not _all_pendencias.empty
        else pd.DataFrame(columns=_PEND_COLS)
    )
    _filter_banner.object = ""
    btn_limpar.visible = False
    _controle_table.selection = []


def _on_rule_click(event: object) -> None:
    sel = _controle_table.selection
    if not sel or _all_pendencias.empty:
        return

    row = _controle_table.value.iloc[sel[0]]
    rid = row["regra_id"]
    rname = row["regra_nome"]
    filtered = _all_pendencias[_all_pendencias["regra_id"] == rid]

    _pendencias_table.value = (
        filtered if not filtered.empty
        else pd.DataFrame(columns=_PEND_COLS)
    )
    _filter_banner.object = (
        f"<span style='background:#dbeafe;border:1px solid #93c5fd;"
        f"border-radius:6px;padding:4px 12px;font-size:13px;'>"
        f"<strong>{rid}</strong> — {rname} ({len(filtered)})</span>"
    )
    btn_limpar.visible = True
    tabs.active = 2  # vai para aba Pendências


btn_limpar.on_click(lambda e: _reset_filter())
_controle_table.param.watch(_on_rule_click, "selection")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _card(label: str, val: int, bg: str) -> str:
    return (
        f"<div style='background:{bg};color:#fff;border-radius:12px;"
        f"padding:20px 0;text-align:center;min-width:120px;flex:1;'>"
        f"<div style='font-size:40px;font-weight:700;line-height:1;'>{val}</div>"
        f"<div style='font-size:12px;margin-top:8px;opacity:.85;'>{label}</div>"
        f"</div>"
    )


def _build_stats(raw: object, result: object, counts: dict) -> str:  # type: ignore[type-arg]
    sc = _STATUS_COLOR.get(result.status, "#6c757d")  # type: ignore[union-attr]
    return f"""<div style="font-family:system-ui,sans-serif;">
  <div style="display:flex;align-items:center;gap:12px;margin-bottom:20px;">
    <span style="background:{sc};color:#fff;padding:6px 20px;border-radius:24px;
          font-weight:700;font-size:15px;">{result.status}</span>
    <span style="font-size:18px;font-weight:600;">{raw.competencia}</span>
    <span style="color:#888;font-size:14px;">{raw.siconfi}</span>
    <span style="color:#888;font-size:13px;margin-left:auto;">
      {result.regras_executadas} regras
      {"· " + str(result.regras_com_erro) + " com erro" if result.regras_com_erro else ""}
    </span>
  </div>
  <div style="display:flex;gap:14px;flex-wrap:wrap;">
    {_card("ERRO", counts.get("ERRO", 0), "#dc3545")}
    {_card("ALERTA", counts.get("ALERTA", 0), "#e67e00")}
    {_card("INFO", counts.get("INFO", 0), "#0d6efd")}
    {_card("TOTAL", result.total_pendencias, "#495057")}
  </div>
</div>"""

# ---------------------------------------------------------------------------
# Callback: Processar
# ---------------------------------------------------------------------------

def _on_processar(event: object) -> None:
    global _all_pendencias

    if not file_upload.value:
        status_indicator.object = "⚠ Selecione um arquivo CSV."
        status_indicator.alert_type = "warning"
        return

    status_indicator.object = "⏳ Processando..."
    status_indicator.alert_type = "info"

    try:
        raw = read_msc_csv(io.BytesIO(file_upload.value))
    except Exception as exc:
        logger.error("Falha ao ler CSV: %s", exc, exc_info=True)
        status_indicator.object = f"❌ Erro na leitura: {exc}"
        status_indicator.alert_type = "danger"
        return

    try:
        df = normalize_ic(raw.df)
    except Exception as exc:
        logger.error("Falha ao normalizar: %s", exc, exc_info=True)
        status_indicator.object = f"❌ Erro na normalização: {exc}"
        status_indicator.alert_type = "danger"
        return

    ctx = EngineContext(
        competencia=raw.competencia, siconfi=raw.siconfi,
        settings=settings, pre_pivot_issues=raw.pre_pivot_issues,
    )

    try:
        result = run_engine(df, ctx)
    except Exception as exc:
        logger.error("Falha no motor: %s", exc, exc_info=True)
        status_indicator.object = f"❌ Erro no motor: {exc}"
        status_indicator.alert_type = "danger"
        return

    # Banner
    alert_map = {"OK": "success", "PARCIAL": "warning", "ERRO": "danger"}
    status_indicator.object = (
        f"✅ {raw.competencia} — {result.total_pendencias} pendência(s), "
        f"{result.regras_executadas} regras."
        if result.status == "OK"
        else f"⚠ {result.status}: {result.regras_com_erro} erro(s), {result.total_pendencias} pendência(s)."
    )
    status_indicator.alert_type = alert_map.get(result.status, "warning")

    # Status Geral
    counts = result.pendencias.groupby("severidade").size().to_dict() if not result.pendencias.empty else {}
    _stats_html.object = _build_stats(raw, result, counts)

    # Regras
    if not result.pendencias.empty:
        ctrl = (
            result.pendencias
            .groupby(["regra_id", "regra_nome", "dimensao"]).size()
            .reset_index(name="pendencias")
            .sort_values("pendencias", ascending=False)
            .reset_index(drop=True)
        )
    else:
        ctrl = pd.DataFrame(columns=["regra_id", "regra_nome", "dimensao", "pendencias"])
    _controle_table.value = ctrl
    _controle_table.selection = []

    # Pendências
    cols = [c for c in _PEND_COLS if c in result.pendencias.columns]
    _all_pendencias = result.pendencias[cols].copy() if not result.pendencias.empty else pd.DataFrame(columns=_PEND_COLS)
    _pendencias_table.value = _all_pendencias
    _filter_banner.object = ""
    btn_limpar.visible = False

    tabs.active = 0  # vai para Status Geral

    logger.info(
        "Execução concluída: status=%s, regras=%d, erros=%d, pendencias=%d",
        result.status, result.regras_executadas, result.regras_com_erro, result.total_pendencias,
        extra={"execucao_id": ctx.execucao_id, "competencia": raw.competencia},
    )


btn_processar.on_click(_on_processar)

# ---------------------------------------------------------------------------
# Template
# ---------------------------------------------------------------------------
template = pn.template.FastListTemplate(
    title="Sistema SAMID",
    main=[upload_bar, tabs],
    theme_toggle=False,
    accent_base_color="#1f77b4",
    header_background="#1f77b4",
)
template.servable()
