"""
ranking_msc.benchmark.generator
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Geração de CSVs MSC sintéticos para benchmark de performance.

Produz arquivos no mesmo formato dos CSVs reais em ``ref/amostras/``:
    - Delimiter ``;``
    - Line ending ``\\r`` (Mac Classic)
    - Header na linha 2 com colunas do layout MSC
    - Linha 1: metadata ``<siconfi>;<competencia>``

Os dados são gerados a partir das tabelas de referência reais
(``ref/mapeamento_ic_tipo.csv`` e ``ref/pcasp.csv``) para garantir
que o pipeline consiga processá-los sem erros de formato.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

from ranking_msc.exceptions import BenchmarkError

logger = logging.getLogger("ranking_msc")

_TIPO_VALOR_OPTIONS: list[str] = [
    "beginning_balance",
    "period_change",
    "ending_balance",
]
_NATUREZA_VALOR_OPTIONS: list[str] = ["D", "C"]

_CSV_HEADER: list[str] = [
    "CONTA", "IC1", "TIPO1", "IC2", "TIPO2", "IC3", "TIPO3",
    "IC4", "TIPO4", "IC5", "TIPO5", "IC6", "TIPO6",
    "Valor", "Tipo_valor", "Natureza_valor",
]

# Valores fictícios mas estruturalmente válidos para cada tipo de IC
_FAKE_IC_VALUES: dict[str, str] = {
    "PO": "10100",
    "FP": "1",
    "DC": "0",
    "FR": "150000000000",
    "CO": "999",
    "NR": "111101110000",
    "ND": "339039000000",
    "FS": "1212",
    "AI": "2025",
}


def generate_csv(
    n_rows: int,
    path: Path,
    *,
    seed: int = 42,
    ref_dir: str | Path = "ref",
    siconfi: str = "9999999EX",
    competencia: str = "2026-01",
) -> Path:
    """Gera CSV MSC sintético com n_rows linhas de dados.

    Args:
        n_rows: número de linhas de dados a gerar.
        path: caminho de destino do CSV.
        seed: seed para reprodutibilidade.
        ref_dir: diretório com tabelas de referência.
        siconfi: código SICONFI fictício para a linha de metadata.
        competencia: competência fictícia no formato YYYY-MM.

    Returns:
        Caminho do CSV gerado (mesmo que ``path``).

    Raises:
        BenchmarkError: se as tabelas de referência não forem encontradas
            ou não contiverem dados suficientes.
    """
    ref_path = Path(ref_dir)
    rng = np.random.default_rng(seed)

    contas = _load_contas_analiticas(ref_path)
    ic_tipo_combos = _load_ic_tipo_combinations(ref_path)

    if not contas:
        raise BenchmarkError(
            "Nenhuma conta analítica encontrada em ref/pcasp.csv. "
            "Verifique se o arquivo existe e contém dados."
        )
    if not ic_tipo_combos:
        raise BenchmarkError(
            "Nenhuma combinação IC/TIPO encontrada em ref/mapeamento_ic_tipo.csv. "
            "Verifique se o arquivo existe e contém dados."
        )

    logger.info(
        "Gerando CSV sintético: n_rows=%d, path=%s, seed=%d",
        n_rows, path, seed,
    )

    # Sortear dados
    conta_indices = rng.integers(0, len(contas), size=n_rows)
    combo_indices = rng.integers(0, len(ic_tipo_combos), size=n_rows)
    valores = rng.uniform(-1e7, 1e7, size=n_rows)
    tipo_valor_indices = rng.integers(0, len(_TIPO_VALOR_OPTIONS), size=n_rows)
    natureza_indices = rng.integers(0, len(_NATUREZA_VALOR_OPTIONS), size=n_rows)

    rows: list[list[str]] = []
    for i in range(n_rows):
        conta = contas[conta_indices[i]]
        combo = ic_tipo_combos[combo_indices[i]]
        valor = f"{valores[i]:.2f}"
        tipo_valor = _TIPO_VALOR_OPTIONS[tipo_valor_indices[i]]
        natureza = _NATUREZA_VALOR_OPTIONS[natureza_indices[i]]

        row = [conta]
        # IC1-IC6 e TIPO1-TIPO6: preencher a partir da combinação
        for j in range(6):
            ic_val = combo.get(f"ic{j + 1}", "")
            tipo_val = combo.get(f"tipo{j + 1}", "")
            row.append(ic_val)
            row.append(tipo_val)
        row.extend([valor, tipo_valor, natureza])
        rows.append(row)

    # Montar conteúdo do CSV
    metadata_line = f"{siconfi};{competencia}"
    header_line = ";".join(_CSV_HEADER)

    lines = [metadata_line, header_line]
    for row in rows:
        lines.append(";".join(row))

    # Escrever com line ending \r (Mac Classic)
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "\r".join(lines) + "\r"
    path.write_bytes(content.encode("ascii"))

    logger.info("CSV sintético gerado: %s (%d linhas)", path, n_rows)
    return path


def _load_contas_analiticas(ref_dir: Path) -> list[str]:
    """Carrega contas analíticas de ref/pcasp.csv.

    Filtra pelo nível mais detalhado disponível. No PCASP da STN, a
    coluna ``nivel`` assume os valores ``Superior`` (contas de síntese
    de níveis superiores) e ``Último`` (contas analíticas, folhas da
    árvore). Apenas as ``Último`` devem alimentar o benchmark, para
    que o perfil do dataset sintético seja representativo dos CSVs
    MSC reais.

    Returns:
        Lista de strings com códigos de contas contábeis do nível
        analítico (``Último``).
    """
    pcasp_path = ref_dir / "pcasp.csv"
    if not pcasp_path.exists():
        raise BenchmarkError(f"Tabela PCASP não encontrada: {pcasp_path}")

    try:
        df = pd.read_csv(pcasp_path, dtype=str, sep=";", keep_default_na=False)
    except Exception as exc:  # noqa: BLE001
        raise BenchmarkError(f"Falha ao ler PCASP: {exc}") from exc

    if "conta_contabil" not in df.columns:
        raise BenchmarkError(
            f"Coluna 'conta_contabil' não encontrada em {pcasp_path}. "
            f"Colunas disponíveis: {list(df.columns)}"
        )
    if "nivel" not in df.columns:
        raise BenchmarkError(
            f"Coluna 'nivel' não encontrada em {pcasp_path}. "
            f"Colunas disponíveis: {list(df.columns)}"
        )

    df["nivel"] = df["nivel"].str.strip()
    analiticas = df[df["nivel"].str.lower() == "último"]["conta_contabil"].tolist()
    if not analiticas:
        niveis_encontrados = sorted(df["nivel"].unique().tolist())
        raise BenchmarkError(
            f"Nenhuma conta analítica (nivel='Último') encontrada em {pcasp_path}. "
            f"Níveis presentes: {niveis_encontrados}"
        )
    return analiticas


def _load_ic_tipo_combinations(ref_dir: Path) -> list[dict[str, str]]:
    """Carrega combinações IC/TIPO de ref/mapeamento_ic_tipo.csv.

    Cada combinação é um dicionário com chaves tipo1..tipo6,
    com valores de IC gerados aleatoriamente para os tipos preenchidos.

    Returns:
        Lista de dicts com chaves ic1..ic6, tipo1..tipo6.
    """
    mapping_path = ref_dir / "mapeamento_ic_tipo.csv"
    if not mapping_path.exists():
        raise BenchmarkError(
            f"Mapeamento IC/TIPO não encontrado: {mapping_path}"
        )

    try:
        df = pd.read_csv(mapping_path, sep=";", dtype=str, keep_default_na=False)
    except Exception as exc:  # noqa: BLE001
        raise BenchmarkError(f"Falha ao ler mapeamento IC/TIPO: {exc}") from exc

    combos: list[dict[str, str]] = []

    for _, row in df.iterrows():
        combo: dict[str, str] = {}
        for i in range(1, 7):
            tipo_col = f"tipo{i}"
            tipo_val = str(row.get(tipo_col, "")).strip()
            combo[tipo_col] = tipo_val
            # Se o tipo está preenchido, gerar um valor IC fictício
            if tipo_val:
                combo[f"ic{i}"] = _generate_ic_value(tipo_val)
            else:
                combo[f"ic{i}"] = ""
        combos.append(combo)

    return combos


def _generate_ic_value(tipo: str) -> str:
    """Gera valor fictício para uma IC dado seu tipo.

    Args:
        tipo: código do tipo (PO, FP, DC, FR, CO, NR, ND, FS, AI).

    Returns:
        String com valor fictício válido para o tipo.
    """
    return _FAKE_IC_VALUES.get(tipo.strip().upper(), "0")
