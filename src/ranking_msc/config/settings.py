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
      secret_key: "gere-com-openssl-rand-hex-32"
      algorithm: "HS256"
      access_token_expire_minutes: 480
      users:
        - username: "admin"
          hashed_password: "$2b$12$..."  # passlib.hash.bcrypt.hash("senha")

Uso:
    from ranking_msc.config.settings import load_settings
    settings = load_settings()            # busca config/settings.yaml
    print(settings.paths.snapshots_dir)
"""

from __future__ import annotations

import dataclasses
import os
import warnings
from dataclasses import dataclass, field, fields
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
    esfera: str = "municipal"  # esfera do ente: "municipal", "estadual" ou "federal"


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
class UserSettings:
    """Credenciais de um usuário cadastrado no sistema."""
    username: str
    hashed_password: str


@dataclass(frozen=True)
class SecuritySettings:
    """Configuração de segurança, autenticação JWT e concorrência."""
    max_concurrent_jobs: int = 3
    secret_key: str = "change-me-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 480  # 8 horas
    users: list[UserSettings] = field(default_factory=list)


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

def _parse_section(raw: dict[str, Any], cls: type[Any], section: str) -> Any:
    """Instancia uma dataclass a partir de um dict, filtrando campos válidos."""
    valid_fields = {f.name for f in fields(cls)}
    filtered = {k: v for k, v in raw.items() if k in valid_fields}
    unknown = set(raw) - valid_fields
    if unknown:
        warnings.warn(
            f"Chaves desconhecidas em '{section}': {unknown}",
            stacklevel=3,
        )
    return cls(**filtered)


def _parse_users(users_raw: list[Any]) -> list[UserSettings]:
    """Converte lista de dicts YAML em lista de UserSettings.

    Raises:
        ConfigError: se alguma entrada em security.users estiver mal-formada
            (ausência de 'username' ou 'hashed_password'). Falha explícita
            evita que um typo no YAML remova usuários silenciosamente, tornando
            todo login indiagnosticável.
    """
    result = []
    for index, u in enumerate(users_raw or []):
        if not isinstance(u, dict):
            raise ConfigError(
                f"security.users[{index}]: esperado dict, encontrado {type(u).__name__}."
            )
        missing = [k for k in ("username", "hashed_password") if k not in u]
        if missing:
            raise ConfigError(
                f"security.users[{index}]: campos obrigatórios ausentes: {missing}. "
                "Verifique o settings.yaml."
            )
        result.append(
            UserSettings(username=u["username"], hashed_password=u["hashed_password"])
        )
    return result


_INSECURE_SECRETS = {"", "change-me-in-production"}


def _validate_security(security: SecuritySettings) -> None:
    """Valida secret_key; falha com ConfigError se usuários estiverem configurados.

    Quando ``security.users`` está preenchido (auth JWT ativo), uma chave padrão
    conhecida é perigosa — qualquer pessoa que conheça o valor pode forjar tokens.
    Nesse caso levanta ConfigError para impedir inicialização em estado inseguro.

    Se não há usuários configurados (modo dev/test), emite apenas um aviso.
    """
    if security.secret_key in _INSECURE_SECRETS:
        msg = (
            "security.secret_key está com valor padrão inseguro. "
            "Gere uma chave com: openssl rand -hex 32"
        )
        if security.users:
            raise ConfigError(msg)
        warnings.warn(msg, stacklevel=4)


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

    # SecuritySettings requer tratamento especial: "users" é lista de objetos aninhados.
    raw_security = dict(raw.get("security", {}))
    users_raw = raw_security.pop("users", [])
    security = _parse_section(raw_security, SecuritySettings, "security")
    users = _parse_users(users_raw)
    security = dataclasses.replace(security, users=users)

    _validate_security(security)

    return Settings(
        app=_parse_section(raw.get("app", {}), AppSettings, "app"),
        paths=_parse_section(raw.get("paths", {}), PathsSettings, "paths"),
        rules=_parse_section(raw.get("rules", {}), RulesSettings, "rules"),
        security=security,
    )
