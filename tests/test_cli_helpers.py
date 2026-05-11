"""Testes dos helpers CLI compartilhados em ``scripts/_cli_helpers.py``."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

import scripts._cli_helpers as helpers
from ranking_msc.config.settings import PathsSettings, Settings


# ---------------------------------------------------------------------------
# OutputPaths
# ---------------------------------------------------------------------------

class TestOutputPaths:
    def test_campos_sao_acessiveis(self) -> None:
        """OutputPaths guarda os três diretórios esperados."""
        op = helpers.OutputPaths(
            snapshots_dir=Path("/a"),
            reports_dir=Path("/b"),
            logs_dir=Path("/c"),
        )
        assert op.snapshots_dir == Path("/a")
        assert op.reports_dir == Path("/b")
        assert op.logs_dir == Path("/c")

    def test_e_imutavel(self) -> None:
        """OutputPaths é frozen — atribuição deve falhar."""
        op = helpers.OutputPaths(
            snapshots_dir=Path("/a"),
            reports_dir=Path("/b"),
            logs_dir=Path("/c"),
        )
        with pytest.raises((AttributeError, TypeError)):
            op.snapshots_dir = Path("/x")  # type: ignore[misc]


# ---------------------------------------------------------------------------
# _resolve_config_path
# ---------------------------------------------------------------------------

class TestResolveConfigPath:
    def test_sem_argumento_retorna_default(self) -> None:
        """Sem --config retorna <project_root>/config/settings.yaml."""
        result = helpers._resolve_config_path(None)
        assert result.name == "settings.yaml"
        assert result.parent.name == "config"

    def test_caminho_absoluto_retornado_sem_alteracao(self, tmp_path: Path) -> None:
        """Caminho absoluto é retornado resolvido."""
        cfg = tmp_path / "my.yaml"
        result = helpers._resolve_config_path(str(cfg))
        assert result == cfg.resolve()

    def test_caminho_relativo_resolvido_a_partir_de_cwd(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Caminho relativo é resolvido em relação ao cwd."""
        monkeypatch.chdir(tmp_path)
        result = helpers._resolve_config_path("custom/settings.yaml")
        assert result == (tmp_path / "custom" / "settings.yaml").resolve()


# ---------------------------------------------------------------------------
# _resolve_project_path
# ---------------------------------------------------------------------------

class TestResolveProjectPath:
    def test_caminho_absoluto_retornado_direto(self, tmp_path: Path) -> None:
        """Caminhos absolutos são retornados sem modificação."""
        result = helpers._resolve_project_path(str(tmp_path))
        assert result == tmp_path.resolve()

    def test_caminho_relativo_resolvido_a_partir_de_project_root(self) -> None:
        """Caminhos relativos são resolvidos a partir da raiz do projeto."""
        result = helpers._resolve_project_path("data/snapshots")
        assert result.is_absolute()
        assert result.parts[-2:] == ("data", "snapshots")


# ---------------------------------------------------------------------------
# _resolve_output_paths
# ---------------------------------------------------------------------------

class TestResolveOutputPaths:
    def _settings(self) -> Settings:
        return Settings(
            paths=PathsSettings(
                data_dir="./data",
                snapshots_dir="./data/snapshots",
                reports_dir="./data/reports",
                logs_dir="./data/logs",
                ref_dir="./ref",
            )
        )

    def test_sem_output_dir_usa_settings(self) -> None:
        """Sem --output-dir usa diretórios das settings."""
        settings = self._settings()
        result = helpers._resolve_output_paths(settings, None)

        assert result.snapshots_dir.is_absolute()
        assert result.snapshots_dir.parts[-2:] == ("data", "snapshots")
        assert result.reports_dir.parts[-2:] == ("data", "reports")
        assert result.logs_dir.parts[-2:] == ("data", "logs")

    def test_com_output_dir_sobrescreve_settings(self, tmp_path: Path) -> None:
        """--output-dir sobrescreve todos os diretórios das settings."""
        settings = self._settings()
        result = helpers._resolve_output_paths(settings, str(tmp_path))

        assert result.snapshots_dir == tmp_path / "snapshots"
        assert result.reports_dir == tmp_path / "reports"
        assert result.logs_dir == tmp_path / "logs"

    def test_output_dir_relativo_resolvido(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """--output-dir relativo é resolvido a partir do cwd."""
        monkeypatch.chdir(tmp_path)
        settings = self._settings()
        result = helpers._resolve_output_paths(settings, "saida")

        assert result.snapshots_dir == (tmp_path / "saida" / "snapshots").resolve()


# ---------------------------------------------------------------------------
# _log_failure
# ---------------------------------------------------------------------------

class TestLogFailure:
    def test_com_logger_chama_error(self) -> None:
        """Com logger fornecido, chama logger.error."""
        logger = logging.getLogger("test_log_failure")
        with patch.object(logger, "error") as mock_error:
            helpers._log_failure(logger, "algo deu errado")
        mock_error.assert_called_once()
        assert "algo deu errado" in mock_error.call_args[0][0]

    def test_sem_logger_nao_levanta_excecao(self) -> None:
        """Sem logger (None) não deve levantar exceção."""
        helpers._log_failure(None, "erro sem logger")
