"""Testes das regras R006–R009 (Estrutura — metadados e formato do CSV).

Cobertura:
    R006 — Código Siconfi válido (7 dígitos + EX)
    R007 — Período YYYY-MM válido e plausível (mês 01-13)
    R008 — Separador ponto-e-vírgula (detector + regra)
    R009 — Exatamente 6 pares IC/TIPO (12 colunas)
"""

from __future__ import annotations

import io

import pandas as pd

from ranking_msc.config.settings import Settings
from ranking_msc.engine.executor import EngineContext
from ranking_msc.io.reader_msc import (
    _detect_effective_separator,
    _detect_separator_issue,
    read_msc_csv,
)
from ranking_msc.rules.r006 import R006
from ranking_msc.rules.r007 import R007
from ranking_msc.rules.r008 import R008
from ranking_msc.rules.r009 import R009

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ctx(settings: Settings, pre_pivot_issues: list[dict] | None = None) -> EngineContext:
    return EngineContext(
        competencia="2024-01",
        siconfi="2507507EX",
        settings=settings,
        usuario="teste",
        pre_pivot_issues=pre_pivot_issues or [],
    )


def _csv_bytes(
    siconfi: str = "2507507EX",
    competencia: str = "2024-01",
    header: str = (
        "CONTA;IC1;TIPO1;IC2;TIPO2;IC3;TIPO3;IC4;TIPO4;IC5;TIPO5;IC6;TIPO6"
        ";Valor;Tipo_valor;Natureza_valor"
    ),
    rows: list[str] | None = None,
) -> bytes:
    """Gera um CSV MSC sintético em bytes para testes de reader."""
    if rows is None:
        rows = [
            "111110200;10131;PO;1;FP;1500;FR;;;;;;;1000.00;beginning_balance;D",
            "111110200;10131;PO;1;FP;1500;FR;;;;;;;500.00;beginning_balance;C",
            "111110200;10131;PO;1;FP;1500;FR;;;;;;;200.00;ending_balance;D",
            "111110200;10131;PO;1;FP;1500;FR;;;;;;;100.00;ending_balance;C",
        ]
    content = "\r".join([f"{siconfi};{competencia}", header] + rows)
    return content.encode("ascii")


def _csv_reduced_ic(
    siconfi: str = "2507507EX",
    competencia: str = "2024-01",
) -> bytes:
    """CSV com apenas IC1/TIPO1 (2 colunas IC/TIPO em vez de 12)."""
    header = "CONTA;IC1;TIPO1;Valor;Tipo_valor;Natureza_valor"
    rows = [
        "111110200;10131;PO;1000.00;beginning_balance;D",
        "111110200;10131;PO;500.00;beginning_balance;C",
        "111110200;10131;PO;200.00;ending_balance;D",
        "111110200;10131;PO;100.00;ending_balance;C",
    ]
    content = "\r".join([f"{siconfi};{competencia}", header] + rows)
    return content.encode("ascii")


# ---------------------------------------------------------------------------
# R006 — Código Siconfi válido
# ---------------------------------------------------------------------------

class TestR006:
    def test_siconfi_valido_sem_pendencia(self, settings: Settings) -> None:
        """Siconfi no padrão 7 dígitos + EX → nenhuma pendência."""
        raw = read_msc_csv(io.BytesIO(_csv_bytes(siconfi="2507507EX")))
        r006_issues = [i for i in raw.pre_pivot_issues if i.get("regra") == "R006"]
        assert r006_issues == []

        ctx = _ctx(settings)
        result = R006().execute(raw.df, ctx)
        assert len(result) == 0

    def test_siconfi_sem_sufixo_ex_gera_pendencia(self, settings: Settings) -> None:
        """Siconfi sem 'EX' (ex: '2507507') → R006 em pre_pivot_issues."""
        raw = read_msc_csv(io.BytesIO(_csv_bytes(siconfi="2507507")))
        r006_issues = [i for i in raw.pre_pivot_issues if i.get("regra") == "R006"]
        assert len(r006_issues) == 1
        assert r006_issues[0]["valor_encontrado"] == "2507507"

    def test_siconfi_invalido_rule_gera_erro(self, settings: Settings) -> None:
        """R006.execute() com pre_pivot_issue pré-injetado → 1 ERRO."""
        issue = {
            "regra": "R006",
            "conta_contabil": "",
            "campo": "siconfi",
            "valor_encontrado": "INVALIDO",
            "competencia": "2024-01",
        }
        ctx = _ctx(settings, pre_pivot_issues=[issue])
        result = R006().execute(pd.DataFrame(), ctx)
        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ERRO"
        assert result.iloc[0]["regra_id"] == "R006"
        assert "INVALIDO" in result.iloc[0]["descricao"]

    def test_siconfi_digitos_incorretos_gera_pendencia(self, settings: Settings) -> None:
        """Siconfi com menos de 7 dígitos + EX → R006 em pre_pivot_issues."""
        raw = read_msc_csv(io.BytesIO(_csv_bytes(siconfi="250400EX")))
        r006_issues = [i for i in raw.pre_pivot_issues if i.get("regra") == "R006"]
        assert len(r006_issues) == 1


# ---------------------------------------------------------------------------
# R007 — Período YYYY-MM válido e plausível
# ---------------------------------------------------------------------------

class TestR007:
    def test_periodo_valido_sem_pendencia(self, settings: Settings) -> None:
        """Período 2024-01 → nenhuma pendência R007."""
        raw = read_msc_csv(io.BytesIO(_csv_bytes(competencia="2024-01")))
        r007_issues = [i for i in raw.pre_pivot_issues if i.get("regra") == "R007"]
        assert r007_issues == []

        ctx = _ctx(settings)
        result = R007().execute(raw.df, ctx)
        assert len(result) == 0

    def test_mes_encerramento_13_valido(self, settings: Settings) -> None:
        """Mês 13 (encerramento anual) é válido → sem pendência R007."""
        raw = read_msc_csv(io.BytesIO(_csv_bytes(competencia="2024-13")))
        r007_issues = [i for i in raw.pre_pivot_issues if i.get("regra") == "R007"]
        assert r007_issues == []

    def test_mes_invalido_gera_pendencia(self, settings: Settings) -> None:
        """Mês 14 (> 13) → R007 em pre_pivot_issues."""
        raw = read_msc_csv(io.BytesIO(_csv_bytes(competencia="2024-14")))
        r007_issues = [i for i in raw.pre_pivot_issues if i.get("regra") == "R007"]
        assert len(r007_issues) == 1
        assert r007_issues[0]["valor_encontrado"] == "2024-14"

    def test_periodo_invalido_rule_gera_erro(self, settings: Settings) -> None:
        """R007.execute() com pre_pivot_issue pré-injetado → 1 ERRO."""
        issue = {
            "regra": "R007",
            "conta_contabil": "",
            "campo": "competencia",
            "valor_encontrado": "2024-14",
            "competencia": "2024-14",
        }
        ctx = _ctx(settings, pre_pivot_issues=[issue])
        result = R007().execute(pd.DataFrame(), ctx)
        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ERRO"
        assert result.iloc[0]["regra_id"] == "R007"
        assert "2024-14" in result.iloc[0]["descricao"]


# ---------------------------------------------------------------------------
# R008 — Separador ponto-e-vírgula
# ---------------------------------------------------------------------------

class TestR008:
    def test_detect_separator_semicolon_sem_issue(self) -> None:
        """Header com ';' → nenhum issue R008."""
        header = "CONTA;IC1;TIPO1;Valor;Tipo_valor;Natureza_valor"
        issues = _detect_separator_issue(header, ";")
        assert issues == []

    def test_detect_separator_comma_retorna_r008(self) -> None:
        """Header com ',' e sem ';' → issue R008 com valor_encontrado=','."""
        header = "CONTA,IC1,TIPO1,Valor,Tipo_valor,Natureza_valor"
        issues = _detect_separator_issue(header, ";")
        assert len(issues) == 1
        assert issues[0]["regra"] == "R008"
        assert issues[0]["valor_encontrado"] == ","

    def test_detect_separator_expected_not_semicolon_sem_issue(self) -> None:
        """expected_sep != ';' → detector sempre retorna vazio (fora do escopo)."""
        header = "CONTA,IC1,TIPO1,Valor"
        issues = _detect_separator_issue(header, ",")
        assert issues == []

    def test_rule_drains_pre_pivot_issues(self, settings: Settings) -> None:
        """R008.execute() com pre_pivot_issue pré-injetado → 1 ERRO."""
        issue = {
            "regra": "R008",
            "conta_contabil": "",
            "campo": "separador",
            "valor_encontrado": ",",
            "competencia": "",
        }
        ctx = _ctx(settings, pre_pivot_issues=[issue])
        result = R008().execute(pd.DataFrame(), ctx)
        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ERRO"
        assert result.iloc[0]["regra_id"] == "R008"
        assert ";" in result.iloc[0]["valor_esperado"]

    def test_csv_valido_sem_pendencia(self, settings: Settings) -> None:
        """CSV com separador ';' correto → sem pendência R008."""
        raw = read_msc_csv(io.BytesIO(_csv_bytes()))
        r008_issues = [i for i in raw.pre_pivot_issues if i.get("regra") == "R008"]
        assert r008_issues == []

        ctx = _ctx(settings)
        result = R008().execute(raw.df, ctx)
        assert len(result) == 0

    def test_csv_comma_delimited_surfaces_r008(self, settings: Settings) -> None:
        """CSV with comma delimiter → R008 in pre_pivot_issues (not InputFormatError).

        Regression: previously the reader would parse with ';', causing all
        critical columns to appear missing and raising InputFormatError before
        R008 could reach the rule engine.
        """
        header = (
            "CONTA,IC1,TIPO1,IC2,TIPO2,IC3,TIPO3,IC4,TIPO4,IC5,TIPO5,IC6,TIPO6"
            + ",Valor,Tipo_valor,Natureza_valor"
        )
        rows = [
            "111110200,10131,PO,1,FP,1500,FR,,,,,,,1000.00,beginning_balance,D",
            "111110200,10131,PO,1,FP,1500,FR,,,,,,,500.00,beginning_balance,C",
            "111110200,10131,PO,1,FP,1500,FR,,,,,,,200.00,ending_balance,D",
            "111110200,10131,PO,1,FP,1500,FR,,,,,,,100.00,ending_balance,C",
        ]
        content = "\r".join(["2507507EX;2024-01", header] + rows)
        csv_bytes = content.encode("ascii")

        raw = read_msc_csv(io.BytesIO(csv_bytes))
        r008_issues = [i for i in raw.pre_pivot_issues if i.get("regra") == "R008"]
        assert len(r008_issues) == 1
        assert r008_issues[0]["valor_encontrado"] == ","
        assert len(raw.df) > 0
        assert "conta_contabil" in raw.df.columns

        ctx = _ctx(settings, pre_pivot_issues=raw.pre_pivot_issues)
        result = R008().execute(raw.df, ctx)
        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ERRO"

    def test_metadata_comma_delimiter_retorna_r008_sem_abort(self) -> None:
        """Metadata com ',' (ex: '2507507EX,2024-01') → R008 em pre_pivot_issues, sem abort."""
        header = (
            "CONTA,IC1,TIPO1,IC2,TIPO2,IC3,TIPO3,IC4,TIPO4,IC5,TIPO5,IC6,TIPO6"
            + ",Valor,Tipo_valor,Natureza_valor"
        )
        lines = [
            "2507507EX,2024-01",
            header,
            "111110200,10131,PO,,,,,,,,,,,,1000.00,beginning_balance,D",
            "111110200,10131,PO,,,,,,,,,,,,500.00,beginning_balance,C",
        ]
        csv_bytes = "\r".join(lines).encode("ascii")
        raw = read_msc_csv(io.BytesIO(csv_bytes))
        r008 = [i for i in raw.pre_pivot_issues if i.get("regra") == "R008"]
        assert len(r008) == 1
        assert r008[0]["valor_encontrado"] == ","

    def test_metadata_invalido_com_virgula_retorna_r008_e_r006(self) -> None:
        """Metadata 'invalido,2024-01' → R008 + R006; não levanta InputFormatError."""
        header = (
            "CONTA,IC1,TIPO1,IC2,TIPO2,IC3,TIPO3,IC4,TIPO4,IC5,TIPO5,IC6,TIPO6"
            + ",Valor,Tipo_valor,Natureza_valor"
        )
        lines = [
            "invalido,2024-01",
            header,
            "111110200,10131,PO,,,,,,,,,,,,1000.00,beginning_balance,D",
        ]
        csv_bytes = "\r".join(lines).encode("ascii")
        raw = read_msc_csv(io.BytesIO(csv_bytes))
        regras = {i["regra"] for i in raw.pre_pivot_issues}
        assert "R008" in regras
        assert "R006" in regras

    def test_detect_effective_separator_metadata_comma(self) -> None:
        """_detect_effective_separator detecta vírgula na metadata e retorna R008."""
        sep, issues = _detect_effective_separator("2507507EX,2024-01", "CONTA;IC1", ";")
        assert sep == ","
        assert len(issues) == 1
        assert issues[0]["regra"] == "R008"

    def test_detect_effective_separator_header_comma_retorna_sep_virgula(self) -> None:
        """Metadata com ';' mas header com ',' → effective_sep=',' e R008."""
        sep, issues = _detect_effective_separator("2507507EX;2024-01", "CONTA,IC1", ";")
        assert sep == ","
        assert len(issues) == 1
        assert issues[0]["regra"] == "R008"

    def test_detect_effective_separator_ambos_corretos(self) -> None:
        """_detect_effective_separator sem desvio → sem issues."""
        sep, issues = _detect_effective_separator("2507507EX;2024-01", "CONTA;IC1", ";")
        assert sep == ";"
        assert issues == []


# ---------------------------------------------------------------------------
# R009 — Exatamente 6 pares IC/TIPO (12 colunas)
# ---------------------------------------------------------------------------

class TestR009:
    def test_12_colunas_ic_tipo_sem_pendencia(self, settings: Settings) -> None:
        """CSV com 12 colunas IC/TIPO → nenhuma pendência R009."""
        raw = read_msc_csv(io.BytesIO(_csv_bytes()))
        r009_issues = [i for i in raw.pre_pivot_issues if i.get("regra") == "R009"]
        assert r009_issues == []

        ctx = _ctx(settings)
        result = R009().execute(raw.df, ctx)
        assert len(result) == 0

    def test_colunas_insuficientes_gera_pendencia(self, settings: Settings) -> None:
        """CSV com 2 colunas IC/TIPO (IC1, TIPO1) → R009 em pre_pivot_issues."""
        raw = read_msc_csv(io.BytesIO(_csv_reduced_ic()))
        r009_issues = [i for i in raw.pre_pivot_issues if i.get("regra") == "R009"]
        assert len(r009_issues) == 1
        assert r009_issues[0]["valor_encontrado"] == "2"

    def test_rule_drains_pre_pivot_issues(self, settings: Settings) -> None:
        """R009.execute() com pre_pivot_issue pré-injetado → 1 ERRO."""
        issue = {
            "regra": "R009",
            "conta_contabil": "",
            "campo": "colunas_ic_tipo",
            "valor_encontrado": "2",
        }
        ctx = _ctx(settings, pre_pivot_issues=[issue])
        result = R009().execute(pd.DataFrame(), ctx)
        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ERRO"
        assert result.iloc[0]["regra_id"] == "R009"
        assert result.iloc[0]["valor_esperado"] == "12"

    def test_rule_sem_violacao_retorna_vazio(self, settings: Settings) -> None:
        """R009.execute() sem issues R009 no context → DataFrame vazio."""
        ctx = _ctx(settings, pre_pivot_issues=[])
        result = R009().execute(pd.DataFrame(), ctx)
        assert len(result) == 0
