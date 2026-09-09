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

from app.api.deps import get_current_user
from app.api.schemas import HeartbeatIn
from app.api.uso_store import ACUMULADOR, ROTAS_VALIDAS

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
