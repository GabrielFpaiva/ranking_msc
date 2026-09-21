"""
desktop.bootstrap
~~~~~~~~~~~~~~~~~

Prepara a pasta de dados do usuário antes de a aplicação subir.

A instalação fica em Arquivos de Programas e é somente leitura para quem não
está elevado, então config, snapshots, relatórios e logs moram em
``%LOCALAPPDATA%\\MCRA``. Os caminhos são gravados absolutos: um atalho do
Windows pode iniciar o processo em qualquer diretório de trabalho, e caminho
relativo ali vira pasta de dados em lugar aleatório.

A config pertence ao usuário: usuários acrescentados, regras desligadas e o
``secret_key`` sorteado sobrevivem aos arranques. O bootstrap só corrige o que
deixaria o aplicativo inutilizável e só regrava o arquivo se algo mudou:

- ``paths.ref_dir`` aponta para as tabelas de referência de dentro da
  instalação e é reescrito a cada arranque, porque muda se a pessoa reinstalar
  em outro diretório;
- ``secret_key`` vazio ou no placeholder é sorteado (cobre a queda no meio da
  primeira execução, que deixaria o template intacto no lugar);
- caminhos de dados relativos são reabsolutizados para dentro de ``home/data``;
- arquivo vazio, ilegível ou sem ``security.users`` (YAML truncado) é recriado
  a partir do template, preservando o ``secret_key`` válido que houver. O
  conteúdo anterior, se não vazio, fica em ``settings.yaml.bak``.

A gravação é atômica (arquivo temporário no mesmo diretório + ``os.replace``):
uma queda no meio deixa o arquivo antigo ou o novo, nunca um truncado.
"""

from __future__ import annotations

import copy
import logging
import os
import secrets
import tempfile
from pathlib import Path
from typing import Any

import yaml

from ranking_msc.config.settings import _INSECURE_SECRETS
from ranking_msc.exceptions import ConfigError

logger = logging.getLogger("ranking_msc")

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


def _ler_yaml(texto: str) -> dict[str, Any] | None:
    """Interpreta o YAML da config; devolve None se ilegível ou se não for mapeamento."""
    try:
        raw = yaml.safe_load(texto)
    except yaml.YAMLError:
        return None
    return raw if isinstance(raw, dict) else None


def _secret_valido(raw: dict[str, Any] | None) -> str | None:
    """Devolve o ``secret_key`` de ``raw`` se for utilizável, senão None."""
    if raw is None or not isinstance(raw.get("security"), dict):
        return None
    secret = raw["security"].get("secret_key")
    if isinstance(secret, str) and secret not in _INSECURE_SECRETS:
        return secret
    return None


def _tem_usuarios(raw: dict[str, Any] | None) -> bool:
    """Diz se ``raw`` tem ao menos um usuário em ``security.users``."""
    if raw is None or not isinstance(raw.get("security"), dict):
        return False
    users = raw["security"].get("users")
    return isinstance(users, list) and len(users) > 0


def _gravar_atomico(destino: Path, conteudo: str) -> None:
    """Grava ``conteudo`` em ``destino`` via temporário no mesmo diretório + ``os.replace``."""
    fd, tmp_nome = tempfile.mkstemp(dir=destino.parent, prefix=".settings-", suffix=".tmp")
    tmp = Path(tmp_nome)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as arquivo:
            arquivo.write(conteudo)
            arquivo.flush()
            os.fsync(arquivo.fileno())
        os.replace(tmp, destino)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def preparar_config(home: Path, *, root: Path) -> Path:
    """Garante a pasta de dados e a config prontas para uso.

    Args:
        home: pasta de dados do usuário (ver ``data_home()``).
        root: raiz dos recursos embutidos (ver ``app.api.paths.resolve_root()``).

    Returns:
        Caminho do ``settings.yaml`` a usar.

    Raises:
        ConfigError: se a config precisar ser (re)criada e o template embutido
            não existir.
    """
    config_dir = home / "config"
    data_dir = home / "data"
    config_dir.mkdir(parents=True, exist_ok=True)
    for sub in _SUBDIRS:
        (data_dir / sub).mkdir(parents=True, exist_ok=True)

    destino = config_dir / "settings.yaml"
    texto_atual = destino.read_text(encoding="utf-8") if destino.exists() else None
    atual = _ler_yaml(texto_atual) if texto_atual is not None else None

    if atual is not None and _tem_usuarios(atual):
        raw = atual
        original: dict[str, Any] | None = copy.deepcopy(atual)
    else:
        template = root / "config" / "settings.desktop.yaml"
        if not template.is_file():
            raise ConfigError(f"Template de configuração ausente no pacote: {template}")
        raw = _ler_yaml(template.read_text(encoding="utf-8")) or {}
        secret_anterior = _secret_valido(atual)
        if secret_anterior is not None:
            raw.setdefault("security", {})["secret_key"] = secret_anterior
        if texto_atual is None:
            logger.info("Config criada a partir do template embutido: %s", destino)
        else:
            if texto_atual.strip():
                backup = destino.with_name(destino.name + ".bak")
                _gravar_atomico(backup, texto_atual)
                logger.warning("Conteúdo anterior da config guardado em %s", backup)
            logger.warning(
                "Config vazia, ilegível ou sem usuários em %s; recriada a partir do template.",
                destino,
            )
        original = None

    security: dict[str, Any] = dict(raw.get("security") or {})
    paths: dict[str, Any] = dict(raw.get("paths") or {})

    if _secret_valido({"security": security}) is None:
        security["secret_key"] = secrets.token_hex(32)
        logger.info("secret_key sorteado para %s", destino)

    padroes = {
        "data_dir": data_dir,
        "snapshots_dir": data_dir / "snapshots",
        "reports_dir": data_dir / "reports",
        "logs_dir": data_dir / "logs",
    }
    for chave, padrao in padroes.items():
        valor = paths.get(chave)
        if not isinstance(valor, str) or not valor or not Path(valor).is_absolute():
            paths[chave] = str(padrao)

    paths["ref_dir"] = str(root / "ref")

    raw["security"] = security
    raw["paths"] = paths
    if raw != original:
        _gravar_atomico(
            destino,
            yaml.safe_dump(raw, allow_unicode=True, sort_keys=False, default_flow_style=False),
        )
    return destino
