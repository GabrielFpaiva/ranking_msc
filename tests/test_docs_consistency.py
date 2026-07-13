"""
tests/test_docs_consistency.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Consistência entre documentação e código: as contagens de regras citadas nos
documentos são verificadas contra o RULE_REGISTRY, para que não possam divergir
silenciosamente de novo (a doc chegou a citar 67 regras com 78 no código).
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

import ranking_msc.rules  # noqa: F401  -- popular RULE_REGISTRY
from ranking_msc.rules.base import RULE_REGISTRY

_PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_catalogo_cita_total_igual_ao_rule_registry() -> None:
    """ref/regras_catalogo.md cita o mesmo total de regras do RULE_REGISTRY."""
    text = (_PROJECT_ROOT / "ref" / "regras_catalogo.md").read_text(encoding="utf-8")
    match = re.search(r"\*\*Total: (\d+) regras\*\*", text)
    assert match, "ref/regras_catalogo.md deve citar '**Total: N regras**'"
    assert int(match.group(1)) == len(RULE_REGISTRY), (
        f"ref/regras_catalogo.md cita {match.group(1)} regras mas o RULE_REGISTRY "
        f"tem {len(RULE_REGISTRY)}. Atualize o documento."
    )


def test_modelo_pontuacao_cita_total_igual_ao_rule_registry() -> None:
    """doc/modelo_pontuacao.md cita o mesmo total de regras do RULE_REGISTRY."""
    text = (_PROJECT_ROOT / "doc" / "modelo_pontuacao.md").read_text(encoding="utf-8")
    match = re.search(r"das (\d+) regras do catálogo", text)
    assert match, "doc/modelo_pontuacao.md deve citar 'das N regras do catálogo'"
    assert int(match.group(1)) == len(RULE_REGISTRY), (
        f"doc/modelo_pontuacao.md cita {match.group(1)} regras mas o RULE_REGISTRY "
        f"tem {len(RULE_REGISTRY)}. Atualize o documento."
    )


def test_example_habilita_exatamente_as_regras_do_registry() -> None:
    """config/settings.yaml.example habilita exatamente as regras registradas.

    Uma regra registrada mas não habilitada no example fica silenciosamente
    inativa em toda instalação nova; uma regra habilitada mas não registrada
    é config morta.
    """
    raw = yaml.safe_load(
        (_PROJECT_ROOT / "config" / "settings.yaml.example").read_text(encoding="utf-8")
    )
    enabled = set(raw["rules"]["enabled"])
    registered = set(RULE_REGISTRY)

    faltando_no_example = registered - enabled
    sem_implementacao = enabled - registered
    assert enabled == registered, (
        f"Divergência example × RULE_REGISTRY. "
        f"Registradas mas não habilitadas: {sorted(faltando_no_example)}. "
        f"Habilitadas mas não registradas: {sorted(sem_implementacao)}."
    )
