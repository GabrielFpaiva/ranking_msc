"""
Cliente da API pública de dados abertos do Siconfi.

Sem autenticação e sem captcha. A única responsabilidade deste módulo é falar
HTTP e paginar — classificação de dados fica em ``entregas.py``.

Doc: https://apidatalake.tesouro.gov.br/docs/siconfi/
"""

from __future__ import annotations

import logging

import httpx

from ranking_msc.exceptions import SiconfiIndisponivelError

logger = logging.getLogger("ranking_msc")

BASE_URL = "https://apidatalake.tesouro.gov.br/ords/siconfi/tt/extrato_entregas"

# Teto de páginas: a API é paginada e um `hasMore` sempre verdadeiro (bug do
# lado deles ou mudança de contrato) travaria o processo para sempre.
_MAX_PAGINAS = 50


def buscar_extrato(
    id_ente: int,
    exercicio: int,
    *,
    transport: httpx.BaseTransport | None = None,
    timeout: float = 30.0,
) -> list[dict[str, object]]:
    """Busca o extrato de entregas de um ente num exercício.

    Args:
        id_ente: código IBGE do ente (ex.: 2507507 para João Pessoa).
        exercicio: ano de referência.
        transport: transporte httpx alternativo — usado nos testes para
            rodar sem rede.
        timeout: timeout por requisição, em segundos.

    Returns:
        Lista de itens crus do extrato, já concatenada de todas as páginas.

    Raises:
        SiconfiIndisponivelError: erro HTTP, timeout ou falha de conexão.
    """
    itens: list[dict[str, object]] = []
    offset = 0

    try:
        with httpx.Client(transport=transport, timeout=timeout) as client:
            for _ in range(_MAX_PAGINAS):
                resp = client.get(
                    BASE_URL,
                    params={
                        "an_referencia": exercicio,
                        "id_ente": id_ente,
                        "offset": offset,
                    },
                )
                resp.raise_for_status()
                dados = resp.json()

                itens.extend(dados.get("items", []))
                if not dados.get("hasMore"):
                    return itens
                offset += int(dados.get("limit", 25))

        logger.warning(
            "Extrato do Siconfi excedeu %s páginas — resultado truncado. ente=%s ano=%s",
            _MAX_PAGINAS,
            id_ente,
            exercicio,
        )
        return itens

    except httpx.HTTPError as exc:
        raise SiconfiIndisponivelError(
            f"Não foi possível consultar o extrato do Siconfi "
            f"(ente={id_ente}, exercício={exercicio}): {exc}"
        ) from exc
