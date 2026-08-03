"""
tests/test_siconfi_cache.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Testes do cache em disco do extrato do Siconfi.

O cache guarda o carimbo de quando os dados foram buscados. Isso não é
decorativo: no modo degradado a tela mostra essa data, para nunca apresentar
dado velho como se fosse atual.
"""

from __future__ import annotations

import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from ranking_msc.siconfi.cache import (
    gravar_cache,
    ler_cache,
    ler_cache_ignorando_ttl,
)

AGORA = datetime(2026, 7, 31, 12, 0, tzinfo=UTC)
ITENS: list[dict[str, object]] = [{"cod_ibge": 2507507, "periodo": 1}]


def test_grava_e_le(tmp_path: Path) -> None:
    gravar_cache(tmp_path, 2507507, 2025, ITENS, agora=AGORA)
    entrada = ler_cache(tmp_path, 2507507, 2025, ttl_horas=24, agora=AGORA)

    assert entrada is not None
    assert entrada.itens == ITENS
    assert entrada.buscado_em == AGORA


def test_cache_ausente_devolve_none(tmp_path: Path) -> None:
    assert ler_cache(tmp_path, 2507507, 2025, ttl_horas=24, agora=AGORA) is None


def test_cache_expirado_devolve_none(tmp_path: Path) -> None:
    """Passado o TTL, o cache não serve para o caminho normal."""
    gravar_cache(tmp_path, 2507507, 2025, ITENS, agora=AGORA)
    depois = AGORA + timedelta(hours=25)

    assert ler_cache(tmp_path, 2507507, 2025, ttl_horas=24, agora=depois) is None


def test_cache_expirado_ainda_serve_no_modo_degradado(tmp_path: Path) -> None:
    """Com a API fora, cache velho é melhor que tela vazia — desde que datado.

    Grava cache com data ANTIGA (meses atrás). Verifica que:
    1. Com TTL respeitado (caminho normal), cache é rejeitado por expiração
    2. Sem TTL (modo degradado), cache é aceito mesmo expirado
    """
    data_antiga = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    gravar_cache(tmp_path, 2507507, 2025, ITENS, agora=data_antiga)

    # Caminho normal: com TTL de 24h, cache de janeiro é rejeitado em julho
    assert ler_cache(tmp_path, 2507507, 2025, ttl_horas=24, agora=AGORA) is None

    # Modo degradado: ignora TTL, retorna dados mesmo antigos
    entrada = ler_cache_ignorando_ttl(tmp_path, 2507507, 2025)
    assert entrada is not None
    assert entrada.itens == ITENS
    assert entrada.buscado_em == data_antiga


def test_entes_e_exercicios_nao_se_misturam(tmp_path: Path) -> None:
    gravar_cache(tmp_path, 2507507, 2025, ITENS, agora=AGORA)

    assert ler_cache(tmp_path, 2507507, 2024, ttl_horas=24, agora=AGORA) is None
    assert ler_cache(tmp_path, 1234567, 2025, ttl_horas=24, agora=AGORA) is None


def test_cache_corrompido_devolve_none(tmp_path: Path) -> None:
    """JSON quebrado no disco não pode derrubar a rota."""
    gravar_cache(tmp_path, 2507507, 2025, ITENS, agora=AGORA)
    (tmp_path / "entregas_2507507_2025.json").write_text("{ isto nao e json")

    assert ler_cache(tmp_path, 2507507, 2025, ttl_horas=24, agora=AGORA) is None
    assert ler_cache_ignorando_ttl(tmp_path, 2507507, 2025) is None


def test_cria_diretorio_se_nao_existir(tmp_path: Path) -> None:
    destino = tmp_path / "nao" / "existe"
    gravar_cache(destino, 2507507, 2025, ITENS, agora=AGORA)

    assert ler_cache(destino, 2507507, 2025, ttl_horas=24, agora=AGORA) is not None


def test_gravar_cache_atomico(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Escrita que falha no meio não corrompe o cache existente.

    A falha é injetada em `json.dump`, que é o ponto de escrita real depois
    que o temporário já foi criado em disco — assim o teste exercita também
    a limpeza do temporário no `except`, e não só o caminho feliz.

    Propriedades provadas:
    1. o arquivo final mantém o conteúdo original, byte a byte;
    2. nenhum temporário sobra no diretório.
    """
    gravar_cache(tmp_path, 2507507, 2025, ITENS, agora=AGORA)

    arquivo = tmp_path / "entregas_2507507_2025.json"
    assert arquivo.exists()
    conteudo_original = arquivo.read_text(encoding="utf-8")

    def dump_que_falha(*args: object, **kwargs: object) -> None:
        raise OSError("falha simulada de escrita em disco")

    monkeypatch.setattr("ranking_msc.siconfi.cache.json.dump", dump_que_falha)

    with pytest.raises(OSError):
        gravar_cache(tmp_path, 2507507, 2025, [{"novo": "item"}], agora=AGORA)

    assert arquivo.read_text(encoding="utf-8") == conteudo_original
    assert not list(tmp_path.glob("*.tmp")), "temporario vazou apos a falha"


def test_gravacoes_concorrentes_nao_disputam_o_mesmo_temporario(
    tmp_path: Path,
) -> None:
    """Duas escritas simultâneas para o mesmo (ente, exercício) não colidem.

    Com temporário de nome fixo, a segunda escrita apagava/substituía o
    temporário da primeira antes do `replace`, e o `FileNotFoundError`
    resultante escapava como HTTP 500 em `/api/entregas` — que não tem lock,
    ao contrário do caminho de snapshot. Este teste prende esse cenário.
    """
    barreira = threading.Barrier(2)
    erros: list[BaseException] = []

    def gravar(marcador: str) -> None:
        try:
            barreira.wait(timeout=5)
            for _ in range(25):
                gravar_cache(
                    tmp_path, 2507507, 2025, [{"quem": marcador}], agora=AGORA
                )
        except BaseException as exc:  # noqa: BLE001 - o teste inspeciona
            erros.append(exc)

    fios = [threading.Thread(target=gravar, args=(m,)) for m in ("A", "B")]
    for fio in fios:
        fio.start()
    for fio in fios:
        fio.join(timeout=15)

    assert not erros, f"escrita concorrente levantou exceção: {erros}"

    entrada = ler_cache(tmp_path, 2507507, 2025, ttl_horas=24, agora=AGORA)
    assert entrada is not None, "o cache precisa existir e ser legível ao final"
    assert entrada.itens in ([{"quem": "A"}], [{"quem": "B"}]), (
        "o conteúdo final deve ser de UMA das escritas, nunca mesclado ou parcial"
    )

    sobras = list(tmp_path.glob("*.tmp"))
    assert not sobras, f"temporários vazaram no diretório de cache: {sobras}"
