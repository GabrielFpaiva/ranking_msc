"""
tests/test_benchmark.py
~~~~~~~~~~~~~~~~~~~~~~~

Testes dos componentes de benchmark: generator, profiler e reporter.

Não testa tempos absolutos (flaky por hardware) nem CLI end-to-end
em tamanhos grandes (lento). Foca em corretude dos componentes.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from ranking_msc.benchmark.generator import generate_csv
from ranking_msc.benchmark.profiler import (
    BenchmarkResult,
    RuleMetrics,
    StageMetrics,
    instrument_rules,
    measure,
)
from ranking_msc.benchmark.reporter import write_report

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def ref_dir() -> str:
    """Diretório de referência real do projeto."""
    return "ref"


@pytest.fixture()
def tmp_csv(tmp_path: Path) -> Path:
    """Caminho temporário para CSV gerado."""
    return tmp_path / "test_benchmark.csv"


# ---------------------------------------------------------------------------
# TestGenerator
# ---------------------------------------------------------------------------

class TestGenerator:
    """Testes do gerador de CSV sintético."""

    def test_generate_csv_schema_correto(
        self, tmp_csv: Path, ref_dir: str
    ) -> None:
        """CSV gerado tem delimiter ';', line ending '\\r' e colunas corretas."""
        generate_csv(n_rows=10, path=tmp_csv, ref_dir=ref_dir)

        content = tmp_csv.read_bytes().decode("ascii")
        # Verificar line ending \r (sem \n)
        assert "\r" in content
        # Separar linhas pelo \r
        lines = content.strip().split("\r")
        assert len(lines) >= 3  # metadata + header + pelo menos 1 dado

        # Header (linha 2) deve conter colunas esperadas
        header = lines[1]
        assert "CONTA" in header
        assert "Valor" in header
        assert "Tipo_valor" in header
        assert "Natureza_valor" in header
        # Delimiter ;
        assert ";" in header

    def test_generate_csv_n_rows_correto(
        self, tmp_csv: Path, ref_dir: str
    ) -> None:
        """Gera exatamente n_rows linhas de dados."""
        n = 100
        generate_csv(n_rows=n, path=tmp_csv, ref_dir=ref_dir)

        content = tmp_csv.read_bytes().decode("ascii")
        lines = content.strip().split("\r")
        # linha 0 = metadata, linha 1 = header, linhas 2+ = dados
        data_lines = lines[2:]
        assert len(data_lines) == n

    def test_generate_csv_deterministico_com_seed(
        self, tmp_path: Path, ref_dir: str
    ) -> None:
        """Mesmo seed → mesmo conteúdo."""
        path1 = tmp_path / "csv1.csv"
        path2 = tmp_path / "csv2.csv"

        generate_csv(n_rows=50, path=path1, seed=123, ref_dir=ref_dir)
        generate_csv(n_rows=50, path=path2, seed=123, ref_dir=ref_dir)

        assert path1.read_bytes() == path2.read_bytes()

    def test_generate_csv_ic_tipo_validos(
        self, tmp_csv: Path, ref_dir: str
    ) -> None:
        """CSV gerado é processável por normalize_ic sem erro."""
        from ranking_msc.io.reader_msc import read_msc_csv
        from ranking_msc.transform.ic_normalize import normalize_ic

        generate_csv(n_rows=50, path=tmp_csv, ref_dir=ref_dir)
        raw = read_msc_csv(tmp_csv)
        # Não deve levantar exceção
        normalize_ic(raw.df)

    def test_generate_csv_usa_apenas_contas_analiticas(
        self, tmp_csv: Path, ref_dir: str
    ) -> None:
        """Contas geradas são apenas do nível 'Último' (analítico).

        Contas 'Superior' são de síntese e não devem aparecer em CSVs
        MSC reais — o perfil do dataset sintético precisa refletir isso.
        """
        import pandas as pd

        pcasp = pd.read_csv(
            Path(ref_dir) / "pcasp.csv", sep=";", dtype=str, keep_default_na=False
        )
        pcasp["nivel"] = pcasp["nivel"].str.strip()
        contas_superiores = set(
            pcasp[pcasp["nivel"].str.lower() == "superior"]["conta_contabil"]
        )
        contas_ultimas = set(
            pcasp[pcasp["nivel"].str.lower() == "último"]["conta_contabil"]
        )

        generate_csv(n_rows=200, path=tmp_csv, ref_dir=ref_dir, seed=7)

        content = tmp_csv.read_bytes().decode("ascii")
        lines = content.strip().split("\r")
        data_lines = lines[2:]
        contas_geradas = {line.split(";")[0] for line in data_lines}

        assert contas_geradas.isdisjoint(contas_superiores), (
            "CSV sintético não deve conter contas de nível 'Superior' "
            f"(encontradas: {contas_geradas & contas_superiores})"
        )
        assert contas_geradas.issubset(contas_ultimas), (
            "Todas as contas geradas devem ser do nível 'Último'"
        )

    def test_generate_csv_pcasp_sem_ultimo_levanta_erro(
        self, tmp_path: Path
    ) -> None:
        """PCASP sem contas 'Último' deve levantar BenchmarkError.

        Evita fallback silencioso que incluiria contas de síntese
        (Superior) no dataset sintético.
        """
        from ranking_msc.exceptions import BenchmarkError

        fake_ref = tmp_path / "ref"
        fake_ref.mkdir()
        (fake_ref / "pcasp.csv").write_text(
            "conta_contabil;id_ic;nat_saldo;status;nivel;ind_sf\n"
            "100000000;0;Devedora;Ativa;Superior;-\n"
            "110000000;0;Devedora;Ativa;Superior;-\n",
            encoding="utf-8",
        )
        (fake_ref / "mapeamento_ic_tipo.csv").write_text(
            "tipo1;tipo2;tipo3;tipo4;tipo5;tipo6\nPO;;;;;\n",
            encoding="utf-8",
        )

        out = tmp_path / "out.csv"
        with pytest.raises(BenchmarkError, match="Último"):
            generate_csv(n_rows=10, path=out, ref_dir=fake_ref)


# ---------------------------------------------------------------------------
# TestProfiler
# ---------------------------------------------------------------------------

class TestProfiler:
    """Testes do profiler de performance."""

    def test_measure_retorna_stage_metrics(self) -> None:
        """Context manager popula wall_seconds e rss_delta_mb."""
        with measure("test_stage") as m:
            time.sleep(0.01)  # Mínimo mensurável

        stage = m.to_stage()
        assert isinstance(stage, StageMetrics)
        assert stage.name == "test_stage"
        assert stage.wall_seconds > 0
        # rss_delta pode ser 0 ou negativo (GC), apenas verificar tipo
        assert isinstance(stage.rss_delta_mb, float)

    def test_instrument_rules_decora_e_reverte(self) -> None:
        """Patch é aplicado dentro e revertido fora do context manager."""
        from ranking_msc.rules.base import RULE_REGISTRY

        # Pegar a primeira regra registrada para verificar
        if not RULE_REGISTRY:
            pytest.skip("Nenhuma regra registrada no RULE_REGISTRY")
        first_cls = next(iter(RULE_REGISTRY.values()))
        original = first_cls.execute

        with instrument_rules():
            # Dentro: método está patcheado
            assert first_cls.execute is not original

        # Fora: método revertido
        assert first_cls.execute is original

    def test_benchmark_result_throughput_calculado(self) -> None:
        """Divisão n_rows / total_seconds é correta."""
        result = BenchmarkResult(
            n_rows=1000,
            total_seconds=2.0,
            peak_rss_mb=100.0,
            throughput_rows_per_sec=1000 / 2.0,
        )
        assert result.throughput_rows_per_sec == 500.0

    def test_benchmark_result_failed(self) -> None:
        """BenchmarkResult falho registra motivo."""
        result = BenchmarkResult(
            n_rows=1000,
            total_seconds=0.0,
            peak_rss_mb=0.0,
            throughput_rows_per_sec=0.0,
            failed=True,
            failure_reason="OOM",
        )
        assert result.failed is True
        assert result.failure_reason == "OOM"


# ---------------------------------------------------------------------------
# TestReporter
# ---------------------------------------------------------------------------

class TestReporter:
    """Testes do gerador de relatório."""

    def _make_result(
        self,
        n_rows: int = 1000,
        total_seconds: float = 5.0,
        *,
        failed: bool = False,
    ) -> BenchmarkResult:
        """Cria BenchmarkResult de teste."""
        stages = [
            StageMetrics(name="read_csv", wall_seconds=1.0, rss_delta_mb=10.0),
            StageMetrics(name="normalize_ic", wall_seconds=1.5, rss_delta_mb=5.0),
            StageMetrics(name="run_engine", wall_seconds=2.5, rss_delta_mb=20.0),
        ]
        rules = [
            RuleMetrics(rule_id="R030", wall_seconds=0.8, issue_count=14),
            RuleMetrics(rule_id="R082", wall_seconds=0.5, issue_count=3),
            RuleMetrics(rule_id="R010", wall_seconds=0.3, issue_count=0),
        ]
        if failed:
            return BenchmarkResult(
                n_rows=n_rows,
                total_seconds=0.0,
                peak_rss_mb=0.0,
                throughput_rows_per_sec=0.0,
                failed=True,
                failure_reason="OOM",
            )
        return BenchmarkResult(
            n_rows=n_rows,
            total_seconds=total_seconds,
            peak_rss_mb=150.0,
            throughput_rows_per_sec=n_rows / total_seconds,
            stages=stages,
            rules=rules,
        )

    def test_write_report_gera_tres_tabelas(self, tmp_path: Path) -> None:
        """Relatório contém 'Resumo geral', 'Tempo por etapa', 'Top-5 regras'."""
        output = tmp_path / "report.md"
        results = [self._make_result()]
        write_report(results, output)

        content = output.read_text(encoding="utf-8")
        assert "Resumo geral" in content
        assert "Tempo por etapa" in content
        assert "Top-5 regras" in content

    def test_report_header_tem_commit_hash_e_data(self, tmp_path: Path) -> None:
        """Header do relatório contém commit hash e data de geração."""
        output = tmp_path / "report.md"
        results = [self._make_result()]
        write_report(results, output)

        content = output.read_text(encoding="utf-8")
        assert "**Gerado em:**" in content
        assert "**Commit:**" in content
        assert "**Python:**" in content

    def test_report_com_resultado_failed(self, tmp_path: Path) -> None:
        """Relatório exibe FAIL para resultados com erro."""
        output = tmp_path / "report.md"
        results = [
            self._make_result(n_rows=1000),
            self._make_result(n_rows=500_000, failed=True),
        ]
        write_report(results, output)

        content = output.read_text(encoding="utf-8")
        assert "FAIL" in content
        assert "OOM" in content

    def test_report_interrompido(self, tmp_path: Path) -> None:
        """Relatório com flag interrupted exibe aviso."""
        output = tmp_path / "report.md"
        results = [self._make_result()]
        write_report(results, output, interrupted=True)

        content = output.read_text(encoding="utf-8")
        assert "INTERROMPIDO" in content


# ---------------------------------------------------------------------------
# TestInstrumentedPipeline — propagação de falha do engine
# ---------------------------------------------------------------------------

def _load_benchmark_script():
    """Carrega scripts/benchmark.py como módulo (não é pacote)."""
    import importlib.util

    script_path = Path(__file__).parent.parent / "scripts" / "benchmark.py"
    spec = importlib.util.spec_from_file_location("_benchmark_script", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestInstrumentedPipelinePropagatesEngineFailure:
    """Garante que erros internos do engine viram BenchmarkResult.failed=True.

    Com ``rules.fail_fast=False`` (padrão), ``run_engine`` captura exceções
    por regra e retorna ``EngineResult`` com ``regras_com_erro > 0`` e
    ``status`` != ``OK``. Sem tratamento, o benchmark publicava throughput
    normal para uma execução inválida.
    """

    def test_engine_result_com_erros_marca_falha(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """regras_com_erro > 0 → BenchmarkResult.failed=True + failure_reason."""
        from ranking_msc.config.settings import load_settings
        from ranking_msc.engine.executor import EngineContext, EngineResult

        bench = _load_benchmark_script()

        # Stub que substitui run_engine por uma versão que retorna erro
        def fake_run_engine(_df, ctx: EngineContext) -> EngineResult:
            return EngineResult(
                context=ctx,
                regras_executadas=3,
                regras_com_erro=1,
                erros=[{
                    "regra_id": "R030",
                    "mensagem": "boom",
                    "fatal": False,
                }],
            )

        monkeypatch.setattr(bench, "run_engine", fake_run_engine)

        # Gerar CSV pequeno real para alimentar o pipeline até o engine
        csv_path = tmp_path / "msc.csv"
        generate_csv(n_rows=10, path=csv_path, ref_dir="ref")

        settings = load_settings()
        result = bench._run_instrumented_pipeline(
            csv_path=csv_path, n_rows=10, settings=settings,
        )

        assert result.failed is True
        assert result.failure_reason is not None
        assert "R030" in result.failure_reason
        assert "regras_com_erro=1" in result.failure_reason

    def test_engine_result_ok_nao_marca_falha(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """status=OK e regras_com_erro=0 → failed=False."""
        from ranking_msc.config.settings import load_settings
        from ranking_msc.engine.executor import EngineContext, EngineResult

        bench = _load_benchmark_script()

        def fake_run_engine(_df, ctx: EngineContext) -> EngineResult:
            return EngineResult(context=ctx, regras_executadas=3, regras_com_erro=0)

        monkeypatch.setattr(bench, "run_engine", fake_run_engine)

        csv_path = tmp_path / "msc.csv"
        generate_csv(n_rows=10, path=csv_path, ref_dir="ref")

        settings = load_settings()
        result = bench._run_instrumented_pipeline(
            csv_path=csv_path, n_rows=10, settings=settings,
        )

        assert result.failed is False
        assert result.failure_reason is None
