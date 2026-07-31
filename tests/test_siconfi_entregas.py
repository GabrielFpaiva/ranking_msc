"""
tests/test_siconfi_entregas.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Testes do domínio de entregas do Siconfi (Dimensão I do Ranking).

Este módulo não toca rede nem disco — recebe dados e devolve conclusões.
Nenhum teste aqui usa mock.
"""

from __future__ import annotations

from datetime import date, datetime

import pytest

from ranking_msc.siconfi.entregas import (
    classificar,
    fim_do_periodo,
    parse_entregas,
    resumir,
)

# Item real da API (JP 2025, RREO 1º bimestre retificado).
ITEM_REAL: dict[str, object] = {
    "exercicio": 2025,
    "cod_ibge": 2507507,
    "populacao": 889618,
    "instituicao": "Prefeitura Municipal de João Pessoa - PB",
    "entregavel": "Relatório Resumido de Execução Orçamentária",
    "periodo": 1,
    "periodicidade": "B",
    "status_relatorio": "RE",
    "data_status": "2025-04-29T09:39:08Z",
    "forma_envio": "CSV",
    "tipo_relatorio": "P",
}

# Item real de MSC — status nulo, que NÃO é pendência.
ITEM_MSC: dict[str, object] = {
    "exercicio": 2025,
    "cod_ibge": 2507507,
    "populacao": 889618,
    "instituicao": "Prefeitura Municipal de João Pessoa - PB",
    "entregavel": "MSC Agregada",
    "periodo": 3,
    "periodicidade": "M",
    "status_relatorio": None,
    "data_status": "2025-05-29T09:39:08Z",
    "forma_envio": "CSV",
    "tipo_relatorio": None,
}


class TestParse:
    def test_parse_converte_item_real(self) -> None:
        """Item da API vira EntregaBruta com tipos corretos."""
        (bruta,) = parse_entregas([ITEM_REAL])

        assert bruta.exercicio == 2025
        assert bruta.cod_ibge == 2507507
        assert bruta.entregavel == "Relatório Resumido de Execução Orçamentária"
        assert bruta.periodo == 1
        assert bruta.periodicidade == "B"
        assert bruta.status_relatorio == "RE"
        assert bruta.data_status == datetime(2025, 4, 29, 9, 39, 8)

    def test_parse_aceita_status_e_data_nulos(self) -> None:
        """MSC vem sem status; parse não pode quebrar nem inventar valor."""
        (bruta,) = parse_entregas([ITEM_MSC])

        assert bruta.status_relatorio is None
        assert bruta.data_status is not None

    def test_parse_ignora_campos_desconhecidos(self) -> None:
        """Campo novo na API não pode quebrar o parse."""
        item = dict(ITEM_REAL) | {"campo_novo_do_tesouro": "surpresa"}
        (bruta,) = parse_entregas([item])
        assert bruta.periodo == 1


class TestFimDoPeriodo:
    @pytest.mark.parametrize(
        ("periodicidade", "periodo", "esperado"),
        [
            ("M", 1, date(2025, 1, 31)),
            ("M", 2, date(2025, 2, 28)),
            ("M", 12, date(2025, 12, 31)),
            ("B", 1, date(2025, 2, 28)),
            ("B", 6, date(2025, 12, 31)),
            ("Q", 1, date(2025, 4, 30)),
            ("Q", 3, date(2025, 12, 31)),
            ("A", 1, date(2025, 12, 31)),
        ],
    )
    def test_calcula_fim_do_periodo(
        self, periodicidade: str, periodo: int, esperado: date
    ) -> None:
        """Fim do período por periodicidade, incluindo fevereiro e virada de ano."""
        assert fim_do_periodo(periodicidade, periodo, 2025) == esperado

    def test_fevereiro_bissexto(self) -> None:
        """2024 é bissexto — o cálculo não pode ser tabela fixa de dias."""
        assert fim_do_periodo("M", 2, 2024) == date(2024, 2, 29)

    @pytest.mark.parametrize(
        ("periodicidade", "periodo"),
        [("X", 1), ("M", 13), ("B", 7), ("Q", 4), ("M", 0)],
    )
    def test_periodicidade_ou_periodo_desconhecido_devolve_none(
        self, periodicidade: str, periodo: int
    ) -> None:
        """Sem base para calcular, devolve None — nunca chuta uma data."""
        assert fim_do_periodo(periodicidade, periodo, 2025) is None


class TestClassificar:
    def test_status_re_vira_retificado(self) -> None:
        (bruta,) = parse_entregas([ITEM_REAL])
        assert classificar(bruta, {}).status == "RETIFICADO"

    def test_status_ho_vira_homologado(self) -> None:
        (bruta,) = parse_entregas([dict(ITEM_REAL) | {"status_relatorio": "HO"}])
        assert classificar(bruta, {}).status == "HOMOLOGADO"

    def test_status_nulo_vira_sem_status_e_nao_e_pendencia(self) -> None:
        """MSC sem status é normal — não pode virar RETIFICADO nem erro."""
        (bruta,) = parse_entregas([ITEM_MSC])
        entrega = classificar(bruta, {})

        assert entrega.status == "SEM_STATUS"
        assert entrega.atrasada is None

    def test_calcula_dias_apos_fim_do_periodo(self) -> None:
        """RREO 1º bim/2025: período fecha 28/02, entrega em 29/04 = 60 dias."""
        (bruta,) = parse_entregas([ITEM_REAL])
        entrega = classificar(bruta, {})

        assert entrega.fim_periodo == date(2025, 2, 28)
        assert entrega.dias_apos_fim_periodo == 60

    def test_sem_prazo_configurado_nao_julga_atraso(self) -> None:
        """A regra de ouro: sem prazo, só o fato. `atrasada` fica None."""
        (bruta,) = parse_entregas([ITEM_REAL])
        entrega = classificar(bruta, prazos={})

        assert entrega.prazo_dias is None
        assert entrega.atrasada is None
        assert entrega.dias_apos_fim_periodo == 60  # o fato continua lá

    def test_com_prazo_configurado_julga_atraso(self) -> None:
        """RREO: prazo de 30 dias, entrega em 60 ⇒ atrasada."""
        (bruta,) = parse_entregas([ITEM_REAL])
        prazos = {"Relatório Resumido de Execução Orçamentária": 30}
        entrega = classificar(bruta, prazos)

        assert entrega.prazo_dias == 30
        assert entrega.atrasada is True

    def test_dentro_do_prazo_nao_e_atraso(self) -> None:
        item = dict(ITEM_REAL) | {"data_status": "2025-03-10T00:00:00Z"}
        (bruta,) = parse_entregas([item])
        entrega = classificar(bruta, {"Relatório Resumido de Execução Orçamentária": 30})

        assert entrega.dias_apos_fim_periodo == 10
        assert entrega.atrasada is False

    def test_prazo_configurado_mas_periodo_indecifravel_nao_julga(self) -> None:
        """Prazo existe mas não sabemos quando o período fechou ⇒ sem veredicto."""
        item = dict(ITEM_REAL) | {"periodicidade": "X"}
        (bruta,) = parse_entregas([item])
        entrega = classificar(bruta, {"Relatório Resumido de Execução Orçamentária": 30})

        assert entrega.fim_periodo is None
        assert entrega.dias_apos_fim_periodo is None
        assert entrega.atrasada is None

    def test_entrega_no_mesmo_dia_do_fim_periodo_da_zero_dias(self) -> None:
        """Fronteira: entrega no mesmo dia do fim do período ⇒ 0 dias após."""
        item = dict(ITEM_REAL) | {
            "periodo": 1,
            "periodicidade": "M",
            "exercicio": 2025,
            "data_status": "2025-01-31T23:30:00Z",
        }
        (bruta,) = parse_entregas([item])
        entrega = classificar(bruta, {})

        assert entrega.fim_periodo == date(2025, 1, 31)
        assert entrega.dias_apos_fim_periodo == 0


class TestResumir:
    def test_conta_homologadas_e_retificadas(self) -> None:
        """O número de retificações é o que a Dimensão I conta."""
        itens = [
            ITEM_REAL,
            dict(ITEM_REAL) | {"status_relatorio": "HO", "periodo": 2},
            dict(ITEM_REAL) | {"status_relatorio": "HO", "periodo": 3},
            ITEM_MSC,
        ]
        entregas = [classificar(b, {}) for b in parse_entregas(itens)]
        resumo = resumir(entregas)

        assert resumo.total == 4
        assert resumo.homologadas == 2
        assert resumo.retificadas == 1
