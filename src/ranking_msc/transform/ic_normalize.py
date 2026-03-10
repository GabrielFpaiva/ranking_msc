"""
ranking_msc.transform.ic_normalize
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Normalização do Indicador Contábil (IC) e Tipo de Valor da MSC.

O CSV MSC original contém colunas IC e TIPO que codificam informações
sobre como interpretar cada linha (Patrimonial, Orçamentário, Controle, etc.).
A normalização separa essas informações em colunas individuais:

    IC/TIPO originais  →  PO, FR, CO, NR, ND, FS

Onde:
    PO = Poder/Órgão
    FR = Fonte de Recurso
    CO = Complemento do Órgão
    NR = Natureza da Receita
    ND = Natureza da Despesa
    FS = Função/Subfunção

Este módulo é chamado logo após ``read_msc_csv()`` e antes do motor
de regras, garantindo que o DataFrame esteja no formato padronizado.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from ranking_msc.exceptions import ConfigError, InputFormatError

logger = logging.getLogger("ranking_msc")

_TIPO_COLS: list[str] = [f"tipo{i}" for i in range(1, 7)]
_IC_COLS: list[str] = [f"ic{i}" for i in range(1, 7)]
_MAPPING_REQUIRED_COLS: list[str] = [
    *_TIPO_COLS,
    "colunas_aplicaveis",
    "descricao",
]
_TIPO_TO_COL: dict[str, str] = {
    "PO": "po",
    "FP": "fp",
    "FS": "fs",
    "FR": "fr",
    "CO": "co",
    "NR": "nr",
    "ND": "nd",
    "AI": "ai",
}
_NORMALIZED_COLS: list[str] = list(_TIPO_TO_COL.values())
_DEFAULT_MAPPING_PATH = Path("ref/mapeamento_ic_tipo.csv")

_KNOWN_COMBINATIONS_CACHE: dict[Path, set[tuple[str, ...]]] = {}


def normalize_ic(
    df: pd.DataFrame,
    *,
    mapping_path: str | Path = _DEFAULT_MAPPING_PATH,
) -> pd.DataFrame:
    """Normaliza colunas IC/TIPO em colunas individuais (PO, FR, CO, NR, ND, FS).

    Args:
        df: DataFrame bruto da MSC (saída de ``read_msc_csv``).
        mapping_path: caminho para ``ref/mapeamento_ic_tipo.csv``.

    Returns:
        DataFrame com colunas IC expandidas. As colunas originais IC/TIPO
        são mantidas para auditoria e as novas colunas são adicionadas.

    Raises:
        InputFormatError: se colunas IC/TIPO obrigatórias não existirem.
        ConfigError: se o mapeamento de referência estiver ausente/inválido.
    """
    _validate_input_columns(df)
    known_combinations = _load_known_combinations(mapping_path)

    normalized_df = df.copy()
    normalized_tipos = _normalize_text_columns(normalized_df[_TIPO_COLS], _TIPO_COLS)
    normalized_ics = _normalize_text_columns(normalized_df[_IC_COLS], _IC_COLS)

    for normalized_col in _NORMALIZED_COLS:
        if normalized_col not in normalized_df.columns:
            normalized_df[normalized_col] = ""

    for idx in range(1, 7):
        tipo_col = f"tipo{idx}"
        ic_col = f"ic{idx}"
        tipo_series = normalized_tipos[tipo_col]
        ic_series = normalized_ics[ic_col]

        for tipo_code, destination_col in _TIPO_TO_COL.items():
            mask = (tipo_series == tipo_code) & (ic_series != "")
            normalized_df.loc[mask, destination_col] = ic_series[mask]

    unknown = _find_unknown_combinations(normalized_tipos, known_combinations)
    if unknown:
        logger.warning(
            "Combinações IC/TIPO não mapeadas encontradas (%d): %s",
            len(unknown),
            [_format_combination(combo) for combo in unknown],
        )

    return normalized_df


def _validate_input_columns(df: pd.DataFrame) -> None:
    """Valida se o DataFrame contém as colunas IC/TIPO esperadas."""
    required_cols = set(_TIPO_COLS + _IC_COLS)
    missing = sorted(required_cols - set(df.columns))
    if missing:
        raise InputFormatError(
            "DataFrame sem colunas obrigatórias para normalização IC/TIPO: "
            f"{missing}"
        )


def _load_known_combinations(mapping_path: str | Path) -> set[tuple[str, ...]]:
    """Carrega combinações conhecidas de TIPO1..TIPO6 do arquivo de referência."""
    path = Path(mapping_path).resolve()
    if path in _KNOWN_COMBINATIONS_CACHE:
        return _KNOWN_COMBINATIONS_CACHE[path]

    if not path.exists():
        raise ConfigError(f"Arquivo de mapeamento IC/TIPO não encontrado: {path}")

    try:
        mapping_df = pd.read_csv(path, sep=";", dtype=str, keep_default_na=False)
    except Exception as exc:  # noqa: BLE001
        raise ConfigError(f"Falha ao ler mapeamento IC/TIPO em {path}: {exc}") from exc

    missing_cols = sorted(set(_MAPPING_REQUIRED_COLS) - set(mapping_df.columns))
    if missing_cols:
        raise ConfigError(
            f"Mapeamento IC/TIPO inválido (colunas ausentes): {missing_cols}. Arquivo: {path}"
        )

    normalized = _normalize_text_columns(mapping_df[_TIPO_COLS].copy(), _TIPO_COLS)
    combinations = {
        tuple(row[col] for col in _TIPO_COLS)
        for _, row in normalized.iterrows()
    }
    _KNOWN_COMBINATIONS_CACHE[path] = combinations
    return combinations


def _normalize_text_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Normaliza colunas textuais como string uppercase sem NaN."""
    normalized_df = df.copy()
    for col in columns:
        normalized_df[col] = (
            normalized_df[col]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.upper()
        )
    return normalized_df


def _find_unknown_combinations(
    df: pd.DataFrame,
    known_combinations: set[tuple[str, ...]],
) -> list[tuple[str, ...]]:
    """Identifica combinações TIPO1..TIPO6 não previstas no mapeamento."""
    found = {
        tuple(row[col] for col in _TIPO_COLS)
        for _, row in df[_TIPO_COLS].iterrows()
    }
    return sorted(found - known_combinations)


def _format_combination(combination: tuple[str, ...]) -> str:
    """Formata combinação de TIPO para log legível."""
    return ";".join(part if part else "-" for part in combination)
