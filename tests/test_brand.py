"""Testes do módulo de marca (paleta e helpers de estilo)."""

from __future__ import annotations

from openpyxl.styles import PatternFill

from ranking_msc.outputs import brand


class TestBandHex:
    def test_score_95_ou_mais_banda_a(self) -> None:
        assert brand.band_hex_for_score(95.0) == brand.BAND_A
        assert brand.band_hex_for_score(100.0) == brand.BAND_A

    def test_score_intermediarios(self) -> None:
        assert brand.band_hex_for_score(85.0) == brand.BAND_B
        assert brand.band_hex_for_score(75.0) == brand.BAND_C
        assert brand.band_hex_for_score(65.0) == brand.BAND_D

    def test_score_abaixo_de_65_banda_e(self) -> None:
        assert brand.band_hex_for_score(64.9) == brand.BAND_E
        assert brand.band_hex_for_score(0.0) == brand.BAND_E

    def test_band_hex_por_letra(self) -> None:
        assert brand.band_hex("A") == brand.BAND_A
        assert brand.band_hex("E") == brand.BAND_E
        assert brand.band_hex("?") == brand.BAND_E  # fallback


class TestSeverityHex:
    def test_severidades_conhecidas(self) -> None:
        assert brand.severity_hex("ERRO") == brand.ERRO
        assert brand.severity_hex("alerta") == brand.ALERTA
        assert brand.severity_hex("INFO") == brand.INFO

    def test_severidade_desconhecida_usa_info(self) -> None:
        assert brand.severity_hex("XPTO") == brand.INFO


class TestOpenpyxlHelpers:
    def test_fill_retorna_patternfill_solido(self) -> None:
        f = brand.fill(brand.NAVY)
        assert isinstance(f, PatternFill)
        assert f.fill_type == "solid"
        assert f.fgColor.rgb.endswith(brand.NAVY)

    def test_header_font_branco_bold(self) -> None:
        assert brand.HEADER_FONT.bold is True
        assert brand.HEADER_FONT.color.rgb.endswith(brand.WHITE)


class TestReportlabHelper:
    def test_rl_color_componentes_normalizados(self) -> None:
        c = brand.rl_color(brand.GOLD)  # C9A449
        assert round(c.red, 3) == round(0xC9 / 255, 3)
        assert round(c.green, 3) == round(0xA4 / 255, 3)
        assert round(c.blue, 3) == round(0x49 / 255, 3)
