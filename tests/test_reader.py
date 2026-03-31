"""
tests/test_reader.py
~~~~~~~~~~~~~~~~~~~~

Testes de ``ranking_msc.io.reader_msc``.

Cobre leitura de CSV, extração de metadados, validação de colunas,
pivoteamento de valores e tratamento de erros.
"""

from __future__ import annotations

import io
from collections.abc import Callable
from pathlib import Path

import pytest

from ranking_msc.exceptions import InputFormatError
from ranking_msc.io.reader_msc import RawMSC, _extract_metadata, read_msc_csv
from ranking_msc.schemas import RAW_MSC_COLUMNS

# ---------------------------------------------------------------------------
# _extract_metadata
# ---------------------------------------------------------------------------

class TestExtractMetadata:
    """Testes da função _extract_metadata."""

    def test_metadata_valida_retorna_tupla(self) -> None:
        """Linha de metadata válida retorna (competencia, siconfi)."""
        comp, siconfi = _extract_metadata("2507507EX;2025-11")
        assert comp == "2025-11"
        assert siconfi == "2507507EX"

    def test_metadata_com_espacos_retorna_tupla(self) -> None:
        """Espaços ao redor são tolerados."""
        comp, siconfi = _extract_metadata("  2507507EX;2025-11  ")
        assert comp == "2025-11"
        assert siconfi == "2507507EX"

    def test_metadata_siconfi_numerico(self) -> None:
        """SICONFI puramente numérico também funciona."""
        comp, siconfi = _extract_metadata("250400;2024-01")
        assert comp == "2024-01"
        assert siconfi == "250400"

    def test_metadata_invalida_levanta_inputformaterror(self) -> None:
        """Formato inesperado levanta InputFormatError."""
        with pytest.raises(InputFormatError, match="formato inesperado"):
            _extract_metadata("dados;sem;formato;valido")

    def test_metadata_vazia_levanta_inputformaterror(self) -> None:
        """Linha vazia levanta InputFormatError."""
        with pytest.raises(InputFormatError, match="formato inesperado"):
            _extract_metadata("")

    def test_metadata_sem_competencia_levanta_inputformaterror(self) -> None:
        """Metadata sem competência YYYY-MM levanta InputFormatError."""
        with pytest.raises(InputFormatError, match="formato inesperado"):
            _extract_metadata("2507507EX;novembro")


# ---------------------------------------------------------------------------
# read_msc_csv — testes positivos
# ---------------------------------------------------------------------------

class TestReadMscCsvPositivo:
    """Testes de leitura bem-sucedida."""

    def test_leitura_por_path_retorna_rawmsc(self, msc_csv_path: Path) -> None:
        """Leitura via caminho de arquivo retorna RawMSC válido."""
        result = read_msc_csv(msc_csv_path)
        assert isinstance(result, RawMSC)
        assert result.competencia == "2025-11"
        assert result.siconfi == "2507507EX"
        assert result.source == str(msc_csv_path)

    def test_leitura_por_bytesio_retorna_rawmsc(self, msc_csv_bytesio: io.BytesIO) -> None:
        """Leitura via BytesIO retorna RawMSC válido."""
        result = read_msc_csv(msc_csv_bytesio)
        assert isinstance(result, RawMSC)
        assert result.competencia == "2025-11"
        assert result.siconfi == "2507507EX"

    def test_leitura_por_string_path(self, msc_csv_path: Path) -> None:
        """Leitura via string de caminho funciona."""
        result = read_msc_csv(str(msc_csv_path))
        assert isinstance(result, RawMSC)

    def test_colunas_raw_msc_presentes(self, msc_csv_path: Path) -> None:
        """DataFrame resultante tem todas as colunas de RAW_MSC_COLUMNS."""
        result = read_msc_csv(msc_csv_path)
        for col in RAW_MSC_COLUMNS:
            assert col in result.df.columns, f"Coluna '{col}' ausente no DataFrame"

    def test_pivot_valores_corretos(self, msc_csv_path: Path) -> None:
        """Valores pivotados correspondem aos dados de entrada."""
        result = read_msc_csv(msc_csv_path)
        row = result.df.iloc[0]
        assert row["saldo_inicial_debito"] == pytest.approx(1000.0)
        assert row["saldo_inicial_credito"] == pytest.approx(500.0)
        assert row["movimento_debito"] == pytest.approx(200.50)
        assert row["movimento_credito"] == pytest.approx(100.25)
        assert row["saldo_final_debito"] == pytest.approx(1100.25)
        assert row["saldo_final_credito"] == pytest.approx(600.25)

    def test_conta_contabil_mapeada(self, msc_csv_path: Path) -> None:
        """Coluna CONTA é renomeada para conta_contabil."""
        result = read_msc_csv(msc_csv_path)
        assert "conta_contabil" in result.df.columns
        assert "CONTA" not in result.df.columns
        assert result.df.iloc[0]["conta_contabil"] == "111110200"

    def test_ics_mapeadas_minusculo(self, msc_csv_path: Path) -> None:
        """Colunas IC/TIPO são renomeadas para minúsculo."""
        result = read_msc_csv(msc_csv_path)
        assert "ic1" in result.df.columns
        assert "tipo1" in result.df.columns
        assert "IC1" not in result.df.columns
        assert result.df.iloc[0]["ic1"] == "10131"
        assert result.df.iloc[0]["tipo1"] == "PO"

    def test_competencia_e_siconfi_no_dataframe(self, msc_csv_path: Path) -> None:
        """Colunas competencia e siconfi são adicionadas ao DataFrame."""
        result = read_msc_csv(msc_csv_path)
        assert all(result.df["competencia"] == "2025-11")
        assert all(result.df["siconfi"] == "2507507EX")

    def test_multiplas_contas_pivotadas(
        self, tmp_path: Path, build_msc_csv: Callable[..., bytes],
    ) -> None:
        """Duas contas distintas geram 2 linhas pivotadas."""
        rows = [
            # Conta 1
            ["111110200", "10131", "PO", "", "", "", "", "", "", "", "", "", "",
             "100.00", "beginning_balance", "D"],
            ["111110200", "10131", "PO", "", "", "", "", "", "", "", "", "", "",
             "50.00", "ending_balance", "D"],
            # Conta 2
            ["222220000", "10132", "PO", "", "", "", "", "", "", "", "", "", "",
             "300.00", "beginning_balance", "D"],
            ["222220000", "10132", "PO", "", "", "", "", "", "", "", "", "", "",
             "250.00", "ending_balance", "D"],
        ]
        csv_bytes = build_msc_csv(rows=rows)
        path = tmp_path / "multi.csv"
        path.write_bytes(csv_bytes)

        result = read_msc_csv(path)
        assert len(result.df) == 2

    def test_ics_vazias_preenchidas_como_string_vazia(self, msc_csv_path: Path) -> None:
        """ICs opcionais vazias são strings vazias, não NaN."""
        result = read_msc_csv(msc_csv_path)
        row = result.df.iloc[0]
        # IC4-IC6 estão vazias nos dados de teste
        assert row["ic4"] == ""
        assert row["tipo4"] == ""
        assert row["ic5"] == ""
        assert row["tipo5"] == ""

    def test_valores_ausentes_preenchidos_com_zero(
        self, tmp_path: Path, build_msc_csv: Callable[..., bytes],
    ) -> None:
        """Combinações Tipo_valor × Natureza_valor ausentes ficam com valor 0."""
        rows = [
            # Apenas beginning_balance;D — demais devem ser 0
            ["111110200", "10131", "PO", "", "", "", "", "", "", "", "", "", "",
             "1000.00", "beginning_balance", "D"],
        ]
        csv_bytes = build_msc_csv(rows=rows)
        path = tmp_path / "parcial.csv"
        path.write_bytes(csv_bytes)

        result = read_msc_csv(path)
        row = result.df.iloc[0]
        assert row["saldo_inicial_debito"] == pytest.approx(1000.0)
        assert row["saldo_inicial_credito"] == pytest.approx(0.0)
        assert row["movimento_debito"] == pytest.approx(0.0)
        assert row["movimento_credito"] == pytest.approx(0.0)
        assert row["saldo_final_debito"] == pytest.approx(0.0)
        assert row["saldo_final_credito"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# read_msc_csv — testes negativos
# ---------------------------------------------------------------------------

class TestReadMscCsvNegativo:
    """Testes de erro e validação."""

    def test_arquivo_vazio_levanta_inputformaterror(self, tmp_path: Path) -> None:
        """Arquivo vazio levanta InputFormatError."""
        path = tmp_path / "vazio.csv"
        path.write_bytes(b"")
        with pytest.raises(InputFormatError, match="vazio"):
            read_msc_csv(path)

    def test_arquivo_inexistente_levanta_inputformaterror(self) -> None:
        """Caminho inexistente levanta InputFormatError."""
        with pytest.raises(InputFormatError, match="Não foi possível ler"):
            read_msc_csv("/caminho/que/nao/existe.csv")

    def test_apenas_metadata_levanta_inputformaterror(self, tmp_path: Path) -> None:
        """Arquivo com apenas metadata (sem header/dados) levanta InputFormatError."""
        path = tmp_path / "so_meta.csv"
        path.write_bytes(b"2507507EX;2025-11")
        with pytest.raises(InputFormatError, match="mínimo 3"):
            read_msc_csv(path)

    def test_metadata_invalida_levanta_inputformaterror(self, tmp_path: Path) -> None:
        """Metadata malformada levanta InputFormatError."""
        content = b"invalido\rCONTA;IC1;TIPO1;Valor;Tipo_valor;Natureza_valor\r1;2;3;4;5;6"
        path = tmp_path / "bad_meta.csv"
        path.write_bytes(content)
        with pytest.raises(InputFormatError, match="formato inesperado"):
            read_msc_csv(path)

    def test_coluna_obrigatoria_ausente_levanta_inputformaterror(self, tmp_path: Path) -> None:
        """CSV sem coluna obrigatória levanta InputFormatError."""
        content = (
            b"2507507EX;2025-11\r"
            b"COLUNA_ERRADA;IC1;TIPO1;Valor;Tipo_valor;Natureza_valor\r"
            b"111;10131;PO;100;beginning_balance;D"
        )
        path = tmp_path / "sem_conta.csv"
        path.write_bytes(content)
        with pytest.raises(InputFormatError, match="críticas"):
            read_msc_csv(path)

    def test_csv_sem_dados_levanta_inputformaterror(self, tmp_path: Path) -> None:
        """CSV com header mas sem linhas de dados levanta InputFormatError."""
        content = (
            b"2507507EX;2025-11\r"
            b"CONTA;IC1;TIPO1;IC2;TIPO2;IC3;TIPO3;IC4;TIPO4;IC5;TIPO5;IC6;TIPO6"
            b";Valor;Tipo_valor;Natureza_valor"
        )
        path = tmp_path / "sem_dados.csv"
        path.write_bytes(content)
        with pytest.raises(InputFormatError, match="mínimo 3"):
            read_msc_csv(path)


# ---------------------------------------------------------------------------
# read_msc_csv — testes com CSV real (amostras)
# ---------------------------------------------------------------------------

class TestReadMscCsvReal:
    """Testes usando os CSVs reais de ref/amostras/."""

    @pytest.fixture
    def amostra_nov(self) -> Path:
        """Caminho para a amostra de novembro/2025."""
        path = Path("ref/amostras/msc_2025-11.csv")
        if not path.exists():
            pytest.skip("Amostra ref/amostras/msc_2025-11.csv não encontrada")
        return path

    @pytest.fixture
    def amostra_dez(self) -> Path:
        """Caminho para a amostra de dezembro/2025."""
        path = Path("ref/amostras/msc_2025-12.csv")
        if not path.exists():
            pytest.skip("Amostra ref/amostras/msc_2025-12.csv não encontrada")
        return path

    def test_leitura_amostra_nov(self, amostra_nov: Path) -> None:
        """Leitura da amostra de novembro retorna RawMSC válido."""
        result = read_msc_csv(amostra_nov)
        assert result.competencia == "2025-11"
        assert result.siconfi == "2507507EX"
        assert len(result.df) > 0
        for col in RAW_MSC_COLUMNS:
            assert col in result.df.columns

    def test_leitura_amostra_dez(self, amostra_dez: Path) -> None:
        """Leitura da amostra de dezembro retorna RawMSC válido."""
        result = read_msc_csv(amostra_dez)
        assert result.competencia == "2025-12"
        assert result.siconfi == "2507507EX"
        assert len(result.df) > 0

    def test_amostra_sem_nan(self, amostra_nov: Path) -> None:
        """Nenhuma coluna de texto tem NaN — devem ser strings vazias."""
        result = read_msc_csv(amostra_nov)
        str_cols = ["conta_contabil", "ic1", "tipo1", "ic2", "tipo2",
                    "ic3", "tipo3", "ic4", "tipo4", "ic5", "tipo5", "ic6", "tipo6"]
        for col in str_cols:
            assert result.df[col].isna().sum() == 0, f"Coluna '{col}' contém NaN"

    def test_amostra_valores_nao_negativos(self, amostra_nov: Path) -> None:
        """Valores monetários nunca são negativos."""
        result = read_msc_csv(amostra_nov)
        value_cols = [
            "saldo_inicial_debito", "saldo_inicial_credito",
            "movimento_debito", "movimento_credito",
            "saldo_final_debito", "saldo_final_credito",
        ]
        for col in value_cols:
            assert (result.df[col] >= 0).all(), f"Coluna '{col}' contém valores negativos"


# ---------------------------------------------------------------------------
# Reader — R001 (validação de colunas)
# ---------------------------------------------------------------------------


class TestReaderR001:
    """Testes do comportamento R001 no reader (colunas ausentes)."""

    def test_csv_com_todas_colunas_retorna_zero_issues_r001(
        self,
        build_msc_csv: Callable[..., bytes],
    ) -> None:
        """CSV com todas as 16 colunas → pre_pivot_issues sem R001."""
        raw = read_msc_csv(io.BytesIO(build_msc_csv()))
        r001 = [i for i in raw.pre_pivot_issues if i["regra"] == "R001"]
        assert r001 == []

    def test_csv_sem_coluna_ic5_coleta_issue_r001(
        self,
        build_msc_csv: Callable[..., bytes],
    ) -> None:
        """CSV sem IC5 → uma issue R001 com campo='IC5', sem levantar exceção."""
        header = (
            "CONTA;IC1;TIPO1;IC2;TIPO2;IC3;TIPO3;IC4;TIPO4"
            ";TIPO5;IC6;TIPO6;Valor;Tipo_valor;Natureza_valor"
        )
        # 15 campos correspondendo ao header de 15 colunas
        rows = [
            ["111110200", "10131", "PO", "1", "FP", "1500", "FR",
             "", "", "", "", "", "1000.00", "beginning_balance", "D"],
            ["111110200", "10131", "PO", "1", "FP", "1500", "FR",
             "", "", "", "", "", "500.00", "beginning_balance", "C"],
        ]
        csv_bytes = build_msc_csv(header=header, rows=rows)
        raw = read_msc_csv(io.BytesIO(csv_bytes))
        r001 = [i for i in raw.pre_pivot_issues if i["regra"] == "R001"]
        assert len(r001) == 1
        assert r001[0]["campo"] == "IC5"

    def test_csv_sem_coluna_critica_levanta_inputformaterror(
        self,
        build_msc_csv: Callable[..., bytes],
    ) -> None:
        """CSV sem coluna crítica 'Valor' → InputFormatError."""
        header = (
            "CONTA;IC1;TIPO1;IC2;TIPO2;IC3;TIPO3;IC4;TIPO4"
            ";IC5;TIPO5;IC6;TIPO6;Tipo_valor;Natureza_valor"
        )
        # 15 campos correspondendo ao header de 15 colunas (sem Valor)
        rows = [
            ["111110200", "10131", "PO", "1", "FP", "1500", "FR",
             "", "", "", "", "", "beginning_balance", "D", ""],
        ]
        csv_bytes = build_msc_csv(header=header, rows=rows)
        with pytest.raises(InputFormatError, match="críticas"):
            read_msc_csv(io.BytesIO(csv_bytes))


# ---------------------------------------------------------------------------
# Reader — R005 (Valor não-numérico)
# ---------------------------------------------------------------------------


class TestReaderR005:
    """Testes do comportamento R005 no reader (Valor não-numérico)."""

    def test_csv_com_valores_numericos_retorna_zero_issues_r005(
        self,
        build_msc_csv: Callable[..., bytes],
    ) -> None:
        """CSV com todos os Valores numéricos → pre_pivot_issues sem R005."""
        raw = read_msc_csv(io.BytesIO(build_msc_csv()))
        r005 = [i for i in raw.pre_pivot_issues if i["regra"] == "R005"]
        assert r005 == []

    def test_csv_com_valor_texto_coleta_issue_r005(
        self,
        build_msc_csv: Callable[..., bytes],
    ) -> None:
        """CSV com Valor='abc' → issue R005 com valor_encontrado='abc'."""
        rows = [
            ["111110200", "10131", "PO", "1", "FP", "1500", "FR",
             "", "", "", "", "", "", "abc", "beginning_balance", "D"],
            ["111110200", "10131", "PO", "1", "FP", "1500", "FR",
             "", "", "", "", "", "", "500.00", "beginning_balance", "C"],
        ]
        csv_bytes = build_msc_csv(rows=rows)
        raw = read_msc_csv(io.BytesIO(csv_bytes))
        r005 = [i for i in raw.pre_pivot_issues if i["regra"] == "R005"]
        assert len(r005) == 1
        assert r005[0]["valor_encontrado"] == "abc"
        assert r005[0]["conta_contabil"] == "111110200"

    def test_csv_com_valor_virgula_como_decimal_coleta_issue_r005(
        self,
        build_msc_csv: Callable[..., bytes],
    ) -> None:
        """CSV com Valor='1.234,56' (vírgula como decimal) → issue R005."""
        rows = [
            ["111110200", "10131", "PO", "1", "FP", "1500", "FR",
             "", "", "", "", "", "", "1.234,56", "beginning_balance", "D"],
            ["111110200", "10131", "PO", "1", "FP", "1500", "FR",
             "", "", "", "", "", "", "500.00", "beginning_balance", "C"],
        ]
        csv_bytes = build_msc_csv(rows=rows)
        raw = read_msc_csv(io.BytesIO(csv_bytes))
        r005 = [i for i in raw.pre_pivot_issues if i["regra"] == "R005"]
        assert len(r005) == 1
        assert "1.234,56" in r005[0]["valor_encontrado"]
