"""
tests/test_compare_periods.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Testes do módulo engine/compare_periods.py.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from ranking_msc.config.settings import RulesSettings, Settings
from ranking_msc.engine.compare_periods import (
    PeriodComparison,
    PeriodScore,
    _discover_competencias,
    _load_period_score,
    compare_periods,
)
from ranking_msc.engine.score_engine import ScoreResult
from ranking_msc.outputs.snapshot import write_scoring_metadata, write_snapshot_atomic
from ranking_msc.schemas import FACT_RESULTADO_REGRAS_COLUMNS

# ---------------------------------------------------------------------------
# Helpers de fixture
# ---------------------------------------------------------------------------


def _make_pendencias(
    regra_ids: list[str],
    severidades: list[str],
    competencia: str = "2024-01",
) -> pd.DataFrame:
    """Cria DataFrame de pendências mínimo para testes."""
    rows = [
        {
            "regra_id": rid,
            "regra_nome": rid,
            "dimensao": "Estrutura",
            "severidade": sev,
            "competencia": competencia,
            "conta_contabil": "1.1.1.1.1.01.00",
            "descricao": "Teste",
            "valor_esperado": "0",
            "valor_encontrado": "0",
        }
        for rid, sev in zip(regra_ids, severidades, strict=True)
    ]
    if not rows:
        return pd.DataFrame(columns=FACT_RESULTADO_REGRAS_COLUMNS)
    return pd.DataFrame(rows)[FACT_RESULTADO_REGRAS_COLUMNS]


def _make_settings(enabled: list[str] | None = None) -> Settings:
    """Cria Settings com lista de regras habilitadas."""
    return Settings(rules=RulesSettings(enabled=enabled or []))


def _write_resultado_snapshot(
    tmp_path: Path,
    siconfi: str,
    competencia: str,
    pendencias: pd.DataFrame,
) -> None:
    """Grava snapshot de resultado_regras em tmp_path/<siconfi>/<competencia>/."""
    base_dir = tmp_path / siconfi
    write_snapshot_atomic(pendencias, competencia, base_dir=base_dir, label="resultado_regras")


# ---------------------------------------------------------------------------
# PeriodComparison.score_delta
# ---------------------------------------------------------------------------


class TestPeriodComparisonScoreDelta:
    def _make_period(self, score: float) -> PeriodScore:
        result = ScoreResult(
            pontuacao=score,
            banda="B",
            dimensions={},
            regras_executadas=0,
            regras_falhas_erro=0,
            regras_falhas_alerta=0,
        )
        return PeriodScore(competencia="2024-01", score_result=result, total_pendencias=0)

    def test_score_delta_primeiro_periodo_retorna_none(self) -> None:
        """Primeiro período não tem delta."""
        comparison = PeriodComparison(
            siconfi="250400",
            periods=[self._make_period(80.0)],
        )
        assert comparison.score_delta(0) is None

    def test_score_delta_melhora_retorna_positivo(self) -> None:
        """Score aumentou → delta positivo."""
        comparison = PeriodComparison(
            siconfi="250400",
            periods=[self._make_period(80.0), self._make_period(85.0)],
        )
        assert comparison.score_delta(1) == pytest.approx(5.0)

    def test_score_delta_piora_retorna_negativo(self) -> None:
        """Score diminuiu → delta negativo."""
        comparison = PeriodComparison(
            siconfi="250400",
            periods=[self._make_period(85.0), self._make_period(80.0)],
        )
        assert comparison.score_delta(1) == pytest.approx(-5.0)

    def test_score_delta_lista_vazia_retorna_none(self) -> None:
        """Sem períodos → retorna None para qualquer índice."""
        comparison = PeriodComparison(siconfi="250400")
        assert comparison.score_delta(0) is None


# ---------------------------------------------------------------------------
# _discover_competencias
# ---------------------------------------------------------------------------


class TestDiscoverCompetencias:
    def test_descobre_competencias_existentes(self, tmp_path: Path) -> None:
        """Descobre períodos disponíveis em disco."""
        empty = pd.DataFrame(columns=FACT_RESULTADO_REGRAS_COLUMNS)
        for comp in ("2024-01", "2024-02", "2024-03"):
            _write_resultado_snapshot(tmp_path, "250400", comp, empty)

        found = _discover_competencias(tmp_path, "250400")
        assert found == ["2024-01", "2024-02", "2024-03"]

    def test_diretorio_inexistente_retorna_lista_vazia(self, tmp_path: Path) -> None:
        """Diretório de siconfi ausente → lista vazia."""
        result = _discover_competencias(tmp_path, "999999")
        assert result == []

    def test_ignora_subpastas_sem_snapshot(self, tmp_path: Path) -> None:
        """Subpastas sem resultado_regras.parquet não são incluídas."""
        (tmp_path / "250400" / "2024-01").mkdir(parents=True)
        # sem arquivo parquet
        result = _discover_competencias(tmp_path, "250400")
        assert result == []


# ---------------------------------------------------------------------------
# _load_period_score
# ---------------------------------------------------------------------------


class TestLoadPeriodScore:
    def test_carrega_snapshot_e_calcula_score(self, tmp_path: Path) -> None:
        """Snapshot presente → retorna PeriodScore com score calculado."""
        pendencias = pd.DataFrame(columns=FACT_RESULTADO_REGRAS_COLUMNS)
        _write_resultado_snapshot(tmp_path, "250400", "2024-01", pendencias)

        period = _load_period_score(
            siconfi="250400",
            competencia="2024-01",
            base_dir=tmp_path,
            executed_rule_ids=[],
        )
        assert period is not None
        assert period.competencia == "2024-01"
        assert period.total_pendencias == 0

    def test_snapshot_ausente_retorna_none(self, tmp_path: Path) -> None:
        """Snapshot ausente → retorna None sem levantar exceção."""
        period = _load_period_score(
            siconfi="250400",
            competencia="2024-01",
            base_dir=tmp_path,
            executed_rule_ids=[],
        )
        assert period is None

    def test_pendencias_refletidas_no_total(self, tmp_path: Path) -> None:
        """Pendências do snapshot refletidas em total_pendencias."""
        pendencias = _make_pendencias(["R001", "R001"], ["ERRO", "ERRO"], "2024-01")
        _write_resultado_snapshot(tmp_path, "250400", "2024-01", pendencias)

        period = _load_period_score(
            siconfi="250400",
            competencia="2024-01",
            base_dir=tmp_path,
            executed_rule_ids=[],
        )
        assert period is not None
        assert period.total_pendencias == 2


# ---------------------------------------------------------------------------
# compare_periods — integração leve
# ---------------------------------------------------------------------------


class TestComparePeriods:
    def test_dois_periodos_ordenados_por_competencia(self, tmp_path: Path) -> None:
        """Dois períodos retornados em ordem ascendente de competência."""
        for comp in ("2024-02", "2024-01"):
            _write_resultado_snapshot(
                tmp_path, "250400", comp,
                pd.DataFrame(columns=FACT_RESULTADO_REGRAS_COLUMNS),
            )

        result = compare_periods("250400", snapshots_dir=tmp_path, settings=_make_settings())
        assert [p.competencia for p in result.periods] == ["2024-01", "2024-02"]

    def test_autodescobre_quando_competencias_omitidas(self, tmp_path: Path) -> None:
        """Sem --competencias → descobre automaticamente."""
        for comp in ("2024-01", "2024-02"):
            _write_resultado_snapshot(
                tmp_path, "250400", comp,
                pd.DataFrame(columns=FACT_RESULTADO_REGRAS_COLUMNS),
            )

        result = compare_periods("250400", snapshots_dir=tmp_path, settings=_make_settings())
        assert len(result.periods) == 2
        assert result.siconfi == "250400"

    def test_sem_snapshots_retorna_lista_vazia(self, tmp_path: Path) -> None:
        """Ente sem snapshots → lista de períodos vazia."""
        result = compare_periods("999999", snapshots_dir=tmp_path, settings=_make_settings())
        assert result.periods == []

    def test_snapshot_ausente_em_competencias_explicitas_ignorado(
        self, tmp_path: Path
    ) -> None:
        """Competência explicitada mas sem snapshot → período ignorado."""
        _write_resultado_snapshot(
            tmp_path, "250400", "2024-01",
            pd.DataFrame(columns=FACT_RESULTADO_REGRAS_COLUMNS),
        )

        result = compare_periods(
            "250400",
            snapshots_dir=tmp_path,
            settings=_make_settings(),
            competencias=["2024-01", "2024-02"],  # 2024-02 não existe
        )
        assert len(result.periods) == 1
        assert result.periods[0].competencia == "2024-01"

    def test_score_delta_entre_periodos(self, tmp_path: Path) -> None:
        """delta calculado corretamente entre períodos."""
        for comp in ("2024-01", "2024-02"):
            _write_resultado_snapshot(
                tmp_path, "250400", comp,
                pd.DataFrame(columns=FACT_RESULTADO_REGRAS_COLUMNS),
            )

        result = compare_periods("250400", snapshots_dir=tmp_path, settings=_make_settings())
        assert len(result.periods) == 2
        assert result.score_delta(0) is None
        assert result.score_delta(1) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# compare_periods CLI
# ---------------------------------------------------------------------------


class TestComparePeriodsCLI:
    def test_run_cli_sem_snapshots_retorna_2(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """CLI sem snapshots retorna exit code 2."""
        import ranking_msc.config.settings as _settings_mod

        monkeypatch.setattr(
            _settings_mod,
            "load_settings",
            lambda path=None: _make_settings(),
        )

        from scripts.compare_periods import run_cli

        code = run_cli(["--siconfi", "999999", "--snapshots-dir", str(tmp_path)])
        assert code == 2

    def test_run_cli_com_snapshots_retorna_0(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """CLI com snapshots disponíveis retorna exit code 0."""
        _write_resultado_snapshot(
            tmp_path, "250400", "2024-01",
            pd.DataFrame(columns=FACT_RESULTADO_REGRAS_COLUMNS),
        )

        import ranking_msc.config.settings as _settings_mod

        monkeypatch.setattr(
            _settings_mod,
            "load_settings",
            lambda path=None: _make_settings(),
        )

        from scripts.compare_periods import run_cli

        code = run_cli(["--siconfi", "250400", "--snapshots-dir", str(tmp_path)])
        assert code == 0

    def test_run_cli_com_output_dir_exporta_excel(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Finding 4: CLI com --output-dir exporta relatório Excel consolidado."""
        _write_resultado_snapshot(
            tmp_path, "250400", "2024-01",
            pd.DataFrame(columns=FACT_RESULTADO_REGRAS_COLUMNS),
        )

        import ranking_msc.config.settings as _settings_mod

        monkeypatch.setattr(
            _settings_mod,
            "load_settings",
            lambda path=None: _make_settings(),
        )

        output_dir = tmp_path / "reports"

        from scripts.compare_periods import run_cli

        code = run_cli([
            "--siconfi", "250400",
            "--snapshots-dir", str(tmp_path),
            "--output-dir", str(output_dir),
        ])

        assert code == 0
        excel_files = list(output_dir.glob("consolidado_*.xlsx"))
        assert len(excel_files) == 1, (
            f"Esperado 1 arquivo consolidado_*.xlsx em {output_dir}, encontrado: {excel_files}"
        )


# ---------------------------------------------------------------------------
# Regressão — Finding 1: estabilidade de scores históricos
# ---------------------------------------------------------------------------


class TestScoreEstabilidadeHistorica:
    """Verifica que scores históricos não mudam quando settings.rules.enabled cresce."""

    def test_score_estavel_quando_regras_mudam(self, tmp_path: Path) -> None:
        """Finding 1: score histórico não muda quando settings.rules.enabled cresce.

        Cenário real:
        - Snapshot gravado com R001 habilitado; R001 gerou 1 ERRO.
        - Posteriormente R002 é adicionado a settings (ambas em dimensão Estrutura).
        - Se os metadados forem ignorados e settings for usado, R002 passa → score
          sobe (R001 falhou + R002 passou = pontuação parcial em Estrutura).
        - Se os metadados forem respeitados, apenas R001 é avaliado → score
          permanece o mesmo independentemente do settings passado.
        - O teste falha quando compare_periods() ignora os metadados persistidos.
        """
        # Snapshot com 1 ERRO de R001 — score NÃO é neutro
        pendencias = _make_pendencias(["R001"], ["ERRO"])
        _write_resultado_snapshot(tmp_path, "250400", "2024-01", pendencias)
        # Metadados persistem que apenas R001 foi executado naquele período
        write_scoring_metadata(
            ["R001"],
            "2024-01",
            base_dir=tmp_path / "250400",
        )

        # Chamada com settings original (só R001) — deve usar metadados
        settings_original = _make_settings(enabled=["R001"])
        result_original = compare_periods(
            "250400", snapshots_dir=tmp_path, settings=settings_original
        )
        assert len(result_original.periods) == 1
        score_original = result_original.periods[0].score_result.pontuacao

        # Chamada com settings ampliado (R001 + R002) — ainda deve usar metadados
        # Se metadados forem ignorados, R002 (sem erros) eleva o score → falso positivo
        settings_ampliado = _make_settings(enabled=["R001", "R002"])
        result_ampliado = compare_periods(
            "250400", snapshots_dir=tmp_path, settings=settings_ampliado
        )
        assert len(result_ampliado.periods) == 1
        score_ampliado = result_ampliado.periods[0].score_result.pontuacao

        # Scores devem ser idênticos: ambas as chamadas devem ter usado ["R001"]
        assert score_original == score_ampliado, (
            f"Score histórico mudou de {score_original:.2f} para {score_ampliado:.2f} "
            "apenas porque settings.rules.enabled foi expandido — "
            "compare_periods() deve usar os metadados persistidos, não settings."
        )

    def test_fallback_sem_metadata_usa_settings_e_loga_warning(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Finding 1 (fallback): sem scoring_metadata.json, usa settings e avisa."""
        import logging

        pendencias = pd.DataFrame(columns=FACT_RESULTADO_REGRAS_COLUMNS)
        _write_resultado_snapshot(tmp_path, "250400", "2024-01", pendencias)
        # NÃO grava scoring_metadata.json — simula snapshot legado

        settings = _make_settings(enabled=[])
        with caplog.at_level(logging.WARNING, logger="ranking_msc"):
            result = compare_periods(
                "250400",
                snapshots_dir=tmp_path,
                settings=settings,
            )

        assert len(result.periods) == 1
        assert "fallback" in caplog.text.lower() or "metadados" in caplog.text.lower()


# ---------------------------------------------------------------------------
# Regressão — Finding 2: validação de metadados corrompidos
# ---------------------------------------------------------------------------


class TestReadScoringMetadataValidacao:
    """Verifica que read_scoring_metadata rejeita payloads estruturalmente inválidos."""

    def _write_raw(self, tmp_path: Path, content: str) -> None:
        d = tmp_path / "2024-01"
        d.mkdir(parents=True, exist_ok=True)
        (d / "scoring_metadata.json").write_text(content, encoding="utf-8")

    def test_json_valido_retorna_lista(self, tmp_path: Path) -> None:
        """Payload correto é aceito."""
        from ranking_msc.outputs.snapshot import read_scoring_metadata

        self._write_raw(tmp_path, '{"executed_rule_ids": ["R001", "R002"]}')
        result = read_scoring_metadata("2024-01", base_dir=tmp_path)
        assert result == ["R001", "R002"]

    def test_payload_nao_dict_retorna_none(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """JSON que não é objeto (ex: lista) → None + warning."""
        import logging

        from ranking_msc.outputs.snapshot import read_scoring_metadata

        self._write_raw(tmp_path, '["R001", "R002"]')
        with caplog.at_level(logging.WARNING, logger="ranking_msc"):
            result = read_scoring_metadata("2024-01", base_dir=tmp_path)
        assert result is None
        assert caplog.text != ""

    def test_executed_rule_ids_ausente_retorna_none(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Chave 'executed_rule_ids' ausente → None + warning."""
        import logging

        from ranking_msc.outputs.snapshot import read_scoring_metadata

        self._write_raw(tmp_path, '{"other_key": []}')
        with caplog.at_level(logging.WARNING, logger="ranking_msc"):
            result = read_scoring_metadata("2024-01", base_dir=tmp_path)
        assert result is None

    def test_executed_rule_ids_string_retorna_none(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """'executed_rule_ids' como string (ex: "R001") → None, não itera chars."""
        import logging

        from ranking_msc.outputs.snapshot import read_scoring_metadata

        self._write_raw(tmp_path, '{"executed_rule_ids": "R001"}')
        with caplog.at_level(logging.WARNING, logger="ranking_msc"):
            result = read_scoring_metadata("2024-01", base_dir=tmp_path)
        assert result is None

    def test_executed_rule_ids_com_item_nao_string_retorna_none(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Lista com item não-string → None + warning."""
        import logging

        from ranking_msc.outputs.snapshot import read_scoring_metadata

        self._write_raw(tmp_path, '{"executed_rule_ids": ["R001", 42]}')
        with caplog.at_level(logging.WARNING, logger="ranking_msc"):
            result = read_scoring_metadata("2024-01", base_dir=tmp_path)
        assert result is None
