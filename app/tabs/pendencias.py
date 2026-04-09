"""
app.tabs.pendencias
~~~~~~~~~~~~~~~~~~~

Aba "Pendências" — listagem completa de pendências com filtros.

Funcionalidades:
    - Tabela interativa (DataFrame) com todas as pendências
    - Filtro por severidade (Select)
    - Filtro por regra_id (Select)
    - Botão "Exportar Excel" chama export_issues_excel()
"""

from __future__ import annotations

import logging

import panel as pn

from app.tabs.base import TabBase, register_tab
from ranking_msc.engine.executor import EngineResult
from ranking_msc.outputs.reports import export_issues_excel

logger = logging.getLogger("ranking_msc")


@register_tab
class PendenciasTab(TabBase):
    """Aba com listagem filtrada de todas as pendências."""

    tab_id = "pendencias"
    tab_name = "⚠ Pendências"
    order = 2

    def render(self, result: EngineResult | None) -> pn.viewable.Viewable:
        """Renderiza tabela de pendências com filtros e exportação."""
        if result is None:
            return pn.pane.Markdown(
                "### Nenhum arquivo processado\n\n"
                "*Carregue um arquivo CSV e clique em **▶ Processar** para começar.*"
            )

        df = result.pendencias.copy()

        if df.empty:
            return pn.Column(
                pn.pane.Alert("Nenhuma pendência encontrada.", alert_type="success"),
                sizing_mode="stretch_width",
            )

        # --- Filtros ---
        severidade_opts = ["Todas"] + sorted(df["severidade"].unique().tolist())
        severidade_filter = pn.widgets.Select(
            name="Severidade",
            options=severidade_opts,
            value="Todas",
            width=160,
        )

        regra_opts = ["Todas"] + sorted(df["regra_id"].unique().tolist())
        regra_filter = pn.widgets.Select(
            name="Regra",
            options=regra_opts,
            value="Todas",
            width=160,
        )

        table_pane = pn.pane.DataFrame(
            df,
            sizing_mode="stretch_width",
        )

        def _update_table(event: object) -> None:
            """Aplica filtros na tabela."""
            filtered = df.copy()
            if severidade_filter.value != "Todas":
                filtered = filtered[filtered["severidade"] == severidade_filter.value]
            if regra_filter.value != "Todas":
                filtered = filtered[filtered["regra_id"] == regra_filter.value]
            table_pane.object = filtered

        severidade_filter.param.watch(_update_table, "value")
        regra_filter.param.watch(_update_table, "value")

        # --- Exportar ---
        export_status = pn.pane.Alert("", alert_type="info", visible=False)

        def _export(event: object) -> None:
            """Exporta pendências atuais para Excel."""
            try:
                path = export_issues_excel(
                    df_pendencias=table_pane.object,
                    competencia=result.context.competencia,
                )
                export_status.object = f"✅ Excel exportado: `{path}`"
                export_status.alert_type = "success"
                export_status.visible = True
            except Exception as exc:  # noqa: BLE001
                logger.error("Erro ao exportar Excel: %s", exc, exc_info=True)
                export_status.object = f"❌ Erro ao exportar: {exc}"
                export_status.alert_type = "danger"
                export_status.visible = True

        btn_export = pn.widgets.Button(
            name="📥 Exportar Excel",
            button_type="success",
            width=180,
        )
        btn_export.on_click(_export)

        filters_row = pn.Row(
            severidade_filter,
            regra_filter,
            pn.Column(pn.layout.VSpacer(), btn_export, sizing_mode="fixed"),
        )

        return pn.Column(
            pn.pane.Markdown(f"### {len(df)} pendência(s) encontrada(s)"),
            filters_row,
            export_status,
            pn.layout.Divider(),
            table_pane,
            sizing_mode="stretch_width",
        )
