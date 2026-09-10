"""
app.api.routes.uso
~~~~~~~~~~~~~~~~~~

Endpoints do tempo de uso por usuário.

O usuário **nunca** é parâmetro: sai sempre do ``sub`` do JWT via
``get_current_user``. Não existindo rota que aceite "de quem", não existe a
classe de bug em que um ``?usuario=`` mal validado vaza o tempo do colega.

As três rotas declaram ``Depends(get_current_user)`` por função, em vez do
padrão de outros módulos de rota (``Depends`` no ``APIRouter``, aplicado a
todas as rotas de uma vez). É deliberado: aqui o username não é só um portão
de acesso — é consumido diretamente por cada handler (chave de agregação,
filtro do acumulador). Se um dia alguém "padronizar" isto para o
``APIRouter``, as três rotas param de receber ``usuario`` como parâmetro.
"""

from __future__ import annotations

import calendar
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.api.deps import absolute_uso_dir, get_current_user
from app.api.schemas import (
    HeartbeatIn,
    UsoAnualOut,
    UsoDiaOut,
    UsoHistoricoOut,
    UsoHojeOut,
    UsoMesOut,
    UsoRotaOut,
)
from app.api.uso_store import (
    ACUMULADOR,
    ROTAS_VALIDAS,
    agregado_do_ano,
    agregado_do_periodo,
    dia_local,
    ler_mes,
)

router = APIRouter(prefix="/api", tags=["uso"])

# O app não tem dado de uso anterior a 2020 — qualquer ano abaixo disso é
# certamente engano ou tentativa de abuso, não um período real a consultar.
ANO_MINIMO = 2020


@router.post(
    "/uso/heartbeat",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Registra uma batida de tempo de uso do usuário autenticado",
)
def post_heartbeat(
    payload: HeartbeatIn,
    usuario: str = Depends(get_current_user),  # noqa: B008
) -> Response:
    """Soma um heartbeat ao acumulador em memória.

    Raises:
        HTTPException 422: se a rota não estiver na allowlist do SPA.
    """
    if payload.rota not in ROTAS_VALIDAS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Rota desconhecida: {payload.rota!r}",
        )

    ACUMULADOR.registrar(
        usuario=usuario,
        rota=payload.rota,
        aberto_s=payload.aberto_s,
        ativo_s=payload.ativo_s,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/uso/hoje",
    response_model=UsoHojeOut,
    summary="Totais do dia corrente para o usuário autenticado",
)
def get_uso_hoje(usuario: str = Depends(get_current_user)) -> UsoHojeOut:  # noqa: B008
    """Soma o que já está em disco com o que ainda está no buffer em memória.

    Sem a parcela do buffer, o número mostrado na sidebar ficaria até um ciclo
    de flush (5 minutos) atrás do relógio que roda no browser.
    """
    hoje = dia_local()
    gravado = ler_mes(absolute_uso_dir(), hoje[:7], usuario)

    aberto_s = sum(tempo.aberto_s for (dia, _), tempo in gravado.items() if dia == hoje)
    ativo_s = sum(tempo.ativo_s for (dia, _), tempo in gravado.items() if dia == hoje)

    for chave, tempo in ACUMULADOR.espiar().items():
        if chave.usuario == usuario and chave.dia == hoje:
            aberto_s += tempo.aberto_s
            ativo_s += tempo.ativo_s

    return UsoHojeOut(aberto_s=aberto_s, ativo_s=ativo_s)


@router.get(
    "/uso/historico",
    response_model=UsoHistoricoOut,
    summary="Série diária do mês e totais do período para o usuário autenticado",
)
def get_uso_historico(
    escala: Literal["dia", "semana", "mes"] = Query(..., description="Bucket do período"),
    ref: str = Query(..., description="Data de referência YYYY-MM-DD"),
    usuario: str = Depends(get_current_user),  # noqa: B008
) -> UsoHistoricoOut:
    """Monta o payload da tela "Meu tempo de uso".

    Inclui a parcela do buffer em memória (``ACUMULADOR.espiar()``) que cai
    dentro do período consultado — do mesmo jeito que ``/api/uso/hoje`` já
    faz para o dia corrente. Sem isso, os dois números da mesma página
    (sidebar e esta tela) discordavam entre si por até um ciclo de flush (5
    minutos), e o tempo gasto na própria tela ``/uso`` nunca aparecia
    enquanto ela estava aberta.

    ``dias`` cobre o mês inteiro de ``ref`` com zeros preenchidos, para o front
    desenhar as semanas agrupadas sob o cabeçalho do mês numa requisição só.
    ``rotas`` e os totais referem-se apenas ao período de ``escala``.

    Quando o período de ``escala`` cruza a virada do mês (ex.: uma semana de
    31/08 a 06/09 com ``ref`` em setembro), os totais e ``rotas`` incluem os
    dois lados da fronteira, mas ``dias`` continua cobrindo só o mês de
    ``ref`` — o dia do outro mês entra na soma, mas não ganha barra no
    gráfico. É intencional: o gráfico é uma visão de mês, os totais são uma
    visão de período.

    Raises:
        HTTPException 422: se ``ref`` não for uma data ISO válida.
    """
    try:
        referencia = date.fromisoformat(ref)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Data de referência inválida: {ref!r}. Use YYYY-MM-DD.",
        ) from exc

    ref_normalizado = referencia.isoformat()
    agregado, inicio, fim = agregado_do_periodo(
        absolute_uso_dir(), escala, ref_normalizado, usuario, buffer=ACUMULADOR.espiar()
    )

    # Série diária: mês inteiro de ref, com zeros preenchidos.
    ultimo_dia = calendar.monthrange(referencia.year, referencia.month)[1]
    por_dia: dict[str, UsoDiaOut] = {}
    for numero in range(1, ultimo_dia + 1):
        chave = referencia.replace(day=numero).isoformat()
        por_dia[chave] = UsoDiaOut(dia=chave, aberto_s=0, ativo_s=0)

    por_rota: dict[str, UsoRotaOut] = {}
    total_aberto_s = 0
    total_ativo_s = 0

    for (dia, rota), tempo in agregado.items():
        if dia in por_dia:
            por_dia[dia].aberto_s += tempo.aberto_s
            por_dia[dia].ativo_s += tempo.ativo_s
            # `agregado` já é chaveado por (dia, rota) — nunca duas entradas
            # para o mesmo par —, então atribuir direto basta; não há soma
            # de duplicata a fazer aqui.
            por_dia[dia].por_rota[rota] = tempo.aberto_s
        if inicio <= dia <= fim:
            atual = por_rota.setdefault(rota, UsoRotaOut(rota=rota, aberto_s=0, ativo_s=0))
            atual.aberto_s += tempo.aberto_s
            atual.ativo_s += tempo.ativo_s
            total_aberto_s += tempo.aberto_s
            total_ativo_s += tempo.ativo_s

    return UsoHistoricoOut(
        escala=escala,
        ref=ref_normalizado,
        inicio=inicio,
        fim=fim,
        total_aberto_s=total_aberto_s,
        total_ativo_s=total_ativo_s,
        dias=list(por_dia.values()),
        rotas=sorted(por_rota.values(), key=lambda item: item.aberto_s, reverse=True),
    )


@router.get(
    "/uso/anual",
    response_model=UsoAnualOut,
    summary="Totais mensais do ano para o usuário autenticado",
)
def get_uso_anual(
    ano: int = Query(..., description="Ano de referência, formato YYYY"),
    usuario: str = Depends(get_current_user),  # noqa: B008
) -> UsoAnualOut:
    """Monta o payload da visão anual — doze barras, uma por mês.

    Existe como rota própria em vez de reaproveitar ``/api/uso/historico``
    com uma escala nova porque o formato de resposta é outro: aqui não há
    ``dias`` nem ``rotas``, só doze totais mensais sempre completos.

    Inclui a parcela do buffer em memória no mês em que ela cair — só o mês
    corrente pode ter buffer pendente, mas ``agregado_do_ano`` não assume
    isso e filtra por mês mesmo assim. Ver ``get_uso_historico`` para o
    porquê.

    Raises:
        HTTPException 422: se ``ano`` estiver fora do intervalo plausível —
            antes de ``ANO_MINIMO`` (o app não tem dado anterior a isso) ou
            além do ano corrente mais um, folga para fuso/relógio do host.
    """
    ano_maximo = date.today().year + 1
    if not (ANO_MINIMO <= ano <= ano_maximo):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Ano fora do intervalo permitido ({ANO_MINIMO}–{ano_maximo}): {ano!r}.",
        )

    meses = [
        UsoMesOut(
            mes=ano_mes,
            aberto_s=tempo.aberto_s,
            ativo_s=tempo.ativo_s,
            por_rota=tempo.por_rota,
        )
        for ano_mes, tempo in agregado_do_ano(
            absolute_uso_dir(), ano, usuario, buffer=ACUMULADOR.espiar()
        )
    ]

    return UsoAnualOut(
        ano=ano,
        total_aberto_s=sum(item.aberto_s for item in meses),
        total_ativo_s=sum(item.ativo_s for item in meses),
        meses=meses,
    )
