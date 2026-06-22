"""Testes unitários do renderer PDF executivo (reportlab)."""

from __future__ import annotations

from ranking_msc.outputs.executive_pdf import (
    DimItem,
    ExecutivePdfPayload,
    HistItem,
    RecItem,
    render_executive_pdf,
)


def _payload() -> ExecutivePdfPayload:
    return ExecutivePdfPayload(
        siconfi="2507507EX",
        competencia="2026-01",
        pontuacao=76.4,
        banda="C",
        regras_executadas=73,
        regras_falhas_erro=3,
        regras_falhas_alerta=11,
        delta_text="Delta vs 2025-12: +2.10",
        history_lines=[],
        dimension_lines=[],
        recommendation_lines=[],
        dimensions=[DimItem("Estrutura", 100.0), DimItem("Fechamento", 55.0)],
        recommendations=[
            RecItem(1, "Investigar R030", "Débito ≠ Crédito", "ERRO", "R030"),
        ],
        history=[
            HistItem("2025-12", 78.5, "C"),
            HistItem("2026-01", 76.4, "C"),
        ],
        data_geracao="2026-06-22 14:30",
    )


def test_pdf_valido_uma_pagina() -> None:
    data = render_executive_pdf(_payload())
    assert data.startswith(b"%PDF")
    assert data.rstrip().endswith(b"%%EOF")
    assert b"/Count 1" in data


def test_pdf_contem_textos_chave_sem_compressao() -> None:
    data = render_executive_pdf(_payload())
    # compressão desligada → texto fica visível nos streams
    assert b"Conformidade MSC" in data
    assert b"2026-01" in data
    assert b"Estrutura" in data
    assert b"Fechamento" in data


def test_pdf_preserva_acentos() -> None:
    data = render_executive_pdf(_payload())
    # reportlab preserva o acento codificando "ã" (WinAnsi 0xE3) como escape
    # octal \343 no content stream — prova que o caractere não foi descartado.
    assert rb"Vis\343o" in data
