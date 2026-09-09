"""
Testes de app/api/uso_store.py — persistência e agregação do tempo de uso.
"""

from __future__ import annotations

from pathlib import Path

from ranking_msc.config.settings import Settings


class TestConfiguracao:
    def test_paths_tem_uso_dir_com_default(self) -> None:
        """PathsSettings expõe uso_dir com default sob ./data."""
        assert Settings().paths.uso_dir == "./data/uso"

    def test_ensure_dirs_cria_uso_dir(self, tmp_path: Path) -> None:
        """ensure_dirs() cria o diretório de tempo de uso."""
        from dataclasses import replace

        paths = replace(Settings().paths, uso_dir=str(tmp_path / "uso"))
        paths.ensure_dirs()
        assert (tmp_path / "uso").is_dir()
