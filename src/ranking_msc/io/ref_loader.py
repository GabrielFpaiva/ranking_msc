"""
ranking_msc.io.ref_loader
~~~~~~~~~~~~~~~~~~~~~~~~~~

Carregadores de tabelas de referência em ``ref/`` com cache em memória.

Este módulo centraliza o acesso a tabelas oficiais usadas pelas regras:
- ``pcasp.csv``: contas contábeis válidas (PCASP vigente).
- ``dominios_fr.csv``: domínio de Fonte de Recurso (FR) em 4 dígitos.

Regras de implementação:
- Sempre ler com ``dtype=str`` para preservar zeros à esquerda.
- Levantar ``ConfigError`` quando arquivo/colunas estiverem inválidos.
- Reutilizar em memória após a primeira leitura por caminho de referência.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

import pandas as pd

from ranking_msc.exceptions import ConfigError

logger = logging.getLogger("ranking_msc")

_PCASP_FILE_NAME = "pcasp.csv"
_DOMINIOS_FR_FILE_NAME = "dominios_fr.csv"

_REQUIRED_PCASP_COLUMNS = ["conta_contabil"]
_REQUIRED_DOMINIOS_FR_COLUMNS = ["fr", "prefixo_exercicio", "codigo_base"]

_CACHE_PCASP: dict[Path, pd.DataFrame] = {}
_CACHE_DOMINIOS_FR: dict[Path, pd.DataFrame] = {}

_FR_REGEX = re.compile(r"^\d{4}$")


def load_pcasp(ref_dir: str | Path = "ref") -> pd.DataFrame:
    """Carrega tabela PCASP vigente com cache em memória.

    Args:
        ref_dir: diretório de referência contendo ``pcasp.csv``.

    Returns:
        DataFrame com ao menos a coluna ``conta_contabil``.

    Raises:
        ConfigError: se o arquivo estiver ausente/inválido.
    """
    path = _resolve_reference_path(ref_dir, _PCASP_FILE_NAME)
    if path in _CACHE_PCASP:
        return _CACHE_PCASP[path].copy()

    df = _read_reference_csv(path, required_columns=_REQUIRED_PCASP_COLUMNS)
    df["conta_contabil"] = (
        df["conta_contabil"].astype(str).str.strip()
    )
    df = (
        df[df["conta_contabil"] != ""]
        .drop_duplicates(subset=["conta_contabil"])
        .reset_index(drop=True)
    )

    _CACHE_PCASP[path] = df
    logger.info("Tabela PCASP carregada: %s (%d contas).", path, len(df))
    return df.copy()


def load_dominios_fr(ref_dir: str | Path = "ref") -> pd.DataFrame:
    """Carrega domínio de Fonte de Recurso (FR) com cache em memória.

    Args:
        ref_dir: diretório de referência contendo ``dominios_fr.csv``.

    Returns:
        DataFrame com colunas ``fr``, ``prefixo_exercicio`` e ``codigo_base``.

    Raises:
        ConfigError: se o arquivo estiver ausente/inválido.
    """
    path = _resolve_reference_path(ref_dir, _DOMINIOS_FR_FILE_NAME)
    if path in _CACHE_DOMINIOS_FR:
        return _CACHE_DOMINIOS_FR[path].copy()

    df = _read_reference_csv(path, required_columns=_REQUIRED_DOMINIOS_FR_COLUMNS)
    df["fr"] = df["fr"].astype(str).str.strip().str.zfill(4)
    df["prefixo_exercicio"] = df["prefixo_exercicio"].astype(str).str.strip()
    df["codigo_base"] = df["codigo_base"].astype(str).str.strip().str.zfill(3)

    invalid_fr = df[~df["fr"].str.match(_FR_REGEX)]
    if not invalid_fr.empty:
        raise ConfigError(
            f"Arquivo de domínio FR inválido em {path}: coluna 'fr' contém valores inválidos."
        )

    valid_prefixes = {"1", "2", "9"}
    invalid_prefix = df[~df["prefixo_exercicio"].isin(valid_prefixes)]
    if not invalid_prefix.empty:
        raise ConfigError(
            "Arquivo de domínio FR inválido em "
            f"{path}: coluna 'prefixo_exercicio' fora do domínio {sorted(valid_prefixes)}."
        )

    df = (
        df[df["fr"] != ""]
        .drop_duplicates(subset=["fr"])
        .sort_values("fr")
        .reset_index(drop=True)
    )

    _CACHE_DOMINIOS_FR[path] = df
    logger.info("Domínio FR carregado: %s (%d códigos).", path, len(df))
    return df.copy()


def _resolve_reference_path(ref_dir: str | Path, file_name: str) -> Path:
    """Resolve caminho absoluto do arquivo de referência."""
    return Path(ref_dir).expanduser().resolve() / file_name


def _read_reference_csv(path: Path, *, required_columns: list[str]) -> pd.DataFrame:
    """Lê um CSV de referência validando colunas obrigatórias."""
    if not path.exists():
        raise ConfigError(f"Tabela de referência não encontrada: {path}")

    try:
        df = pd.read_csv(path, sep=";", dtype=str, keep_default_na=False)
    except Exception as exc:  # noqa: BLE001
        raise ConfigError(f"Falha ao ler tabela de referência {path}: {exc}") from exc

    missing = sorted(set(required_columns) - set(df.columns))
    if missing:
        raise ConfigError(
            f"Tabela de referência inválida em {path}: colunas ausentes {missing}."
        )
    return df
