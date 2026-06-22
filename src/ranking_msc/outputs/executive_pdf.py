"""
ranking_msc.outputs.executive_pdf
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

PDF da Visão Executiva com identidade MCRA (navy + dourado), 1 página A4,
renderizado com reportlab. Mantém assinaturas estáveis de render/write.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from ranking_msc.outputs import brand

# Geometria (pontos; A4 = 595 x 842)
_W, _H = A4
_MARGIN = 40.0


@dataclass(slots=True)
class DimItem:
    """Dimensão de pontuação para a barra de desempenho."""

    nome: str
    pct: float


@dataclass(slots=True)
class RecItem:
    """Recomendação priorizada para os cards de ação."""

    ordem: int
    titulo: str
    descricao: str
    severidade: str
    referencia: str | None


@dataclass(slots=True)
class HistItem:
    """Ponto do mini-histórico de competências."""

    competencia: str
    score: float
    banda: str


@dataclass(slots=True)
class ExecutivePdfSection:
    """Seção textual genérica (compatibilidade com chamadas legadas)."""

    title: str
    lines: list[str]


@dataclass(slots=True)
class ExecutivePdfPayload:
    """Dados da Visão Executiva consumidos pelo renderer.

    Os campos ``*_lines`` são legados (mantidos para compatibilidade); o layout
    branded usa os campos estruturados ``dimensions``/``recommendations``/
    ``history``.
    """

    siconfi: str
    competencia: str
    pontuacao: float
    banda: str
    regras_executadas: int
    regras_falhas_erro: int
    regras_falhas_alerta: int
    delta_text: str | None
    history_lines: list[str]
    dimension_lines: list[str]
    recommendation_lines: list[str]
    dimensions: list[DimItem] = field(default_factory=list)
    recommendations: list[RecItem] = field(default_factory=list)
    history: list[HistItem] = field(default_factory=list)
    data_geracao: str = ""


def _fmt_num(value: float) -> str:
    """Formata número com vírgula decimal PT-BR."""
    return f"{value:.1f}".replace(".", ",")


def _draw_header(c: canvas.Canvas, payload: ExecutivePdfPayload) -> None:
    """Desenha a faixa navy do topo com wordmark e metadados."""
    band_h = 70.0
    top = _H - band_h
    c.setFillColor(brand.rl_color(brand.NAVY))
    c.rect(0, top, _W, band_h, stroke=0, fill=1)
    # régua dourada inferior
    c.setFillColor(brand.rl_color(brand.GOLD))
    c.rect(0, top - 3, _W, 3, stroke=0, fill=1)
    # wordmark
    c.setFillColor(brand.rl_color(brand.GOLD))
    c.setFont("Helvetica-Bold", 22)
    c.drawString(_MARGIN, top + 38, "MCRA")
    c.setFillColor(brand.rl_color(brand.WHITE))
    c.setFont("Helvetica", 10)
    c.drawString(_MARGIN, top + 22, "PMJP · Ranking MSC")
    # direita
    c.setFont("Helvetica-Bold", 12)
    c.drawRightString(_W - _MARGIN, top + 40, "Visão Executiva")
    c.setFont("Helvetica", 9)
    c.drawRightString(_W - _MARGIN, top + 25, f"Competência {payload.competencia}")
    if payload.data_geracao:
        c.drawRightString(_W - _MARGIN, top + 12, f"Gerado em {payload.data_geracao}")


def _draw_score_hero(c: canvas.Canvas, payload: ExecutivePdfPayload, y: float) -> float:
    """Desenha o bloco herói do score (nota grande + banda + stats)."""
    c.setFillColor(brand.rl_color(brand.INK))
    c.setFont("Helvetica", 11)
    c.drawString(_MARGIN, y, "Conformidade MSC")
    y -= 34
    c.setFillColor(brand.rl_color(brand.band_hex(payload.banda)))
    c.setFont("Helvetica-Bold", 40)
    c.drawString(_MARGIN, y, _fmt_num(payload.pontuacao))
    c.setFont("Helvetica", 12)
    c.setFillColor(brand.rl_color(brand.GRAPHITE))
    c.drawString(_MARGIN + 120, y + 6, f"/100  ·  BANDA {payload.banda}")
    if payload.delta_text:
        c.setFont("Helvetica", 9)
        c.drawString(_MARGIN + 120, y - 8, payload.delta_text)
    y -= 18
    c.setFont("Helvetica", 9)
    c.setFillColor(brand.rl_color(brand.GRAPHITE))
    c.drawString(
        _MARGIN,
        y,
        f"{payload.regras_executadas} regras pontuáveis  ·  "
        f"{payload.regras_falhas_erro} erros  ·  "
        f"{payload.regras_falhas_alerta} alertas",
    )
    return y - 22


def _draw_dimensions(c: canvas.Canvas, payload: ExecutivePdfPayload, y: float) -> float:
    """Desenha as barras horizontais de desempenho por dimensão."""
    if not payload.dimensions:
        return y
    c.setFillColor(brand.rl_color(brand.NAVY))
    c.setFont("Helvetica-Bold", 12)
    c.drawString(_MARGIN, y, "Desempenho por dimensão")
    y -= 20
    bar_x = _MARGIN + 150
    bar_w = _W - _MARGIN - bar_x - 50
    for dim in payload.dimensions:
        c.setFillColor(brand.rl_color(brand.INK))
        c.setFont("Helvetica", 9)
        c.drawString(_MARGIN, y, dim.nome[:24])
        # trilho
        c.setFillColor(brand.rl_color(brand.PARCHMENT))
        c.rect(bar_x, y - 2, bar_w, 10, stroke=0, fill=1)
        # preenchimento
        pct = max(0.0, min(dim.pct, 100.0))
        c.setFillColor(brand.rl_color(brand.band_hex_for_score(dim.pct)))
        c.rect(bar_x, y - 2, bar_w * pct / 100, 10, stroke=0, fill=1)
        c.setFillColor(brand.rl_color(brand.GRAPHITE))
        c.drawRightString(_W - _MARGIN, y, f"{dim.pct:.0f}%")
        y -= 18
    return y - 8


def _draw_history(c: canvas.Canvas, payload: ExecutivePdfPayload, y: float) -> float:
    """Desenha o mini-histórico das últimas competências."""
    if not payload.history:
        return y
    c.setFillColor(brand.rl_color(brand.NAVY))
    c.setFont("Helvetica-Bold", 12)
    c.drawString(_MARGIN, y, "Histórico recente")
    y -= 18
    c.setFont("Helvetica", 9)
    for h in payload.history[-6:]:
        c.setFillColor(brand.rl_color(brand.INK))
        c.drawString(_MARGIN, y, h.competencia)
        c.setFillColor(brand.rl_color(brand.band_hex(h.banda)))
        c.drawString(_MARGIN + 90, y, f"{_fmt_num(h.score)}  · banda {h.banda}")
        y -= 14
    return y - 8


def _draw_recommendations(
    c: canvas.Canvas, payload: ExecutivePdfPayload, y: float
) -> float:
    """Desenha os cards de ações prioritárias."""
    if not payload.recommendations:
        return y
    c.setFillColor(brand.rl_color(brand.NAVY))
    c.setFont("Helvetica-Bold", 12)
    c.drawString(_MARGIN, y, "Ações prioritárias")
    y -= 18
    for rec in payload.recommendations[:5]:
        c.setFillColor(brand.rl_color(brand.severity_hex(rec.severidade)))
        c.rect(_MARGIN, y - 2, 8, 10, stroke=0, fill=1)
        c.setFillColor(brand.rl_color(brand.INK))
        c.setFont("Helvetica-Bold", 9)
        c.drawString(_MARGIN + 16, y, f"{rec.ordem}. {rec.titulo}"[:90])
        y -= 12
        c.setFillColor(brand.rl_color(brand.GRAPHITE))
        c.setFont("Helvetica", 8)
        c.drawString(_MARGIN + 16, y, rec.descricao[:110])
        y -= 16
    return y


def _draw_footer(c: canvas.Canvas) -> None:
    """Desenha o rodapé institucional."""
    c.setFillColor(brand.rl_color(brand.GRAPHITE))
    c.setFont("Helvetica", 7)
    c.drawString(
        _MARGIN,
        _MARGIN - 12,
        "Gerado pelo MCRA · Fonte: SICONFI · Detalhe completo no Excel",
    )
    c.drawRightString(_W - _MARGIN, _MARGIN - 12, "Página 1/1")


def render_executive_pdf(payload: ExecutivePdfPayload) -> bytes:
    """Renderiza a Visão Executiva como PDF binário branded (1 página)."""
    buf = io.BytesIO()
    # pageCompression=0 → streams legíveis (texto greppável; PDFs pequenos).
    c = canvas.Canvas(buf, pagesize=A4, pageCompression=0)
    c.setTitle(f"MCRA Visao Executiva {payload.siconfi} {payload.competencia}")
    _draw_header(c, payload)
    y = _H - 70 - 30
    y = _draw_score_hero(c, payload, y)
    y = _draw_dimensions(c, payload, y)
    y = _draw_history(c, payload, y)
    _draw_recommendations(c, payload, y)
    _draw_footer(c)
    c.showPage()
    c.save()
    return buf.getvalue()


def write_executive_pdf(payload: ExecutivePdfPayload, output_path: str | Path) -> Path:
    """Escreve o PDF no disco e retorna o caminho final."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(render_executive_pdf(payload))
    return path
