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
    for chave in ("data_dir", "snapshots_dir", "reports_dir", "logs_dir", "uso_dir", "ref_dir"):
        assert Path(paths[chave]).is_absolute(), chave
    assert Path(paths["snapshots_dir"]) == tmp_path / "data" / "snapshots"
    assert Path(paths["uso_dir"]) == tmp_path / "data" / "uso"
    assert (tmp_path / "data" / "uso").is_dir()
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


def test_config_com_placeholder_de_queda_na_primeira_execucao_ganha_secret(
    tmp_path: Path,
) -> None:
    """Queda entre a cópia do template e a gravação: o próximo arranque sorteia o secret."""
    destino = tmp_path / "config" / "settings.yaml"
    destino.parent.mkdir(parents=True)
    template = _ROOT / "config" / "settings.desktop.yaml"
    destino.write_bytes(template.read_bytes())

    preparar_config(tmp_path, root=_ROOT)

    raw = yaml.safe_load(destino.read_text(encoding="utf-8"))
    assert raw["security"]["secret_key"] not in {"", "change-me-in-production"}
    assert len(raw["security"]["secret_key"]) == 64
    assert len(raw["security"]["users"]) == 3


def test_config_vazia_e_recriada_do_template(tmp_path: Path) -> None:
    """Arquivo truncado a zero bytes volta com os 3 usuários e secret válido."""
    destino = tmp_path / "config" / "settings.yaml"
    destino.parent.mkdir(parents=True)
    destino.write_text("", encoding="utf-8")

    preparar_config(tmp_path, root=_ROOT)

    raw = yaml.safe_load(destino.read_text(encoding="utf-8"))
    assert len(raw["security"]["users"]) == 3
    assert raw["security"]["secret_key"] not in {"", "change-me-in-production"}
    assert Path(raw["paths"]["data_dir"]) == tmp_path / "data"


def test_config_sem_usuarios_recriada_preserva_secret_valido(tmp_path: Path) -> None:
    """YAML truncado antes de security.users volta do template com o mesmo secret."""
    destino = tmp_path / "config" / "settings.yaml"
    destino.parent.mkdir(parents=True)
    secret = "a" * 64
    destino.write_text(f"security:\n  secret_key: {secret}\n", encoding="utf-8")

    preparar_config(tmp_path, root=_ROOT)

    raw = yaml.safe_load(destino.read_text(encoding="utf-8"))
    assert raw["security"]["secret_key"] == secret
    assert len(raw["security"]["users"]) == 3
    assert (tmp_path / "config" / "settings.yaml.bak").is_file()


def test_paths_relativos_sao_absolutizados(tmp_path: Path) -> None:
    """Caminhos de dados relativos passam a apontar para dentro de home/data."""
    destino = preparar_config(tmp_path, root=_ROOT)
    raw = yaml.safe_load(destino.read_text(encoding="utf-8"))
    raw["paths"].update(
        {
            "data_dir": "./data",
            "snapshots_dir": "./data/snapshots",
            "reports_dir": "data/reports",
            "logs_dir": "./data/logs",
        }
    )
    destino.write_text(yaml.safe_dump(raw, allow_unicode=True, sort_keys=False), encoding="utf-8")

    preparar_config(tmp_path, root=_ROOT)

    paths = yaml.safe_load(destino.read_text(encoding="utf-8"))["paths"]
    assert Path(paths["data_dir"]) == tmp_path / "data"
    assert Path(paths["snapshots_dir"]) == tmp_path / "data" / "snapshots"
    assert Path(paths["uso_dir"]) == tmp_path / "data" / "uso"
    assert (tmp_path / "data" / "uso").is_dir()
    assert Path(paths["reports_dir"]) == tmp_path / "data" / "reports"
    assert Path(paths["logs_dir"]) == tmp_path / "data" / "logs"


def test_segundo_arranque_sem_mudanca_nao_regrava(tmp_path: Path) -> None:
    """Sem nada a corrigir, o arquivo não é regravado (mtime e inode iguais)."""
    destino = preparar_config(tmp_path, root=_ROOT)
    antes = destino.stat()

    preparar_config(tmp_path, root=_ROOT)

    depois = destino.stat()
    assert depois.st_mtime_ns == antes.st_mtime_ns
    assert depois.st_ino == antes.st_ino


def test_gravacao_nao_deixa_temporario_na_pasta(tmp_path: Path) -> None:
    """A escrita atômica não deixa arquivo .tmp para trás."""
    preparar_config(tmp_path, root=_ROOT)
    assert [p.name for p in (tmp_path / "config").iterdir()] == ["settings.yaml"]


def test_template_tem_config_version_e_carrega(tmp_path: Path) -> None:
    """O marcador de versão fica no topo, sobrevive ao bootstrap e o loader aceita."""
    from ranking_msc.config.settings import load_settings

    template = yaml.safe_load(
        (_ROOT / "config" / "settings.desktop.yaml").read_text(encoding="utf-8")
    )
    assert next(iter(template)) == "config_version"
    assert template["config_version"] == 1

    destino = preparar_config(tmp_path, root=_ROOT)

    assert yaml.safe_load(destino.read_text(encoding="utf-8"))["config_version"] == 1
    settings = load_settings(destino)
    assert len(settings.security.users) == 3


def test_uso_dir_relativo_e_absolutizado_em_instalacao_existente(tmp_path: Path) -> None:
    """Config de versao anterior, sem uso_dir absoluto, e corrigida no arranque.

    A tela de tempo de uso chegou depois da primeira versao instalada. Sem esta
    correcao, `absolute_uso_dir()` resolveria para dentro do diretorio de
    extracao do bundle, que some quando o aplicativo fecha.
    """
    destino = preparar_config(tmp_path, root=_ROOT)
    raw = yaml.safe_load(destino.read_text(encoding="utf-8"))
    raw["paths"]["uso_dir"] = "./data/uso"
    destino.write_text(yaml.safe_dump(raw, allow_unicode=True, sort_keys=False), encoding="utf-8")

    preparar_config(tmp_path, root=_ROOT)

    depois = yaml.safe_load(destino.read_text(encoding="utf-8"))
    assert Path(depois["paths"]["uso_dir"]) == tmp_path / "data" / "uso"
