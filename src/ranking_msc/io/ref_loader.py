"""
ranking_msc.io.ref_loader
~~~~~~~~~~~~~~~~~~~~~~~~~~

Carregadores de tabelas de referência em ``ref/`` com cache em memória.

Este módulo centraliza o acesso a tabelas oficiais usadas pelas regras:
- ``pcasp.csv``: contas contábeis válidas (PCASP vigente).
- ``dominios_fr.csv``: domínio de Fonte de Recurso (FR) em 4 dígitos.
- ``tabela_po.csv``: códigos de Poder/Órgão (PO) em 5 dígitos.
- ``tabela_co.csv``: códigos de Acompanhamento da Execução Orçamentária (CO) em 4 dígitos.
- ``tabela_nr.csv``: códigos de Natureza da Receita (NR) em 8 dígitos.
- ``tabela_nd.csv``: códigos de Natureza da Despesa (ND) em 8 dígitos.
- ``tabela_fs.csv``: classificação funcional Função/Subfunção (FS).

Constantes:
- ``IC_MAP``: mapeamento ID_IC → lista de tipos de IC obrigatórios.
- ``IC_DIGITOS``: mapeamento tipo de IC → quantidade de dígitos esperada.
- ``FP_DOMAIN``: domínio de valores válidos para FP (Financeiro/Permanente).

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

# ---------------------------------------------------------------------------
# Constantes de mapeamento IC
# ---------------------------------------------------------------------------

IC_MAP: dict[int, list[str]] = {
    0: [],
    1: ["PO"],
    2: ["PO", "FP"],
    3: ["PO", "FP", "DC"],
    4: ["PO", "FP", "FR", "CO"],
    5: ["PO", "FR", "CO"],
    6: ["PO", "FR", "CO", "NR"],
    7: ["PO", "FS", "FR", "CO", "ND"],
    8: ["PO", "FP", "DC", "FR"],
    9: ["PO", "FS", "FR", "CO", "ND", "AI"],
}

IC_DIGITOS: dict[str, int] = {
    "PO": 5,
    "FP": 1,
    "DC": 1,
    "FR": 4,
    "CO": 4,
    "NR": 8,
    "ND": 8,
    "FS": 5,
    "AI": 4,
}

FP_DOMAIN: frozenset[str] = frozenset({"1", "2"})

# ---------------------------------------------------------------------------
# Nomes de arquivo e colunas obrigatórias
# ---------------------------------------------------------------------------

_PCASP_FILE_NAME = "pcasp.csv"
_DOMINIOS_FR_FILE_NAME = "dominios_fr.csv"
_TABELA_PO_FILE_NAME = "tabela_po.csv"
_TABELA_CO_FILE_NAME = "tabela_co.csv"
_TABELA_NR_FILE_NAME = "tabela_nr.csv"
_TABELA_ND_FILE_NAME = "tabela_nd.csv"
_TABELA_FR_FILE_NAME = "tabela_fr.csv"
_TABELA_FS_FILE_NAME = "tabela_fs.csv"

_REQUIRED_PCASP_COLUMNS = ["conta_contabil"]
_REQUIRED_DOMINIOS_FR_COLUMNS = ["fr", "prefixo_exercicio", "codigo_base"]
_REQUIRED_PO_COLUMNS = ["codigo"]
_REQUIRED_CO_COLUMNS = ["codigo"]
_REQUIRED_NR_COLUMNS = ["codigo", "valorizavel"]
_REQUIRED_ND_COLUMNS = ["codigo", "nivel", "nome"]
_REQUIRED_FR_COLUMNS = ["codigo_base", "nome"]
_REQUIRED_FS_COLUMNS = ["funcao", "subfuncao"]

# ---------------------------------------------------------------------------
# Caches por caminho absoluto
# ---------------------------------------------------------------------------

_CACHE_PCASP: dict[Path, pd.DataFrame] = {}
_CACHE_DOMINIOS_FR: dict[Path, pd.DataFrame] = {}
_CACHE_PO: dict[Path, pd.DataFrame] = {}
_CACHE_CO: dict[Path, pd.DataFrame] = {}
_CACHE_NR: dict[Path, pd.DataFrame] = {}
_CACHE_ND: dict[Path, pd.DataFrame] = {}
_CACHE_FR: dict[Path, pd.DataFrame] = {}
_CACHE_FS: dict[Path, pd.DataFrame] = {}

_FR_REGEX = re.compile(r"^\d{4}$")


# ---------------------------------------------------------------------------
# Funções públicas de carregamento
# ---------------------------------------------------------------------------


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


def load_tabela_po(ref_dir: str | Path = "ref") -> pd.DataFrame:
    """Carrega tabela de Poder/Órgão (PO) com cache em memória.

    Args:
        ref_dir: diretório de referência contendo ``tabela_po.csv``.

    Returns:
        DataFrame com coluna ``codigo`` (5 dígitos).

    Raises:
        ConfigError: se o arquivo estiver ausente/inválido.
    """
    path = _resolve_reference_path(ref_dir, _TABELA_PO_FILE_NAME)
    if path in _CACHE_PO:
        return _CACHE_PO[path].copy()

    df = _read_reference_csv(path, required_columns=_REQUIRED_PO_COLUMNS)
    df["codigo"] = df["codigo"].astype(str).str.strip().str.zfill(5)
    df = (
        df[df["codigo"] != ""]
        .drop_duplicates(subset=["codigo"])
        .sort_values("codigo")
        .reset_index(drop=True)
    )

    _CACHE_PO[path] = df
    logger.info("Tabela PO carregada: %s (%d códigos).", path, len(df))
    return df.copy()


def load_tabela_co(ref_dir: str | Path = "ref") -> pd.DataFrame:
    """Carrega tabela de Acompanhamento da Execução Orçamentária (CO) com cache.

    Args:
        ref_dir: diretório de referência contendo ``tabela_co.csv``.

    Returns:
        DataFrame com coluna ``codigo`` (4 dígitos).

    Raises:
        ConfigError: se o arquivo estiver ausente/inválido.
    """
    path = _resolve_reference_path(ref_dir, _TABELA_CO_FILE_NAME)
    if path in _CACHE_CO:
        return _CACHE_CO[path].copy()

    df = _read_reference_csv(path, required_columns=_REQUIRED_CO_COLUMNS)
    df["codigo"] = df["codigo"].astype(str).str.strip().str.zfill(4)
    df = (
        df[df["codigo"] != ""]
        .drop_duplicates(subset=["codigo"])
        .sort_values("codigo")
        .reset_index(drop=True)
    )

    _CACHE_CO[path] = df
    logger.info("Tabela CO carregada: %s (%d códigos).", path, len(df))
    return df.copy()


def load_tabela_fr(ref_dir: str | Path = "ref") -> pd.DataFrame:
    """Carrega tabela de códigos-raiz de Fonte de Recurso (FR) com cache.

    Diferente de ``load_dominios_fr`` (que tem FR expandido com prefixo de exercício),
    esta tabela contém os códigos-raiz de 3 dígitos e suas nomenclaturas.

    Args:
        ref_dir: diretório de referência contendo ``tabela_fr.csv``.

    Returns:
        DataFrame com colunas ``codigo_base`` (3 dígitos) e ``nome``.

    Raises:
        ConfigError: se o arquivo estiver ausente/inválido.
    """
    path = _resolve_reference_path(ref_dir, _TABELA_FR_FILE_NAME)
    if path in _CACHE_FR:
        return _CACHE_FR[path].copy()

    df = _read_reference_csv(path, required_columns=_REQUIRED_FR_COLUMNS)
    df["codigo_base"] = df["codigo_base"].astype(str).str.strip().str.zfill(3)
    df["nome"] = df["nome"].astype(str).str.strip()
    df = (
        df[df["codigo_base"] != ""]
        .drop_duplicates(subset=["codigo_base"])
        .sort_values("codigo_base")
        .reset_index(drop=True)
    )

    _CACHE_FR[path] = df
    logger.info("Tabela FR carregada: %s (%d códigos-raiz).", path, len(df))
    return df.copy()


def load_tabela_nr(ref_dir: str | Path = "ref") -> pd.DataFrame:
    """Carrega tabela de Natureza da Receita (NR) com cache em memória.

    Args:
        ref_dir: diretório de referência contendo ``tabela_nr.csv``.

    Returns:
        DataFrame com colunas ``codigo`` (8 dígitos) e ``valorizavel`` (SIM/NÃO).

    Raises:
        ConfigError: se o arquivo estiver ausente/inválido.
    """
    path = _resolve_reference_path(ref_dir, _TABELA_NR_FILE_NAME)
    if path in _CACHE_NR:
        return _CACHE_NR[path].copy()

    df = _read_reference_csv(path, required_columns=_REQUIRED_NR_COLUMNS)
    df["codigo"] = df["codigo"].astype(str).str.strip().str.zfill(8)
    df["valorizavel"] = df["valorizavel"].astype(str).str.strip().str.upper()
    df = (
        df[df["codigo"] != ""]
        .drop_duplicates(subset=["codigo"])
        .sort_values("codigo")
        .reset_index(drop=True)
    )

    _CACHE_NR[path] = df
    logger.info("Tabela NR carregada: %s (%d códigos).", path, len(df))
    return df.copy()


def load_tabela_nd(ref_dir: str | Path = "ref") -> pd.DataFrame:
    """Carrega tabela de Natureza da Despesa (ND) com cache em memória.

    Args:
        ref_dir: diretório de referência contendo ``tabela_nd.csv``.

    Returns:
        DataFrame com colunas ``codigo`` (8 dígitos), ``nivel`` e ``nome``.

    Raises:
        ConfigError: se o arquivo estiver ausente/inválido.
    """
    path = _resolve_reference_path(ref_dir, _TABELA_ND_FILE_NAME)
    if path in _CACHE_ND:
        return _CACHE_ND[path].copy()

    df = _read_reference_csv(path, required_columns=_REQUIRED_ND_COLUMNS)
    df["codigo"] = df["codigo"].astype(str).str.strip().str.zfill(8)
    df["nivel"] = df["nivel"].astype(str).str.strip()
    df["nome"] = df["nome"].astype(str).str.strip()
    df = (
        df[df["codigo"] != ""]
        .drop_duplicates(subset=["codigo"])
        .sort_values("codigo")
        .reset_index(drop=True)
    )

    _CACHE_ND[path] = df
    logger.info("Tabela ND carregada: %s (%d códigos).", path, len(df))
    return df.copy()


def load_tabela_fs(ref_dir: str | Path = "ref") -> pd.DataFrame:
    """Carrega tabela de classificação funcional Função/Subfunção (FS) com cache.

    Args:
        ref_dir: diretório de referência contendo ``tabela_fs.csv``.

    Returns:
        DataFrame com colunas ``funcao`` (2 dígitos) e ``subfuncao`` (3 dígitos).

    Raises:
        ConfigError: se o arquivo estiver ausente/inválido.
    """
    path = _resolve_reference_path(ref_dir, _TABELA_FS_FILE_NAME)
    if path in _CACHE_FS:
        return _CACHE_FS[path].copy()

    df = _read_reference_csv(path, required_columns=_REQUIRED_FS_COLUMNS)
    df["funcao"] = df["funcao"].astype(str).str.strip().str.zfill(2)
    df["subfuncao"] = df["subfuncao"].astype(str).str.strip().str.zfill(3)
    df = (
        df[(df["funcao"] != "") & (df["subfuncao"] != "")]
        .drop_duplicates(subset=["funcao", "subfuncao"])
        .sort_values(["funcao", "subfuncao"])
        .reset_index(drop=True)
    )

    _CACHE_FS[path] = df
    logger.info("Tabela FS carregada: %s (%d combinações).", path, len(df))
    return df.copy()


def clear_all_caches() -> None:
    """Limpa todos os caches de tabelas de referência em memória."""
    _CACHE_PCASP.clear()
    _CACHE_DOMINIOS_FR.clear()
    _CACHE_PO.clear()
    _CACHE_CO.clear()
    _CACHE_FR.clear()
    _CACHE_NR.clear()
    _CACHE_ND.clear()
    _CACHE_FS.clear()


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------


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
