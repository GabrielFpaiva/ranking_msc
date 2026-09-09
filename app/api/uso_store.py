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

import json
import logging
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

logger = logging.getLogger("ranking_msc")

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

# Serializa apenas threads dentro de um único processo — protege tanto
# escritor contra escritor (dois flushes concorrentes) quanto leitor contra
# escritor (uma leitura HTTP no meio de um `escrever_flush` não pode ver
# linha partida ao meio). Isso basta porque docker/entrypoint.sh sobe
# `uvicorn app.api.main:app` sem `--workers` — hoje existe exatamente um
# processo. Se um dia alguém adicionar `--workers`, dois processos vão poder
# intercalar `write()`s parciais no mesmo arquivo mensal (append não é
# atômico entre processos, especialmente no Windows), e este lock deixa de
# proteger — vai precisar de um lock de arquivo de verdade.
_LOCK_ARQUIVO = threading.Lock()


def _caminho_mes(uso_dir: Path, ano_mes: str) -> Path | None:
    """Arquivo de um mês — o compactado tem precedência sobre o bruto.

    Returns:
        Caminho existente, ou ``None`` se o mês não tem registro.
    """
    compactado = uso_dir / f"{ano_mes}.agg.jsonl"
    if compactado.exists():
        return compactado
    bruto = uso_dir / f"{ano_mes}.jsonl"
    return bruto if bruto.exists() else None


def escrever_flush(uso_dir: Path, dados: dict[ChaveUso, TempoUso]) -> int:
    """Anexa os deltas acumulados ao JSONL do mês correspondente.

    Args:
        uso_dir: diretório de tempo de uso (``settings.paths.uso_dir``).
        dados: saída de ``Acumulador.drenar()``.

    Returns:
        Quantidade de linhas escritas.
    """
    if not dados:
        return 0

    uso_dir.mkdir(parents=True, exist_ok=True)
    carimbo = datetime.now(tz=FUSO).isoformat(timespec="seconds")

    por_mes: dict[str, list[str]] = {}
    for chave, tempo in dados.items():
        linha = json.dumps(
            {
                "usuario": chave.usuario,
                "dia": chave.dia,
                "rota": chave.rota,
                "aberto_s": tempo.aberto_s,
                "ativo_s": tempo.ativo_s,
                "ts": carimbo,
            },
            ensure_ascii=False,
        )
        por_mes.setdefault(chave.dia[:7], []).append(linha)

    total = 0
    with _LOCK_ARQUIVO:
        for ano_mes, linhas in por_mes.items():
            caminho = uso_dir / f"{ano_mes}.jsonl"
            with caminho.open("a", encoding="utf-8") as arquivo:
                arquivo.write("\n".join(linhas) + "\n")
            total += len(linhas)
    return total


def ler_mes(uso_dir: Path, ano_mes: str, usuario: str) -> dict[tuple[str, str], TempoUso]:
    """Soma os deltas de um mês para um usuário, agrupados por ``(dia, rota)``.

    Args:
        uso_dir: diretório de tempo de uso.
        ano_mes: mês em ``YYYY-MM``.
        usuario: username do JWT.

    Returns:
        Mapa de ``(dia, rota)`` para ``TempoUso``. Vazio se o mês não existe.
    """
    caminho = _caminho_mes(uso_dir, ano_mes)
    if caminho is None:
        return {}

    agregado: dict[tuple[str, str], TempoUso] = {}
    # Lê em binário e decodifica linha a linha, dentro do mesmo try do parse:
    # se abríssemos em modo texto, o `TextIOWrapper` decodificaria o arquivo
    # inteiro dentro do `for`, e um byte inválido no meio estouraria
    # `UnicodeDecodeError` fora de qualquer try, derrubando o mês inteiro.
    with _LOCK_ARQUIVO, caminho.open("rb") as arquivo:
        for linha_bytes in arquivo:
            if not linha_bytes.strip():
                continue
            try:
                registro = json.loads(linha_bytes.decode("utf-8"))
                if registro["usuario"] != usuario:
                    continue
                chave = (registro["dia"], registro["rota"])
                aberto_s = registro["aberto_s"]
                ativo_s = registro["ativo_s"]
            except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError) as erro:
                logger.warning(
                    "Linha inválida em %s — %s. Trecho: %r. Ignorando linha.",
                    caminho,
                    erro,
                    linha_bytes[:200],
                    extra={"modulo": "uso_store"},
                )
                continue
            tempo = agregado.setdefault(chave, TempoUso())
            tempo.aberto_s += aberto_s
            tempo.ativo_s += ativo_s
    return agregado
