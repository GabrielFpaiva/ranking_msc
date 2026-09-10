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

import calendar
import json
import logging
import threading
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
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
#
# Fonte canônica: `app/api/schemas.py` importa esta constante para o
# `le=` de `HeartbeatIn.aberto_s`/`ativo_s` — é ela, e não um literal
# duplicado no schema, que a API de fato aplica. O browser espelha o mesmo
# número em `LIMITE_SERVIDOR_S` (`web/src/store/relogioUso.ts`); os dois
# precisam mudar juntos.
MAX_SEGUNDOS_POR_HEARTBEAT = 120


def dia_local(momento: datetime | None = None) -> str:
    """Retorna o dia no formato ``YYYY-MM-DD`` no fuso de João Pessoa.

    O container roda em UTC. Sem fixar o fuso, todo trabalho depois das 21h
    cairia no dia seguinte e a semana ficaria torta.

    Args:
        momento: instante a converter. Se ``None``, usa o agora. Quando
            informado, **precisa ser timezone-aware** — um ``datetime`` naive
            é interpretado por ``astimezone()`` como estando no fuso local do
            sistema operacional, não em UTC, e o resultado sai errado em
            silêncio num host configurado num fuso diferente. Nenhum call
            site atual passa ``momento``; todos usam o default e caem no
            ramo ``datetime.now(tz=FUSO)``.

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


@dataclass
class TotalComRotas:
    """Total de um período (aqui, um mês) mais o detalhamento por rota.

    Usada só por ``agregado_do_ano``: os campos ``aberto_s``/``ativo_s`` têm o
    mesmo nome e sentido de ``TempoUso`` de propósito — o restante do módulo
    (e os testes existentes de ``agregado_do_ano``) trata o retorno como se
    fosse um ``TempoUso`` comum, sem precisar saber desta classe. ``por_rota``
    é o campo novo: segundos de aba aberta naquele mês, por rota — sustenta o
    gráfico anual empilhado por tela (ver F6-01).
    """

    aberto_s: int = 0
    ativo_s: int = 0
    por_rota: dict[str, int] = field(default_factory=dict)


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
            dia: dia local; se ``None``, calculado na hora. Existe para testes
                e para chamadas internas. **Nenhuma rota HTTP pode passar
                aqui um valor vindo do cliente ou do corpo da requisição** —
                deixe sempre o default, para que ``dia_local()`` seja avaliado
                no servidor. Um ``dia`` de um mês já compactado grava o delta
                num ``.jsonl`` novo ao lado do ``.agg.jsonl`` daquele mês;
                ``_caminho_mes`` nunca lê esse arquivo (o compactado tem
                precedência), e a varredura de órfãos da próxima compactação
                o apaga como se fosse lixo de crash — sem erro, sem log
                distinguível, dado perdido em silêncio.
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


def _parse_linhas_uso(caminho: Path) -> Iterator[tuple[ChaveUso, TempoUso]]:
    """Itera registros válidos de um JSONL de tempo de uso, linha a linha.

    Não toma lock — quem chama já deve estar de posse do ``_LOCK_ARQUIVO``
    quando isso importa. Cuida só do parsing e do log de linha inválida.

    Compartilhado por ``ler_mes`` e ``compactar_meses_pendentes`` para que o
    endurecimento contra linha malformada exista num só lugar: as duas
    funções já duplicaram esse trecho uma vez, e foi assim que passou um
    ``aberto_s`` não numérico — extraído dentro do ``try``, mas somado fora
    dele, estourando ``TypeError`` sem handler nos dois lugares.

    Lê em binário e decodifica linha a linha, dentro do mesmo try do parse:
    se abríssemos em modo texto, o ``TextIOWrapper`` decodificaria o arquivo
    inteiro dentro do ``for``, e um byte inválido no meio estouraria
    ``UnicodeDecodeError`` fora de qualquer try, derrubando o mês inteiro. Pela
    mesma razão, ``aberto_s``/``ativo_s`` são convertidos com ``int(...)``
    dentro do try — se não fossem, uma soma mais tarde com um valor não
    numérico estouraria fora de qualquer handler.

    Args:
        caminho: arquivo JSONL a ler (bruto ou compactado).

    Yields:
        Par ``(ChaveUso, TempoUso)`` já validado.
    """
    with caminho.open("rb") as arquivo:
        for linha_bytes in arquivo:
            if not linha_bytes.strip():
                continue
            try:
                registro = json.loads(linha_bytes.decode("utf-8"))
                chave = ChaveUso(
                    usuario=registro["usuario"],
                    dia=registro["dia"],
                    rota=registro["rota"],
                )
                tempo = TempoUso(
                    aberto_s=int(registro["aberto_s"]),
                    ativo_s=int(registro["ativo_s"]),
                )
            except (
                UnicodeDecodeError,
                json.JSONDecodeError,
                KeyError,
                TypeError,
                ValueError,
            ) as erro:
                logger.warning(
                    "Linha inválida em %s — %s. Trecho: %r. Ignorando linha.",
                    caminho,
                    erro,
                    linha_bytes[:200],
                    extra={"modulo": "uso_store"},
                )
                continue
            yield chave, tempo


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
    with _LOCK_ARQUIVO:
        for chave, tempo_lido in _parse_linhas_uso(caminho):
            if chave.usuario != usuario:
                continue
            tempo = agregado.setdefault((chave.dia, chave.rota), TempoUso())
            tempo.aberto_s += tempo_lido.aberto_s
            tempo.ativo_s += tempo_lido.ativo_s
    return agregado


def compactar_meses_pendentes(uso_dir: Path, ano_mes_corrente: str) -> list[str]:
    """Compacta todo mês já fechado que ainda esteja em formato bruto.

    Um mês fechado nunca mais muda, então seus deltas podem colapsar em uma
    linha por ``(usuario, dia, rota)``. Isso derruba a leitura de centenas de
    milissegundos para dezenas e o disco de dezenas de MB por ano para poucos.

    A varredura cobre **todos** os meses pendentes, não só o anterior: se o
    servidor ficar fora do ar por um mês inteiro, o mês pulado não pode ficar
    bruto para sempre.

    A gravação é atômica — escreve ``.tmp``, renomeia, e só então remove o
    bruto. Uma interrupção no meio não deixa o mês sem dado.

    Args:
        uso_dir: diretório de tempo de uso.
        ano_mes_corrente: mês em curso, em ``YYYY-MM``; não é compactado.

    Returns:
        Lista ordenada dos meses compactados nesta chamada.
    """
    if not uso_dir.is_dir():
        return []

    compactados: list[str] = []
    # O glob roda fora do lock, e cada mês só toma `_LOCK_ARQUIVO` para o
    # próprio corpo (ler, agregar, escrever `.tmp`, `replace`, `unlink`) — não
    # para a varredura inteira. Um backlog de vários meses fora do ar não pode
    # travar as leituras HTTP (`ler_mes`) por segundos justamente quando o app
    # volta e as pessoas começam a usar.
    #
    # Isso abre uma corrida estreita entre o glob (fora do lock) e o
    # `bruto.unlink()` de um mês (dentro dele): um segundo chamador
    # concorrente poderia ter, na sua própria lista, um bruto que este já
    # removeu. Hoje isso é inalcançável — o único chamador é o loop de flush
    # em background, que roda serialmente. Se um dia surgir um segundo
    # chamador (por exemplo uma ação administrativa de "compactar agora"),
    # esta função vai precisar reconferir `bruto.exists()` dentro do lock
    # antes de processar, ou os dois chamadores vão precisar ser serializados
    # por fora.
    for bruto in sorted(uso_dir.glob("[0-9][0-9][0-9][0-9]-[0-9][0-9].jsonl")):
        ano_mes = bruto.stem
        if ano_mes >= ano_mes_corrente:
            continue

        destino = uso_dir / f"{ano_mes}.agg.jsonl"

        with _LOCK_ARQUIVO:
            if destino.exists():
                # Ambos existem: sinal de crash na janela entre o `replace()`
                # abaixo e o `bruto.unlink()` seguinte, de uma execução
                # anterior. O `.agg.jsonl` só existe depois de um replace
                # atômico do `.tmp` — logo, se está aqui, já está completo e é
                # a fonte da verdade; recompactar do bruto geraria o mesmo
                # conteúdo à toa. O certo é só descartar o bruto órfão (dado
                # pessoal sem valor de auditoria) e seguir, sem contar o mês
                # como compactado nesta chamada — ele não foi, só teve lixo
                # removido.
                bruto.unlink()
                continue

            agregado: dict[ChaveUso, TempoUso] = {}
            for chave, tempo_lido in _parse_linhas_uso(bruto):
                tempo = agregado.setdefault(chave, TempoUso())
                tempo.aberto_s += tempo_lido.aberto_s
                tempo.ativo_s += tempo_lido.ativo_s

            temporario = destino.with_suffix(".tmp")
            with temporario.open("w", encoding="utf-8") as arquivo:
                # `ChaveUso` é `frozen=True` mas não `order=True` — não tem
                # `__lt__` — então `sorted()` direto sobre as chaves levanta
                # `TypeError`. A ordenação existe só para o `.agg.jsonl` sair
                # determinístico, então um `key=` explícito basta; não vale
                # ligar `order=True` na classe inteira por causa de um detalhe
                # de escrita de arquivo.
                for chave, tempo in sorted(
                    agregado.items(), key=lambda item: (item[0].usuario, item[0].dia, item[0].rota)
                ):
                    arquivo.write(
                        json.dumps(
                            {
                                "usuario": chave.usuario,
                                "dia": chave.dia,
                                "rota": chave.rota,
                                "aberto_s": tempo.aberto_s,
                                "ativo_s": tempo.ativo_s,
                            },
                            ensure_ascii=False,
                        )
                        + "\n"
                    )
            temporario.replace(destino)
            bruto.unlink()
            compactados.append(ano_mes)

    return compactados


# Cache de meses fechados, keyed por (uso_dir, ano_mes, usuario). Mesmo
# padrão do load_pcasp() em io/ref_loader.py: cache simples em variável de
# módulo, sem framework. Só entram meses que não recebem mais escrita.
#
# O diretório entra na chave porque em produção existe um único `uso_dir`,
# mas nada nesta função impede outro — dois `uso_dir` diferentes com o mesmo
# mês e usuário compartilhariam entrada sem isso. Já causou um problema real
# de isolamento entre testes (cada um com seu próprio `tmp_path`, mesmo
# `ano_mes`/`usuario`) que precisou ser contornado com `limpar_cache()`
# defensivo espalhado pelos testes; incluir o diretório na chave resolve na
# raiz, por construção.
#
# Deliberadamente sem lock próprio. `__setitem__` e `clear()` sobre um dict
# são atômicos sob o GIL, e a corrida check-then-act entre "chave not in
# _CACHE_MES" e a escrita em agregado_do_mes é inofensiva: na pior hipótese
# duas threads leem o mesmo mês fechado ao mesmo tempo e uma escrita
# sobrescreve a outra — `ler_mes` sobre um mês fechado é idempotente, então
# as duas leituras dão o mesmo resultado, nunca um dado errado. Dar um lock
# próprio a este cache criaria aninhamento com o `_LOCK_ARQUIVO` que
# `ler_mes` adquire — que não é reentrante — e travaria o processo.
_CACHE_MES: dict[tuple[str, str, str], dict[tuple[str, str], TempoUso]] = {}


def agregado_do_mes(
    uso_dir: Path,
    ano_mes: str,
    usuario: str,
    ano_mes_corrente: str | None = None,
) -> dict[tuple[str, str], TempoUso]:
    """Agregado de um mês para um usuário, com cache para meses fechados.

    Um mês fechado nunca mais muda — foi compactado e passou a ser imutável —
    então seu agregado pode ser calculado uma vez e reaproveitado. O mês em
    curso é sempre relido, porque ainda recebe escrita.

    O mapa devolvido é compartilhado: para um mês fechado, é o mesmo objeto
    guardado em ``_CACHE_MES``, não uma cópia. Quem chama deve tratá-lo como
    somente leitura — mutar o mapa ou um ``TempoUso`` dele corrompe o cache
    para toda chamada futura, silenciosamente, e só um restart do servidor
    recupera.

    Args:
        uso_dir: diretório de tempo de uso.
        ano_mes: mês pedido, em ``YYYY-MM``.
        usuario: username do JWT.
        ano_mes_corrente: mês em curso; se ``None``, calculado do dia local.

    Returns:
        Mapa de ``(dia, rota)`` para ``TempoUso``.
    """
    corrente = ano_mes_corrente or dia_local()[:7]
    if ano_mes >= corrente:
        return ler_mes(uso_dir, ano_mes, usuario)

    chave = (str(uso_dir), ano_mes, usuario)
    if chave not in _CACHE_MES:
        _CACHE_MES[chave] = ler_mes(uso_dir, ano_mes, usuario)
    return _CACHE_MES[chave]


def limpar_cache() -> None:
    """Esvazia o cache de meses fechados.

    Deve ser chamado depois de toda compactação que produza mudança — isto é,
    sempre que ``compactar_meses_pendentes`` devolver lista não vazia, já que
    o arquivo do mês muda de forma (bruto → agregado). Essa fiação ainda não
    existe no código: é da Task 12. Quem chamar ``compactar_meses_pendentes``
    é responsável por chamar esta função quando a lista vier não vazia. Se
    surgir um segundo call site — por exemplo uma ação administrativa de
    "compactar agora" — e ele esquecer disso, agregados velhos passam a ser
    servidos do cache em silêncio, sem erro.

    Também usada pelos testes para isolar casos entre si.
    """
    _CACHE_MES.clear()


def intervalo(escala: str, ref: str) -> tuple[str, str]:
    """Primeiro e último dia do período que contém ``ref``.

    Args:
        escala: ``"dia"``, ``"semana"`` ou ``"mes"``.
        ref: data de referência em ``YYYY-MM-DD``.

    Returns:
        Tupla ``(inicio, fim)`` sempre em ``YYYY-MM-DD`` canônico, ambos
        inclusivos — mesmo que ``ref`` chegue numa variante aceita por
        ``date.fromisoformat`` (ex.: ``"20260909"`` ou uma data de semana ISO).
        Essa garantia sustenta o filtro ``inicio <= dia <= fim`` da rota de
        histórico, que compara strings direto contra o ``dia`` gravado no
        JSONL; um retorno não canônico faria essa comparação de string falhar
        silenciosamente, devolvendo "sem uso" para um período com dados.

    Raises:
        ValueError: se a escala for desconhecida.
    """
    referencia = date.fromisoformat(ref)

    if escala == "dia":
        return referencia.isoformat(), referencia.isoformat()
    if escala == "semana":
        segunda = referencia - timedelta(days=referencia.weekday())
        return segunda.isoformat(), (segunda + timedelta(days=6)).isoformat()
    if escala == "mes":
        ultimo = calendar.monthrange(referencia.year, referencia.month)[1]
        return (
            referencia.replace(day=1).isoformat(),
            referencia.replace(day=ultimo).isoformat(),
        )

    raise ValueError(f"Escala desconhecida: {escala!r}. Use 'dia', 'semana' ou 'mes'.")


def sobrepor_buffer(
    agregado: dict[tuple[str, str], TempoUso],
    buffer: dict[ChaveUso, TempoUso],
    usuario: str,
    inicio: str,
    fim: str,
) -> dict[tuple[str, str], TempoUso]:
    """Soma ao agregado a parcela do buffer em memória de ``usuario`` dentro de ``[inicio, fim]``.

    Existe para que ``/api/uso/historico`` e ``/api/uso/anual`` enxerguem o
    mesmo número que ``/api/uso/hoje`` já enxerga para o dia corrente: sem
    isto, o buffer (até 5 minutos de heartbeats ainda não gravados em disco)
    aparece na sidebar mas não na tela — dois números da mesma página se
    contradizendo, e o tempo gasto na própria tela ``/uso`` nunca aparece
    enquanto ela está aberta.

    Função pura: não lê nem escreve ``ACUMULADOR`` — recebe o resultado de
    ``ACUMULADOR.espiar()`` já pronto em ``buffer``. Quem chama decide se e
    quando sobrepor.

    **Sempre devolve um dict novo, com ``TempoUso`` novos** — nunca o
    ``agregado`` recebido, nem os objetos dentro dele, são mutados. Isso
    importa porque ``agregado`` pode ser (ou derivar rasamente de, como
    ``agregado_do_periodo`` monta) o dict cacheado por referência em
    ``_CACHE_MES`` para um mês fechado; mutar um ``TempoUso`` ali corromperia
    o cache para toda chamada futura, silenciosamente, até o próximo restart
    do servidor — ver o aviso na docstring de ``agregado_do_mes``.

    Só entram entradas do buffer cujo ``usuario`` bate e cujo ``dia`` cai
    dentro de ``[inicio, fim]`` (inclusive) — o buffer normalmente só contém
    o dia corrente, mas nada aqui assume isso.

    Args:
        agregado: mapa ``(dia, rota)`` → ``TempoUso``, já lido do disco.
        buffer: conteúdo do ``Acumulador`` (``ACUMULADOR.espiar()``).
        usuario: username do JWT — filtra o buffer, que pode conter baldes de
            outros usuários.
        inicio: primeiro dia do período, ``YYYY-MM-DD``, inclusive.
        fim: último dia do período, ``YYYY-MM-DD``, inclusive.

    Returns:
        Novo mapa ``(dia, rota)`` → ``TempoUso`` — o conteúdo de ``agregado``
        mais a contribuição filtrada do buffer, em chaves existentes ou
        novas.
    """
    resultado: dict[tuple[str, str], TempoUso] = {
        chave: TempoUso(tempo.aberto_s, tempo.ativo_s) for chave, tempo in agregado.items()
    }
    for chave_buffer, tempo_buffer in buffer.items():
        if chave_buffer.usuario != usuario:
            continue
        if not (inicio <= chave_buffer.dia <= fim):
            continue
        chave = (chave_buffer.dia, chave_buffer.rota)
        tempo = resultado.setdefault(chave, TempoUso())
        tempo.aberto_s += tempo_buffer.aberto_s
        tempo.ativo_s += tempo_buffer.ativo_s
    return resultado


def agregado_do_periodo(
    uso_dir: Path,
    escala: str,
    ref: str,
    usuario: str,
    buffer: dict[ChaveUso, TempoUso] | None = None,
) -> tuple[dict[tuple[str, str], TempoUso], str, str]:
    """Agregado combinado do período de ``escala`` que contém ``ref``, mais o intervalo.

    Carrega o mês de ``ref`` e, quando o período cruza a virada do mês — uma
    semana que começa no mês anterior ou termina no seguinte —, também carrega
    e funde o mês do lado que diferir. Os dois lados são checados de forma
    independente porque nunca ocorrem ao mesmo tempo (uma janela de até 31
    dias por ``escala`` não alcança um terceiro mês), mas checar só um deles
    já escondeu um bug: uma versão anterior olhava só o mês de ``fim``, e uma
    semana começando no mês anterior a ``ref`` perdia dado em silêncio.

    Chaves são ``(dia, rota)`` e ``dia`` embute o mês (``YYYY-MM-DD``): dois
    meses diferentes nunca produzem a mesma chave, então o merge nunca
    sobrescreve dado por colisão. O dict devolvido é sempre um objeto novo —
    ``agregado_do_mes`` pode devolver, para um mês fechado, o mesmo dict
    guardado no cache de módulo, e este merge nunca o repassa direto; inserir
    ou remover chave no resultado não afeta o cache.

    Isso **não** estende à mutação de atributo de um ``TempoUso`` dentro do
    dict — a cópia é rasa, então os valores de um mês fechado ainda são os
    mesmos objetos guardados em ``_CACHE_MES``. Vale a mesma ressalva de
    ``agregado_do_mes``: trate o resultado como somente leitura. Quando
    ``buffer`` é passado, ``sobrepor_buffer`` cuida disso — devolve um dict
    com ``TempoUso`` novos, então o retorno desta função deixa de compartilhar
    qualquer objeto com o cache.

    Args:
        uso_dir: diretório de tempo de uso.
        escala: ``"dia"``, ``"semana"`` ou ``"mes"``.
        ref: data de referência, em qualquer variante aceita por
            ``date.fromisoformat`` — não precisa vir pré-normalizada.
        usuario: username do JWT.
        buffer: conteúdo do ``Acumulador`` (``ACUMULADOR.espiar()``) a
            sobrepor ao agregado, restrito a ``usuario`` e ao intervalo
            ``[inicio, fim]`` resultante — ver ``sobrepor_buffer``. Se
            ``None`` (default) ou vazio, nenhuma sobreposição ocorre; é o que
            os testes que querem só o disco usam.

    Returns:
        Tupla ``(agregado, inicio, fim)`` — ``agregado`` é o mapa combinado de
        ``(dia, rota)`` para ``TempoUso``; ``inicio``/``fim`` são o intervalo
        canônico devolvido por ``intervalo()``.

    Raises:
        ValueError: se ``ref`` não for parseável ou ``escala`` for
            desconhecida — ver ``intervalo()``.
    """
    ano_mes = date.fromisoformat(ref).isoformat()[:7]
    inicio, fim = intervalo(escala, ref)

    agregado = dict(agregado_do_mes(uso_dir, ano_mes, usuario))

    ano_mes_inicio = inicio[:7]
    if ano_mes_inicio != ano_mes:
        agregado.update(agregado_do_mes(uso_dir, ano_mes_inicio, usuario))
    ano_mes_fim = fim[:7]
    if ano_mes_fim != ano_mes:
        agregado.update(agregado_do_mes(uso_dir, ano_mes_fim, usuario))

    if buffer:
        agregado = sobrepor_buffer(agregado, buffer, usuario, inicio, fim)

    return agregado, inicio, fim


def agregado_do_ano(
    uso_dir: Path,
    ano: int,
    usuario: str,
    buffer: dict[ChaveUso, TempoUso] | None = None,
) -> list[tuple[str, TotalComRotas]]:
    """Totais mensais de ``ano`` para um usuário — doze meses, sempre completos.

    Sustenta ``GET /api/uso/anual``: doze chamadas a ``/api/uso/historico``
    seriam doze idas ao servidor para desenhar um gráfico só; esta função
    monta o ano inteiro numa única passada, reaproveitando ``agregado_do_mes``
    para que meses fechados venham do cache.

    Cada mês vira um ``TotalComRotas`` **novo** — nunca o dicionário devolvido
    por ``agregado_do_mes`` para um mês fechado, que é compartilhado com
    ``_CACHE_MES`` por referência. Somar direto num objeto do cache
    corromperia o total do mês para toda chamada futura, silenciosamente.
    Quando ``buffer`` sobrepõe um mês (via ``sobrepor_buffer``, que também
    devolve estruturas novas), a soma seguinte lê do resultado dessa
    sobreposição — nunca do dict do cache diretamente —, então o mesmo
    cuidado se aplica lá.

    Args:
        uso_dir: diretório de tempo de uso.
        ano: ano consultado (``YYYY``).
        usuario: username do JWT.
        buffer: conteúdo do ``Acumulador`` (``ACUMULADOR.espiar()``) a
            sobrepor a cada mês, restrito a ``usuario`` e aos limites daquele
            mês (primeiro ao último dia). Se ``None`` (default) ou vazio,
            nenhuma sobreposição ocorre — meses fechados nunca têm buffer
            relevante de qualquer forma, só o mês corrente pode.

    Returns:
        Lista de doze pares ``(YYYY-MM, TotalComRotas)``, de janeiro a
        dezembro, nesta ordem. Meses sem registro vêm zerados, com
        ``por_rota`` vazio.
    """
    resultado: list[tuple[str, TotalComRotas]] = []
    for mes in range(1, 13):
        ano_mes = f"{ano:04d}-{mes:02d}"
        agregado_mes = agregado_do_mes(uso_dir, ano_mes, usuario)
        if buffer:
            ultimo_dia_num = calendar.monthrange(ano, mes)[1]
            agregado_mes = sobrepor_buffer(
                agregado_mes,
                buffer,
                usuario,
                f"{ano_mes}-01",
                f"{ano_mes}-{ultimo_dia_num:02d}",
            )
        total = TotalComRotas()
        for (_dia, rota), tempo in agregado_mes.items():
            total.aberto_s += tempo.aberto_s
            total.ativo_s += tempo.ativo_s
            total.por_rota[rota] = total.por_rota.get(rota, 0) + tempo.aberto_s
        resultado.append((ano_mes, total))
    return resultado
