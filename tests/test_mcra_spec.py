"""Testes de mcra.spec — invariantes da receita do PyInstaller."""

from __future__ import annotations

import re
from pathlib import Path

_SPEC = Path(__file__).resolve().parents[1] / "mcra.spec"


def test_spec_embute_invites_yaml_em_config() -> None:
    """O convite lê config/invites.yaml do bundle: sem a entrada em datas o exe o perde."""
    texto = _SPEC.read_text(encoding="utf-8")
    bloco = re.search(r"^datas = \[(?P<itens>.*?)^\]", texto, flags=re.MULTILINE | re.DOTALL)
    assert bloco, "mcra.spec deve declarar a lista 'datas = [...]'"
    assert re.search(r'\(\s*"config/invites\.yaml"\s*,\s*"config"\s*\)', bloco["itens"])
