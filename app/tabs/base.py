"""
app.tabs.base
~~~~~~~~~~~~~

Base para o sistema de abas do dashboard.

Padrão Tab Registry: espelha o RULE_REGISTRY das regras.
Para registrar nova aba: criar arquivo em app/tabs/, decorar a classe
com @register_tab, e importar o módulo em app/tabs/__init__.py.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import panel as pn

from ranking_msc.engine.executor import EngineResult

# Registry global: tab_id → instância de TabBase
TAB_REGISTRY: dict[str, TabBase] = {}


def register_tab(cls: type[TabBase]) -> type[TabBase]:
    """Decorator que instancia a aba e a registra no TAB_REGISTRY.

    Uso:
        @register_tab
        class StatusGeralTab(TabBase):
            tab_id = "status_geral"
            ...
    """
    instance = cls()
    if not getattr(instance, "tab_id", ""):
        raise ValueError(f"Tab {cls.__name__} precisa definir 'tab_id'.")
    TAB_REGISTRY[instance.tab_id] = instance
    return cls


class TabBase(ABC):
    """Classe base para todas as abas do dashboard.

    Para criar nova aba:
        1. Criar arquivo `app/tabs/<nome>.py`
        2. Definir classe com @register_tab herdando TabBase
        3. Preencher tab_id, tab_name, order
        4. Implementar render()
        5. Importar em app/tabs/__init__.py
    """

    tab_id: str = ""    # identificador único, ex: "status_geral"
    tab_name: str = ""  # label exibido na UI, ex: "Status Geral"
    order: int = -1     # posição na barra de abas (menor = mais à esquerda)

    @abstractmethod
    def render(self, result: EngineResult | None) -> pn.viewable.Viewable:
        """Renderiza o conteúdo da aba.

        Args:
            result: resultado do motor. None quando nenhum CSV foi processado.

        Returns:
            Objeto Panel renderizável (Column, Row, Tabs, etc.).
        """
