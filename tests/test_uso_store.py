"""
Testes de app/api/uso_store.py — persistência e agregação do tempo de uso.
"""

from __future__ import annotations

from datetime import UTC, datetime
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


class TestDiaLocal:
    def test_meia_noite_utc_ainda_e_o_dia_anterior_em_joao_pessoa(self) -> None:
        """00:30 UTC de 10/09 é 21:30 de 09/09 em Recife — o dia não pode virar."""
        from app.api.uso_store import dia_local

        momento = datetime(2026, 9, 10, 0, 30, tzinfo=UTC)
        assert dia_local(momento) == "2026-09-09"

    def test_meio_dia_utc_e_o_mesmo_dia(self) -> None:
        """12:00 UTC é 09:00 local — mesmo dia."""
        from app.api.uso_store import dia_local

        momento = datetime(2026, 9, 10, 12, 0, tzinfo=UTC)
        assert dia_local(momento) == "2026-09-10"
