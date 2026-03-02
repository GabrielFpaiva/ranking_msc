"""
app/web_app.py
~~~~~~~~~~~~~~

Aplicação web Panel — interface principal do Ranking MSC.

Para rodar localmente:
    panel serve app/web_app.py --show --autoreload

Para rodar no servidor (multiusuário):
    panel serve app/web_app.py --address 0.0.0.0 --port 5006 \\
        --allow-websocket-origin=* --num-procs 2

Abas obrigatórias:
    1. Status Geral       — visão consolidada (score, totais por severidade)
    2. Controle por Regras — detalhamento das regras R082–R111
    3. Pendências         — listagem filtrada de pendências
    4. Meu Caixa          — fluxo de caixa / conciliação
    5. Passivos           — análise de passivos
    6. Superávit          — análise do superávit financeiro
    7. Auditoria          — log de execuções e rastreabilidade
"""

from __future__ import annotations

import sys
from pathlib import Path

import panel as pn

# --- Ajuste de path para importar o pacote src/ ---
# Em produção, prefira instalar o pacote via pip install -e .
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "src"))

from ranking_msc.config.settings import load_settings  # noqa: E402
from ranking_msc.outputs.logs import setup_logging      # noqa: E402

# ---------------------------------------------------------------------------
# Inicialização
# ---------------------------------------------------------------------------
pn.extension("plotly", "tabulator", sizing_mode="stretch_width")

try:
    settings = load_settings(_PROJECT_ROOT / "config" / "settings.yaml")
except Exception as exc:
    # Se o config não existir, usa defaults (bom para primeiro run)
    from ranking_msc.config.settings import Settings
    settings = Settings()
    print(f"⚠ Config não encontrado, usando defaults: {exc}")

logger = setup_logging(log_dir=settings.paths.logs_dir)
logger.info("Aplicação web iniciada.")


# ---------------------------------------------------------------------------
# Widgets de upload e controle
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

# Indicador de status do processamento
status_indicator = pn.pane.Alert(
    "Nenhum arquivo processado ainda.",
    alert_type="info",
)


def _on_processar(event: object) -> None:
    """Callback do botão Processar.

    Fluxo futuro:
        1. Validar que um arquivo foi selecionado.
        2. Chamar read_msc_csv(file_upload.value) para obter RawMSC.
        3. Chamar normalize_ic(raw.df) para normalizar IC/TIPO.
        4. Montar EngineContext com competência, siconfi, settings.
        5. Chamar run_engine(df_normalizado, context) para obter EngineResult.
        6. Gravar snapshot (write_snapshot_atomic).
        7. Atualizar widgets das abas com os resultados.
        8. Gerar relatório Excel (export_issues_excel) se solicitado.

    TODO: tratar exceções e exibir mensagens amigáveis no status_indicator.
    """
    if file_upload.value is None:
        status_indicator.object = "⚠ Selecione um arquivo CSV antes de processar."
        status_indicator.alert_type = "warning"
        return

    status_indicator.object = "⏳ Processando... (stub — motor não implementado ainda)"
    status_indicator.alert_type = "info"

    # --- STUB: aqui entra o fluxo real ---
    # from ranking_msc.io.reader_msc import read_msc_csv
    # from ranking_msc.transform.ic_normalize import normalize_ic
    # from ranking_msc.engine.executor import run_engine, EngineContext
    #
    # raw = read_msc_csv(io.BytesIO(file_upload.value))
    # df = normalize_ic(raw.df)
    # context = EngineContext(competencia=raw.competencia, siconfi=raw.siconfi, settings=settings)
    # result = run_engine(df, context)
    # _update_tabs(result)

    status_indicator.object = "✅ Stub concluído. Implemente run_engine() para resultados reais."
    status_indicator.alert_type = "success"


btn_processar.on_click(_on_processar)

# Painel lateral de controle
sidebar = pn.Column(
    "## 📂 Importar MSC",
    file_upload,
    btn_processar,
    pn.layout.Divider(),
    status_indicator,
    width=320,
)


# ---------------------------------------------------------------------------
# Abas de conteúdo
# ---------------------------------------------------------------------------

def _make_placeholder(title: str, description: str) -> pn.Column:
    """Cria conteúdo placeholder para uma aba ainda não implementada."""
    return pn.Column(
        f"## {title}",
        pn.pane.Markdown(f"*{description}*"),
        pn.pane.Markdown("---\n> Conteúdo será preenchido após implementação do motor."),
    )


tab_status_geral = _make_placeholder(
    "📊 Status Geral",
    "Visão consolidada: score final, total de pendências por severidade, "
    "e gráficos de evolução por competência.",
    # TODO: adicionar gráficos Plotly (gauge do score, barras por severidade)
    # TODO: adicionar tabela resumo usando pn.widgets.Tabulator
)

tab_controle_regras = _make_placeholder(
    "📋 Controle por Regras (R082–R111)",
    "Detalhamento regra a regra: status (OK / ERRO / ALERTA), "
    "quantidade de pendências, e drill-down.",
    # TODO: tabela com uma linha por regra, colunas: id, nome, status, count
    # TODO: filtro por dimensão e severidade
)

tab_pendencias = _make_placeholder(
    "⚠ Pendências",
    "Listagem completa de pendências com filtros interativos.",
    # TODO: pn.widgets.Tabulator com df de pendências
    # TODO: filtros: severidade, regra, conta contábil
    # TODO: botão "Exportar Excel"
)

tab_meu_caixa = _make_placeholder(
    "💰 Meu Caixa",
    "Análise de fluxo de caixa e conciliação bancária.",
    # TODO: tabelas e gráficos específicos de caixa
)

tab_passivos = _make_placeholder(
    "📑 Passivos",
    "Análise de passivos financeiros e patrimoniais.",
    # TODO: detalhamento de contas de passivo
)

tab_superavit = _make_placeholder(
    "📈 Superávit",
    "Análise do superávit financeiro.",
    # TODO: cálculo e visualização do superávit
)

tab_auditoria = _make_placeholder(
    "🔍 Auditoria",
    "Log de execuções: quem processou, quando, resultados.",
    # TODO: tabela com Fact_Execucao
    # TODO: filtro por usuário, competência, status
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


# ---------------------------------------------------------------------------
# Layout principal
# ---------------------------------------------------------------------------

template = pn.template.FastListTemplate(
    title=settings.app.title,
    sidebar=[sidebar],
    main=[tabs],
    accent_base_color="#1f77b4",
    header_background="#1f77b4",
)

# Panel serve procura por ``template`` ou objetos servíveis no módulo.
template.servable()
