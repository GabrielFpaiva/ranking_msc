"""
desktop.bootstrap
~~~~~~~~~~~~~~~~~

Prepara a pasta de dados do usuário antes de a aplicação subir.

A instalação fica em Arquivos de Programas e é somente leitura para quem não
está elevado, então config, snapshots, relatórios e logs moram em
``%LOCALAPPDATA%\\MCRA``. Os caminhos são gravados absolutos: um atalho do
Windows pode iniciar o processo em qualquer diretório de trabalho, e caminho
relativo ali vira pasta de dados em lugar aleatório.

A config pertence ao usuário e só é escrita na primeira execução. A exceção é
``paths.ref_dir``, que aponta para as tabelas de referência de dentro da
instalação e é reescrito a cada arranque, porque muda se a pessoa reinstalar
em outro diretório.
"""

from __future__ import annotations

import logging
import os
import secrets
import shutil
from pathlib import Path
from typing import Any

import yaml

from ranking_msc.exceptions import ConfigError

logger = logging.getLogger("ranking_msc")

_PLACEHOLDER_SECRET = "change-me-in-production"
_SUBDIRS = ("snapshots", "reports", "logs")


def data_home() -> Path:
    """Devolve a pasta de dados do usuário.

    Usa ``%LOCALAPPDATA%`` no Windows. Em macOS e Linux, onde a variável não
    existe, cai em ``~/.local/share`` — o que só acontece em desenvolvimento e
    nos testes, já que o alvo da entrega é Windows.
    """
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base) / "MCRA"
    return Path.home() / ".local" / "share" / "MCRA"


def preparar_config(home: Path, *, root: Path) -> Path:
    """Garante a pasta de dados e a config prontas para uso.

    Args:
        home: pasta de dados do usuário (ver ``data_home()``).
        root: raiz dos recursos embutidos (ver ``app.api.paths.resolve_root()``).

    Returns:
        Caminho do ``settings.yaml`` a usar.

    Raises:
        ConfigError: se o template embutido não existir.
    """
    config_dir = home / "config"
    data_dir = home / "data"
    config_dir.mkdir(parents=True, exist_ok=True)
    for sub in _SUBDIRS:
        (data_dir / sub).mkdir(parents=True, exist_ok=True)

    destino = config_dir / "settings.yaml"
    primeira_execucao = not destino.exists()

    if primeira_execucao:
        template = root / "config" / "settings.desktop.yaml"
        if not template.is_file():
            raise ConfigError(f"Template de configuração ausente no pacote: {template}")
        shutil.copyfile(template, destino)
        logger.info("Config criada a partir do template embutido: %s", destino)

    raw: dict[str, Any] = yaml.safe_load(destino.read_text(encoding="utf-8")) or {}
    security: dict[str, Any] = dict(raw.get("security") or {})
    paths: dict[str, Any] = dict(raw.get("paths") or {})

    if primeira_execucao:
        security["secret_key"] = secrets.token_hex(32)
        paths["data_dir"] = str(data_dir)
        paths["snapshots_dir"] = str(data_dir / "snapshots")
        paths["reports_dir"] = str(data_dir / "reports")
        paths["logs_dir"] = str(data_dir / "logs")

    paths["ref_dir"] = str(root / "ref")

    raw["security"] = security
    raw["paths"] = paths
    destino.write_text(
        yaml.safe_dump(raw, allow_unicode=True, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
    return destino
