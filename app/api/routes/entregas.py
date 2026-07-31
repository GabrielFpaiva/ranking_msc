"""
app.api.routes.entregas
~~~~~~~~~~~~~~~~~~~~~~~

GET /api/entregas — extrato de entregas ao Siconfi (Dimensão I do Ranking).

Três origens possíveis, todas com HTTP 200:

* ``api``          — dados frescos;
* ``cache``        — Siconfi indisponível, servindo cache com a data da busca;
* ``indisponivel`` — sem API e sem cache: vazio explicativo.

Indisponibilidade de serviço externo não vira 500: a tela precisa continuar
utilizável, e precisa dizer com clareza o que está mostrando.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user, get_settings
from app.api.schemas import EntregaOut, EntregasOut, ResumoEntregasOut
from ranking_msc.config.settings import Settings
from ranking_msc.exceptions import SiconfiIndisponivelError
from ranking_msc.siconfi.cache import (
    gravar_cache,
    ler_cache,
    ler_cache_ignorando_ttl,
)
from ranking_msc.siconfi.client import buscar_extrato
from ranking_msc.siconfi.entregas import Entrega, classificar, parse_entregas, resumir

logger = logging.getLogger("ranking_msc")

router = APIRouter(
    prefix="/api",
    tags=["entregas"],
    dependencies=[Depends(get_current_user)],
)


def _to_out(entrega: Entrega) -> EntregaOut:
    """Converte a entrega do domínio no schema da API."""
    return EntregaOut(
        instituicao=entrega.bruta.instituicao,
        entregavel=entrega.bruta.entregavel,
        periodo=entrega.bruta.periodo,
        periodicidade=entrega.bruta.periodicidade,
        status=entrega.status,
        data_status=entrega.bruta.data_status,
        fim_periodo=entrega.fim_periodo,
        dias_apos_fim_periodo=entrega.dias_apos_fim_periodo,
        prazo_dias=entrega.prazo_dias,
        atrasada=entrega.atrasada,
    )


@router.get(
    "/entregas",
    response_model=EntregasOut,
    summary="Extrato de entregas ao Siconfi (prazos e retificações)",
)
def get_entregas(
    ano: int = Query(..., ge=2000, le=2100, description="Exercício de referência"),
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> EntregasOut:
    """Busca o extrato, com cache e degradação explícita."""
    cfg = settings.siconfi
    cache_dir = Path(settings.paths.data_dir) / "cache"

    origem = "api"
    aviso: str | None = None
    buscado_em: datetime | None = None

    entrada = ler_cache(cache_dir, cfg.id_ente, ano, cfg.cache_ttl_horas)
    if entrada is not None:
        itens = entrada.itens
        buscado_em = entrada.buscado_em
    else:
        try:
            itens = buscar_extrato(cfg.id_ente, ano)
            buscado_em = datetime.now(UTC)
            gravar_cache(cache_dir, cfg.id_ente, ano, itens, agora=buscado_em)
        except SiconfiIndisponivelError as exc:
            logger.warning("Siconfi indisponível: %s", exc)
            antigo = ler_cache_ignorando_ttl(cache_dir, cfg.id_ente, ano)
            if antigo is not None:
                itens = antigo.itens
                buscado_em = antigo.buscado_em
                origem = "cache"
                aviso = (
                    "Não foi possível atualizar com o Siconfi. "
                    "Exibindo os últimos dados obtidos."
                )
            else:
                itens = []
                origem = "indisponivel"
                aviso = (
                    "Não foi possível consultar o Siconfi e não há dados salvos. "
                    "Verifique a conexão do servidor com a internet."
                )

    entregas = [classificar(b, cfg.prazos_dias) for b in parse_entregas(itens)]
    resumo = resumir(entregas)

    return EntregasOut(
        ano=ano,
        id_ente=cfg.id_ente,
        origem=origem,
        buscado_em=buscado_em,
        aviso=aviso,
        resumo=ResumoEntregasOut(
            total=resumo.total,
            homologadas=resumo.homologadas,
            retificadas=resumo.retificadas,
        ),
        entregas=[_to_out(e) for e in entregas],
    )
