"""
app/web_app.py
~~~~~~~~~~~~~~

Aplicação web Panel — interface principal do Ranking MSC.

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

# --- Ajuste de path para importar o pacote src/ ---
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "src"))

import ranking_msc.rules  # noqa: E402, F401  # popula RULE_REGISTRY via @register_rule
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
    print(f"⚠ Config não encontrado, usando defaults: {exc}")

logger = setup_logging(log_dir=settings.paths.logs_dir)
logger.info("Aplicação web iniciada.")


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


# ---------------------------------------------------------------------------
# Widgets reativos das abas — atualizados após cada execução
# ---------------------------------------------------------------------------

# Aba Status Geral
_stats_pane = pn.pane.Markdown("*Aguardando processamento...*")
tab_status_geral = pn.Column(
    "## 📊 Status Geral",
    _stats_pane,
)

# Aba Controle por Regras
_controle_table = pn.widgets.Tabulator(
    pd.DataFrame(columns=["regra_id", "regra_nome", "dimensao", "pendencias"]),
    pagination="local",
    page_size=20,
    sizing_mode="stretch_width",
    show_index=False,
)
tab_controle_regras = pn.Column(
    "## 📋 Controle por Regras",
    _controle_table,
)

# Aba Pendências
_pendencias_table = pn.widgets.Tabulator(
    pd.DataFrame(columns=FACT_RESULTADO_REGRAS_COLUMNS),
    pagination="local",
    page_size=25,
    sizing_mode="stretch_width",
    show_index=False,
    hidden_columns=["competencia"],
    header_filters=True,
)
tab_pendencias = pn.Column(
    "## ⚠ Pendências",
    _pendencias_table,
)

# Abas ainda não implementadas — Fase 5
tab_meu_caixa = pn.Column(
    "## 💰 Meu Caixa",
    pn.pane.Markdown("*Análise de fluxo de caixa — implementação na Fase 5.*"),
)

tab_passivos = pn.Column(
    "## 📑 Passivos",
    pn.pane.Markdown("*Análise de passivos — implementação na Fase 5.*"),
)

tab_superavit = pn.Column(
    "## 📈 Superávit",
    pn.pane.Markdown("*Análise do superávit financeiro — implementação na Fase 5.*"),
)

tab_auditoria = pn.Column(
    "## 🔍 Auditoria",
    pn.pane.Markdown("*Log de execuções — implementação na Fase 5.*"),
)


# ---------------------------------------------------------------------------
# Callback do botão Processar
# ---------------------------------------------------------------------------

_ENGINE_STATUS_TO_ALERT: dict[str, str] = {
    "OK": "success",
    "PARCIAL": "warning",
    "ERRO": "danger",
}

_STATUS_ICON: dict[str, str] = {
    "OK": "✅",
    "PARCIAL": "⚠️",
    "ERRO": "❌",
}


def _on_processar(event: object) -> None:
    """Executa o pipeline MSC e atualiza todas as abas com os resultados."""
    if not file_upload.value:  # cobre None e b""
        status_indicator.object = "⚠ Selecione um arquivo CSV antes de processar."
        status_indicator.alert_type = "warning"
        return

    status_indicator.object = "⏳ Processando..."
    status_indicator.alert_type = "info"

    try:
        raw = read_msc_csv(io.BytesIO(file_upload.value))
    except Exception as exc:
        logger.error("Falha ao ler CSV MSC: %s", exc, exc_info=True)
        status_indicator.object = f"❌ Erro ao ler o arquivo CSV: {exc}"
        status_indicator.alert_type = "danger"
        return

    try:
        df = normalize_ic(raw.df)
    except Exception as exc:
        logger.error("Falha ao normalizar IC: %s", exc, exc_info=True)
        status_indicator.object = f"❌ Erro ao normalizar o arquivo: {exc}"
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
        status_indicator.object = f"❌ Erro crítico no motor de regras: {exc}"
        status_indicator.alert_type = "danger"
        return

    # --- Banner de status ---
    alert_type = _ENGINE_STATUS_TO_ALERT.get(result.status, "warning")
    icon = _STATUS_ICON.get(result.status, "❓")

    if result.status == "OK":
        msg = (
            f"{icon} Processado: {raw.competencia} — {raw.siconfi}. "
            f"{result.total_pendencias} pendência(s), "
            f"{result.regras_executadas} regra(s) executada(s)."
        )
    elif result.status == "PARCIAL":
        msg = (
            f"{icon} Processamento parcial: {result.regras_com_erro} regra(s) com erro. "
            f"{result.total_pendencias} pendência(s) gerada(s). "
            "Verifique o log de auditoria."
        )
    else:  # ERRO
        msg = (
            f"{icon} Falha no motor: {result.regras_com_erro} regra(s) com erro fatal. "
            f"{result.total_pendencias} pendência(s) gerada(s) antes da falha. "
            "Verifique o log de auditoria."
        )

    status_indicator.object = msg
    status_indicator.alert_type = alert_type

    # --- Atualizar aba Status Geral ---
    if not result.pendencias.empty:
        counts = result.pendencias.groupby("severidade").size().to_dict()
    else:
        counts = {}

    n_erros = counts.get("ERRO", 0)
    n_alertas = counts.get("ALERTA", 0)
    n_infos = counts.get("INFO", 0)

    _stats_pane.object = f"""
**Competência:** {raw.competencia} &nbsp;|&nbsp; **Ente (SICONFI):** {raw.siconfi}

**Status da execução:** {icon} {result.status}

| Severidade | Pendências |
|:---|---:|
| 🔴 ERRO | {n_erros} |
| 🟡 ALERTA | {n_alertas} |
| 🔵 INFO | {n_infos} |
| **Total** | **{result.total_pendencias}** |

**Regras executadas:** {result.regras_executadas} &nbsp;|&nbsp; **Com erro:** {result.regras_com_erro}
"""

    # --- Atualizar aba Controle por Regras ---
    if not result.pendencias.empty:
        controle_df = (
            result.pendencias
            .groupby(["regra_id", "regra_nome", "dimensao"])
            .size()
            .reset_index(name="pendencias")
            .sort_values("pendencias", ascending=False)
        )
    else:
        controle_df = pd.DataFrame(
            columns=["regra_id", "regra_nome", "dimensao", "pendencias"]
        )
    _controle_table.value = controle_df

    # --- Atualizar aba Pendências ---
    _pendencias_table.value = result.pendencias

    logger.info(
        "Execução concluída: status=%s, regras=%d, erros=%d, pendencias=%d",
        result.status, result.regras_executadas, result.regras_com_erro, result.total_pendencias,
        extra={"execucao_id": context.execucao_id, "competencia": raw.competencia},
    )


btn_processar.on_click(_on_processar)

# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

sidebar = pn.Column(
    "## 📂 Importar MSC",
    file_upload,
    btn_processar,
    pn.layout.Divider(),
    status_indicator,
    width=320,
)

tabs = pn.Tabs(
    ("Status Geral", tab_status_geral),
    ("Controle por Regras", tab_controle_regras),
    ("Pendências", tab_pendencias),
    ("Meu Caixa", tab_meu_caixa),
    ("Passivos", tab_passivos),
    ("Superávit", tab_superavit),
    ("Auditoria", tab_auditoria),
    dynamic=True,
)

template = pn.template.FastListTemplate(
    title=settings.app.title,
    sidebar=[sidebar],
    main=[tabs],
    accent_base_color="#1f77b4",
    header_background="#1f77b4",
)

template.servable()
