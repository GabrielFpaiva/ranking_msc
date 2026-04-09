"""
app.tabs.saldo_devedor
~~~~~~~~~~~~~~~~~~~~~~

Aba "Saldo Devedor" — contas com natureza de saldo incompatível (R032).

Filtra pendências da regra R032 do EngineResult e exibe em tabela
com row coloring: ERRO → vermelho, ALERTA → amarelo.

Entrega tangível da Fase 3 acordada com Rodrigo Teixeira (2026-03-30).
"""

from __future__ import annotations

import logging

import pandas as pd
import panel as pn

from app.tabs.base import TabBase, register_tab
from ranking_msc.engine.executor import EngineResult
from ranking_msc.schemas import FACT_RESULTADO_REGRAS_COLUMNS

logger = logging.getLogger("ranking_msc")

_SALDO_DEVEDOR_RULE_ID = "R032"

_COLS_DISPLAY = [
    "conta_contabil",
    "valor_esperado",
    "valor_encontrado",
    "descricao",
    "severidade",
]
_COL_LABELS = {
    "conta_contabil": "Conta Contábil",
    "valor_esperado": "Natureza Esperada",
    "valor_encontrado": "Saldo Encontrado",
    "descricao": "Descrição",
    "severidade": "Severidade",
}


def _severity_row_style(row: pd.Series) -> list[str]:
    """Retorna estilo CSS por linha com base na severidade."""
    mapping = {
        "ERRO": "background-color: #ffe0e0",
        "ALERTA": "background-color: #fff3cd",
    }
    style = mapping.get(str(row.get("Severidade", "")), "")
    return [style] * len(row)


@register_tab
class SaldoDevedorTab(TabBase):
    """Aba com contas de natureza de saldo incompatível — regra R032."""

    tab_id = "saldo_devedor"
    tab_name = "🔴 Saldo Devedor"
    order = 3

    def render(self, result: EngineResult | None) -> pn.viewable.Viewable:
        """Renderiza tabela de contas com saldo incompatível (R032)."""
        if result is None:
            return pn.pane.Markdown(
                "### Nenhum arquivo processado\n\n"
                "*Carregue um arquivo CSV e clique em **▶ Processar** para começar.*"
            )

        df = result.pendencias
        r032 = (
            df[df["regra_id"] == _SALDO_DEVEDOR_RULE_ID].copy()
            if not df.empty
            else pd.DataFrame(columns=FACT_RESULTADO_REGRAS_COLUMNS)
        )

        if r032.empty:
            return pn.Column(
                pn.pane.Alert(
                    "✅ Nenhuma incompatibilidade de natureza de saldo encontrada.",
                    alert_type="success",
                ),
                sizing_mode="stretch_width",
            )

        view = r032[_COLS_DISPLAY].copy()
        view = view.rename(columns=_COL_LABELS)

        # Try styled rendering; fall back to plain if pn.pane.DataFrame rejects Styler
        try:
            styled = view.style.apply(_severity_row_style, axis=1)
            table = pn.pane.DataFrame(styled, sizing_mode="stretch_width")
        except Exception:  # noqa: BLE001
            logger.warning("Row coloring não disponível; exibindo tabela sem estilos.")
            table = pn.pane.DataFrame(view, sizing_mode="stretch_width")

        return pn.Column(
            pn.pane.Markdown(
                f"### 🔴 {len(r032)} conta(s) com natureza de saldo incompatível"
            ),
            pn.pane.Markdown(
                "*Contas credoras com saldo devedor ou devedoras com saldo credor, "
                "conforme regra R032 do PCASP.*"
            ),
            table,
            sizing_mode="stretch_width",
        )
