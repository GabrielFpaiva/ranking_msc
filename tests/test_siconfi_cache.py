"""
tests/test_siconfi_cache.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Testes do cache em disco do extrato do Siconfi.

O cache guarda o carimbo de quando os dados foram buscados. Isso não é
decorativo: no modo degradado a tela mostra essa data, para nunca apresentar
dado velho como se fosse atual.
"""

from __future__ import annotations

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
    """Escrita com falha não corrompe cache existente.

    Simula falha durante gravação (via monkeypatch em Path.write_text)
    e verifica que:
    1. Arquivo final mantém conteúdo original (byte a byte)
    2. Arquivo .tmp não sobrou

    Propriedade testada: atomicidade via write-tmp-then-replace.
    """
    # Grave cache inicial válido
    gravar_cache(tmp_path, 2507507, 2025, ITENS, agora=AGORA)

    arquivo = tmp_path / "entregas_2507507_2025.json"
    assert arquivo.exists()
    conteudo_original = arquivo.read_text(encoding="utf-8")

    # Segunda gravação vai falhar no meio
    # Monkeypatch Path.write_text para levantar OSError quando escrever no .tmp
    original_write_text = Path.write_text

    def write_text_que_falha(
        self: Path, data: str, encoding: str | None = None
    ) -> None:
        # Falha apenas ao escrever no arquivo .tmp (não no primeiro uso)
        if str(self).endswith(".json.tmp"):
            raise OSError("Simulated disk write failure")
        original_write_text(self, data, encoding)

    monkeypatch.setattr(Path, "write_text", write_text_que_falha)

    # Tente gravar novamente com dados diferentes — deve falhar
    with pytest.raises(OSError):
        gravar_cache(tmp_path, 2507507, 2025, [{"novo": "item"}], agora=AGORA)

    # Verificar propriedades atômicas:
    # 1. Arquivo final ainda tem conteúdo original (não foi sobrescrito)
    assert arquivo.read_text(encoding="utf-8") == conteudo_original

    # 2. Arquivo .tmp não sobrou
    arquivo_tmp = tmp_path / "entregas_2507507_2025.json.tmp"
    assert not arquivo_tmp.exists()
