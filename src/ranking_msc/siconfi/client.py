"""
Cliente da API pública de dados abertos do Siconfi.

Sem autenticação e sem captcha. A única responsabilidade deste módulo é falar
HTTP e paginar — classificação de dados fica em ``entregas.py``.

Doc: https://apidatalake.tesouro.gov.br/docs/siconfi/
"""

from __future__ import annotations

import json
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
        SiconfiIndisponivelError: erro HTTP, timeout, falha de conexão, JSON malformado
            ou resposta truncada (teto de páginas atingido).
    """
    itens: list[dict[str, object]] = []
    offset = 0

    try:
        with httpx.Client(transport=transport, timeout=timeout) as client:
            for _pagina in range(_MAX_PAGINAS):
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

                # Extrai limit defensivamente — pode ser None, string, ou número
                limit_raw = dados.get("limit", 25)
                try:
                    limit = int(limit_raw) if limit_raw is not None else 25
                except (ValueError, TypeError) as e:
                    raise SiconfiIndisponivelError(
                        f"Valor inválido para 'limit' na resposta do Siconfi: {limit_raw!r}"
                    ) from e

                offset += limit

            # Saiu do loop sem retornar → atingiu teto de páginas com hasMore=true
            logger.warning(
                "Extrato do Siconfi excedeu %s páginas — resultado possivelmente truncado. "
                "ente=%s ano=%s offset=%s",
                _MAX_PAGINAS,
                id_ente,
                exercicio,
                offset,
            )
            raise SiconfiIndisponivelError(
                f"Extrato do Siconfi excedeu {_MAX_PAGINAS} páginas (ente={id_ente}, "
                f"exercício={exercicio}) — resposta possivelmente truncada"
            )

    except httpx.HTTPError as exc:
        raise SiconfiIndisponivelError(
            f"Não foi possível consultar o extrato do Siconfi "
            f"(ente={id_ente}, exercício={exercicio}): {exc}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise SiconfiIndisponivelError(
            f"Resposta do Siconfi contém JSON malformado "
            f"(ente={id_ente}, exercício={exercicio}): {exc}"
        ) from exc
