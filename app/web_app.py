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

import io
import sys
from pathlib import Path

import panel as pn

# --- Ajuste de path para importar o pacote src/ ---
# Em produção, prefira instalar o pacote via pip install -e .
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "src"))

import ranking_msc.rules  # noqa: E402, F401  # popula RULE_REGISTRY via @register_rule
from ranking_msc.config.settings import load_settings  # noqa: E402
from ranking_msc.engine.executor import EngineContext, run_engine  # noqa: E402
from ranking_msc.io.reader_msc import read_msc_csv  # noqa: E402
from ranking_msc.outputs.logs import setup_logging  # noqa: E402
from ranking_msc.transform.ic_normalize import normalize_ic  # noqa: E402

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


_ENGINE_STATUS_TO_ALERT: dict[str, str] = {
    "OK": "success",
    "PARCIAL": "warning",
    "ERRO": "danger",
}


def _on_processar(event: object) -> None:
    """Callback do botão Processar.

    Fluxo:
        1. Valida que um arquivo foi selecionado.
        2. Lê o CSV via read_msc_csv() → RawMSC.
        3. Normaliza IC/TIPO via normalize_ic().
        4. Monta EngineContext e executa run_engine().
        5. Mapeia result.status → alert_type do banner (OK/PARCIAL/ERRO).
           O banner reflete falhas do motor (regras com erro) mesmo quando
           nenhuma pendência com severidade ERRO foi produzida.
    """
    if not file_upload.value:  # cobre None e b"" (arquivo desmarcado no widget)
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

    # Mapeia result.status → alert. Desta forma, falhas de execução de regras
    # (result.status == "PARCIAL" ou "ERRO") sempre chegam ao usuário como
    # warning/danger — independente de quantas pendências foram geradas.
    alert_type = _ENGINE_STATUS_TO_ALERT.get(result.status, "warning")

    if result.status == "OK":
        msg = (
            f"✅ Processado: {raw.competencia} — {raw.siconfi}. "
            f"{result.total_pendencias} pendência(s), "
            f"{result.regras_executadas} regra(s) executada(s)."
        )
    elif result.status == "PARCIAL":
        msg = (
            f"⚠ Processamento parcial: {result.regras_com_erro} regra(s) com erro, "
            f"{result.regras_executadas} executada(s). "
            f"{result.total_pendencias} pendência(s) gerada(s). "
            "Verifique o log de auditoria."
        )
    else:  # ERRO
        msg = (
            f"❌ Falha no motor: {result.regras_com_erro} regra(s) com erro fatal. "
            f"{result.total_pendencias} pendência(s) gerada(s) antes da falha. "
            "Verifique o log de auditoria."
        )

    status_indicator.object = msg
    status_indicator.alert_type = alert_type
    logger.info(
        "Execução concluída: status=%s, regras=%d, erros=%d, pendencias=%d",
        result.status, result.regras_executadas, result.regras_com_erro, result.total_pendencias,
        extra={"execucao_id": context.execucao_id, "competencia": raw.competencia},
    )


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
