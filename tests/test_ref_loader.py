"""
tests/test_ref_loader.py
~~~~~~~~~~~~~~~~~~~~~~~~

Testes dos carregadores de referência em ``ranking_msc.io.ref_loader``.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

import ranking_msc.io.ref_loader as ref_loader
from ranking_msc.exceptions import ConfigError
from ranking_msc.io.reader_msc import read_msc_csv
from ranking_msc.io.ref_loader import load_dominios_fr, load_pcasp
from ranking_msc.transform.ic_normalize import normalize_ic


@pytest.fixture(autouse=True)
def clear_ref_loader_cache() -> None:
    """Limpa cache de referências entre testes para evitar efeito colateral."""
    ref_loader._CACHE_PCASP.clear()
    ref_loader._CACHE_DOMINIOS_FR.clear()


def test_load_pcasp_retorna_dataframe_com_coluna_conta() -> None:
    """Carrega PCASP padrão e retorna DataFrame com conta_contabil."""
    df = load_pcasp()
    assert isinstance(df, pd.DataFrame)
    assert "conta_contabil" in df.columns
    assert len(df) > 0


def test_load_pcasp_contem_contas_dos_csvs_reais() -> None:
    """Todas as contas das amostras reais devem existir no PCASP carregado."""
    csvs = sorted(Path("ref/amostras").glob("msc_*.csv"))
    if not csvs:
        pytest.skip("Nenhuma amostra real encontrada em ref/amostras")

    pcasp_df = load_pcasp()
    contas_pcasp = set(pcasp_df["conta_contabil"].astype(str))

    contas_amostras: set[str] = set()
    for csv_path in csvs:
        raw = read_msc_csv(csv_path)
        contas_amostras.update(raw.df["conta_contabil"].astype(str).unique())

    missing = contas_amostras - contas_pcasp
    assert not missing, f"Contas das amostras ausentes no PCASP: {sorted(missing)[:20]}"


def test_load_pcasp_segunda_chamada_usa_cache(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Evita novo I/O na segunda chamada para o mesmo caminho."""
    ref_dir = tmp_path / "ref"
    ref_dir.mkdir(parents=True, exist_ok=True)
    (ref_dir / "pcasp.csv").write_text(
        "conta_contabil;id_ic\n111110200;4\n531100000;4\n",
        encoding="utf-8",
    )

    call_count = 0
    original_read_csv = ref_loader.pd.read_csv

    def tracked_read_csv(*args: object, **kwargs: object) -> pd.DataFrame:
        nonlocal call_count
        call_count += 1
        return original_read_csv(*args, **kwargs)

    monkeypatch.setattr(ref_loader.pd, "read_csv", tracked_read_csv)

    first = load_pcasp(ref_dir=ref_dir)
    second = load_pcasp(ref_dir=ref_dir)

    assert len(first) == 2
    assert len(second) == 2
    assert call_count == 1


def test_load_pcasp_arquivo_ausente_levanta_configerror(tmp_path: Path) -> None:
    """Levanta ConfigError quando pcasp.csv não existe no ref_dir."""
    with pytest.raises(ConfigError, match="não encontrada"):
        load_pcasp(ref_dir=tmp_path / "ref_inexistente")


def test_load_dominios_fr_retorna_dataframe_com_colunas_esperadas() -> None:
    """Carrega domínio FR padrão e retorna colunas esperadas."""
    df = load_dominios_fr()
    assert isinstance(df, pd.DataFrame)
    assert {"fr", "prefixo_exercicio", "codigo_base"}.issubset(df.columns)
    assert len(df) > 0


def test_load_dominios_fr_contem_fontes_das_amostras_reais() -> None:
    """Fontes FR observadas nas amostras reais devem existir no domínio FR."""
    csvs = sorted(Path("ref/amostras").glob("msc_*.csv"))
    if not csvs:
        pytest.skip("Nenhuma amostra real encontrada em ref/amostras")

    dominios_df = load_dominios_fr()
    fr_validas = set(dominios_df["fr"].astype(str))

    fr_amostras: set[str] = set()
    for csv_path in csvs:
        raw = read_msc_csv(csv_path)
        normalized = normalize_ic(raw.df)
        values = normalized["fr"].astype(str).str.strip()
        fr_amostras.update(v for v in values.unique() if v)

    missing = fr_amostras - fr_validas
    assert not missing, f"Fontes FR das amostras ausentes no domínio: {sorted(missing)[:20]}"


def test_load_dominios_fr_segunda_chamada_usa_cache(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Evita novo I/O na segunda chamada de domínio FR para o mesmo caminho."""
    ref_dir = tmp_path / "ref"
    ref_dir.mkdir(parents=True, exist_ok=True)
    (ref_dir / "dominios_fr.csv").write_text(
        "fr;prefixo_exercicio;codigo_base\n1500;1;500\n2500;2;500\n",
        encoding="utf-8",
    )

    call_count = 0
    original_read_csv = ref_loader.pd.read_csv

    def tracked_read_csv(*args: object, **kwargs: object) -> pd.DataFrame:
        nonlocal call_count
        call_count += 1
        return original_read_csv(*args, **kwargs)

    monkeypatch.setattr(ref_loader.pd, "read_csv", tracked_read_csv)

    first = load_dominios_fr(ref_dir=ref_dir)
    second = load_dominios_fr(ref_dir=ref_dir)

    assert len(first) == 2
    assert len(second) == 2
    assert call_count == 1


def test_load_dominios_fr_arquivo_ausente_levanta_configerror(tmp_path: Path) -> None:
    """Levanta ConfigError quando dominios_fr.csv não existe no ref_dir."""
    with pytest.raises(ConfigError, match="não encontrada"):
        load_dominios_fr(ref_dir=tmp_path / "ref_inexistente")
