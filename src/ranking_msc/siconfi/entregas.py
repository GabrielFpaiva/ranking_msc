"""
Domínio das entregas ao Siconfi — Dimensão I do Ranking.

Este módulo é puro: não conhece rede nem disco. Recebe os itens crus do
extrato de entregas e devolve entregas classificadas.

Referência: https://ranking-municipios.tesouro.gov.br/metodologia
"""

from __future__ import annotations

import calendar
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

StatusEntrega = Literal["HOMOLOGADO", "RETIFICADO", "SEM_STATUS"]

# Quantos meses cada período cobre, por código de periodicidade da API.
_MESES_POR_PERIODO: dict[str, int] = {"M": 1, "B": 2, "Q": 4, "A": 12}

_STATUS: dict[str, StatusEntrega] = {"HO": "HOMOLOGADO", "RE": "RETIFICADO"}


@dataclass(frozen=True)
class EntregaBruta:
    """Um item do extrato de entregas, como a API devolve."""

    exercicio: int
    cod_ibge: int
    instituicao: str
    entregavel: str
    periodo: int
    periodicidade: str
    status_relatorio: str | None
    data_status: datetime | None
    forma_envio: str | None


@dataclass(frozen=True)
class Entrega:
    """Entrega classificada.

    ``atrasada`` é ``None`` quando não há base para julgar — prazo não
    configurado, ou período que não sabemos decifrar. Nunca inferir ``False``
    a partir de ausência de informação.
    """

    bruta: EntregaBruta
    status: StatusEntrega
    fim_periodo: date | None
    dias_apos_fim_periodo: int | None
    prazo_dias: int | None
    atrasada: bool | None


@dataclass(frozen=True)
class ResumoEntregas:
    """Contagens do exercício. ``retificadas`` é o que a Dimensão I penaliza."""

    total: int
    homologadas: int
    retificadas: int


def _parse_data(valor: object) -> datetime | None:
    """Converte a data ISO da API (sufixo ``Z``) em ``datetime`` naive.

    O sufixo ``Z`` na API Siconfi representa hora local brasileira mal rotulada,
    não UTC. Análise de 117 timestamps reais (2023–2025): 93% caem em horário
    comercial (8h–19h) quando interpretados como hora local; distribuição cumpre
    padrão de expediente (picos às 10h e 15h, queda no almoço).

    Devolve datetime naive para evitar corrupção silenciosa em operações de fuso
    futuro (.astimezone()), que teriam consequências graves para cálculo de atraso.
    """
    if not isinstance(valor, str) or not valor:
        return None
    return datetime.fromisoformat(valor.replace("Z", ""))


def parse_entregas(items: list[dict[str, object]]) -> list[EntregaBruta]:
    """Converte itens crus da API em ``EntregaBruta``.

    Campos desconhecidos são ignorados de propósito: um campo novo no extrato
    não pode derrubar a tela.
    """
    return [
        EntregaBruta(
            exercicio=int(item["exercicio"]),  # type: ignore[call-overload]
            cod_ibge=int(item["cod_ibge"]),  # type: ignore[call-overload]
            instituicao=str(item["instituicao"]),
            entregavel=str(item["entregavel"]),
            periodo=int(item["periodo"]),  # type: ignore[call-overload]
            periodicidade=str(item["periodicidade"]),
            status_relatorio=(
                str(item["status_relatorio"])
                if item.get("status_relatorio") is not None
                else None
            ),
            data_status=_parse_data(item.get("data_status")),
            forma_envio=(
                str(item["forma_envio"]) if item.get("forma_envio") is not None else None
            ),
        )
        for item in items
    ]


def fim_do_periodo(periodicidade: str, periodo: int, exercicio: int) -> date | None:
    """Último dia do período coberto pela entrega.

    Devolve ``None`` quando a periodicidade é desconhecida ou o número do
    período está fora da faixa — não chutamos data.
    """
    meses = _MESES_POR_PERIODO.get(periodicidade)
    if meses is None or periodo < 1:
        return None

    mes_final = periodo * meses
    if mes_final > 12:
        return None

    ultimo_dia = calendar.monthrange(exercicio, mes_final)[1]
    return date(exercicio, mes_final, ultimo_dia)


def classificar(bruta: EntregaBruta, prazos: Mapping[str, int]) -> Entrega:
    """Classifica uma entrega, julgando atraso apenas quando há base para isso.

    Args:
        bruta: entrega como veio da API.
        prazos: mapa ``entregável -> prazo em dias``. Entregável ausente do
            mapa recebe apenas o dado factual, sem veredicto de atraso.

    Note:
        Quando ``status == "RETIFICADO"``, ``atrasada`` é sempre ``None``,
        mesmo com prazo configurado. ``data_status`` de um registro
        retificado é a data da RETIFICAÇÃO, não da entrega original — meses
        depois do envio real. O extrato da API não traz a data da entrega
        original, então não há base para julgar atraso nesse caso.
        ``dias_apos_fim_periodo`` continua exposto como fato (mede a
        distância até a retificação), só não vira veredicto de atraso.
    """
    status: StatusEntrega = _STATUS.get(bruta.status_relatorio or "", "SEM_STATUS")
    fim = fim_do_periodo(bruta.periodicidade, bruta.periodo, bruta.exercicio)

    dias: int | None = None
    if fim is not None and bruta.data_status is not None:
        dias = (bruta.data_status.date() - fim).days

    prazo = prazos.get(bruta.entregavel)
    atrasada: bool | None = None
    if status != "RETIFICADO" and prazo is not None and dias is not None:
        atrasada = dias > prazo

    return Entrega(
        bruta=bruta,
        status=status,
        fim_periodo=fim,
        dias_apos_fim_periodo=dias,
        prazo_dias=prazo,
        atrasada=atrasada,
    )


def resumir(entregas: Sequence[Entrega]) -> ResumoEntregas:
    """Conta total, homologadas e retificadas."""
    return ResumoEntregas(
        total=len(entregas),
        homologadas=sum(1 for e in entregas if e.status == "HOMOLOGADO"),
        retificadas=sum(1 for e in entregas if e.status == "RETIFICADO"),
    )
