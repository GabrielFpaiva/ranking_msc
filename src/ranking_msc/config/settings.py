"""
ranking_msc.config.settings
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Carregamento e validação do arquivo de configuração ``config/settings.yaml``.

Estrutura esperada do YAML (ver config/settings.yaml.example):

    app:
      title: "Ranking MSC"
      debug: false
    paths:
      data_dir: "./data"
      snapshots_dir: "./data/snapshots"
      reports_dir: "./data/reports"
      logs_dir: "./data/logs"
      ref_dir: "./ref"
    rules:
      enabled: ["R082", "R083", ...]     # lista de regras ativas
      fail_fast: false                    # interrompe ao primeiro ERRO?
    security:
      max_concurrent_jobs: 3             # limite de processamentos simultâneos
      allowed_users: []                   # vazio = todos permitidos

Uso:
    from ranking_msc.config.settings import load_settings
    settings = load_settings()            # busca config/settings.yaml
    print(settings.paths.snapshots_dir)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml  # PyYAML — ver pyproject.toml

from ranking_msc.exceptions import ConfigError

# Caminho default (relativo à raiz do repositório)
_DEFAULT_CONFIG_PATH = Path("config/settings.yaml")


# ---------------------------------------------------------------------------
# Dataclasses de configuração
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AppSettings:
    """Configurações gerais da aplicação."""
    title: str = "Ranking MSC"
    debug: bool = False


@dataclass(frozen=True)
class PathsSettings:
    """Caminhos de diretórios do projeto."""
    data_dir: str = "./data"
    snapshots_dir: str = "./data/snapshots"
    reports_dir: str = "./data/reports"
    logs_dir: str = "./data/logs"
    ref_dir: str = "./ref"

    def ensure_dirs(self) -> None:
        """Cria diretórios se não existirem."""
        for dir_path in (
            self.data_dir, self.snapshots_dir,
            self.reports_dir, self.logs_dir, self.ref_dir,
        ):
            Path(dir_path).mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class RulesSettings:
    """Configuração das regras de validação."""
    enabled: list[str] = field(default_factory=list)
    fail_fast: bool = False


@dataclass(frozen=True)
class SecuritySettings:
    """Configuração de segurança e concorrência.

    # TODO (multiusuário): quando o servidor rodar com múltiplos
    # usuários simultâneos, usar ``max_concurrent_jobs`` para limitar
    # processamentos paralelos via semáforo ou fila.
    """
    max_concurrent_jobs: int = 3
    allowed_users: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Settings:
    """Configuração consolidada do projeto."""
    app: AppSettings = field(default_factory=AppSettings)
    paths: PathsSettings = field(default_factory=PathsSettings)
    rules: RulesSettings = field(default_factory=RulesSettings)
    security: SecuritySettings = field(default_factory=SecuritySettings)


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def _parse_section(raw: dict[str, Any], cls: type, section: str) -> Any:
    """Instancia uma dataclass a partir de um dict, filtrando campos válidos."""
    valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
    filtered = {k: v for k, v in raw.items() if k in valid_fields}
    unknown = set(raw) - valid_fields
    if unknown:
        # Avisa, mas não impede — facilita evolução do YAML
        import warnings
        warnings.warn(
            f"Chaves desconhecidas em '{section}': {unknown}",
            stacklevel=3,
        )
    return cls(**filtered)


def load_settings(path: Path | str | None = None) -> Settings:
    """Carrega e valida configurações do YAML.

    Args:
        path: caminho até o settings.yaml. Se ``None``, usa variável de
              ambiente ``RANKING_MSC_CONFIG`` ou o default ``config/settings.yaml``.

    Returns:
        Instância imutável de ``Settings``.

    Raises:
        ConfigError: se o arquivo não existir ou for inválido.
    """
    if path is None:
        path = Path(os.environ.get("RANKING_MSC_CONFIG", _DEFAULT_CONFIG_PATH))
    else:
        path = Path(path)

    if not path.exists():
        raise ConfigError(
            f"Arquivo de configuração não encontrado: {path.resolve()}. "
            "Copie config/settings.yaml.example → config/settings.yaml e ajuste."
        )

    try:
        raw: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"YAML inválido em {path}: {exc}") from exc

    return Settings(
        app=_parse_section(raw.get("app", {}), AppSettings, "app"),
        paths=_parse_section(raw.get("paths", {}), PathsSettings, "paths"),
        rules=_parse_section(raw.get("rules", {}), RulesSettings, "rules"),
        security=_parse_section(raw.get("security", {}), SecuritySettings, "security"),
    )
