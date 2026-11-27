"""Testes de consistência da tabela de-para verificações oficiais × regras (F7-02)."""

from __future__ import annotations

import csv
from pathlib import Path

import ranking_msc.rules  # noqa: F401  (popula o RULE_REGISTRY)
from ranking_msc.rules.base import RULE_REGISTRY

REF = Path(__file__).resolve().parents[1] / "ref"
COBERTURAS = {"total", "parcial", "nenhuma", "nao_se_aplica"}
TIPOS = {"so_msc", "cruzamento", "externo", "sem_msc"}


def _ler(nome: str) -> list[dict[str, str]]:
    """Lê um CSV de `ref/` separado por ponto-e-vírgula."""
    with open(REF / nome, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f, delimiter=";"))


def test_de_para_codigos_existem_na_lista_oficial() -> None:
    """Todo código do de-para existe na descrição oficial do Tesouro, sem repetição."""
    oficiais = {r["no_verificacao"].strip() for r in _ler("ranking_descricao_verificacoes.csv")}
    codigos = [r["codigo"] for r in _ler("de_para_verificacoes.csv")]
    assert len(codigos) == len(set(codigos))
    assert set(codigos) <= oficiais


def test_de_para_cobre_todas_as_verificacoes_municipais_2025() -> None:
    """O de-para tem exatamente as verificações aplicáveis a município em 2025."""
    aplicaveis = {
        r["VERIFICACAO"]
        for r in _ler("ranking_aplicabilidade_verificacoes.csv")
        if r["2025"] in ("T", "M")
    }
    assert {r["codigo"] for r in _ler("de_para_verificacoes.csv")} == aplicaveis


def test_de_para_regras_citadas_estao_registradas() -> None:
    """Toda regra citada existe no motor; sem regra, a cobertura é nenhuma ou não se aplica."""
    for linha in _ler("de_para_verificacoes.csv"):
        assert linha["tipo"] in TIPOS, linha["codigo"]
        assert linha["cobertura"] in COBERTURAS, linha["codigo"]
        regras = [r for r in linha["regras"].split(";") if r]
        for regra in regras:
            assert regra in RULE_REGISTRY, f"{linha['codigo']} cita {regra} inexistente"
        if not regras:
            assert linha["cobertura"] in {"nenhuma", "nao_se_aplica"}, linha["codigo"]
