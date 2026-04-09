"""
app.tabs.status_geral
~~~~~~~~~~~~~~~~~~~~~

Aba "Status Geral" — visão consolidada de uma execução.

Exibe:
    - 3 cards de métricas: total de ERROs, ALERTAs e INFOs
    - Tabela resumo por dimensão × severidade
    - Identificação da competência e ente processado
"""

from __future__ import annotations

import logging

import pandas as pd
import panel as pn

from app.tabs.base import TabBase, register_tab
from ranking_msc.engine.executor import EngineResult

logger = logging.getLogger("ranking_msc")


@register_tab
class StatusGeralTab(TabBase):
    """Aba de visão consolidada do resultado do motor."""

    tab_id = "status_geral"
    tab_name = "📊 Status Geral"
    order = 1

    def render(self, result: EngineResult | None) -> pn.viewable.Viewable:
        """Renderiza métricas gerais e resumo por dimensão."""
        if result is None:
            return pn.pane.Markdown(
                "### Nenhum arquivo processado\n\n"
                "*Carregue um arquivo CSV e clique em **▶ Processar** para começar.*"
            )

        df = result.pendencias

        erros = int((df["severidade"] == "ERRO").sum()) if not df.empty else 0
        alertas = int((df["severidade"] == "ALERTA").sum()) if not df.empty else 0
        infos = int((df["severidade"] == "INFO").sum()) if not df.empty else 0

        card_erros = pn.indicators.Number(
            value=erros,
            name="ERROs",
            default_color="red",
            font_size="32pt",
            title_size="14pt",
            width=200,
        )
        card_alertas = pn.indicators.Number(
            value=alertas,
            name="ALERTAs",
            default_color="darkorange",
            font_size="32pt",
            title_size="14pt",
            width=200,
        )
        card_infos = pn.indicators.Number(
            value=infos,
            name="INFOs",
            default_color="gray",
            font_size="32pt",
            title_size="14pt",
            width=200,
        )

        cards_row = pn.Row(card_erros, card_alertas, card_infos)

        if df.empty:
            resumo = pd.DataFrame({"dimensao": [], "ERRO": [], "ALERTA": [], "INFO": []})
        else:
            pivot = (
                df.groupby(["dimensao", "severidade"])
                .size()
                .unstack(fill_value=0)
                .reset_index()
            )
            for col in ["ERRO", "ALERTA", "INFO"]:
                if col not in pivot.columns:
                    pivot[col] = 0
            known = ("dimensao", "ERRO", "ALERTA", "INFO")
            unexpected = [c for c in pivot.columns if c not in known]
            if unexpected:
                logger.warning("Severidades inesperadas no pivot (serão ignoradas): %s", unexpected)
            resumo = pivot[
                ["dimensao"] + [c for c in ["ERRO", "ALERTA", "INFO"] if c in pivot.columns]
            ]

        tabulator = pn.pane.DataFrame(
            resumo,
            index=False,
            sizing_mode="stretch_width",
        )

        status_color = {"OK": "green", "PARCIAL": "orange", "ERRO": "red"}.get(
            result.status, "gray"
        )

        return pn.Column(
            pn.pane.Markdown(
                f"## Competência: `{result.context.competencia}` | "
                f"Ente: `{result.context.siconfi}` | "
                f"Status: <span style='color:{status_color};font-weight:bold'>"
                f"{result.status}</span>",
                sizing_mode="stretch_width",
            ),
            cards_row,
            pn.layout.Divider(),
            pn.pane.Markdown("### Resumo por Dimensão"),
            tabulator,
            sizing_mode="stretch_width",
        )
