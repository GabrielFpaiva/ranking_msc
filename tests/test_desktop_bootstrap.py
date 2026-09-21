"""Testes de desktop/bootstrap.py — primeira execução e rearranque."""

from __future__ import annotations

from pathlib import Path

import yaml
from desktop.bootstrap import data_home, preparar_config

_ROOT = Path(__file__).resolve().parents[1]


def test_data_home_usa_localappdata_quando_definido(tmp_path: Path, monkeypatch) -> None:
    """No Windows a pasta é %LOCALAPPDATA%\\MCRA."""
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert data_home() == tmp_path / "MCRA"


def test_primeira_execucao_cria_config_com_secret_proprio(tmp_path: Path) -> None:
    """Sem settings.yaml, o bootstrap cria o arquivo e sorteia o secret."""
    destino = preparar_config(tmp_path, root=_ROOT)

    raw = yaml.safe_load(destino.read_text(encoding="utf-8"))
    assert destino == tmp_path / "config" / "settings.yaml"
    assert raw["security"]["secret_key"] != "change-me-in-production"
    assert len(raw["security"]["secret_key"]) == 64
    assert len(raw["security"]["users"]) == 3


def test_primeira_execucao_grava_paths_absolutos(tmp_path: Path) -> None:
    """Os diretórios de dados não podem depender do diretório de trabalho."""
    destino = preparar_config(tmp_path, root=_ROOT)

    paths = yaml.safe_load(destino.read_text(encoding="utf-8"))["paths"]
    for chave in ("data_dir", "snapshots_dir", "reports_dir", "logs_dir", "ref_dir"):
        assert Path(paths[chave]).is_absolute(), chave
    assert Path(paths["snapshots_dir"]) == tmp_path / "data" / "snapshots"
    assert (tmp_path / "data" / "snapshots").is_dir()


def test_segunda_execucao_preserva_secret_e_usuarios(tmp_path: Path) -> None:
    """Config existente não é sobrescrito."""
    primeiro = preparar_config(tmp_path, root=_ROOT)
    raw = yaml.safe_load(primeiro.read_text(encoding="utf-8"))
    raw["security"]["users"].append({"username": "extra", "hashed_password": "x"})
    primeiro.write_text(yaml.safe_dump(raw, allow_unicode=True, sort_keys=False), encoding="utf-8")
    secret_original = raw["security"]["secret_key"]

    preparar_config(tmp_path, root=_ROOT)

    depois = yaml.safe_load(primeiro.read_text(encoding="utf-8"))
    assert depois["security"]["secret_key"] == secret_original
    assert len(depois["security"]["users"]) == 4


def test_segunda_execucao_reaponta_ref_dir(tmp_path: Path) -> None:
    """ref_dir pertence à instalação e é reescrito a cada arranque."""
    destino = preparar_config(tmp_path, root=_ROOT)
    raw = yaml.safe_load(destino.read_text(encoding="utf-8"))
    raw["paths"]["ref_dir"] = "/caminho/da/instalacao/antiga/ref"
    destino.write_text(yaml.safe_dump(raw, allow_unicode=True, sort_keys=False), encoding="utf-8")

    preparar_config(tmp_path, root=_ROOT)

    depois = yaml.safe_load(destino.read_text(encoding="utf-8"))
    assert Path(depois["paths"]["ref_dir"]) == _ROOT / "ref"
