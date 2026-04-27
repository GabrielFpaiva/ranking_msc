"""
ranking_msc.io.reader_msc
~~~~~~~~~~~~~~~~~~~~~~~~~~

Leitura e parse inicial do CSV MSC (Matriz de Saldos Contábeis).

O CSV MSC é o arquivo mensal enviado ao SICONFI. Cada arquivo contém:
    - Metadados: código SICONFI do ente e competência (YYYY-MM).
    - Dados: saldos contábeis por conta PCASP.

Este módulo NÃO aplica regras de validação de negócio. Ele apenas:
    1. Lê o CSV (detectando encoding e tratando line terminator ``\\r``).
    2. Extrai competência e siconfi da linha 1 de metadata.
    3. Valida o layout mínimo (colunas obrigatórias presentes?).
    4. Pivota Tipo_valor × Natureza_valor em 6 colunas de valor.
    5. Retorna um ``RawMSC`` com o DataFrame + metadados.

Validações de conteúdo (domínios, PCASP, etc.) ficam nas regras.
"""

from __future__ import annotations

import datetime
import io
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from ranking_msc.exceptions import InputFormatError
from ranking_msc.schemas import RAW_MSC_COLUMNS

logger = logging.getLogger("ranking_msc")

# Colunas obrigatórias no header do CSV original (linha 2)
_REQUIRED_CSV_COLUMNS: list[str] = [
    "CONTA", "IC1", "TIPO1", "Valor", "Tipo_valor", "Natureza_valor",
]

# Todas as colunas esperadas no CSV original
_ALL_CSV_COLUMNS: list[str] = [
    "CONTA", "IC1", "TIPO1", "IC2", "TIPO2", "IC3", "TIPO3",
    "IC4", "TIPO4", "IC5", "TIPO5", "IC6", "TIPO6",
    "Valor", "Tipo_valor", "Natureza_valor",
]

# Colunas sem as quais o pivot é impossível — levantam exceção imediata
_CRITICAL_CSV_COLUMNS: frozenset[str] = frozenset(
    {"CONTA", "Valor", "Tipo_valor", "Natureza_valor"}
)

# Mapeamento Tipo_valor × Natureza_valor → nome da coluna pivotada
_PIVOT_MAP: dict[tuple[str, str], str] = {
    ("beginning_balance", "D"): "saldo_inicial_debito",
    ("beginning_balance", "C"): "saldo_inicial_credito",
    ("period_change", "D"): "movimento_debito",
    ("period_change", "C"): "movimento_credito",
    ("ending_balance", "D"): "saldo_final_debito",
    ("ending_balance", "C"): "saldo_final_credito",
}

# Colunas de agrupamento para o pivot (chave da linha pivotada)
_GROUP_COLS: list[str] = [
    "CONTA", "IC1", "TIPO1", "IC2", "TIPO2", "IC3", "TIPO3",
    "IC4", "TIPO4", "IC5", "TIPO5", "IC6", "TIPO6",
]

# Mapeamento de nomes CSV originais → nomes padronizados (minúsculos)
_RENAME_MAP: dict[str, str] = {
    "CONTA": "conta_contabil",
    "IC1": "ic1", "TIPO1": "tipo1",
    "IC2": "ic2", "TIPO2": "tipo2",
    "IC3": "ic3", "TIPO3": "tipo3",
    "IC4": "ic4", "TIPO4": "tipo4",
    "IC5": "ic5", "TIPO5": "tipo5",
    "IC6": "ic6", "TIPO6": "tipo6",
}


@dataclass
class RawMSC:
    """Resultado da leitura de um CSV MSC.

    Attributes:
        competencia: mês de referência no formato "YYYY-MM".
        siconfi: código SICONFI do ente (ex: "2507507EX").
        df: DataFrame com colunas de RAW_MSC_COLUMNS (valores já pivotados).
        source: caminho ou nome do arquivo de origem.
        pre_pivot_issues: violações estruturais detectadas antes do pivot —
            inclui erros de Tipo_valor/Natureza_valor (R003, R004), código
            Siconfi inválido (R006), período inválido (R007), separador
            incorreto (R008) e contagem de colunas IC/TIPO (R009).
    """

    competencia: str
    siconfi: str
    df: pd.DataFrame
    source: str = ""
    pre_pivot_issues: list[dict[str, object]] = field(default_factory=list)


def read_msc_csv(
    file: str | Path | io.BytesIO,
    *,
    encoding: str = "ascii",
    separator: str = ";",
) -> RawMSC:
    """Lê o CSV MSC e devolve um ``RawMSC``.

    O CSV MSC possui uma estrutura peculiar:
    - Linha 1: metadata ``<SICONFI>;<competencia>``
    - Linha 2: header das colunas
    - Linha 3+: dados
    - Line terminator: ``\\r`` (CR only)

    O método lê o arquivo em modo binário, trata o line terminator,
    extrai metadados e pivota os valores por Tipo_valor × Natureza_valor.

    Args:
        file: caminho do arquivo ou objeto BytesIO (ex: upload do Panel).
        encoding: encoding do CSV (padrão ASCII, compatível UTF-8).
        separator: separador de colunas (padrão ``;``).

    Returns:
        ``RawMSC`` com metadados e DataFrame no formato RAW_MSC_COLUMNS.

    Raises:
        InputFormatError: se o arquivo estiver vazio, ilegível ou sem
                          as colunas mínimas esperadas.
    """
    source = _resolve_source(file)
    text = _read_and_decode(file, encoding)
    lines = text.strip().split("\n")

    if len(lines) < 3:
        raise InputFormatError(
            f"Arquivo MSC com apenas {len(lines)} linha(s) — "
            "esperado no mínimo 3 (metadata + header + dados). "
            f"Fonte: {source}"
        )

    competencia, siconfi = _extract_metadata(lines[0])
    metadata_issues = _validate_metadata(siconfi, competencia)
    r008_issues = _detect_separator_issue(lines[1], separator)
    logger.info(
        "Lendo CSV MSC: siconfi=%s, competência=%s, fonte=%s",
        siconfi, competencia, source,
        extra={"siconfi": siconfi, "competencia": competencia, "modulo": "reader_msc"},
    )

    csv_text = "\n".join(lines[1:])
    actual_sep = separator
    if r008_issues:
        # Wrong delimiter detected — re-parse with the detected separator so
        # the pipeline can continue.  R008 will surface as a proper rule
        # result instead of _validate_columns raising InputFormatError on
        # missing critical columns.
        detected = str(r008_issues[0].get("valor_encontrado", ","))
        logger.warning(
            "Separador esperado '%s' não encontrado; re-parsing com '%s'. Fonte: %s",
            separator, detected, source,
            extra={"siconfi": siconfi, "competencia": competencia, "modulo": "reader_msc"},
        )
        actual_sep = detected

    df = _parse_csv(csv_text, actual_sep, source)
    r001_r009_issues = _validate_columns(df, source)
    df, pivot_issues = _pivot_values(df, competencia, siconfi)
    pre_pivot_issues = metadata_issues + r008_issues + r001_r009_issues + pivot_issues

    logger.info(
        "CSV MSC lido com sucesso: %d linhas pivotadas. Fonte: %s",
        len(df), source,
        extra={"siconfi": siconfi, "competencia": competencia, "modulo": "reader_msc"},
    )

    return RawMSC(
        competencia=competencia,
        siconfi=siconfi,
        df=df,
        source=source,
        pre_pivot_issues=pre_pivot_issues,
    )


# ---------------------------------------------------------------------------
# Funções internas
# ---------------------------------------------------------------------------

def _resolve_source(file: str | Path | io.BytesIO) -> str:
    """Retorna o nome/caminho do arquivo para mensagens de erro e log."""
    if isinstance(file, (str, Path)):
        return str(file)
    name = getattr(file, "name", None)
    return str(name) if name else "<BytesIO>"


def _read_and_decode(file: str | Path | io.BytesIO, encoding: str) -> str:
    """Lê o arquivo em modo binário e decodifica, tratando line terminator \\r.

    O CSV MSC usa ``\\r`` (CR only) como line terminator. Esta função
    normaliza para ``\\n`` para compatibilidade com pd.read_csv.
    """
    try:
        if isinstance(file, (str, Path)):
            raw = Path(file).read_bytes()
        else:
            raw = file.read()
    except OSError as exc:
        raise InputFormatError(
            f"Não foi possível ler o arquivo MSC: {exc}"
        ) from exc

    if not raw:
        raise InputFormatError("Arquivo MSC está vazio.")

    try:
        text = raw.decode(encoding)
    except (UnicodeDecodeError, LookupError) as exc:
        raise InputFormatError(
            f"Falha ao decodificar o arquivo MSC com encoding '{encoding}': {exc}"
        ) from exc

    # Normalizar line terminators: \r\n → \n, depois \r → \n
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text


_METADATA_RE = re.compile(r"^(.+);(\d{4}-\d{2})$")
_SICONFI_RE = re.compile(r"^\d{7}EX$")


def _extract_metadata(first_line: str) -> tuple[str, str]:
    """Extrai competência e siconfi a partir da primeira linha do CSV.

    Formato esperado: ``<SICONFI>;<YYYY-MM>``
    Exemplo: ``2507507EX;2025-11`` → (``"2025-11"``, ``"2507507EX"``)

    Args:
        first_line: primeira linha do arquivo (metadata).

    Returns:
        Tupla ``(competencia, siconfi)``.

    Raises:
        InputFormatError: se a linha não seguir o formato esperado.
    """
    line = first_line.strip()
    match = _METADATA_RE.match(line)
    if not match:
        raise InputFormatError(
            f"Linha de metadata com formato inesperado: '{line}'. "
            "Esperado: '<SICONFI>;<YYYY-MM>' (ex: '2507507EX;2025-11')."
        )
    siconfi = match.group(1)
    competencia = match.group(2)
    return competencia, siconfi


def _validate_metadata(siconfi: str, competencia: str) -> list[dict[str, object]]:
    """Valida código Siconfi (R006) e período (R007) extraídos da linha de metadata.

    Args:
        siconfi: código SICONFI extraído da primeira linha.
        competencia: período no formato YYYY-MM extraído da primeira linha.

    Returns:
        Lista de issues R006 e/ou R007 (pode ser vazia).
    """
    issues: list[dict[str, object]] = []

    if not _SICONFI_RE.match(siconfi):
        issues.append({
            "regra": "R006",
            "conta_contabil": "",
            "campo": "siconfi",
            "valor_encontrado": siconfi,
            "competencia": competencia,
        })

    try:
        ano_str, mes_str = competencia.split("-")
        mes_int = int(mes_str)
        ano_int = int(ano_str)
        ano_corrente = datetime.date.today().year
        if not (1 <= mes_int <= 13) or not (2020 <= ano_int <= ano_corrente + 1):
            issues.append({
                "regra": "R007",
                "conta_contabil": "",
                "campo": "competencia",
                "valor_encontrado": competencia,
                "competencia": competencia,
            })
    except (ValueError, AttributeError):
        issues.append({
            "regra": "R007",
            "conta_contabil": "",
            "campo": "competencia",
            "valor_encontrado": competencia,
            "competencia": competencia,
        })

    return issues


def _detect_separator_issue(header_line: str, expected_sep: str) -> list[dict[str, object]]:
    """Detecta uso de separador incorreto na linha de cabeçalho (R008).

    Compara contagem de ponto-e-vírgula vs vírgula no header. Se o header
    não tem nenhum ";" mas tem "," → separador incorreto.

    Args:
        header_line: segunda linha do arquivo CSV (cabeçalho das colunas).
        expected_sep: separador esperado (padrão ";").

    Returns:
        Lista com um issue R008 se vírgula for detectada em vez de ";".
    """
    if expected_sep != ";":
        return []
    semi_count = header_line.count(";")
    comma_count = header_line.count(",")
    if semi_count == 0 and comma_count > 0:
        return [{
            "regra": "R008",
            "conta_contabil": "",
            "campo": "separador",
            "valor_encontrado": ",",
            "competencia": "",
        }]
    return []


def _parse_csv(csv_text: str, separator: str, source: str) -> pd.DataFrame:
    """Faz o parse do CSV (sem a linha de metadata) usando pandas."""
    try:
        df = pd.read_csv(
            io.StringIO(csv_text),
            sep=separator,
            dtype=str,
            keep_default_na=False,
        )
    except Exception as exc:
        raise InputFormatError(
            f"Falha ao parsear o CSV MSC: {exc}. Fonte: {source}"
        ) from exc

    if df.empty:
        raise InputFormatError(
            f"CSV MSC sem dados (apenas header encontrado). Fonte: {source}"
        )

    return df


def _validate_columns(df: pd.DataFrame, source: str) -> list[dict[str, object]]:
    """Valida colunas do CSV e coleta issues R001 para colunas ausentes.

    Levanta InputFormatError apenas se colunas críticas (CONTA, Valor,
    Tipo_valor, Natureza_valor) estiverem ausentes — sem elas o pivot é
    impossível. Demais ausências viram issues R001 para o motor de regras.

    Args:
        df: DataFrame lido do CSV (antes do pivot).
        source: nome/caminho do arquivo de origem.

    Returns:
        Lista de issues R001 (pode ser vazia).

    Raises:
        InputFormatError: se alguma coluna crítica estiver ausente.
    """
    missing = [col for col in _ALL_CSV_COLUMNS if col not in df.columns]
    issues: list[dict[str, object]] = [
        {
            "regra": "R001",
            "conta_contabil": "",
            "campo": col,
            "valor_encontrado": "coluna ausente no CSV",
        }
        for col in missing
    ]

    ic_tipo_cols = [c for c in df.columns if c.startswith("IC") or c.startswith("TIPO")]
    if len(ic_tipo_cols) != 12:
        issues.append({
            "regra": "R009",
            "conta_contabil": "",
            "campo": "colunas_ic_tipo",
            "valor_encontrado": str(len(ic_tipo_cols)),
        })

    critical_missing = {col for col in missing if col in _CRITICAL_CSV_COLUMNS}
    if critical_missing:
        raise InputFormatError(
            f"Colunas críticas ausentes no CSV MSC: {sorted(critical_missing)}. "
            f"Colunas encontradas: {list(df.columns)}. "
            f"Fonte: {source}"
        )

    return issues


_TIPO_VALOR_DOMAIN: frozenset[str] = frozenset(
    {"beginning_balance", "ending_balance", "period_change"}
)
_NATUREZA_VALOR_DOMAIN: frozenset[str] = frozenset({"D", "C"})


def _pivot_values(
    df: pd.DataFrame,
    competencia: str,
    siconfi: str,
) -> tuple[pd.DataFrame, list[dict[str, object]]]:
    """Pivota Tipo_valor × Natureza_valor em 6 colunas de valor.

    Agrupa por conta + ICs e espalha as combinações de
    (Tipo_valor, Natureza_valor) em colunas individuais:
        - saldo_inicial_debito, saldo_inicial_credito
        - movimento_debito, movimento_credito
        - saldo_final_debito, saldo_final_credito

    Args:
        df: DataFrame com colunas originais do CSV.
        competencia: competência extraída da metadata.
        siconfi: código SICONFI extraído da metadata.

    Returns:
        Tupla (DataFrame pivotado, lista de violações pré-pivot).
        As violações registram linhas com Tipo_valor ou Natureza_valor
        fora do domínio válido (usadas pelas regras R003 e R004).
    """
    # R005: capturar valores não-numéricos antes do coerce
    _valor_raw = df["Valor"].astype(str).str.strip().str.replace(",", ".", regex=False)
    _invalidos = pd.to_numeric(_valor_raw, errors="coerce").isna() & _valor_raw.ne("")
    r005_issues: list[dict[str, object]] = [
        {
            "regra": "R005",
            "conta_contabil": str(df.loc[idx, "CONTA"]) if "CONTA" in df.columns else "",
            "campo": "Valor",
            "valor_encontrado": str(df.loc[idx, "Valor"]),
            "competencia": competencia,
        }
        for idx in df.index[_invalidos]
    ]

    # Converter Valor para float
    df["Valor"] = pd.to_numeric(df["Valor"].str.replace(",", "."), errors="coerce").fillna(0.0)

    # Criar coluna combinada para pivot
    df["_pivot_col"] = list(zip(df["Tipo_valor"], df["Natureza_valor"], strict=True))

    # Capturar violações de domínio para R003 e R004
    pre_pivot_issues: list[dict[str, object]] = []
    for _, row in df.iterrows():
        tipo = str(row["Tipo_valor"])
        natureza = str(row["Natureza_valor"])
        conta = str(row.get("CONTA", ""))
        if tipo not in _TIPO_VALOR_DOMAIN:
            pre_pivot_issues.append({
                "regra": "R003",
                "conta_contabil": conta,
                "campo": "Tipo_valor",
                "valor_encontrado": tipo,
                "competencia": competencia,
            })
        if natureza not in _NATUREZA_VALOR_DOMAIN:
            pre_pivot_issues.append({
                "regra": "R004",
                "conta_contabil": conta,
                "campo": "Natureza_valor",
                "valor_encontrado": natureza,
                "competencia": competencia,
            })

    # Verificar combinações desconhecidas (log apenas)
    known = set(_PIVOT_MAP.keys())
    found = set(df["_pivot_col"].unique())
    unknown = found - known
    if unknown:
        logger.warning(
            "Combinações Tipo_valor × Natureza_valor desconhecidas: %s",
            sorted(str(c) for c in unknown),
            extra={"competencia": competencia, "siconfi": siconfi, "modulo": "reader_msc"},
        )

    # Mapear para nomes de coluna
    df["_pivot_name"] = df["_pivot_col"].map(_PIVOT_MAP)

    # Filtrar linhas com combinação desconhecida (não mapeada)
    df_valid = df[df["_pivot_name"].notna()].copy()

    # Colunas de agrupamento presentes no DataFrame
    group_cols = [c for c in _GROUP_COLS if c in df_valid.columns]

    # Indicadores de presença — detectar se a conta possui ao menos uma linha
    # beginning_balance / ending_balance no CSV original. Necessário para
    # distinguir "saldo ausente" (fill_value=0.0) de "saldo zero legítimo".
    _bb_names: frozenset[str] = frozenset({"saldo_inicial_debito", "saldo_inicial_credito"})
    _eb_names: frozenset[str] = frozenset({"saldo_final_debito", "saldo_final_credito"})
    presence = (
        df_valid
        .assign(
            _is_bb=lambda x: x["_pivot_name"].isin(_bb_names),
            _is_eb=lambda x: x["_pivot_name"].isin(_eb_names),
        )
        .groupby(group_cols, as_index=False)
        .agg(
            _has_saldo_inicial=("_is_bb", "any"),
            _has_saldo_final=("_is_eb", "any"),
        )
    )

    # Pivot (soma de valores por conta × IC)
    pivoted = df_valid.pivot_table(
        index=group_cols,
        columns="_pivot_name",
        values="Valor",
        aggfunc="sum",
        fill_value=0.0,
    ).reset_index()

    # Merge dos indicadores de presença — left join garante que toda linha pivotada
    # recebe os indicadores; fillna(False) cobre o caso de df_valid vazio.
    pivoted = pivoted.merge(
        presence[group_cols + ["_has_saldo_inicial", "_has_saldo_final"]],
        on=group_cols,
        how="left",
    )
    pivoted["_has_saldo_inicial"] = pivoted["_has_saldo_inicial"].fillna(False)
    pivoted["_has_saldo_final"] = pivoted["_has_saldo_final"].fillna(False)

    # Garantir que todas as 6 colunas de valor existem (mesmo que zeradas)
    value_cols = list(_PIVOT_MAP.values())
    for col in value_cols:
        if col not in pivoted.columns:
            pivoted[col] = 0.0

    # Renomear colunas (CONTA → conta_contabil, IC1 → ic1, etc.)
    pivoted = pivoted.rename(columns=_RENAME_MAP)

    # Adicionar metadados
    pivoted.insert(0, "competencia", competencia)
    pivoted.insert(1, "siconfi", siconfi)

    # Garantir strings vazias (não NaN) nas colunas de texto
    str_cols = [c for c in pivoted.columns if c not in value_cols]
    for col in str_cols:
        pivoted[col] = pivoted[col].astype(str).replace("nan", "")

    # Reordenar conforme RAW_MSC_COLUMNS (colunas extras são descartadas)
    final_cols = [c for c in RAW_MSC_COLUMNS if c in pivoted.columns]
    pivoted = pivoted[final_cols]

    return pivoted, pre_pivot_issues + r005_issues
