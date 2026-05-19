"""
ranking_msc.outputs.executive_pdf
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Geração de PDF simples da Visão Executiva sem dependências externas.

O módulo produz um PDF textual, suficiente para distribuição interna e
auditoria rápida, usando apenas a sintaxe básica do formato PDF.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from textwrap import wrap


@dataclass(slots=True)
class ExecutivePdfSection:
    title: str
    lines: list[str]


@dataclass(slots=True)
class ExecutivePdfPayload:
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


def _escape_pdf_text(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("(", "\\(")
        .replace(")", "\\)")
    )


def _line_stream(text: str, *, x: int, y: int, font: str, size: int) -> str:
    return f"BT /{font} {size} Tf 1 0 0 1 {x} {y} Tm ({_escape_pdf_text(text)}) Tj ET"


def _wrap_lines(lines: list[str], width: int) -> list[str]:
    wrapped: list[str] = []
    for line in lines:
        if not line.strip():
            wrapped.append("")
            continue
        parts = wrap(line, width=width, break_long_words=False, break_on_hyphens=False)
        wrapped.extend(parts or [""])
    return wrapped


def _build_pages(payload: ExecutivePdfPayload) -> list[str]:
    pages: list[str] = []
    commands: list[str] = []
    y = 790

    def ensure_space(lines_needed: int) -> None:
        nonlocal commands, y
        if y - (lines_needed * 14) >= 60:
            return
        pages.append("\n".join(commands))
        commands = []
        y = 790

    def add_line(text: str, *, font: str = "F1", size: int = 11, spacing: int = 14) -> None:
        nonlocal y
        ensure_space(1)
        commands.append(_line_stream(text, x=48, y=y, font=font, size=size))
        y -= spacing

    def add_section(section: ExecutivePdfSection) -> None:
        nonlocal y
        wrapped_lines = _wrap_lines(section.lines, width=88)
        ensure_space(len(wrapped_lines) + 3)
        add_line(section.title, font="F2", size=13, spacing=18)
        for line in wrapped_lines:
            add_line(line if line else " ", font="F1", size=11, spacing=14)
        y -= 6

    add_line("Ranking MSC — Visao Executiva", font="F2", size=18, spacing=22)
    add_line(
        f"Ente {payload.siconfi}  Competencia {payload.competencia}",
        font="F1",
        size=11,
        spacing=18,
    )
    add_line(
        (
            f"Pontuacao {payload.pontuacao:.1f}  "
            f"Banda {payload.banda}  "
            f"Regras {payload.regras_executadas}"
        ),
        font="F2",
        size=12,
        spacing=16,
    )
    add_line(
        f"Erros {payload.regras_falhas_erro}  Alertas {payload.regras_falhas_alerta}",
        font="F1",
        size=11,
        spacing=14,
    )
    if payload.delta_text:
        add_line(payload.delta_text, font="F1", size=11, spacing=18)
    else:
        y -= 4

    add_section(
        ExecutivePdfSection(
            title="Historico recente",
            lines=payload.history_lines or ["Sem historico registrado para este ente."],
        )
    )
    add_section(
        ExecutivePdfSection(
            title="Dimensoes ativas",
            lines=payload.dimension_lines or ["Nenhuma dimensao ativa no score atual."],
        )
    )
    add_section(
        ExecutivePdfSection(
            title="Recomendacoes",
            lines=payload.recommendation_lines
            or ["Nenhuma acao critica recomendada no momento."],
        )
    )

    if commands:
        pages.append("\n".join(commands))
    return pages


def _assemble_pdf(pages: list[str]) -> bytes:
    objects: list[bytes] = []

    def add_object(content: str | bytes) -> int:
        encoded = content.encode("latin-1") if isinstance(content, str) else content
        objects.append(encoded)
        return len(objects)

    font_regular = add_object("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    font_bold = add_object("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>")

    content_ids: list[int] = []
    page_ids: list[int] = []
    pages_id = 0

    for page in pages:
        stream = page.encode("latin-1", errors="replace")
        content_id = add_object(
            b"<< /Length "
            + str(len(stream)).encode("ascii")
            + b" >>\nstream\n"
            + stream
            + b"\nendstream"
        )
        content_ids.append(content_id)
        page_ids.append(0)

    kids_refs = " ".join(f"{len(objects) + 2 + idx} 0 R" for idx in range(len(pages)))
    pages_id = add_object(f"<< /Type /Pages /Kids [{kids_refs}] /Count {len(pages)} >>")

    for idx, content_id in enumerate(content_ids):
        page_ids[idx] = add_object(
            "<< /Type /Page /Parent "
            f"{pages_id} 0 R /MediaBox [0 0 595 842] "
            "/Resources << /Font << "
            f"/F1 {font_regular} 0 R /F2 {font_bold} 0 R "
            ">> >> "
            f"/Contents {content_id} 0 R >>"
        )

    add_object(f"<< /Type /Catalog /Pages {pages_id} 0 R >>")
    catalog_id = len(objects)

    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for idx, obj in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{idx} 0 obj\n".encode("ascii"))
        output.extend(obj)
        output.extend(b"\nendobj\n")

    xref_offset = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend(
        (
            "trailer\n<< "
            f"/Size {len(objects) + 1} /Root {catalog_id} 0 R "
            ">>\nstartxref\n"
            f"{xref_offset}\n%%EOF"
        ).encode("ascii")
    )
    return bytes(output)


def render_executive_pdf(payload: ExecutivePdfPayload) -> bytes:
    """Renderiza o payload da Visão Executiva como PDF binário."""
    return _assemble_pdf(_build_pages(payload))


def write_executive_pdf(payload: ExecutivePdfPayload, output_path: str | Path) -> Path:
    """Escreve o PDF no disco e retorna o caminho final."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(render_executive_pdf(payload))
    return path
