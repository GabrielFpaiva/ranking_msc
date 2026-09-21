"""Testes de installer/mcra.iss — invariantes do script do Inno Setup."""

from __future__ import annotations

import re
from pathlib import Path

_ISS = Path(__file__).resolve().parents[1] / "installer" / "mcra.iss"


def _texto() -> str:
    """Lê o script sem o BOM."""
    return _ISS.read_bytes().decode("utf-8-sig")


def test_iss_mantem_bom_utf8() -> None:
    """O Inno lê o script como UTF-8 por causa do BOM; sem ele os acentos quebram."""
    assert _ISS.read_bytes()[:3] == b"\xef\xbb\xbf"


def test_iss_abre_app_no_fim_sem_elevacao() -> None:
    """A entrada postinstall do exe usa runasoriginaluser, nunca runascurrentuser."""
    linhas = _texto().splitlines()
    idx = next(i for i, linha in enumerate(linhas) if "{#MyAppExeName}\"; Description:" in linha)
    entrada = linhas[idx] + linhas[idx + 1]
    assert "runasoriginaluser" in entrada
    assert "runascurrentuser" not in entrada


def test_iss_tem_appid_fixo() -> None:
    """AppId com GUID fixo, no escape de chave dupla do Inno."""
    assert re.search(
        r"^AppId=\{\{[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}\}$",
        _texto(),
        flags=re.MULTILINE,
    )


def test_iss_limpa_internal_da_versao_anterior() -> None:
    """Reinstalação por cima apaga {app}\\_internal antes de copiar."""
    texto = _texto()
    assert "[InstallDelete]" in texto
    assert 'Type: filesandordirs; Name: "{app}\\_internal"' in texto
