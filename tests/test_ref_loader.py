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
from ranking_msc.io.ref_loader import (
    FP_DOMAIN,
    IC_DIGITOS,
    IC_MAP,
    clear_all_caches,
    load_dominios_fr,
    load_pcasp,
    load_tabela_co,
    load_tabela_fr,
    load_tabela_fs,
    load_tabela_nd,
    load_tabela_nr,
    load_tabela_po,
)
from ranking_msc.transform.ic_normalize import normalize_ic


@pytest.fixture(autouse=True)
def _clear_ref_loader_cache() -> None:
    """Limpa cache de referências entre testes para evitar efeito colateral."""
    clear_all_caches()


# ===================================================================
# Constantes IC_MAP e IC_DIGITOS
# ===================================================================


class TestICMap:
    """Testes das constantes IC_MAP e IC_DIGITOS."""

    def test_ic_map_contem_todos_ids(self) -> None:
        """IC_MAP deve conter IDs de 0 a 9."""
        assert set(IC_MAP.keys()) == set(range(10))

    def test_ic_map_id0_vazio(self) -> None:
        """ID_IC=0 não exige nenhuma IC."""
        assert IC_MAP[0] == []

    def test_ic_map_id1_apenas_po(self) -> None:
        """ID_IC=1 exige apenas PO."""
        assert IC_MAP[1] == ["PO"]

    def test_ic_map_id9_completo(self) -> None:
        """ID_IC=9 exige o conjunto completo com AI."""
        assert IC_MAP[9] == ["PO", "FS", "FR", "CO", "ND", "AI"]

    def test_ic_digitos_contem_todos_tipos(self) -> None:
        """IC_DIGITOS deve mapear todos os tipos de IC."""
        assert set(IC_DIGITOS.keys()) == {"PO", "FP", "DC", "FR", "CO", "NR", "ND", "FS", "AI"}

    def test_ic_digitos_valores(self) -> None:
        """Verifica dígitos esperados por tipo."""
        assert IC_DIGITOS["PO"] == 5
        assert IC_DIGITOS["FP"] == 1
        assert IC_DIGITOS["DC"] == 1
        assert IC_DIGITOS["FR"] == 4
        assert IC_DIGITOS["CO"] == 4
        assert IC_DIGITOS["NR"] == 8
        assert IC_DIGITOS["ND"] == 8
        assert IC_DIGITOS["FS"] == 5
        assert IC_DIGITOS["AI"] == 4

    def test_fp_domain(self) -> None:
        """FP_DOMAIN deve conter apenas '1' e '2'."""
        assert FP_DOMAIN == frozenset({"1", "2"})


# ===================================================================
# PCASP
# ===================================================================


class TestLoadPcasp:
    """Testes de load_pcasp."""

    def test_retorna_dataframe_com_coluna_conta(self) -> None:
        """Carrega PCASP padrão e retorna DataFrame com conta_contabil."""
        df = load_pcasp()
        assert isinstance(df, pd.DataFrame)
        assert "conta_contabil" in df.columns
        assert len(df) > 0

    def test_pcasp_contem_colunas_extras(self) -> None:
        """PCASP deve conter colunas de domínio: nat_saldo, status, nivel, ind_sf."""
        df = load_pcasp()
        for col in ("id_ic", "nat_saldo", "status", "nivel", "ind_sf"):
            assert col in df.columns, f"Coluna '{col}' ausente no PCASP"

    def test_contem_contas_dos_csvs_reais(self) -> None:
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

    def test_segunda_chamada_usa_cache(
        self,
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

    def test_arquivo_ausente_levanta_configerror(self, tmp_path: Path) -> None:
        """Levanta ConfigError quando pcasp.csv não existe no ref_dir."""
        with pytest.raises(ConfigError, match="não encontrada"):
            load_pcasp(ref_dir=tmp_path / "ref_inexistente")


# ===================================================================
# Domínios FR
# ===================================================================


class TestLoadDominiosFr:
    """Testes de load_dominios_fr."""

    def test_retorna_dataframe_com_colunas_esperadas(self) -> None:
        """Carrega domínio FR padrão e retorna colunas esperadas."""
        df = load_dominios_fr()
        assert isinstance(df, pd.DataFrame)
        assert {"fr", "prefixo_exercicio", "codigo_base"}.issubset(df.columns)
        assert len(df) > 0

    def test_contem_fontes_das_amostras_reais(self) -> None:
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
        assert not missing, (
            f"Fontes FR das amostras ausentes no domínio: {sorted(missing)[:20]}"
        )

    def test_segunda_chamada_usa_cache(
        self,
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

    def test_arquivo_ausente_levanta_configerror(self, tmp_path: Path) -> None:
        """Levanta ConfigError quando dominios_fr.csv não existe no ref_dir."""
        with pytest.raises(ConfigError, match="não encontrada"):
            load_dominios_fr(ref_dir=tmp_path / "ref_inexistente")


# ===================================================================
# Tabela PO
# ===================================================================


class TestLoadTabelaPo:
    """Testes de load_tabela_po."""

    def test_retorna_dataframe_com_coluna_codigo(self) -> None:
        """Carrega tabela PO e retorna DataFrame com coluna codigo."""
        df = load_tabela_po()
        assert isinstance(df, pd.DataFrame)
        assert "codigo" in df.columns
        assert len(df) > 0

    def test_codigos_tem_5_digitos(self) -> None:
        """Todos os códigos PO devem ter 5 dígitos."""
        df = load_tabela_po()
        assert all(len(c) == 5 and c.isdigit() for c in df["codigo"])

    def test_contem_po_das_amostras_reais(self) -> None:
        """POs observados nas amostras reais devem existir na tabela PO."""
        csvs = sorted(Path("ref/amostras").glob("msc_*.csv"))
        if not csvs:
            pytest.skip("Nenhuma amostra real encontrada em ref/amostras")

        po_df = load_tabela_po()
        po_validos = set(po_df["codigo"].astype(str))

        po_amostras: set[str] = set()
        for csv_path in csvs:
            raw = read_msc_csv(csv_path)
            normalized = normalize_ic(raw.df)
            values = normalized["po"].astype(str).str.strip()
            po_amostras.update(v for v in values.unique() if v and v != "nan")

        missing = po_amostras - po_validos
        assert not missing, f"POs das amostras ausentes na tabela: {sorted(missing)}"

    def test_segunda_chamada_usa_cache(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """Evita novo I/O na segunda chamada."""
        ref_dir = tmp_path / "ref"
        ref_dir.mkdir(parents=True, exist_ok=True)
        (ref_dir / "tabela_po.csv").write_text(
            "codigo\n10131\n10132\n",
            encoding="utf-8",
        )

        call_count = 0
        original_read_csv = ref_loader.pd.read_csv

        def tracked_read_csv(*args: object, **kwargs: object) -> pd.DataFrame:
            nonlocal call_count
            call_count += 1
            return original_read_csv(*args, **kwargs)

        monkeypatch.setattr(ref_loader.pd, "read_csv", tracked_read_csv)

        first = load_tabela_po(ref_dir=ref_dir)
        second = load_tabela_po(ref_dir=ref_dir)

        assert len(first) == 2
        assert len(second) == 2
        assert call_count == 1

    def test_arquivo_ausente_levanta_configerror(self, tmp_path: Path) -> None:
        """Levanta ConfigError quando tabela_po.csv não existe."""
        with pytest.raises(ConfigError, match="não encontrada"):
            load_tabela_po(ref_dir=tmp_path / "ref_inexistente")


# ===================================================================
# Tabela CO
# ===================================================================


class TestLoadTabelaCo:
    """Testes de load_tabela_co."""

    def test_retorna_dataframe_com_coluna_codigo(self) -> None:
        """Carrega tabela CO e retorna DataFrame com coluna codigo."""
        df = load_tabela_co()
        assert isinstance(df, pd.DataFrame)
        assert "codigo" in df.columns
        assert len(df) > 0

    def test_codigos_tem_4_digitos(self) -> None:
        """Todos os códigos CO devem ter 4 dígitos."""
        df = load_tabela_co()
        assert all(len(c) == 4 and c.isdigit() for c in df["codigo"])

    def test_contem_co_das_amostras_reais(self) -> None:
        """COs observados nas amostras reais devem existir na tabela CO."""
        csvs = sorted(Path("ref/amostras").glob("msc_*.csv"))
        if not csvs:
            pytest.skip("Nenhuma amostra real encontrada em ref/amostras")

        co_df = load_tabela_co()
        co_validos = set(co_df["codigo"].astype(str))

        co_amostras: set[str] = set()
        for csv_path in csvs:
            raw = read_msc_csv(csv_path)
            normalized = normalize_ic(raw.df)
            values = normalized["co"].astype(str).str.strip()
            co_amostras.update(v for v in values.unique() if v and v != "nan")

        missing = co_amostras - co_validos
        assert not missing, f"COs das amostras ausentes na tabela: {sorted(missing)}"

    def test_segunda_chamada_usa_cache(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """Evita novo I/O na segunda chamada."""
        ref_dir = tmp_path / "ref"
        ref_dir.mkdir(parents=True, exist_ok=True)
        (ref_dir / "tabela_co.csv").write_text(
            "codigo\n1001\n1002\n",
            encoding="utf-8",
        )

        call_count = 0
        original_read_csv = ref_loader.pd.read_csv

        def tracked_read_csv(*args: object, **kwargs: object) -> pd.DataFrame:
            nonlocal call_count
            call_count += 1
            return original_read_csv(*args, **kwargs)

        monkeypatch.setattr(ref_loader.pd, "read_csv", tracked_read_csv)

        first = load_tabela_co(ref_dir=ref_dir)
        second = load_tabela_co(ref_dir=ref_dir)

        assert len(first) == 2
        assert len(second) == 2
        assert call_count == 1

    def test_arquivo_ausente_levanta_configerror(self, tmp_path: Path) -> None:
        """Levanta ConfigError quando tabela_co.csv não existe."""
        with pytest.raises(ConfigError, match="não encontrada"):
            load_tabela_co(ref_dir=tmp_path / "ref_inexistente")


# ===================================================================
# Tabela FR (códigos-raiz)
# ===================================================================


class TestLoadTabelaFr:
    """Testes de load_tabela_fr."""

    def test_retorna_dataframe_com_colunas_esperadas(self) -> None:
        """Carrega tabela FR e retorna colunas codigo_base e nome."""
        df = load_tabela_fr()
        assert isinstance(df, pd.DataFrame)
        assert {"codigo_base", "nome"}.issubset(df.columns)
        assert len(df) > 0

    def test_codigos_tem_3_digitos(self) -> None:
        """Todos os códigos-raiz FR devem ter exatamente 3 dígitos numéricos."""
        df = load_tabela_fr()
        assert all(len(c) == 3 and c.isdigit() for c in df["codigo_base"])

    def test_contem_fr_das_amostras_reais(self) -> None:
        """Códigos-raiz FR das amostras reais devem existir na tabela FR."""
        csvs = sorted(Path("ref/amostras").glob("msc_*.csv"))
        if not csvs:
            pytest.skip("Nenhuma amostra real encontrada em ref/amostras")

        fr_df = load_tabela_fr()
        fr_validos = set(fr_df["codigo_base"].astype(str))

        fr_amostras: set[str] = set()
        for csv_path in csvs:
            raw = read_msc_csv(csv_path)
            normalized = normalize_ic(raw.df)
            values = normalized["fr"].astype(str).str.strip()
            for v in values.unique():
                if v and v != "nan" and len(v) >= 3:
                    fr_amostras.add(v[1:])  # remove prefixo de exercício (1/2/9)

        missing = fr_amostras - fr_validos
        assert not missing, (
            f"Códigos-raiz FR das amostras ausentes na tabela: {sorted(missing)[:20]}"
        )

    def test_segunda_chamada_usa_cache(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """Evita novo I/O na segunda chamada."""
        ref_dir = tmp_path / "ref"
        ref_dir.mkdir(parents=True, exist_ok=True)
        (ref_dir / "tabela_fr.csv").write_text(
            "codigo_base;nome\n500;Recursos Diversos\n501;Outro\n",
            encoding="utf-8",
        )

        call_count = 0
        original_read_csv = ref_loader.pd.read_csv

        def tracked_read_csv(*args: object, **kwargs: object) -> pd.DataFrame:
            nonlocal call_count
            call_count += 1
            return original_read_csv(*args, **kwargs)

        monkeypatch.setattr(ref_loader.pd, "read_csv", tracked_read_csv)

        first = load_tabela_fr(ref_dir=ref_dir)
        second = load_tabela_fr(ref_dir=ref_dir)

        assert len(first) == 2
        assert len(second) == 2
        assert call_count == 1

    def test_arquivo_ausente_levanta_configerror(self, tmp_path: Path) -> None:
        """Levanta ConfigError quando tabela_fr.csv não existe."""
        with pytest.raises(ConfigError, match="não encontrada"):
            load_tabela_fr(ref_dir=tmp_path / "ref_inexistente")


# ===================================================================
# Tabela NR
# ===================================================================


class TestLoadTabelaNr:
    """Testes de load_tabela_nr."""

    def test_retorna_dataframe_com_colunas_esperadas(self) -> None:
        """Carrega tabela NR e retorna colunas codigo e valorizavel."""
        df = load_tabela_nr()
        assert isinstance(df, pd.DataFrame)
        assert {"codigo", "valorizavel"}.issubset(df.columns)
        assert len(df) > 0

    def test_codigos_tem_8_digitos(self) -> None:
        """Todos os códigos NR devem ter 8 dígitos."""
        df = load_tabela_nr()
        assert all(len(c) == 8 and c.isdigit() for c in df["codigo"])

    def test_maioria_nr_das_amostras_existe_na_tabela(self) -> None:
        """A grande maioria das NRs das amostras deve existir na tabela oficial.

        Algumas NRs usadas pelo município podem não constar no ementário STN 2026
        — esse tipo de divergência é exatamente o que a regra R026 deve detectar.
        """
        csvs = sorted(Path("ref/amostras").glob("msc_*.csv"))
        if not csvs:
            pytest.skip("Nenhuma amostra real encontrada em ref/amostras")

        nr_df = load_tabela_nr()
        nr_validos = set(nr_df["codigo"].astype(str))

        nr_amostras: set[str] = set()
        for csv_path in csvs:
            raw = read_msc_csv(csv_path)
            normalized = normalize_ic(raw.df)
            values = normalized["nr"].astype(str).str.strip()
            nr_amostras.update(v for v in values.unique() if v and v != "nan")

        cobertura = len(nr_amostras & nr_validos) / len(nr_amostras)
        assert cobertura >= 0.90, (
            f"Cobertura NR das amostras muito baixa: {cobertura:.1%}"
        )

    def test_valorizavel_dominio_valido(self) -> None:
        """Coluna valorizavel deve conter apenas SIM ou NÃO."""
        df = load_tabela_nr()
        assert df["valorizavel"].isin({"SIM", "NÃO"}).all()

    def test_segunda_chamada_usa_cache(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """Evita novo I/O na segunda chamada."""
        ref_dir = tmp_path / "ref"
        ref_dir.mkdir(parents=True, exist_ok=True)
        (ref_dir / "tabela_nr.csv").write_text(
            "codigo;valorizavel\n11125001;SIM\n11125002;SIM\n",
            encoding="utf-8",
        )

        call_count = 0
        original_read_csv = ref_loader.pd.read_csv

        def tracked_read_csv(*args: object, **kwargs: object) -> pd.DataFrame:
            nonlocal call_count
            call_count += 1
            return original_read_csv(*args, **kwargs)

        monkeypatch.setattr(ref_loader.pd, "read_csv", tracked_read_csv)

        first = load_tabela_nr(ref_dir=ref_dir)
        second = load_tabela_nr(ref_dir=ref_dir)

        assert len(first) == 2
        assert len(second) == 2
        assert call_count == 1

    def test_arquivo_ausente_levanta_configerror(self, tmp_path: Path) -> None:
        """Levanta ConfigError quando tabela_nr.csv não existe."""
        with pytest.raises(ConfigError, match="não encontrada"):
            load_tabela_nr(ref_dir=tmp_path / "ref_inexistente")


# ===================================================================
# Tabela ND
# ===================================================================


class TestLoadTabelaNd:
    """Testes de load_tabela_nd."""

    def test_retorna_dataframe_com_colunas_esperadas(self) -> None:
        """Carrega tabela ND e retorna colunas codigo, nivel e nome."""
        df = load_tabela_nd()
        assert isinstance(df, pd.DataFrame)
        assert {"codigo", "nivel", "nome"}.issubset(df.columns)
        assert len(df) > 0

    def test_codigos_tem_8_digitos(self) -> None:
        """Todos os códigos ND devem ter 8 dígitos."""
        df = load_tabela_nd()
        assert all(len(c) == 8 and c.isdigit() for c in df["codigo"])

    def test_contem_nd_das_amostras_reais(self) -> None:
        """NDs observadas nas amostras reais devem existir na tabela ND."""
        csvs = sorted(Path("ref/amostras").glob("msc_*.csv"))
        if not csvs:
            pytest.skip("Nenhuma amostra real encontrada em ref/amostras")

        nd_df = load_tabela_nd()
        nd_validos = set(nd_df["codigo"].astype(str))

        nd_amostras: set[str] = set()
        for csv_path in csvs:
            raw = read_msc_csv(csv_path)
            normalized = normalize_ic(raw.df)
            values = normalized["nd"].astype(str).str.strip()
            nd_amostras.update(v for v in values.unique() if v and v != "nan")

        missing = nd_amostras - nd_validos
        assert not missing, (
            f"NDs das amostras ausentes na tabela: {sorted(missing)[:20]}"
        )

    def test_segunda_chamada_usa_cache(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """Evita novo I/O na segunda chamada."""
        ref_dir = tmp_path / "ref"
        ref_dir.mkdir(parents=True, exist_ok=True)
        (ref_dir / "tabela_nd.csv").write_text(
            "codigo;nivel;nome\n33903099;Último;Material de consumo\n33904099;Último;Serviços\n",
            encoding="utf-8",
        )

        call_count = 0
        original_read_csv = ref_loader.pd.read_csv

        def tracked_read_csv(*args: object, **kwargs: object) -> pd.DataFrame:
            nonlocal call_count
            call_count += 1
            return original_read_csv(*args, **kwargs)

        monkeypatch.setattr(ref_loader.pd, "read_csv", tracked_read_csv)

        first = load_tabela_nd(ref_dir=ref_dir)
        second = load_tabela_nd(ref_dir=ref_dir)

        assert len(first) == 2
        assert len(second) == 2
        assert call_count == 1

    def test_arquivo_ausente_levanta_configerror(self, tmp_path: Path) -> None:
        """Levanta ConfigError quando tabela_nd.csv não existe."""
        with pytest.raises(ConfigError, match="não encontrada"):
            load_tabela_nd(ref_dir=tmp_path / "ref_inexistente")


# ===================================================================
# Tabela FS
# ===================================================================


class TestLoadTabelaFs:
    """Testes de load_tabela_fs."""

    def test_retorna_dataframe_com_colunas_esperadas(self) -> None:
        """Carrega tabela FS e retorna colunas funcao e subfuncao."""
        df = load_tabela_fs()
        assert isinstance(df, pd.DataFrame)
        assert {"funcao", "subfuncao"}.issubset(df.columns)
        assert len(df) > 0

    def test_funcao_2_digitos_subfuncao_3_digitos(self) -> None:
        """Função deve ter 2 dígitos e subfunção 3 dígitos."""
        df = load_tabela_fs()
        assert all(len(f) == 2 and f.isdigit() for f in df["funcao"])
        assert all(len(s) == 3 and s.isdigit() for s in df["subfuncao"])

    def test_contem_subfuncoes_das_amostras_reais(self) -> None:
        """Subfunções das amostras reais devem existir na tabela FS.

        Conforme Portaria MOG 42/99, subfunções podem combinar com qualquer
        função, então verificamos apenas a existência da subfunção.
        """
        csvs = sorted(Path("ref/amostras").glob("msc_*.csv"))
        if not csvs:
            pytest.skip("Nenhuma amostra real encontrada em ref/amostras")

        fs_df = load_tabela_fs()
        subfuncoes_validas = set(fs_df["subfuncao"].astype(str))

        subfuncoes_amostras: set[str] = set()
        for csv_path in csvs:
            raw = read_msc_csv(csv_path)
            normalized = normalize_ic(raw.df)
            fs_raw = normalized["fs"].astype(str).str.strip()
            for v in fs_raw.unique():
                if v and v != "nan" and len(v) == 5:
                    subfuncoes_amostras.add(v[2:])

        missing = subfuncoes_amostras - subfuncoes_validas
        assert not missing, (
            f"Subfunções das amostras ausentes na tabela: {sorted(missing)}"
        )

    def test_segunda_chamada_usa_cache(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """Evita novo I/O na segunda chamada."""
        ref_dir = tmp_path / "ref"
        ref_dir.mkdir(parents=True, exist_ok=True)
        (ref_dir / "tabela_fs.csv").write_text(
            "funcao;subfuncao\n01;031\n10;301\n",
            encoding="utf-8",
        )

        call_count = 0
        original_read_csv = ref_loader.pd.read_csv

        def tracked_read_csv(*args: object, **kwargs: object) -> pd.DataFrame:
            nonlocal call_count
            call_count += 1
            return original_read_csv(*args, **kwargs)

        monkeypatch.setattr(ref_loader.pd, "read_csv", tracked_read_csv)

        first = load_tabela_fs(ref_dir=ref_dir)
        second = load_tabela_fs(ref_dir=ref_dir)

        assert len(first) == 2
        assert len(second) == 2
        assert call_count == 1

    def test_arquivo_ausente_levanta_configerror(self, tmp_path: Path) -> None:
        """Levanta ConfigError quando tabela_fs.csv não existe."""
        with pytest.raises(ConfigError, match="não encontrada"):
            load_tabela_fs(ref_dir=tmp_path / "ref_inexistente")


# ===================================================================
# clear_all_caches
# ===================================================================


class TestClearAllCaches:
    """Testes de clear_all_caches."""

    def test_limpa_todos_os_caches(self, tmp_path: Path) -> None:
        """Limpar caches força re-leitura de todos os arquivos."""
        ref_dir = tmp_path / "ref"
        ref_dir.mkdir(parents=True, exist_ok=True)
        (ref_dir / "pcasp.csv").write_text(
            "conta_contabil;id_ic\n111110200;4\n",
            encoding="utf-8",
        )

        first = load_pcasp(ref_dir=ref_dir)
        assert len(first) == 1

        # Atualiza arquivo com mais linhas
        (ref_dir / "pcasp.csv").write_text(
            "conta_contabil;id_ic\n111110200;4\n531100000;4\n",
            encoding="utf-8",
        )

        # Sem limpar cache, retorna resultado antigo
        cached = load_pcasp(ref_dir=ref_dir)
        assert len(cached) == 1

        # Após limpar, re-lê do disco
        clear_all_caches()
        refreshed = load_pcasp(ref_dir=ref_dir)
        assert len(refreshed) == 2
