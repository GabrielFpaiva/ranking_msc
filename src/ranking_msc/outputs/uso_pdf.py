"""
ranking_msc.outputs.uso_pdf
~~~~~~~~~~~~~~~~~~~~~~~~~~~

PDF do relatório de tempo de uso de um usuário, com a identidade MCRA (navy +
dourado). Mostra totais do período, o tempo por tela e a série por dia.

Cada usuário só emite o próprio relatório: quem decide o ``usuario`` é a rota
(``sub`` do JWT), nunca um parâmetro vindo do cliente.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from ranking_msc.outputs import brand

_W, _H = A4
_MARGIN = 40.0
_LINHA = 15.0
_HEADER_H = 70.0

# Espelha ``web/src/routeTitles.ts``. Rota sem título cai no próprio caminho.
TITULOS_ROTA: dict[str, str] = {
    "/inicio": "Início",
    "/pendencias": "Pendências",
    "/caixa": "Caixa",
    "/passivos": "Passivos",
    "/superavit": "Superávit",
    "/executivo": "Visão Executiva",
    "/comparar": "Comparar Competências",
    "/entregas": "Entregas",
    "/regras": "Regras",
    "/execucao": "Execução",
    "/uso": "Meu tempo de uso",
    "/convidar": "Convidar colaborador",
}

_ROTULO_ESCALA = {"dia": "Dia", "semana": "Semana", "mes": "Mês"}


@dataclass(slots=True)
class UsoLinha:
    """Uma linha de tabela: rótulo (dia ou tela) e os dois tempos em segundos."""

    rotulo: str
    aberto_s: int
    ativo_s: int


@dataclass(slots=True)
class UsoPdfPayload:
    """Dados consumidos pelo renderer do relatório de uso."""

    usuario: str
    escala: str
    inicio: str
    fim: str
    total_aberto_s: int
    total_ativo_s: int
    data_geracao: str
    rotas: list[UsoLinha] = field(default_factory=list)
    dias: list[UsoLinha] = field(default_factory=list)


def formatar_duracao(segundos: int) -> str:
    """Formata segundos como ``Xh YYmin`` (ou ``Ymin`` abaixo de 1 hora)."""
    minutos_totais = max(0, int(segundos)) // 60
    horas, minutos = divmod(minutos_totais, 60)
    if horas:
        return f"{horas}h {minutos:02d}min"
    return f"{minutos}min"


def _data_br(iso: str) -> str:
    """Converte ``YYYY-MM-DD`` em ``DD/MM/YYYY``."""
    ano, mes, dia = iso.split("-")
    return f"{dia}/{mes}/{ano}"


def titulo_rota(rota: str) -> str:
    """Nome amigável da tela, igual ao exibido no app."""
    return TITULOS_ROTA.get(rota, rota)


class _Pagina:
    """Controla o cursor vertical e a quebra de página."""

    def __init__(self, c: canvas.Canvas, payload: UsoPdfPayload) -> None:
        self.c = c
        self.payload = payload
        self.numero = 1
        self.y = 0.0
        self._cabecalho()

    def _cabecalho(self) -> None:
        c, p = self.c, self.payload
        top = _H - _HEADER_H
        c.setFillColor(brand.rl_color(brand.NAVY))
        c.rect(0, top, _W, _HEADER_H, stroke=0, fill=1)
        c.setFillColor(brand.rl_color(brand.GOLD))
        c.rect(0, top - 3, _W, 3, stroke=0, fill=1)
        c.setFont("Helvetica-Bold", 22)
        c.drawString(_MARGIN, top + 38, "MCRA")
        c.setFillColor(brand.rl_color(brand.WHITE))
        c.setFont("Helvetica", 10)
        c.drawString(_MARGIN, top + 22, "PMJP · Ranking MSC")
        c.setFont("Helvetica-Bold", 12)
        c.drawRightString(_W - _MARGIN, top + 40, "Relatório de uso")
        c.setFont("Helvetica", 9)
        c.drawRightString(_W - _MARGIN, top + 25, p.usuario)
        c.drawRightString(_W - _MARGIN, top + 12, f"Gerado em {p.data_geracao}")
        self.y = top - 30

    def _rodape(self) -> None:
        c = self.c
        c.setFillColor(brand.rl_color(brand.GRAPHITE))
        c.setFont("Helvetica", 7)
        c.drawString(_MARGIN, _MARGIN - 12, "Gerado pelo MCRA · Tempo registrado pelo próprio app")
        c.drawRightString(_W - _MARGIN, _MARGIN - 12, f"Página {self.numero}")

    def garantir(self, altura: float) -> None:
        """Quebra a página se não couber ``altura`` pontos acima do rodapé."""
        if self.y - altura < _MARGIN + 10:
            self._rodape()
            self.c.showPage()
            self.numero += 1
            self._cabecalho()

    def finalizar(self) -> None:
        self._rodape()
        self.c.showPage()


def _resumo(pg: _Pagina) -> None:
    c, p = pg.c, pg.payload
    c.setFillColor(brand.rl_color(brand.INK))
    c.setFont("Helvetica", 11)
    periodo = (
        _data_br(p.inicio) if p.inicio == p.fim else f"{_data_br(p.inicio)} a {_data_br(p.fim)}"
    )
    c.drawString(_MARGIN, pg.y, f"{_ROTULO_ESCALA.get(p.escala, p.escala)} · {periodo}")
    pg.y -= 34

    ocioso = max(0, p.total_aberto_s - p.total_ativo_s)
    blocos = [
        ("Aberto", p.total_aberto_s),
        ("Ativo", p.total_ativo_s),
        ("Ocioso", ocioso),
    ]
    largura = (_W - 2 * _MARGIN) / len(blocos)
    for indice, (rotulo, segundos) in enumerate(blocos):
        x = _MARGIN + indice * largura
        c.setFillColor(brand.rl_color(brand.GRAPHITE))
        c.setFont("Helvetica", 9)
        c.drawString(x, pg.y + 18, rotulo.upper())
        c.setFillColor(brand.rl_color(brand.NAVY))
        c.setFont("Helvetica-Bold", 20)
        c.drawString(x, pg.y - 4, formatar_duracao(segundos))
    pg.y -= 36


def _tabela(pg: _Pagina, titulo: str, cabecalho: str, linhas: list[UsoLinha]) -> None:
    c = pg.c
    pg.garantir(_LINHA * 4)
    c.setFillColor(brand.rl_color(brand.NAVY))
    c.setFont("Helvetica-Bold", 12)
    c.drawString(_MARGIN, pg.y, titulo)
    pg.y -= 6
    c.setFillColor(brand.rl_color(brand.GOLD))
    c.rect(_MARGIN, pg.y, _W - 2 * _MARGIN, 1.5, stroke=0, fill=1)
    pg.y -= _LINHA

    col_aberto = _W - _MARGIN - 110
    col_ativo = _W - _MARGIN

    def _cab() -> None:
        c.setFillColor(brand.rl_color(brand.GRAPHITE))
        c.setFont("Helvetica-Bold", 8)
        c.drawString(_MARGIN, pg.y, cabecalho.upper())
        c.drawRightString(col_aberto, pg.y, "ABERTO")
        c.drawRightString(col_ativo, pg.y, "ATIVO")
        pg.y -= _LINHA

    _cab()
    if not linhas:
        c.setFillColor(brand.rl_color(brand.GRAPHITE))
        c.setFont("Helvetica-Oblique", 9)
        c.drawString(_MARGIN, pg.y, "Sem uso registrado no período.")
        pg.y -= _LINHA
    for indice, linha in enumerate(linhas):
        if pg.y - _LINHA < _MARGIN + 10:
            pg.garantir(_LINHA * 2)
            _cab()
        if indice % 2 == 0:
            c.setFillColor(brand.rl_color(brand.PARCHMENT))
            c.rect(_MARGIN - 4, pg.y - 4, _W - 2 * _MARGIN + 8, _LINHA, stroke=0, fill=1)
        c.setFillColor(brand.rl_color(brand.INK))
        c.setFont("Helvetica", 9.5)
        c.drawString(_MARGIN, pg.y, linha.rotulo)
        c.drawRightString(col_aberto, pg.y, formatar_duracao(linha.aberto_s))
        c.drawRightString(col_ativo, pg.y, formatar_duracao(linha.ativo_s))
        pg.y -= _LINHA
    pg.y -= 18


def render_uso_pdf(payload: UsoPdfPayload) -> bytes:
    """Renderiza o relatório de uso como PDF binário (uma ou mais páginas A4)."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4, pageCompression=0)
    c.setTitle(f"MCRA Relatorio de uso {payload.usuario} {payload.inicio} {payload.fim}")
    pg = _Pagina(c, payload)
    _resumo(pg)
    _tabela(pg, "Tempo por tela", "Tela", payload.rotas)
    if payload.escala != "dia":
        _tabela(pg, "Tempo por dia", "Dia", payload.dias)
    pg.finalizar()
    c.save()
    return buf.getvalue()


__all__ = [
    "TITULOS_ROTA",
    "UsoLinha",
    "UsoPdfPayload",
    "formatar_duracao",
    "render_uso_pdf",
    "titulo_rota",
]
