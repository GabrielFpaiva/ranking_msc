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

import threading
from dataclasses import dataclass
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


@dataclass(frozen=True)
class ChaveUso:
    """Chave de agregação do tempo de uso."""

    usuario: str
    dia: str
    rota: str


@dataclass
class TempoUso:
    """Segundos acumulados de aba aberta e de uso ativo para uma chave."""

    aberto_s: int = 0
    ativo_s: int = 0


class Acumulador:
    """Buffer em memória de tempo de uso, agregado por ``ChaveUso``.

    Existe para evitar uma escrita em disco por heartbeat: com 10 pessoas
    batendo a cada 60 s seriam 4.800 linhas por dia. Acumulando e drenando a
    cada 5 minutos, caem para cerca de 500.
    """

    def __init__(self) -> None:
        self._dados: dict[ChaveUso, TempoUso] = {}
        self._lock = threading.Lock()

    def registrar(
        self,
        usuario: str,
        rota: str,
        aberto_s: int,
        ativo_s: int,
        dia: str | None = None,
    ) -> None:
        """Soma um heartbeat ao balde correspondente.

        Args:
            usuario: username vindo do ``sub`` do JWT.
            rota: rota do SPA, já validada contra ``ROTAS_VALIDAS``.
            aberto_s: segundos com a aba visível desde o último heartbeat.
            ativo_s: segundos com interação desde o último heartbeat.
            dia: dia local; se ``None``, calculado na hora.
        """
        chave = ChaveUso(usuario=usuario, dia=dia or dia_local(), rota=rota)
        with self._lock:
            tempo = self._dados.setdefault(chave, TempoUso())
            tempo.aberto_s += aberto_s
            tempo.ativo_s += ativo_s

    def drenar(self) -> dict[ChaveUso, TempoUso]:
        """Devolve o conteúdo acumulado e esvazia o buffer."""
        with self._lock:
            dados = self._dados
            self._dados = {}
            return dados

    def espiar(self) -> dict[ChaveUso, TempoUso]:
        """Cópia do buffer atual, sem esvaziá-lo.

        Usado pelo endpoint ``/api/uso/hoje``: sem isto, o número da sidebar
        ficaria até 5 minutos atrasado em relação ao relógio do browser.
        """
        with self._lock:
            return {
                chave: TempoUso(tempo.aberto_s, tempo.ativo_s)
                for chave, tempo in self._dados.items()
            }


ACUMULADOR = Acumulador()
