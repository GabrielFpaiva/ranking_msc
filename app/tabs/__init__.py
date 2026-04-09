"""
app.tabs
~~~~~~~~

Importa todos os módulos de abas, disparando o auto-registro no TAB_REGISTRY.
Para adicionar nova aba: criar o arquivo e adicionar o import aqui.
"""

from app.tabs.base import TAB_REGISTRY, TabBase, register_tab  # noqa: F401
from app.tabs.pendencias import PendenciasTab  # noqa: F401
from app.tabs.status_geral import StatusGeralTab  # noqa: F401

# from app.tabs.saldo_devedor import SaldoDevedorTab  # noqa: F401
