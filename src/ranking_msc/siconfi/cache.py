"""
Cache em disco do extrato de entregas do Siconfi.

O extrato muda raramente. Buscar a cada carregamento de tela seria desperdício
e criaria dependência da disponibilidade do Tesouro.

Toda entrada guarda ``buscado_em``: no modo degradado a tela mostra essa data,
de modo que dado velho nunca seja apresentado como atual.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

logger = logging.getLogger("ranking_msc")


@dataclass(frozen=True)
class EntradaCache:
    """Itens do extrato mais o instante em que foram buscados."""

    itens: list[dict[str, object]]
    buscado_em: datetime


def _caminho(cache_dir: Path, id_ente: int, exercicio: int) -> Path:
    return Path(cache_dir) / f"entregas_{id_ente}_{exercicio}.json"


def _carregar(caminho: Path) -> EntradaCache | None:
    """Lê e valida o arquivo. Conteúdo inválido é tratado como ausência."""
    if not caminho.is_file():
        return None
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        return EntradaCache(
            itens=dados["itens"],
            buscado_em=datetime.fromisoformat(dados["buscado_em"]),
        )
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        logger.warning("Cache do Siconfi ilegível, ignorando: %s", caminho)
        return None


def gravar_cache(
    cache_dir: Path,
    id_ente: int,
    exercicio: int,
    itens: list[dict[str, object]],
    *,
    agora: datetime | None = None,
) -> None:
    """Grava os itens com carimbo de data/hora."""
    caminho = _caminho(cache_dir, id_ente, exercicio)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    momento = agora or datetime.now(UTC)
    caminho.write_text(
        json.dumps(
            {"itens": itens, "buscado_em": momento.isoformat()},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def ler_cache(
    cache_dir: Path,
    id_ente: int,
    exercicio: int,
    ttl_horas: float,
    *,
    agora: datetime | None = None,
) -> EntradaCache | None:
    """Lê o cache se existir e ainda estiver dentro do TTL."""
    entrada = _carregar(_caminho(cache_dir, id_ente, exercicio))
    if entrada is None:
        return None

    momento = agora or datetime.now(UTC)
    if momento - entrada.buscado_em > timedelta(hours=ttl_horas):
        return None
    return entrada


def ler_cache_ignorando_ttl(
    cache_dir: Path, id_ente: int, exercicio: int
) -> EntradaCache | None:
    """Lê o cache mesmo expirado — usado quando a API está indisponível."""
    return _carregar(_caminho(cache_dir, id_ente, exercicio))
