"""
app.api.paths
~~~~~~~~~~~~~

Raiz dos recursos empacotados (``web/dist``, ``ref/``, templates de config).

Fora do PyInstaller a raiz é a pasta do repositório. Dentro do executável
congelado, os dados embutidos ficam no diretório temporário de extração
apontado por ``sys._MEIPASS`` — derivar a raiz de ``__file__`` ali devolve um
caminho que não contém nenhum dado embutido.

Este módulo é o único lugar do projeto que sabe dessa diferença.
"""

from __future__ import annotations

import sys
from pathlib import Path


def is_frozen() -> bool:
    """Indica se o processo roda dentro de um bundle PyInstaller."""
    return bool(getattr(sys, "frozen", False)) and hasattr(sys, "_MEIPASS")


def resolve_root() -> Path:
    """Devolve a raiz dos recursos embutidos.

    Returns:
        ``sys._MEIPASS`` quando congelado; a raiz do repositório caso
        contrário (dois níveis acima de ``app/api/``).
    """
    if is_frozen():
        return Path(str(sys._MEIPASS))  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent.parent.parent
