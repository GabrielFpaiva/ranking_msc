"""
app.api.uso_store
~~~~~~~~~~~~~~~~~

Persistência e agregação do tempo de uso por usuário.

Lógica pura, sem dependências de FastAPI — testável isoladamente, no mesmo
espírito de ``app/api/auth.py``. O binding HTTP fica em ``app/api/routes/uso.py``.

Formato em disco: ``data/uso/<YYYY-MM>.jsonl``, uma linha por flush, contendo
**deltas** e não totais acumulados. Somar deltas é idempotente diante de
reinícios do servidor; gravar totais faria o contador andar para trás depois
de um restart no meio do dia.

Meses fechados são compactados em ``<YYYY-MM>.agg.jsonl`` com uma linha por
``(usuario, dia, rota)`` e servidos de cache de módulo.

A agregação usa ``json`` e ``dict`` da stdlib de propósito: para somar dois
inteiros por chave num arquivo de poucos milhares de linhas, pandas é 2,7x mais
lento e usa 26x mais memória.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

FUSO = ZoneInfo("America/Recife")

# Rotas conhecidas do SPA. O heartbeat vem do cliente, então a rota passa por
# allowlist — sem isso, um front bugado (ou o DevTools de um curioso) escreve
# texto arbitrário dentro do JSONL.
ROTAS_VALIDAS: frozenset[str] = frozenset({
    "/inicio", "/pendencias", "/caixa", "/passivos", "/superavit",
    "/executivo", "/comparar", "/entregas", "/regras", "/execucao", "/uso",
})

# Teto por heartbeat. O front bate a cada 60 s; 120 s dá folga para atraso de
# rede sem permitir que alguém se dê 40 horas de uso com um curl.
MAX_SEGUNDOS_POR_HEARTBEAT = 120


def dia_local(momento: datetime | None = None) -> str:
    """Retorna o dia no formato ``YYYY-MM-DD`` no fuso de João Pessoa.

    O container roda em UTC. Sem fixar o fuso, todo trabalho depois das 21h
    cairia no dia seguinte e a semana ficaria torta.

    Args:
        momento: instante a converter. Se ``None``, usa o agora.

    Returns:
        Data local em ``YYYY-MM-DD``.
    """
    referencia = momento.astimezone(FUSO) if momento is not None else datetime.now(tz=FUSO)
    return referencia.strftime("%Y-%m-%d")
