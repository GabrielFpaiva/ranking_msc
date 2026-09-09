"""
app.api.routes.uso
~~~~~~~~~~~~~~~~~~

Endpoints do tempo de uso por usuário.

O usuário **nunca** é parâmetro: sai sempre do ``sub`` do JWT via
``get_current_user``. Não existindo rota que aceite "de quem", não existe a
classe de bug em que um ``?usuario=`` mal validado vaza o tempo do colega.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.api.deps import absolute_uso_dir, get_current_user
from app.api.schemas import HeartbeatIn, UsoHojeOut
from app.api.uso_store import ACUMULADOR, ROTAS_VALIDAS, dia_local, ler_mes

router = APIRouter(prefix="/api", tags=["uso"])


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
