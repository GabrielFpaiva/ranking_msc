"""
tests/test_smoke.py
~~~~~~~~~~~~~~~~~~~

Smoke tests — verificam que o scaffold importa e funciona.
Não testam lógica de negócio (ainda não implementada).

Rodar:
    pytest
    pytest tests/test_smoke.py -v
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# 1. Imports básicos funcionam
# ---------------------------------------------------------------------------

class TestImports:
    """Verifica que todos os módulos importam sem erro."""

    def test_import_package(self) -> None:
        import ranking_msc
        assert ranking_msc.__version__

    def test_import_exceptions(self) -> None:
        from ranking_msc.exceptions import (
            ConfigError,
            ConcurrencyError,
            InputFormatError,
            RankingMSCError,
            ReportError,
            RuleExecutionError,
            SnapshotError,
        )
        # Todas herdam da base
        assert issubclass(ConfigError, RankingMSCError)
        assert issubclass(SnapshotError, RankingMSCError)

    def test_import_schemas(self) -> None:
        from ranking_msc.schemas import (
            FACT_EXECUCAO_COLUMNS,
            FACT_MSC_COLUMNS,
            FACT_RESULTADO_REGRAS_COLUMNS,
        )
        assert len(FACT_MSC_COLUMNS) > 0
        assert "competencia" in FACT_MSC_COLUMNS
        assert "regra_id" in FACT_RESULTADO_REGRAS_COLUMNS
        assert "execucao_id" in FACT_EXECUCAO_COLUMNS

    def test_import_engine(self) -> None:
        from ranking_msc.engine.executor import EngineContext, EngineResult, run_engine
        assert callable(run_engine)

    def test_import_rules_base(self) -> None:
        from ranking_msc.rules.base import RULE_REGISTRY, Rule, register_rule
        assert isinstance(RULE_REGISTRY, dict)

    def test_import_io(self) -> None:
        from ranking_msc.io.reader_msc import RawMSC, read_msc_csv
        assert callable(read_msc_csv)

    def test_import_transform(self) -> None:
        from ranking_msc.transform.ic_normalize import normalize_ic
        assert callable(normalize_ic)

    def test_import_outputs(self) -> None:
        from ranking_msc.outputs.snapshot import read_snapshot, write_snapshot_atomic
        from ranking_msc.outputs.reports import export_issues_excel
        from ranking_msc.outputs.logs import setup_logging, log_execucao


# ---------------------------------------------------------------------------
# 2. Settings loader
# ---------------------------------------------------------------------------

class TestSettings:
    """Testa o carregamento de configuração."""

    def test_load_defaults(self) -> None:
        """Settings com valores default (sem arquivo)."""
        from ranking_msc.config.settings import Settings
        s = Settings()
        assert s.app.title == "Ranking MSC"
        assert s.security.max_concurrent_jobs == 3

    def test_load_from_yaml(self, tmp_path: Path) -> None:
        """Settings a partir de um YAML mínimo."""
        yaml_content = """
app:
  title: "Teste"
  debug: true
paths:
  data_dir: "./test_data"
rules:
  enabled: ["R082"]
  fail_fast: true
security:
  max_concurrent_jobs: 1
"""
        yaml_file = tmp_path / "settings.yaml"
        yaml_file.write_text(yaml_content)

        from ranking_msc.config.settings import load_settings
        s = load_settings(yaml_file)

        assert s.app.title == "Teste"
        assert s.app.debug is True
        assert s.rules.enabled == ["R082"]
        assert s.rules.fail_fast is True

    def test_missing_file_raises(self) -> None:
        from ranking_msc.config.settings import load_settings
        from ranking_msc.exceptions import ConfigError
        with pytest.raises(ConfigError, match="não encontrado"):
            load_settings("/tmp/nao_existe_xyz.yaml")


# ---------------------------------------------------------------------------
# 3. Engine context
# ---------------------------------------------------------------------------

class TestEngineContext:
    """Testa criação de EngineContext."""

    def test_create_context(self) -> None:
        from ranking_msc.config.settings import Settings
        from ranking_msc.engine.executor import EngineContext

        ctx = EngineContext(
            competencia="2024-01",
            siconfi="250400",
            settings=Settings(),
            usuario="teste",
        )
        assert ctx.competencia == "2024-01"
        assert ctx.execucao_id  # UUID gerado automaticamente
        assert ctx.usuario == "teste"

    def test_engine_stub_raises(self) -> None:
        from ranking_msc.config.settings import Settings
        from ranking_msc.engine.executor import EngineContext, run_engine

        ctx = EngineContext(
            competencia="2024-01", siconfi="250400", settings=Settings(),
        )
        with pytest.raises(NotImplementedError):
            run_engine(pd.DataFrame(), ctx)


# ---------------------------------------------------------------------------
# 4. Rules base
# ---------------------------------------------------------------------------

class TestRulesBase:
    """Testa infraestrutura de regras."""

    def test_register_rule(self) -> None:
        from ranking_msc.rules.base import RULE_REGISTRY, Rule, register_rule
        from ranking_msc.engine.executor import EngineContext

        @register_rule
        class RTest(Rule):
            rule_id = "RTEST"
            rule_name = "Regra de teste"
            dimensao = "Teste"

            def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
                return self.build_issues([])

        assert "RTEST" in RULE_REGISTRY
        # Limpa registro para não afetar outros testes
        del RULE_REGISTRY["RTEST"]

    def test_build_issues_empty(self) -> None:
        from ranking_msc.rules.base import Rule
        from ranking_msc.engine.executor import EngineContext

        class RDummy(Rule):
            rule_id = "RDUMMY"
            rule_name = "Dummy"
            dimensao = "Teste"

            def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
                return self.build_issues([])

        r = RDummy()
        result = r.build_issues([])
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0

    def test_build_issues_with_data(self) -> None:
        from ranking_msc.rules.base import Rule
        from ranking_msc.engine.executor import EngineContext

        class RDummy(Rule):
            rule_id = "RDUMMY"
            rule_name = "Dummy"
            dimensao = "Teste"

            def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
                return self.build_issues([])

        r = RDummy()
        result = r.build_issues([{
            "severidade": "ERRO",
            "conta_contabil": "1.1.1",
            "descricao": "Teste",
            "valor_esperado": "100",
            "valor_encontrado": "200",
            "competencia": "2024-01",
        }])
        assert len(result) == 1
        assert result.iloc[0]["regra_id"] == "RDUMMY"


# ---------------------------------------------------------------------------
# 5. Logging
# ---------------------------------------------------------------------------

class TestLogging:
    """Testa setup de logging."""

    def test_setup_logging(self, tmp_path: Path) -> None:
        from ranking_msc.outputs.logs import setup_logging
        logger = setup_logging(log_dir=tmp_path, log_file="test.jsonl")
        assert logger.name == "ranking_msc"
        logger.info("smoke test")
        # Verifica que o arquivo foi criado
        assert (tmp_path / "test.jsonl").exists()
