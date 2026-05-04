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
from ranking_msc.io.ref_loader import IC_MAP
from ranking_msc.schemas import RAW_MSC_COLUMNS

logger = logging.getLogger("ranking_msc")

# Encodings tentados em cascata quando encoding="auto" (ordem importa: cp1252 antes
# de latin-1 porque cp1252 rejeita bytes 0x81/0x8D/0x8F/0x90/0x9D que latin-1 aceita,
# permitindo distinguir os dois; latin-1 como último fallback nunca falha).
_ENCODING_CANDIDATES: list[str] = ["utf-8-sig", "utf-8", "cp1252", "latin-1"]

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

# Conjunto de sequências de tipos de IC consideradas canônicas pelo leiaute MSC.
# Derivado do IC_MAP (ref_loader): cada entry é uma tupla ordenada dos tipos.
_IC_VALID_ORDERS: frozenset[tuple[str, ...]] = frozenset(
    tuple(types) for types in IC_MAP.values() if types
)

# Valores considerados "sem IC" — alinhado com ic_mask_informada em rules/base.py.
_IC_EMPTY_VALS: frozenset[str] = frozenset({"", "0", "nan"})

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
        pre_pivot_issues: violações estruturais detectadas antes/durante pivot —
            inclui erros de Tipo_valor/Natureza_valor (R003, R004), código
            Siconfi inválido (R006), período inválido (R007), separador
            incorreto (R008), contagem de colunas IC/TIPO (R009), pares
            IC/TIPO desemparelhados (R033) e ordem IC incorreta (R082).
    """

    competencia: str
    siconfi: str
    df: pd.DataFrame
    source: str = ""
    pre_pivot_issues: list[dict[str, object]] = field(default_factory=list)


def read_msc_csv(
    file: str | Path | io.BytesIO,
    *,
    encoding: str = "auto",
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
        encoding: encoding do CSV. Use ``"auto"`` (padrão) para detecção
            automática em cascata: UTF-8 BOM → UTF-8 → CP1252 → Latin-1.
            Passe um encoding explícito (ex: ``"utf-8"``, ``"latin-1"``)
            para forçar sem fallback.
        separator: separador de colunas (padrão ``;``). Suportados: ``;``,
            ``,``, ``|``. O separador efetivo é inferido do arquivo quando
            há inconsistência com o esperado.

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

    effective_sep, r008_issues = _detect_effective_separator(
        lines[0], lines[1], separator, data_lines=lines[2:]
    )

    # Quando o separador efetivo do corpo difere do separador do header (ex: header
    # usa vírgula ou pipe mas dados usam ";"), normalizar o header para usar o separador
    # do corpo antes de passar para pd.read_csv.  Isso garante parse correto enquanto
    # R008 já foi emitido acima.
    header_line = lines[1]
    _hcounts = {
        ";": header_line.count(";"),
        ",": header_line.count(","),
        "|": header_line.count("|"),
    }
    header_sep_in_use = max(_hcounts, key=lambda s: _hcounts[s])
    if header_sep_in_use != effective_sep:
        header_line = header_line.replace(header_sep_in_use, effective_sep)

    # Metadata separator is inferred from delimiter presence, independent of
    # period format validity.  A malformed period (e.g. "2024/01") must not
    # push parsing onto the wrong delimiter — that would corrupt siconfi /
    # competencia extraction and produce a false R006 instead of R007.
    # Ordem: ; (canônico) → | → , (consistente com R008/separator detection).
    _meta = lines[0].strip()
    if ";" in _meta:
        meta_sep = ";"
    elif "|" in _meta:
        meta_sep = "|"
    elif "," in _meta:
        meta_sep = ","
    else:
        meta_sep = separator
    competencia, siconfi = _extract_metadata(lines[0], meta_sep)
    metadata_issues = _validate_metadata(siconfi, competencia)
    # Sanitizar antes de usar em caminhos — R006/R007 já capturaram os valores originais.
    siconfi, competencia = _sanitize_for_paths(siconfi, competencia)
    logger.info(
        "Lendo CSV MSC: siconfi=%s, competência=%s, fonte=%s",
        siconfi, competencia, source,
        extra={"siconfi": siconfi, "competencia": competencia, "modulo": "reader_msc"},
    )

    csv_text = "\n".join([header_line] + lines[2:])
    df = _parse_csv(csv_text, effective_sep, source)
    r001_r009_issues = _validate_columns(df, source)
    df, pivot_issues = _pivot_values(df, competencia, siconfi)
    ic_pair_issues = _check_ic_pairs(df, competencia)
    ic_order_issues = _check_ic_order(df, competencia)
    pre_pivot_issues = (
        metadata_issues + r008_issues + r001_r009_issues
        + pivot_issues + ic_pair_issues + ic_order_issues
    )

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

    Quando ``encoding == "auto"``, tenta os encodings de ``_ENCODING_CANDIDATES``
    em cascata até o primeiro que decodificar sem erro.  Um encoding explícito
    (ex: ``"utf-8"``) falha imediatamente se o arquivo não for compatível.
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

    candidates = _ENCODING_CANDIDATES if encoding == "auto" else [encoding]
    last_exc: Exception | None = None
    for enc in candidates:
        try:
            text = raw.decode(enc)
            if encoding == "auto" and enc != "utf-8":
                logger.debug(
                    "encoding detectado: %s", enc,
                    extra={"modulo": "reader_msc"},
                )
            text = text.replace("\r\n", "\n").replace("\r", "\n")
            return text
        except (UnicodeDecodeError, LookupError) as exc:
            last_exc = exc

    raise InputFormatError(
        f"Falha ao decodificar o arquivo MSC com encodings {candidates}: {last_exc}"
    ) from last_exc


_METADATA_RE = re.compile(r"^(.+);(\d{4}-\d{2})$")
_METADATA_COMMA_RE = re.compile(r"^([^,]+),(\d{4}-\d{2})$")
_METADATA_PIPE_RE = re.compile(r"^([^|]+)\|(\d{4}-\d{2})$")
_METADATA_PATTERNS: dict[str, re.Pattern[str]] = {
    ";": _METADATA_RE,
    ",": _METADATA_COMMA_RE,
    "|": _METADATA_PIPE_RE,
}
_SICONFI_RE = re.compile(r"^\d{7}EX$")
_COMPETENCIA_SAFE_RE = re.compile(r"^\d{4}-\d{2}$")
_PATH_UNSAFE_RE = re.compile(r"[^A-Za-z0-9\-_]")


def _extract_metadata(first_line: str, sep: str = ";") -> tuple[str, str]:
    """Extrai competência e siconfi a partir da primeira linha do CSV.

    Formato esperado: ``<SICONFI>;<YYYY-MM>``
    Exemplo: ``2507507EX;2025-11`` → (``"2025-11"``, ``"2507507EX"``)

    Nunca levanta exceção para entradas parcialmente legíveis: utiliza
    extração por melhor esforço (``split``) quando os padrões conhecidos
    não casam.  Reserva ``InputFormatError`` somente para linha em branco
    — único caso em que nenhum dado pode ser recuperado.

    Args:
        first_line: primeira linha do arquivo (metadata).
        sep: separador usado na linha (padrão ``";"``).

    Returns:
        Tupla ``(competencia, siconfi)``.

    Raises:
        InputFormatError: somente se a linha estiver completamente em branco.
    """
    line = first_line.strip()

    if not line:
        raise InputFormatError(
            "Linha de metadata está em branco — não é possível extrair "
            "siconfi nem competência."
        )

    # Tentativa 1: padrão canônico — dispatch por separador (;, , ou |)
    pattern = _METADATA_PATTERNS.get(sep, _METADATA_RE)
    match = pattern.match(line)
    if match:
        return match.group(2), match.group(1)

    # Tentativa 2: melhor esforço via split — extrai o que for possível e
    # deixa _validate_metadata emitir R006/R007 para valores inválidos.
    if sep in line:
        left, right = line.split(sep, 1)
        return right.strip(), left.strip()

    # Linha sem separador algum: siconfi não reconhecível, competência vazia.
    return "", line


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

    if not _COMPETENCIA_SAFE_RE.match(competencia):
        # Formato inválido (ex: "2024-1", "02024-01") → emitir imediatamente.
        issues.append({
            "regra": "R007",
            "conta_contabil": "",
            "campo": "competencia",
            "valor_encontrado": competencia,
            "competencia": competencia,
        })
    else:
        # Formato garantido YYYY-MM — parse direto sem try/except.
        ano_int = int(competencia[:4])
        mes_int = int(competencia[5:])
        ano_corrente = datetime.date.today().year
        if not (1 <= mes_int <= 13) or not (2020 <= ano_int <= ano_corrente + 1):
            issues.append({
                "regra": "R007",
                "conta_contabil": "",
                "campo": "competencia",
                "valor_encontrado": competencia,
                "competencia": competencia,
            })

    return issues


def _infer_sep_from_rows(data_lines: list[str] | None, fallback: str) -> str:
    """Infere o separador efetivo amostrado das primeiras linhas de dados.

    Compara a contagem de ``;``, ``,`` e ``|`` em até 3 linhas não-vazias.
    Retorna o separador com maior contagem total.  Quando não há linhas
    disponíveis ou o vencedor empata, retorna ``fallback``.

    Args:
        data_lines: linhas de dados (linha 3 em diante do arquivo MSC).
        fallback: separador a retornar quando a inferência é inconclusiva.

    Returns:
        Separador inferido (``";"``, ``","`` ou ``"|"``) ou ``fallback``.
    """
    if not data_lines:
        return fallback

    sample = [ln for ln in data_lines if ln.strip()][:3]
    if not sample:
        return fallback

    counts = {
        ";": sum(ln.count(";") for ln in sample),
        ",": sum(ln.count(",") for ln in sample),
        "|": sum(ln.count("|") for ln in sample),
    }
    winner = max(counts, key=lambda s: counts[s])
    if counts[winner] == 0:
        return fallback
    # Empate entre dois separadores → fallback (ambíguo)
    if sum(1 for v in counts.values() if v == counts[winner]) > 1:
        return fallback
    return winner


def _sanitize_for_paths(siconfi: str, competencia: str) -> tuple[str, str]:
    """Sanitiza metadados para uso seguro em caminhos de filesystem.

    Impede path traversal (ex: ``../../``) em valores inválidos produzidos pela
    extração por melhor esforço. As violações R006/R007 já foram emitidas com
    os valores originais por ``_validate_metadata``; aqui apenas tornamos os
    valores seguros para I/O de snapshots e relatórios.

    Args:
        siconfi: código SICONFI extraído (pode ser inválido).
        competencia: período extraído (pode ser inválido ou conter ``/..``).

    Returns:
        Tupla ``(siconfi_seguro, competencia_segura)``.
        ``competencia`` é substituída por ``"0000-00"`` se não respeitar
        o formato ``YYYY-MM``; ``siconfi`` tem caracteres não-alfanuméricos
        substituídos por ``_``.
    """
    safe_comp = competencia if _COMPETENCIA_SAFE_RE.match(competencia) else "0000-00"
    safe_sico = _PATH_UNSAFE_RE.sub("_", siconfi) if siconfi else "_"
    return safe_sico, safe_comp


def _detect_separator_issue(header_line: str, expected_sep: str) -> list[dict[str, object]]:
    """Detecta uso de separador incorreto na linha de cabeçalho (R008).

    Compara contagem de ``;``, ``,`` e ``|`` no header. Se o header não tem
    nenhum ``;`` mas tem ``,`` ou ``|`` → separador incorreto. O separador
    encontrado (``","`` ou ``"|"``) é reportado no issue.

    Args:
        header_line: segunda linha do arquivo CSV (cabeçalho das colunas).
        expected_sep: separador esperado (padrão ``";"``).

    Returns:
        Lista com um issue R008 se separador incorreto for detectado.
    """
    if expected_sep != ";":
        return []
    semi_count = header_line.count(";")
    comma_count = header_line.count(",")
    pipe_count = header_line.count("|")
    if semi_count == 0 and (comma_count > 0 or pipe_count > 0):
        found_sep = "|" if pipe_count >= comma_count else ","
        return [{
            "regra": "R008",
            "conta_contabil": "",
            "campo": "separador",
            "valor_encontrado": found_sep,
            "competencia": "",
        }]
    return []


def _detect_effective_separator(
    metadata_line: str,
    header_line: str,
    expected_sep: str,
    data_lines: list[str] | None = None,
) -> tuple[str, list[dict[str, object]]]:
    """Detecta o separador efetivo verificando metadata, header e linhas de dados.

    Emite R008 quando o header usa vírgula em vez de ponto-e-vírgula.  Antes
    de confirmar o separador efetivo como vírgula, amostra as primeiras linhas
    de dados via ``_infer_sep_from_rows``: se os dados ainda usam ``;``, o
    corpo continua sendo lido com ``;`` (cabeçalho malformado, dados corretos).

    Essa abordagem impede que arquivos cujo header usa vírgula mas cujos dados
    usam ``;`` sejam parseados com separador errado, resultando em DataFrame
    vazio silencioso.

    Args:
        metadata_line: primeira linha do arquivo (metadata).
        header_line: segunda linha do arquivo (cabeçalho das colunas).
        expected_sep: separador esperado (padrão ``";"``).
        data_lines: linhas de dados (linha 3+) para inferência de separador.

    Returns:
        Tupla ``(sep_efetivo, r008_issues)``.
    """
    if expected_sep != ";":
        return expected_sep, []

    # Header é a fonte primária para detecção de separador incorreto.
    header_issues = _detect_separator_issue(header_line, expected_sep)
    if header_issues:
        # Antes de forçar vírgula, verificar o que as linhas de dados usam.
        # Se os dados usam ";", o corpo deve ser lido com ";" mesmo que o
        # header esteja malformado — R008 ainda é emitido.
        body_sep = _infer_sep_from_rows(data_lines, fallback=",")
        return body_sep, header_issues

    # Header limpo; verificar metadata como fonte secundária de R008.
    # Trigger por presença do delimitador, independente da validade do período:
    # linhas como "2507507EX,2024/01" devem emitir R008 mesmo com data malformada,
    # para que o diagnóstico de delimitador seja consistente com o caso de período válido.
    meta = metadata_line.strip()
    if ";" not in meta and ("," in meta or "|" in meta):
        found_sep = "|" if meta.count("|") >= meta.count(",") else ","
        return expected_sep, [{
            "regra": "R008",
            "conta_contabil": "",
            "campo": "separador",
            "valor_encontrado": found_sep,
            "competencia": "",
        }]

    return expected_sep, []


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


def _check_ic_pairs(df: pd.DataFrame, competencia: str) -> list[dict[str, object]]:
    """Verifica que cada IC_n está emparelhado com TIPO_n e vice-versa (R033).

    Para cada posição n (1..6), detecta linhas onde IC_n está preenchido mas
    TIPO_n está vazio — ou o contrário.  Opera no df pivotado (uma linha por
    combinação conta × ICs) após ``_pivot_values``.

    Args:
        df: DataFrame pivotado com colunas ic1/tipo1..ic6/tipo6.
        competencia: competência do arquivo (para preencher o campo no issue).

    Returns:
        Lista de issues com ``"regra": "R033"``.
    """
    if df.empty:
        return []

    issues: list[dict[str, object]] = []

    for n in range(1, 7):
        ic_col = f"ic{n}"
        tipo_col = f"tipo{n}"
        ic_present = ic_col in df.columns
        tipo_present = tipo_col in df.columns

        if not ic_present and not tipo_present:
            continue

        if not ic_present:
            # TIPO column exists but IC column is structurally absent — treat IC as empty.
            tipo_filled = df[tipo_col].astype(str).str.strip().ne("")
            for idx in df.index[tipo_filled]:
                conta = str(df.at[idx, "conta_contabil"])
                tipo_val = str(df.at[idx, tipo_col]).strip()
                issues.append({
                    "regra": "R033",
                    "conta_contabil": conta,
                    "campo": f"IC{n}/TIPO{n}",
                    "valor_encontrado": f"TIPO{n}='{tipo_val}' presente mas IC{n} está vazio",
                    "competencia": competencia,
                })
            continue

        if not tipo_present:
            # IC column exists but TIPO column is structurally absent — treat TIPO as empty.
            ic_filled = ~df[ic_col].fillna("").astype(str).str.strip().str.lower().isin(_IC_EMPTY_VALS)
            for idx in df.index[ic_filled]:
                conta = str(df.at[idx, "conta_contabil"])
                ic_val = str(df.at[idx, ic_col]).strip()
                issues.append({
                    "regra": "R033",
                    "conta_contabil": conta,
                    "campo": f"IC{n}/TIPO{n}",
                    "valor_encontrado": f"IC{n}='{ic_val}' presente mas TIPO{n} está vazio",
                    "competencia": competencia,
                })
            continue

        ic_filled = ~df[ic_col].fillna("").astype(str).str.strip().str.lower().isin(_IC_EMPTY_VALS)
        tipo_filled = df[tipo_col].astype(str).str.strip().ne("")
        mismatch = ic_filled.ne(tipo_filled)

        if not mismatch.any():
            continue

        for idx in df.index[mismatch]:
            conta = str(df.at[idx, "conta_contabil"])
            ic_val = str(df.at[idx, ic_col]).strip()
            tipo_val = str(df.at[idx, tipo_col]).strip()
            if ic_filled.at[idx]:
                descricao = f"IC{n}='{ic_val}' presente mas TIPO{n} está vazio"
            else:
                descricao = f"TIPO{n}='{tipo_val}' presente mas IC{n} está vazio"
            issues.append({
                "regra": "R033",
                "conta_contabil": conta,
                "campo": f"IC{n}/TIPO{n}",
                "valor_encontrado": descricao,
                "competencia": competencia,
            })

    return issues


def _check_ic_order(
    df: pd.DataFrame,
    competencia: str,
) -> list[dict[str, object]]:
    """Verifica que as ICs seguem a ordem canônica do leiaute MSC (R082).

    Para cada linha, extrai a sequência de tipos não-vazios (tipo1..tipo6) e
    verifica se é uma das sequências válidas definidas no IC_MAP.  Linhas sem
    nenhuma IC são ignoradas.

    **Filtro de Emparelhamento:** Linhas com pares IC/TIPO desemparelhados
    (onde um existe e o outro não) são ignoradas na checagem de ordem
    (já são pegas pela R033), evitando alertas R082 falsos em registros malformados.
    Isso é verificado registro a registro, permitindo que contas com múltiplas
    linhas ainda sejam verificadas onde os pares estão corretos.

    Args:
        df: DataFrame pivotado com colunas tipo1..tipo6 e ic1..ic6.
        competencia: competência do arquivo.

    Returns:
        Lista de issues com ``"regra": "R082"``.
    """
    if df.empty:
        return []

    tipo_cols = [f"tipo{n}" for n in range(1, 7) if f"tipo{n}" in df.columns]
    if not tipo_cols:
        return []

    issues: list[dict[str, object]] = []

    for _, row in df.iterrows():
        conta = str(row.get("conta_contabil", ""))

        # Verificar que cada tipo não-vazio está emparelhado com IC preenchido
        # e vice-versa, apenas para a linha atual (defesa contra R033).
        # Se houver inconsistência, a ordem é inválida e não checamos.
        tipos: list[str] = []
        is_consistent = True

        for n in range(1, 7):
            tipo_col = f"tipo{n}"
            ic_col = f"ic{n}"

            tipo_val = str(row.get(tipo_col, "")).strip().upper()
            ic_val = str(row.get(ic_col, "")).strip()
            ic_is_filled = ic_val.lower() not in _IC_EMPTY_VALS

            if bool(tipo_val) != ic_is_filled:
                is_consistent = False
                break

            if tipo_val:
                tipos.append(tipo_val)

        if not is_consistent:
            continue

        tipos_tuple = tuple(tipos)
        if not tipos_tuple:
            continue

        if tipos_tuple not in _IC_VALID_ORDERS:
            issues.append({
                "regra": "R082",
                "conta_contabil": conta,
                "campo": "ordem_IC",
                "valor_encontrado": ",".join(tipos_tuple),
                "competencia": competencia,
            })

    return issues
