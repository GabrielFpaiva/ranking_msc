"""
app.api.deps
~~~~~~~~~~~~

Dependências compartilhadas entre rotas: settings carregado, logger configurado,
e paths absolutos do projeto.

Carrega ``ranking_msc.rules`` por side-effect na importação para popular
RULE_REGISTRY antes que qualquer rota tente listar regras.
"""

from __future__ import annotations

import logging
import sys
from functools import lru_cache
from pathlib import Path

# Adicionar src/ ao path antes de importar ranking_msc — espelha o que web_app.py faz.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "src"))

import ranking_msc.rules  # noqa: E402, F401  -- popular RULE_REGISTRY
from ranking_msc.config.settings import Settings, load_settings  # noqa: E402
from ranking_msc.outputs.logs import setup_logging  # noqa: E402

PROJECT_ROOT: Path = _PROJECT_ROOT


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Carrega o ``settings.yaml`` (ou retorna defaults)."""
    config_path = PROJECT_ROOT / "config" / "settings.yaml"
    return load_settings(config_path)


@lru_cache(maxsize=1)
def get_logger() -> logging.Logger:
    """Configura e retorna o logger padrão do ranking_msc."""
    settings = get_settings()
    return setup_logging(log_dir=PROJECT_ROOT / settings.paths.logs_dir)


def absolute_snapshots_dir() -> Path:
    """Retorna o diretório de snapshots resolvido absolutamente."""
    settings = get_settings()
    return (PROJECT_ROOT / settings.paths.snapshots_dir).resolve()


def absolute_reports_dir() -> Path:
    """Retorna o diretório de relatórios Excel resolvido absolutamente."""
    settings = get_settings()
    return (PROJECT_ROOT / settings.paths.reports_dir).resolve()
