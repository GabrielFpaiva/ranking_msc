"""Testes de desktop/launcher.py — arranque headless."""

from __future__ import annotations

import logging
import os
from pathlib import Path

import desktop.launcher as launcher_module
import pytest
from desktop.launcher import main

from ranking_msc.exceptions import ConfigError
from ranking_msc.outputs.logs import setup_logging


def test_headless_sobe_e_encerra_com_zero(tmp_path: Path, monkeypatch) -> None:
    """Em modo headless o launcher prepara tudo, confere a saúde e sai."""
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.delenv("RANKING_MSC_CONFIG", raising=False)

    assert main(["--headless"]) == 0

    assert (tmp_path / "MCRA" / "config" / "settings.yaml").is_file()
    assert os.environ["RANKING_MSC_CONFIG"] == str(
        tmp_path / "MCRA" / "config" / "settings.yaml"
    )

    log_path = tmp_path / "MCRA" / "data" / "logs" / "desktop.log"
    assert log_path.is_file()
    assert log_path.stat().st_size > 0


def test_headless_duas_vezes_nao_duplica_handlers_nem_linhas(
    tmp_path: Path, monkeypatch
) -> None:
    """Chamar main() duas vezes no mesmo processo não duplica handlers nem linhas do log."""
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.delenv("RANKING_MSC_CONFIG", raising=False)

    assert main(["--headless"]) == 0
    assert main(["--headless"]) == 0

    log_path = tmp_path / "MCRA" / "data" / "logs" / "desktop.log"
    log_path_absoluto = os.path.abspath(str(log_path))
    conteudo = log_path.read_text(encoding="utf-8")

    # Duas execuções bem-sucedidas devem gerar exatamente duas ocorrências de
    # cada marco de arranque/parada — se um handler tivesse sido duplicado,
    # cada chamada teria escrito a mensagem duas vezes no arquivo.
    assert conteudo.count("Servidor local iniciado em") == 2
    assert conteudo.count("Servidor local encerrado.") == 2

    logger = logging.getLogger("ranking_msc")
    handlers_deste_arquivo = [
        h
        for h in logger.handlers
        if isinstance(h, logging.FileHandler) and h.baseFilename == log_path_absoluto
    ]
    assert len(handlers_deste_arquivo) == 1


def test_headless_depois_setup_logging_ainda_anexa_handler_jsonl(
    tmp_path: Path, monkeypatch
) -> None:
    """Sequência real do app: depois de main(), setup_logging() ainda cria o JSONL.

    ``desktop.launcher.main()`` anexa seus próprios handlers ao logger
    ``"ranking_msc"`` antes de o servidor subir. Se ``setup_logging()`` (chamado sob
    demanda por ``app.api.deps.get_logger()`` na primeira requisição) tratasse "logger
    já tem handler" como "não faço nada", o arquivo ``ranking_msc.jsonl`` de auditoria
    nunca seria criado no aplicativo empacotado. Este teste reproduz exatamente essa
    sequência.
    """
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.delenv("RANKING_MSC_CONFIG", raising=False)

    assert main(["--headless"]) == 0

    logger = logging.getLogger("ranking_msc")
    handlers_antes = list(logger.handlers)

    logs_dir = tmp_path / "MCRA" / "data" / "logs"
    resultado = setup_logging(log_dir=logs_dir)
    resultado.info("linha de teste após arranque headless")

    jsonl_path = logs_dir / "ranking_msc.jsonl"
    try:
        assert jsonl_path.is_file()
        assert jsonl_path.stat().st_size > 0
    finally:
        # Não deixa o handler do JSONL grudado no logger compartilhado para o
        # resto da sessão de testes.
        for h in list(logger.handlers):
            if h not in handlers_antes:
                logger.removeHandler(h)
                h.close()


def test_headless_falha_no_iniciar_grava_traceback_no_log(
    tmp_path: Path, monkeypatch
) -> None:
    """Falha em ServidorLocal.iniciar() (ex.: hiddenimport faltando no PyInstaller) vai
    para o desktop.log com traceback completo, e main() devolve 1 em vez de estourar.
    """
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.delenv("RANKING_MSC_CONFIG", raising=False)

    def _iniciar_com_falha(self: object) -> None:
        raise ImportError("simulado")

    monkeypatch.setattr(launcher_module.ServidorLocal, "iniciar", _iniciar_com_falha)

    assert main(["--headless"]) == 1

    log_path = tmp_path / "MCRA" / "data" / "logs" / "desktop.log"
    conteudo = log_path.read_text(encoding="utf-8")
    assert "ImportError" in conteudo
    assert "simulado" in conteudo


def test_headless_falha_no_preparar_config_grava_no_log_sem_quebrar_finally(
    tmp_path: Path, monkeypatch
) -> None:
    """Falha em preparar_config() (ex.: template ausente no pacote) vai para o
    desktop.log, main() devolve 1, e o finally não tenta parar um servidor que nunca
    chegou a ser criado — se tentasse, main() estouraria em vez de devolver 1.
    """
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.delenv("RANKING_MSC_CONFIG", raising=False)

    def _preparar_config_com_falha(home: Path, *, root: Path) -> Path:
        raise ConfigError("template ausente simulado")

    monkeypatch.setattr(launcher_module, "preparar_config", _preparar_config_com_falha)

    assert main(["--headless"]) == 1

    log_path = tmp_path / "MCRA" / "data" / "logs" / "desktop.log"
    conteudo = log_path.read_text(encoding="utf-8")
    assert "ConfigError" in conteudo
    assert "template ausente simulado" in conteudo


@pytest.mark.filterwarnings("ignore::pytest.PytestUnhandledThreadExceptionWarning")
def test_erro_do_uvicorn_ao_subir_chega_ao_desktop_log(tmp_path: Path, monkeypatch) -> None:
    """Porta ocupada: o erro de bind do logger uvicorn.error vai para o desktop.log.

    O uvicorn encerra a própria thread com ``sys.exit(1)`` depois de logar o erro;
    o aviso do pytest sobre essa exceção em thread é o comportamento esperado.
    """
    import socket
    import time

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.delenv("RANKING_MSC_CONFIG", raising=False)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as ocupado:
        ocupado.bind(("127.0.0.1", 0))
        ocupado.listen()
        porta = int(ocupado.getsockname()[1])
        monkeypatch.setattr(launcher_module, "porta_livre", lambda: porta)

        inicio = time.monotonic()
        assert main(["--headless"]) == 1
        # Servidor morto não espera os 120 s do timeout de saúde.
        assert time.monotonic() - inicio < 30.0

    log_path = tmp_path / "MCRA" / "data" / "logs" / "desktop.log"
    conteudo = log_path.read_text(encoding="utf-8")
    assert conteudo.count("error while attempting to bind") == 1
    assert "O servidor local não respondeu" in conteudo


def test_registro_de_uvicorn_error_vai_para_o_arquivo_uma_vez(
    tmp_path: Path, monkeypatch
) -> None:
    """O handler do desktop.log está ligado à árvore uvicorn sem duplicar linhas."""
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    log_path = launcher_module._configurar_logging(tmp_path / "MCRA")
    launcher_module._configurar_logging(tmp_path / "MCRA")

    logging.getLogger("uvicorn.error").error("rota estourou: marcador-uvicorn")

    assert log_path.read_text(encoding="utf-8").count("marcador-uvicorn") == 1


def _falhar_preparar_config(home: Path, *, root: Path) -> Path:
    raise ConfigError("falha simulada")


def test_modo_janela_com_falha_mostra_messagebox(tmp_path: Path, monkeypatch) -> None:
    """Sem --headless, main() devolvendo 1 chama MessageBoxW com o caminho do log."""
    from unittest import mock

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(launcher_module, "preparar_config", _falhar_preparar_config)
    monkeypatch.setattr(launcher_module, "_eh_windows", lambda: True)
    ctypes_falso = mock.MagicMock()
    monkeypatch.setattr(launcher_module, "ctypes", ctypes_falso)

    assert main([]) == 1

    message_box = ctypes_falso.windll.user32.MessageBoxW
    message_box.assert_called_once()
    texto = message_box.call_args.args[1]
    assert str(tmp_path / "MCRA" / "data" / "logs" / "desktop.log") in texto


def test_modo_headless_com_falha_nao_mostra_messagebox(tmp_path: Path, monkeypatch) -> None:
    """Em --headless (smoke do CI) não há caixa de mensagem."""
    from unittest import mock

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(launcher_module, "preparar_config", _falhar_preparar_config)
    monkeypatch.setattr(launcher_module, "_eh_windows", lambda: True)
    ctypes_falso = mock.MagicMock()
    monkeypatch.setattr(launcher_module, "ctypes", ctypes_falso)

    assert main(["--headless"]) == 1

    ctypes_falso.windll.user32.MessageBoxW.assert_not_called()


def test_messagebox_que_falha_nao_derruba_main(tmp_path: Path, monkeypatch) -> None:
    """Se a própria caixa falhar, main() ainda devolve 1 sem levantar."""
    from unittest import mock

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(launcher_module, "preparar_config", _falhar_preparar_config)
    monkeypatch.setattr(launcher_module, "_eh_windows", lambda: True)
    ctypes_falso = mock.MagicMock()
    ctypes_falso.windll.user32.MessageBoxW.side_effect = OSError("sem user32")
    monkeypatch.setattr(launcher_module, "ctypes", ctypes_falso)

    assert main([]) == 1


def test_fora_do_windows_nao_toca_em_ctypes(tmp_path: Path, monkeypatch) -> None:
    """No macOS/Linux a caixa não é tentada (ctypes.windll não existe lá)."""
    from unittest import mock

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(launcher_module, "preparar_config", _falhar_preparar_config)
    monkeypatch.setattr(launcher_module, "_eh_windows", lambda: False)
    ctypes_falso = mock.MagicMock()
    monkeypatch.setattr(launcher_module, "ctypes", ctypes_falso)

    assert main([]) == 1

    ctypes_falso.windll.user32.MessageBoxW.assert_not_called()


def test_janela_liga_downloads_antes_de_criar_a_janela(monkeypatch) -> None:
    """Sem ALLOW_DOWNLOADS o pywebview cancela todo download (relatório, Excel, PDF)."""
    import sys
    import types

    chamadas: list[str] = []
    settings: dict[str, bool] = {"ALLOW_DOWNLOADS": False}
    falso = types.ModuleType("webview")

    def create_window(*args: object, **kwargs: object) -> None:
        chamadas.append(f"create_window downloads={settings['ALLOW_DOWNLOADS']}")

    def start() -> None:
        chamadas.append("start")

    falso.settings = settings  # type: ignore[attr-defined]
    falso.create_window = create_window  # type: ignore[attr-defined]
    falso.start = start  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "webview", falso)

    launcher_module._abrir_janela("http://127.0.0.1:1234")

    assert chamadas == ["create_window downloads=True", "start"]
