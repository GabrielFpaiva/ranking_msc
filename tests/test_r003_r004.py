"""Testes das regras R003 e R004 — Tipo_valor e Natureza_valor válidos."""

from __future__ import annotations

import pandas as pd
import pytest

from ranking_msc.engine.executor import EngineContext
from ranking_msc.rules.r003 import R003
from ranking_msc.rules.r004 import R004


def _context_com_issues(
    issues: list[dict],
    settings: object,
) -> EngineContext:
    """Cria EngineContext com pre_pivot_issues populados."""
    return EngineContext(
        competencia="2025-11",
        siconfi="2507507EX",
        settings=settings,  # type: ignore[arg-type]
        pre_pivot_issues=issues,
    )


_DF_VAZIO = pd.DataFrame()


class TestR003:
    def test_sem_violacoes_nao_gera_pendencia(self, settings: object) -> None:
        """Context sem issues de R003 não gera pendência."""
        context = _context_com_issues([], settings)
        result = R003().execute(_DF_VAZIO, context)

        assert len(result) == 0

    def test_tipo_valor_invalido_gera_erro(self, settings: object) -> None:
        """Issue de R003 no context gera pendência ERRO."""
        issues = [{
            "regra": "R003",
            "conta_contabil": "111110200",
            "campo": "Tipo_valor",
            "valor_encontrado": "saldo_invalido",
            "competencia": "2025-11",
        }]
        context = _context_com_issues(issues, settings)
        result = R003().execute(_DF_VAZIO, context)

        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ERRO"
        assert result.iloc[0]["regra_id"] == "R003"
        assert "saldo_invalido" in result.iloc[0]["descricao"]

    def test_issues_de_r004_sao_ignoradas(self, settings: object) -> None:
        """Issues de outra regra no context não são retornadas por R003."""
        issues = [{
            "regra": "R004",
            "conta_contabil": "111110200",
            "campo": "Natureza_valor",
            "valor_encontrado": "X",
            "competencia": "2025-11",
        }]
        context = _context_com_issues(issues, settings)
        result = R003().execute(_DF_VAZIO, context)

        assert len(result) == 0

    def test_multiplas_violacoes_geram_pendencias_separadas(
        self, settings: object
    ) -> None:
        """Cada linha inválida de Tipo_valor gera uma pendência."""
        issues = [
            {
                "regra": "R003",
                "conta_contabil": "111110200",
                "campo": "Tipo_valor",
                "valor_encontrado": "tipo_a",
                "competencia": "2025-11",
            },
            {
                "regra": "R003",
                "conta_contabil": "211000000",
                "campo": "Tipo_valor",
                "valor_encontrado": "tipo_b",
                "competencia": "2025-11",
            },
        ]
        context = _context_com_issues(issues, settings)
        result = R003().execute(_DF_VAZIO, context)

        assert len(result) == 2


class TestR004:
    def test_sem_violacoes_nao_gera_pendencia(self, settings: object) -> None:
        """Context sem issues de R004 não gera pendência."""
        context = _context_com_issues([], settings)
        result = R004().execute(_DF_VAZIO, context)

        assert len(result) == 0

    def test_natureza_valor_invalida_gera_erro(self, settings: object) -> None:
        """Issue de R004 no context gera pendência ERRO."""
        issues = [{
            "regra": "R004",
            "conta_contabil": "111110200",
            "campo": "Natureza_valor",
            "valor_encontrado": "X",
            "competencia": "2025-11",
        }]
        context = _context_com_issues(issues, settings)
        result = R004().execute(_DF_VAZIO, context)

        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ERRO"
        assert result.iloc[0]["regra_id"] == "R004"
        assert "X" in result.iloc[0]["descricao"]

    def test_issues_de_r003_sao_ignoradas(self, settings: object) -> None:
        """Issues de outra regra no context não são retornadas por R004."""
        issues = [{
            "regra": "R003",
            "conta_contabil": "111110200",
            "campo": "Tipo_valor",
            "valor_encontrado": "invalido",
            "competencia": "2025-11",
        }]
        context = _context_com_issues(issues, settings)
        result = R004().execute(_DF_VAZIO, context)

        assert len(result) == 0


class TestPrePivotIntegracao:
    def test_reader_captura_tipo_valor_invalido(self, tmp_path: pytest.TempPath) -> None:
        """reader_msc captura Tipo_valor inválido em pre_pivot_issues."""
        from ranking_msc.io.reader_msc import read_msc_csv

        linhas = [
            "2507507EX;2025-11",
            "CONTA;IC1;TIPO1;IC2;TIPO2;IC3;TIPO3;IC4;TIPO4;IC5;TIPO5;IC6;TIPO6"
            ";Valor;Tipo_valor;Natureza_valor",
            "111110200;10131;PO;1;FP;1500;FR;;;;;;;1000.00;tipo_invalido;D",
        ]
        csv_bytes = "\r".join(linhas).encode("ascii")
        csv_path = tmp_path / "msc_teste.csv"
        csv_path.write_bytes(csv_bytes)

        raw = read_msc_csv(csv_path)

        assert any(i["regra"] == "R003" for i in raw.pre_pivot_issues)

    def test_reader_captura_natureza_valor_invalida(
        self, tmp_path: pytest.TempPath
    ) -> None:
        """reader_msc captura Natureza_valor inválida em pre_pivot_issues."""
        from ranking_msc.io.reader_msc import read_msc_csv

        linhas = [
            "2507507EX;2025-11",
            "CONTA;IC1;TIPO1;IC2;TIPO2;IC3;TIPO3;IC4;TIPO4;IC5;TIPO5;IC6;TIPO6"
            ";Valor;Tipo_valor;Natureza_valor",
            "111110200;10131;PO;1;FP;1500;FR;;;;;;;1000.00;beginning_balance;X",
        ]
        csv_bytes = "\r".join(linhas).encode("ascii")
        csv_path = tmp_path / "msc_teste.csv"
        csv_path.write_bytes(csv_bytes)

        raw = read_msc_csv(csv_path)

        assert any(i["regra"] == "R004" for i in raw.pre_pivot_issues)

    def test_reader_csv_valido_sem_pre_pivot_issues(
        self, msc_csv_path: object
    ) -> None:
        """CSV com Tipo_valor e Natureza_valor válidos não gera pre_pivot_issues."""
        from ranking_msc.io.reader_msc import read_msc_csv

        raw = read_msc_csv(msc_csv_path)  # type: ignore[arg-type]

        assert raw.pre_pivot_issues == []
