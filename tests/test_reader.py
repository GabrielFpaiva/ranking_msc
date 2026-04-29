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

    def test_metadata_multiplos_separadores_retorna_melhor_esforco(self) -> None:
        """Formato com múltiplos separadores retorna extração por melhor esforço.

        "dados;sem;formato;valido" possui ";": left="dados", right="sem;formato;valido".
        _validate_metadata irá emitir R006/R007; nenhuma exceção é levantada.
        """
        competencia, siconfi = _extract_metadata("dados;sem;formato;valido")
        # left="dados" → siconfi; right="sem;formato;valido" → competencia
        assert siconfi == "dados"
        assert competencia == "sem;formato;valido"

    def test_metadata_vazia_levanta_inputformaterror(self) -> None:
        """Linha completamente em branco levanta InputFormatError."""
        with pytest.raises(InputFormatError, match="em branco"):
            _extract_metadata("")

    def test_metadata_sem_competencia_retorna_melhor_esforco(self) -> None:
        """Metadata sem competência YYYY-MM retorna extração por melhor esforço.

        "2507507EX;novembro" não casa com padrão canônico mas possui ";":
        siconfi="2507507EX", competencia="novembro".  R007 é emitido downstream.
        """
        competencia, siconfi = _extract_metadata("2507507EX;novembro")
        assert siconfi == "2507507EX"
        assert competencia == "novembro"


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

    def test_metadata_invalida_emite_r006_r007_sem_abortar(self, tmp_path: Path) -> None:
        """Metadata malformada sem separador emite R006 e R007; não levanta exceção.

        "invalido" (sem ";") → siconfi="" (inválido → R006),
        competencia="invalido" (inválido → R007).
        Pipeline não aborta — issues ficam em pre_pivot_issues.
        """
        hdr = "CONTA;IC1;TIPO1;IC2;TIPO2;IC3;TIPO3;IC4;TIPO4;IC5;TIPO5;IC6;TIPO6"
        hdr += ";Valor;Tipo_valor;Natureza_valor"
        data = "111110200;10131;PO;1;FP;1500;FR;;;;;;;1000.00;beginning_balance;D"
        content = f"invalido\r{hdr}\r{data}".encode("ascii")
        path = tmp_path / "bad_meta.csv"
        path.write_bytes(content)
        result = read_msc_csv(path)
        regras = {i["regra"] for i in result.pre_pivot_issues}
        assert "R006" in regras
        assert "R007" in regras

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


# ---------------------------------------------------------------------------
# Testes de integração — P1 (separador misto) e P2 (metadata parcial)
# ---------------------------------------------------------------------------


class TestP1SeparadorMisto:
    """Testes de integração para P1: header usa vírgula, dados usam ponto-e-vírgula."""

    def test_header_virgula_dados_ponto_virgula_emite_r008_e_nao_esvazia_dataframe(
        self, tmp_path: Path,
    ) -> None:
        """Header com vírgula + dados com ";" → R008 emitido, DataFrame não vazio.

        Antes do fix, effective_sep era forçado para "," ao detectar R008 no
        header, fazendo cada linha de dados cair inteira na primeira coluna.
        _validate_columns não levantava exceção (colunas existiam no header)
        e _pivot_values descartava todas as linhas → DataFrame vazio silencioso.
        Após o fix, _infer_sep_from_rows detecta ";" nos dados e body_sep=";"
        é usado para parsear o corpo, preservando os dados.
        """
        _cols = "CONTA,IC1,TIPO1,IC2,TIPO2,IC3,TIPO3,IC4,TIPO4,IC5,TIPO5,IC6,TIPO6"
        header = f"{_cols},Valor,Tipo_valor,Natureza_valor"
        data_row = "111110200;10131;PO;1;FP;1500;FR;;;;;;;;1000.00;beginning_balance;D"
        content = f"2507507EX;2025-11\r{header}\r{data_row}".encode("ascii")
        path = tmp_path / "mixed_sep.csv"
        path.write_bytes(content)

        result = read_msc_csv(path)

        r008 = [i for i in result.pre_pivot_issues if i["regra"] == "R008"]
        assert len(r008) >= 1, "R008 deve ser emitido para header com vírgula"
        assert len(result.df) > 0, "DataFrame não pode ser vazio quando dados estão presentes"

    def test_header_e_dados_virgula_emite_r008_e_parseia_com_virgula(
        self, tmp_path: Path,
    ) -> None:
        """Header com vírgula + dados com vírgula → R008 emitido, leitura com vírgula."""
        _cols = "CONTA,IC1,TIPO1,IC2,TIPO2,IC3,TIPO3,IC4,TIPO4,IC5,TIPO5,IC6,TIPO6"
        header = f"{_cols},Valor,Tipo_valor,Natureza_valor"
        data_row = "111110200,10131,PO,1,FP,1500,FR,,,,,,,,1000.00,beginning_balance,D"
        content = f"2507507EX;2025-11\r{header}\r{data_row}".encode("ascii")
        path = tmp_path / "all_comma.csv"
        path.write_bytes(content)

        result = read_msc_csv(path)

        r008 = [i for i in result.pre_pivot_issues if i["regra"] == "R008"]
        assert len(r008) >= 1, "R008 deve ser emitido para header com vírgula"
        assert len(result.df) > 0, "DataFrame não pode ser vazio quando dados usam vírgula"


class TestP2MetadataParcial:
    """Testes de integração para P2: metadata malformada → R006/R007, sem abort."""

    def test_metadata_com_barra_emite_r007_sem_abort(self, tmp_path: Path) -> None:
        """Metadata '2507507EX;2024/01' → R007 em pre_pivot_issues, sem abort.

        '2024/01' não casa com padrão YYYY-MM; extração por melhor esforço
        retorna competencia='2024/01', siconfi='2507507EX'.
        _validate_metadata emite R007.
        """
        content = (
            b"2507507EX;2024/01\r"
            b"CONTA;IC1;TIPO1;IC2;TIPO2;IC3;TIPO3;IC4;TIPO4;IC5;TIPO5;IC6;TIPO6;Valor;Tipo_valor;Natureza_valor\r"
            b"111110200;10131;PO;1;FP;1500;FR;;;;;;;;1000.00;beginning_balance;D"
        )
        path = tmp_path / "meta_barra.csv"
        path.write_bytes(content)

        result = read_msc_csv(path)

        regras = {i["regra"] for i in result.pre_pivot_issues}
        assert "R007" in regras, "R007 deve ser emitido para competencia='2024/01'"
        assert len(result.df) > 0, "DataFrame não pode ser vazio"

    def test_metadata_sem_separador_emite_r006_e_r007_sem_abort(
        self, tmp_path: Path,
    ) -> None:
        """Metadata 'invalido' (sem ";") → R006 + R007 em pre_pivot_issues, sem abort.

        Linha sem ";" retorna siconfi="" e competencia="invalido".
        _validate_metadata emite R006 (siconfi inválido) e R007 (competencia inválida).
        """
        content = (
            b"invalido\r"
            b"CONTA;IC1;TIPO1;IC2;TIPO2;IC3;TIPO3;IC4;TIPO4;IC5;TIPO5;IC6;TIPO6;Valor;Tipo_valor;Natureza_valor\r"
            b"111110200;10131;PO;1;FP;1500;FR;;;;;;;;1000.00;beginning_balance;D"
        )
        path = tmp_path / "meta_sem_sep.csv"
        path.write_bytes(content)

        result = read_msc_csv(path)

        regras = {i["regra"] for i in result.pre_pivot_issues}
        assert "R006" in regras, "R006 deve ser emitido para siconfi vazio"
        assert "R007" in regras, "R007 deve ser emitido para competencia inválida"


# ---------------------------------------------------------------------------
# Sanitização de path traversal
# ---------------------------------------------------------------------------


class TestPathTraversalSanitization:
    """Testes de sanitização de path traversal em metadados."""

    def test_competencia_path_traversal_emite_r007_com_valor_original(
        self, tmp_path: Path,
    ) -> None:
        """Competência com path traversal → R007 com valor original, RawMSC sanitizado.

        Entrada: ``../../outside`` como competência.
        Esperado:
        - R007 em pre_pivot_issues com ``valor_encontrado="../../outside"``.
        - ``RawMSC.competencia == "0000-00"`` (valor sanitizado, seguro para I/O).
        - Pipeline não aborta.
        """
        content = (
            b"2507507EX;../../outside\r"
            b"CONTA;IC1;TIPO1;IC2;TIPO2;IC3;TIPO3;IC4;TIPO4;IC5;TIPO5;IC6;TIPO6;Valor;Tipo_valor;Natureza_valor\r"
            b"111110200;10131;PO;1;FP;1500;FR;;;;;;;;1000.00;beginning_balance;D"
        )
        path = tmp_path / "path_traversal.csv"
        path.write_bytes(content)

        result = read_msc_csv(path)

        # R007 deve conter o valor ORIGINAL (não sanitizado)
        r007_issues = [i for i in result.pre_pivot_issues if i["regra"] == "R007"]
        assert len(r007_issues) >= 1, "R007 deve ser emitido para competencia inválida"
        assert r007_issues[0]["valor_encontrado"] == "../../outside", (
            "valor_encontrado deve ser o valor original (pre-sanitização)"
        )

        # RawMSC deve conter o valor SANITIZADO
        assert result.competencia == "0000-00", (
            f"competencia do RawMSC deve ser '0000-00', foi '{result.competencia}'"
        )
        assert len(result.df) > 0, "DataFrame não pode ser vazio"

    def test_siconfi_com_caracteres_invalidos_sanitizado_no_rawmsc(
        self, tmp_path: Path,
    ) -> None:
        """SICONFI com caracteres não-alfanuméricos é sanitizado antes de RawMSC.

        Entrada: ``MAU;SICONFI`` como siconfi (não casa com padrão ``\\d{7}EX``).
        Esperado:
        - R006 emitido com valor original.
        - ``RawMSC.siconfi`` não contém ``;`` nem outros caracteres inseguros.
        """
        content = (
            b"MAU;SICONFI;2025-11\r"
            b"CONTA;IC1;TIPO1;IC2;TIPO2;IC3;TIPO3;IC4;TIPO4;IC5;TIPO5;IC6;TIPO6;Valor;Tipo_valor;Natureza_valor\r"
            b"111110200;10131;PO;1;FP;1500;FR;;;;;;;;1000.00;beginning_balance;D"
        )
        path = tmp_path / "siconfi_invalido.csv"
        path.write_bytes(content)

        result = read_msc_csv(path)

        # R006 deve ter sido emitido
        r006_issues = [i for i in result.pre_pivot_issues if i["regra"] == "R006"]
        assert len(r006_issues) >= 1, "R006 deve ser emitido para siconfi inválido"

        # siconfi sanitizado não deve conter caracteres perigosos para caminhos
        assert ";" not in result.siconfi
        assert "/" not in result.siconfi
        assert ".." not in result.siconfi
