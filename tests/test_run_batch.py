"""Testes da CLI de processamento em lote em ``scripts/run_batch.py``."""

from __future__ import annotations

import logging
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest
import scripts.run_batch as batch

from ranking_msc.config.settings import PathsSettings, Settings
from ranking_msc.engine.score_engine import ScoreResult
from ranking_msc.exceptions import ConfigError, InputFormatError
from ranking_msc.io.reader_msc import RawMSC

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PENDENCIAS_COLUMNS = [
    "regra_id",
    "regra_nome",
    "dimensao",
    "severidade",
    "conta_contabil",
    "descricao",
    "valor_esperado",
    "valor_encontrado",
    "competencia",
]

_EMPTY_PENDENCIAS = pd.DataFrame(columns=_PENDENCIAS_COLUMNS)

_SAMPLE_RAW_MSC = RawMSC(
    competencia="2025-11",
    siconfi="2507507EX",
    df=pd.DataFrame(
        [
            {
                "competencia": "2025-11",
                "siconfi": "2507507EX",
                "conta_contabil": "111110200",
                "ic1": "10131",
                "tipo1": "PO",
                "ic2": "",
                "tipo2": "",
                "ic3": "",
                "tipo3": "",
                "ic4": "",
                "tipo4": "",
                "ic5": "",
                "tipo5": "",
                "ic6": "",
                "tipo6": "",
                "saldo_inicial_debito": 1.0,
                "saldo_inicial_credito": 0.0,
                "movimento_debito": 0.0,
                "movimento_credito": 0.0,
                "saldo_final_debito": 1.0,
                "saldo_final_credito": 0.0,
            }
        ]
    ),
    source="fake.csv",
)


_FAKE_SCORE = ScoreResult(
    pontuacao=100.0,
    banda="A",
    dimensions={},
    regras_executadas=0,
    regras_falhas_erro=0,
    regras_falhas_alerta=0,
)


def _fake_engine_ok(_df: pd.DataFrame, _ctx: object) -> SimpleNamespace:
    """Stub de run_engine que retorna status OK sem pendências."""
    return SimpleNamespace(
        status="OK",
        pendencias=_EMPTY_PENDENCIAS,
        total_pendencias=0,
        executed_rule_ids=[],
    )


def _fake_engine_erro(_df: pd.DataFrame, _ctx: object) -> SimpleNamespace:
    """Stub de run_engine que retorna status ERRO."""
    return SimpleNamespace(
        status="ERRO",
        pendencias=_EMPTY_PENDENCIAS,
        total_pendencias=0,
        executed_rule_ids=[],
    )


class _NullStore:
    """Store que não grava nada (o teste só olha a orquestração)."""

    def save_msc(self, *_args: object, **_kwargs: object) -> None:
        """Ignora a matriz."""

    def save_resultado(self, *_args: object, **_kwargs: object) -> None:
        """Ignora o resultado."""


def _noop(*_args: object, **_kwargs: object) -> Path:
    """Stub genérico para funções de I/O que retornam um Path."""
    return Path("/tmp/fake")


# ---------------------------------------------------------------------------
# _find_csv_files
# ---------------------------------------------------------------------------


def test_find_csv_files_retorna_csvs_ordenados(tmp_path: Path) -> None:
    """Retorna lista de CSVs no diretório, ordenada por nome."""
    (tmp_path / "c.csv").touch()
    (tmp_path / "a.csv").touch()
    (tmp_path / "b.csv").touch()
    (tmp_path / "outros.txt").touch()

    result = batch._find_csv_files(tmp_path)

    assert [p.name for p in result] == ["a.csv", "b.csv", "c.csv"]


def test_find_csv_files_diretorio_vazio_retorna_lista_vazia(tmp_path: Path) -> None:
    """Diretório sem CSVs retorna lista vazia."""
    result = batch._find_csv_files(tmp_path)
    assert result == []


def test_find_csv_files_diretorio_inexistente_retorna_lista_vazia(tmp_path: Path) -> None:
    """Caminho inexistente não levanta exceção — retorna lista vazia."""
    result = batch._find_csv_files(tmp_path / "nao_existe")
    assert result == []


def test_find_csv_files_nao_recursivo(tmp_path: Path) -> None:
    """Não varre subdiretórios — apenas o diretório raiz."""
    sub = tmp_path / "subdir"
    sub.mkdir()
    (sub / "escondido.csv").touch()
    (tmp_path / "visivel.csv").touch()

    result = batch._find_csv_files(tmp_path)

    assert [p.name for p in result] == ["visivel.csv"]


# ---------------------------------------------------------------------------
# BatchSummary
# ---------------------------------------------------------------------------


def test_batch_summary_exit_code_todos_ok() -> None:
    """Exit code 0 quando todos os resultados são OK."""
    summary = batch.BatchSummary(
        results=[
            batch.CsvResult(csv_path=Path("a.csv"), status="OK"),
            batch.CsvResult(csv_path=Path("b.csv"), status="OK"),
        ]
    )
    assert summary.exit_code == 0
    assert summary.succeeded == 2
    assert summary.failed == 0


def test_batch_summary_exit_code_algum_falhou() -> None:
    """Exit code 1 quando há pelo menos um resultado ERRO."""
    summary = batch.BatchSummary(
        results=[
            batch.CsvResult(csv_path=Path("a.csv"), status="OK"),
            batch.CsvResult(csv_path=Path("b.csv"), status="ERRO"),
        ]
    )
    assert summary.exit_code == 1
    assert summary.failed == 1


def test_batch_summary_exit_code_parcial() -> None:
    """Exit code 1 quando há pelo menos um resultado PARCIAL."""
    summary = batch.BatchSummary(
        results=[
            batch.CsvResult(csv_path=Path("a.csv"), status="PARCIAL"),
        ]
    )
    assert summary.exit_code == 1
    assert summary.partial == 1


def test_csv_result_succeeded_ok_e_parcial() -> None:
    """CsvResult.succeeded é True para OK e PARCIAL."""
    assert batch.CsvResult(csv_path=Path("a.csv"), status="OK").succeeded is True
    assert batch.CsvResult(csv_path=Path("a.csv"), status="PARCIAL").succeeded is True
    assert batch.CsvResult(csv_path=Path("a.csv"), status="ERRO").succeeded is False
    assert batch.CsvResult(csv_path=Path("a.csv"), status="EXCECAO").succeeded is False


# ---------------------------------------------------------------------------
# _resolve_output_paths
# ---------------------------------------------------------------------------


def test_resolve_output_paths_sem_output_dir_usa_settings() -> None:
    """Resolve diretórios a partir de settings quando --output-dir não é informado."""
    settings = Settings(
        paths=PathsSettings(
            data_dir="./data",
            snapshots_dir="./data/snapshots",
            reports_dir="./data/reports",
            logs_dir="./data/logs",
            ref_dir="./ref",
        )
    )

    resolved = batch._resolve_output_paths(settings, None)

    assert resolved.snapshots_dir == (batch._PROJECT_ROOT / "data/snapshots").resolve()
    assert resolved.reports_dir == (batch._PROJECT_ROOT / "data/reports").resolve()
    assert resolved.logs_dir == (batch._PROJECT_ROOT / "data/logs").resolve()


def test_resolve_output_paths_com_output_dir_sobrescreve_settings(tmp_path: Path) -> None:
    """Quando --output-dir é informado, deriva snapshots/reports/logs nele."""
    settings = Settings()
    base_dir = tmp_path / "saida"

    resolved = batch._resolve_output_paths(settings, str(base_dir))

    assert resolved.snapshots_dir == (base_dir / "snapshots").resolve()
    assert resolved.reports_dir == (base_dir / "reports").resolve()
    assert resolved.logs_dir == (base_dir / "logs").resolve()


# ---------------------------------------------------------------------------
# _execute_single_csv
# ---------------------------------------------------------------------------


def test_execute_single_csv_fluxo_feliz(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pipeline completo para um CSV retorna CsvResult com status OK."""
    logger = logging.getLogger("test_batch")
    settings = Settings()
    output_paths = batch.OutputPaths(
        snapshots_dir=tmp_path / "snapshots",
        reports_dir=tmp_path / "reports",
        logs_dir=tmp_path / "logs",
    )
    csv_path = tmp_path / "teste.csv"
    csv_path.touch()

    monkeypatch.setattr(batch, "read_msc_csv", lambda _: _SAMPLE_RAW_MSC)
    monkeypatch.setattr(batch, "normalize_ic", lambda df: df)
    monkeypatch.setattr(batch, "make_store", lambda *_a: _NullStore())
    monkeypatch.setattr(batch, "registro_execucao", lambda *_a: None)
    monkeypatch.setattr(batch, "run_engine", _fake_engine_ok)
    monkeypatch.setattr(batch, "calculate_score", lambda df, ids: _FAKE_SCORE)
    monkeypatch.setattr(batch, "export_issues_excel", _noop)
    monkeypatch.setattr(batch, "log_execucao", lambda *a, **kw: None)

    result = batch._execute_single_csv(
        csv_path=csv_path,
        settings=settings,
        output_paths=output_paths,
        logger=logger,
    )

    assert result.status == "OK"
    assert result.competencia == "2025-11"
    assert result.siconfi == "2507507EX"
    assert result.pendencias == 0
    assert result.error_message == ""


def test_execute_single_csv_usuario_e_batch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """EngineContext criado pelo batch usa usuario='batch'."""
    logger = logging.getLogger("test_batch")
    settings = Settings()
    output_paths = batch.OutputPaths(
        snapshots_dir=tmp_path / "snapshots",
        reports_dir=tmp_path / "reports",
        logs_dir=tmp_path / "logs",
    )
    csv_path = tmp_path / "teste.csv"
    csv_path.touch()

    captured: dict[str, str] = {}

    def fake_run_engine(_df: pd.DataFrame, ctx: object) -> SimpleNamespace:
        captured["usuario"] = getattr(ctx, "usuario", "")
        return SimpleNamespace(
            status="OK",
            pendencias=_EMPTY_PENDENCIAS,
            total_pendencias=0,
            executed_rule_ids=[],
        )

    monkeypatch.setattr(batch, "read_msc_csv", lambda _: _SAMPLE_RAW_MSC)
    monkeypatch.setattr(batch, "normalize_ic", lambda df: df)
    monkeypatch.setattr(batch, "make_store", lambda *_a: _NullStore())
    monkeypatch.setattr(batch, "registro_execucao", lambda *_a: None)
    monkeypatch.setattr(batch, "run_engine", fake_run_engine)
    monkeypatch.setattr(batch, "calculate_score", lambda df, ids: _FAKE_SCORE)
    monkeypatch.setattr(batch, "export_issues_excel", _noop)
    monkeypatch.setattr(batch, "log_execucao", lambda *a, **kw: None)

    batch._execute_single_csv(
        csv_path=csv_path,
        settings=settings,
        output_paths=output_paths,
        logger=logger,
    )

    assert captured["usuario"] == "batch"


def test_execute_single_csv_erro_ranking_msc_nao_propaga(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """RankingMSCError é capturado e retornado como CsvResult com status EXCECAO."""
    logger = logging.getLogger("test_batch")
    settings = Settings()
    output_paths = batch.OutputPaths(
        snapshots_dir=tmp_path / "snapshots",
        reports_dir=tmp_path / "reports",
        logs_dir=tmp_path / "logs",
    )
    csv_path = tmp_path / "invalido.csv"
    csv_path.touch()

    monkeypatch.setattr(
        batch,
        "read_msc_csv",
        lambda _: (_ for _ in ()).throw(InputFormatError("CSV inválido")),
    )

    result = batch._execute_single_csv(
        csv_path=csv_path,
        settings=settings,
        output_paths=output_paths,
        logger=logger,
    )

    assert result.status == "EXCECAO"
    assert "CSV inválido" in result.error_message


def test_execute_single_csv_erro_inesperado_nao_propaga(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exceção inesperada é capturada e retornada como CsvResult com status EXCECAO."""
    logger = logging.getLogger("test_batch")
    settings = Settings()
    output_paths = batch.OutputPaths(
        snapshots_dir=tmp_path / "snapshots",
        reports_dir=tmp_path / "reports",
        logs_dir=tmp_path / "logs",
    )
    csv_path = tmp_path / "problema.csv"
    csv_path.touch()

    monkeypatch.setattr(
        batch,
        "read_msc_csv",
        lambda _: (_ for _ in ()).throw(RuntimeError("falha inesperada")),
    )

    result = batch._execute_single_csv(
        csv_path=csv_path,
        settings=settings,
        output_paths=output_paths,
        logger=logger,
    )

    assert result.status == "EXCECAO"
    assert "falha inesperada" in result.error_message


# ---------------------------------------------------------------------------
# run_cli (fluxo completo)
# ---------------------------------------------------------------------------


def test_run_cli_batch_fluxo_feliz_retorna_zero(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Batch com dois CSVs sem erros retorna exit code 0."""
    input_dir = tmp_path / "csvs"
    input_dir.mkdir()
    (input_dir / "a.csv").touch()
    (input_dir / "b.csv").touch()

    config_path = tmp_path / "settings.yaml"
    config_path.write_text("app: {}\n", encoding="utf-8")

    output_base = tmp_path / "output"
    logger = logging.getLogger("test_batch_cli")

    monkeypatch.setattr(batch, "load_settings", lambda _: Settings())
    monkeypatch.setattr(batch, "setup_logging", lambda *, log_dir, **kw: logger)
    monkeypatch.setattr(batch, "read_msc_csv", lambda _: _SAMPLE_RAW_MSC)
    monkeypatch.setattr(batch, "normalize_ic", lambda df: df)
    monkeypatch.setattr(batch, "make_store", lambda *_a: _NullStore())
    monkeypatch.setattr(batch, "registro_execucao", lambda *_a: None)
    monkeypatch.setattr(batch, "run_engine", _fake_engine_ok)
    monkeypatch.setattr(batch, "calculate_score", lambda df, ids: _FAKE_SCORE)
    monkeypatch.setattr(batch, "export_issues_excel", _noop)
    monkeypatch.setattr(batch, "log_execucao", lambda *a, **kw: None)

    exit_code = batch.run_cli(
        [
            "--dir", str(input_dir),
            "--config", str(config_path),
            "--output-dir", str(output_base),
        ]
    )

    assert exit_code == 0


def test_run_cli_batch_csv_com_erro_continua_proximo(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Erro no primeiro CSV não impede processamento dos demais; exit code 1."""
    input_dir = tmp_path / "csvs"
    input_dir.mkdir()
    (input_dir / "bom.csv").touch()
    (input_dir / "ruim.csv").touch()

    logger = logging.getLogger("test_batch_cli_parcial")
    processed: list[str] = []

    def fake_read(path: Path) -> RawMSC:
        if "ruim" in path.name:
            raise InputFormatError("CSV inválido")
        processed.append(path.name)
        return _SAMPLE_RAW_MSC

    monkeypatch.setattr(batch, "load_settings", lambda _: Settings())
    monkeypatch.setattr(batch, "setup_logging", lambda *, log_dir, **kw: logger)
    monkeypatch.setattr(batch, "read_msc_csv", fake_read)
    monkeypatch.setattr(batch, "normalize_ic", lambda df: df)
    monkeypatch.setattr(batch, "make_store", lambda *_a: _NullStore())
    monkeypatch.setattr(batch, "registro_execucao", lambda *_a: None)
    monkeypatch.setattr(batch, "run_engine", _fake_engine_ok)
    monkeypatch.setattr(batch, "calculate_score", lambda df, ids: _FAKE_SCORE)
    monkeypatch.setattr(batch, "export_issues_excel", _noop)
    monkeypatch.setattr(batch, "log_execucao", lambda *a, **kw: None)

    exit_code = batch.run_cli(["--dir", str(input_dir)])

    assert exit_code == 1
    assert "bom.csv" in processed


def test_run_cli_batch_sem_csvs_retorna_codigo_2(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Diretório sem CSVs retorna exit code 2."""
    input_dir = tmp_path / "vazio"
    input_dir.mkdir()

    logger = logging.getLogger("test_batch_cli_vazio")

    monkeypatch.setattr(batch, "load_settings", lambda _: Settings())
    monkeypatch.setattr(batch, "setup_logging", lambda *, log_dir, **kw: logger)

    exit_code = batch.run_cli(["--dir", str(input_dir)])

    assert exit_code == 2


def test_run_cli_batch_erro_de_config_retorna_codigo_2(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Falha de configuração retorna exit code 2."""
    monkeypatch.setattr(
        batch,
        "load_settings",
        lambda _: (_ for _ in ()).throw(ConfigError("config inválido")),
    )

    exit_code = batch.run_cli(["--dir", "/qualquer"])

    assert exit_code == 2


def test_run_cli_batch_processa_dois_csvs_corretamente(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dois CSVs processados com sucesso produzem dois resultados OK no summary."""
    input_dir = tmp_path / "csvs"
    input_dir.mkdir()
    (input_dir / "jan.csv").touch()
    (input_dir / "fev.csv").touch()

    logger = logging.getLogger("test_batch_dois")
    captured_summaries: list[batch.BatchSummary] = []

    original_log_summary = batch._log_batch_summary

    def spy_log_summary(summary: batch.BatchSummary, log: logging.Logger) -> None:
        captured_summaries.append(summary)
        original_log_summary(summary, log)

    monkeypatch.setattr(batch, "load_settings", lambda _: Settings())
    monkeypatch.setattr(batch, "setup_logging", lambda *, log_dir, **kw: logger)
    monkeypatch.setattr(batch, "read_msc_csv", lambda _: _SAMPLE_RAW_MSC)
    monkeypatch.setattr(batch, "normalize_ic", lambda df: df)
    monkeypatch.setattr(batch, "make_store", lambda *_a: _NullStore())
    monkeypatch.setattr(batch, "registro_execucao", lambda *_a: None)
    monkeypatch.setattr(batch, "run_engine", _fake_engine_ok)
    monkeypatch.setattr(batch, "calculate_score", lambda df, ids: _FAKE_SCORE)
    monkeypatch.setattr(batch, "export_issues_excel", _noop)
    monkeypatch.setattr(batch, "log_execucao", lambda *a, **kw: None)
    monkeypatch.setattr(batch, "_log_batch_summary", spy_log_summary)

    batch.run_cli(["--dir", str(input_dir)])

    assert len(captured_summaries) == 1
    summary = captured_summaries[0]
    assert summary.total == 2
    assert summary.succeeded == 2
    assert summary.failed == 0


def test_execute_single_csv_engine_parcial_propaga_status(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Engine retornando PARCIAL gera CsvResult com status PARCIAL."""
    logger = logging.getLogger("test_batch_parcial")
    settings = Settings()
    output_paths = batch.OutputPaths(
        snapshots_dir=tmp_path / "snapshots",
        reports_dir=tmp_path / "reports",
        logs_dir=tmp_path / "logs",
    )
    csv_path = tmp_path / "parcial.csv"
    csv_path.touch()

    monkeypatch.setattr(batch, "read_msc_csv", lambda _: _SAMPLE_RAW_MSC)
    monkeypatch.setattr(batch, "normalize_ic", lambda df: df)
    monkeypatch.setattr(batch, "make_store", lambda *_a: _NullStore())
    monkeypatch.setattr(batch, "registro_execucao", lambda *_a: None)
    monkeypatch.setattr(batch, "run_engine", _fake_engine_erro)
    monkeypatch.setattr(batch, "calculate_score", lambda df, ids: _FAKE_SCORE)
    monkeypatch.setattr(batch, "export_issues_excel", _noop)
    monkeypatch.setattr(batch, "log_execucao", lambda *a, **kw: None)

    result = batch._execute_single_csv(
        csv_path=csv_path,
        settings=settings,
        output_paths=output_paths,
        logger=logger,
    )

    assert result.status == "ERRO"
    assert result.error_message == ""


def test_run_cli_batch_dir_inexistente_retorna_codigo_2(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Diretório inexistente (não vazio, mas ausente) retorna exit code 2."""
    input_dir = tmp_path / "nao_existe"

    logger = logging.getLogger("test_batch_cli_dir_inexistente")

    monkeypatch.setattr(batch, "load_settings", lambda _: Settings())
    monkeypatch.setattr(batch, "setup_logging", lambda *, log_dir, **kw: logger)

    exit_code = batch.run_cli(["--dir", str(input_dir)])

    assert exit_code == 2


# ---------------------------------------------------------------------------
# Regressões — findings da revisão F4
# ---------------------------------------------------------------------------


def test_filenames_unicos_para_csvs_da_mesma_competencia(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Finding 2: dois CSVs com mesmo siconfi e mesma competência não colidem.

    Cenário real: o mesmo ente reenvia o CSV com nome diferente. O filename
    deve incluir o stem do CSV para distinguir os dois relatórios.
    """
    logger = logging.getLogger("test_batch_filename_collision")
    settings = Settings()
    output_paths = batch.OutputPaths(
        snapshots_dir=tmp_path / "snapshots",
        reports_dir=tmp_path / "reports",
        logs_dir=tmp_path / "logs",
    )

    # Mesmo siconfi, mesma competência — apenas o nome do arquivo muda
    raw_same = _SAMPLE_RAW_MSC  # siconfi = "2507507EX", competencia = "2025-11"

    filenames_captured: list[str] = []

    def capture_export(
        df: pd.DataFrame, comp: str, *, output_dir: object,
        filename: str | None = None, **kw: object
    ) -> Path:
        if filename:
            filenames_captured.append(filename)
        return Path("/tmp/fake.xlsx")

    for csv_name in ["envio_v1.csv", "envio_v2.csv"]:
        csv_path = tmp_path / csv_name
        csv_path.touch()
        monkeypatch.setattr(batch, "read_msc_csv", lambda _: raw_same)
        monkeypatch.setattr(batch, "normalize_ic", lambda df: df)
        monkeypatch.setattr(batch, "make_store", lambda *_a: _NullStore())
        monkeypatch.setattr(batch, "registro_execucao", lambda *_a: None)
        monkeypatch.setattr(batch, "run_engine", _fake_engine_ok)
        monkeypatch.setattr(batch, "calculate_score", lambda df, ids: _FAKE_SCORE)
        monkeypatch.setattr(batch, "export_issues_excel", capture_export)
        monkeypatch.setattr(batch, "log_execucao", lambda *a, **kw: None)

        batch._execute_single_csv(
            csv_path=csv_path,
            settings=settings,
            output_paths=output_paths,
            logger=logger,
        )

    assert len(filenames_captured) == 2
    assert filenames_captured[0] != filenames_captured[1], (
        "Dois CSVs com mesmo siconfi e mesma competência geraram o mesmo filename"
        " — o stem do CSV deve fazer parte do nome do relatório"
    )
    assert "envio_v1" in filenames_captured[0]
    assert "envio_v2" in filenames_captured[1]


def test_batch_gera_aba_score_no_excel(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Finding 3: batch calcula score e passa score_result para export_issues_excel."""
    logger = logging.getLogger("test_batch_score_sheet")
    settings = Settings()
    output_paths = batch.OutputPaths(
        snapshots_dir=tmp_path / "snapshots",
        reports_dir=tmp_path / "reports",
        logs_dir=tmp_path / "logs",
    )
    csv_path = tmp_path / "teste.csv"
    csv_path.touch()

    score_results_received: list[object] = []

    def capture_export(
        df: object,
        comp: object,
        *,
        output_dir: object,
        filename: object = None,
        score_result: object = None,
        **kw: object,
    ) -> Path:
        score_results_received.append(score_result)
        return Path("/tmp/fake.xlsx")

    monkeypatch.setattr(batch, "read_msc_csv", lambda _: _SAMPLE_RAW_MSC)
    monkeypatch.setattr(batch, "normalize_ic", lambda df: df)
    monkeypatch.setattr(batch, "make_store", lambda *_a: _NullStore())
    monkeypatch.setattr(batch, "registro_execucao", lambda *_a: None)
    monkeypatch.setattr(batch, "run_engine", _fake_engine_ok)
    monkeypatch.setattr(batch, "calculate_score", lambda df, ids: _FAKE_SCORE)
    monkeypatch.setattr(batch, "export_issues_excel", capture_export)
    monkeypatch.setattr(batch, "log_execucao", lambda *a, **kw: None)

    batch._execute_single_csv(
        csv_path=csv_path,
        settings=settings,
        output_paths=output_paths,
        logger=logger,
    )

    assert len(score_results_received) == 1
    assert score_results_received[0] is _FAKE_SCORE, (
        "score_result não foi passado para export_issues_excel"
        " — aba Score ausente no relatório batch"
    )


def test_log_failure_sem_excecao_nao_emite_traceback(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Finding 6: _log_failure sem exceção ativa não loga 'NoneType: None'."""
    logger = logging.getLogger("test_log_failure")

    with caplog.at_level(logging.ERROR, logger="test_log_failure"):
        # Chama fora de qualquer bloco except — não há exceção ativa
        batch._log_failure(logger, "falha sem exceção")

    assert "NoneType" not in caplog.text
    assert "None" not in caplog.text or "NoneType" not in caplog.text
    # Mensagem deve ter sido logada normalmente
    assert "falha sem exceção" in caplog.text
