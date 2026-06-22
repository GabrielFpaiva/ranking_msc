"""
ranking_msc.outputs.brand
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Identidade visual compartilhada (paleta MCRA) e helpers de estilo para
openpyxl (Excel) e reportlab (PDF). Fonte única de cores — evita duplicação.
"""

from __future__ import annotations

from openpyxl.styles import Font, PatternFill
from reportlab.lib.colors import Color

# -- Paleta (hex sem '#') -----------------------------------------------------
NAVY = "0F1E3D"
GOLD = "C9A449"
GOLD_LT = "F3E6BA"
PARCHMENT = "F6F4EE"
INK = "1B1B1F"
GRAPHITE = "5A5C66"
WHITE = "FFFFFF"

BAND_A = "2F8F5C"
BAND_B = "6BA642"
BAND_C = "D9B433"
BAND_D = "D98B1C"
BAND_E = "C02B2B"

ERRO = "C02B2B"
ALERTA = "D98B1C"
INFO = "1E5AA8"

_BAND_BY_LETTER: dict[str, str] = {
    "A": BAND_A,
    "B": BAND_B,
    "C": BAND_C,
    "D": BAND_D,
    "E": BAND_E,
}
# (limite inferior inclusivo, hex) — espelha as bandas do score_engine
_BAND_THRESHOLDS: list[tuple[float, str]] = [
    (95.0, BAND_A),
    (85.0, BAND_B),
    (75.0, BAND_C),
    (65.0, BAND_D),
    (0.0, BAND_E),
]
_SEVERITY_BY_NAME: dict[str, str] = {"ERRO": ERRO, "ALERTA": ALERTA, "INFO": INFO}


def band_hex(banda: str) -> str:
    """Cor da banda A-E; fallback para a banda E (vermelho)."""
    return _BAND_BY_LETTER.get(banda.strip().upper(), BAND_E)


def band_hex_for_score(nota_pct: float) -> str:
    """Cor correspondente a uma nota 0-100."""
    for threshold, hex_color in _BAND_THRESHOLDS:
        if nota_pct >= threshold:
            return hex_color
    return BAND_E


def severity_hex(sev: str) -> str:
    """Cor da severidade; fallback para INFO."""
    return _SEVERITY_BY_NAME.get(sev.strip().upper(), INFO)


def fill(hex_str: str) -> PatternFill:
    """PatternFill sólido a partir de um hex sem '#'."""
    return PatternFill(fill_type="solid", fgColor=f"FF{hex_str}")


HEADER_FILL = fill(NAVY)
HEADER_FONT = Font(bold=True, color=f"FF{WHITE}")
TITLE_FONT = Font(bold=True, color=f"FF{GOLD}", size=16)


def rl_color(hex_str: str) -> Color:
    """reportlab Color a partir de um hex sem '#'."""
    r = int(hex_str[0:2], 16) / 255
    g = int(hex_str[2:4], 16) / 255
    b = int(hex_str[4:6], 16) / 255
    return Color(r, g, b)
