"""
Testes de app/api/uso_store.py — persistência e agregação do tempo de uso.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from ranking_msc.config.settings import Settings


class TestConfiguracao:
    def test_paths_tem_uso_dir_com_default(self) -> None:
        """PathsSettings expõe uso_dir com default sob ./data."""
        assert Settings().paths.uso_dir == "./data/uso"

    def test_ensure_dirs_cria_uso_dir(self, tmp_path: Path) -> None:
        """ensure_dirs() cria o diretório de tempo de uso."""
        from dataclasses import replace

        paths = replace(Settings().paths, uso_dir=str(tmp_path / "uso"))
        paths.ensure_dirs()
        assert (tmp_path / "uso").is_dir()


class TestDiaLocal:
    def test_meia_noite_utc_ainda_e_o_dia_anterior_em_joao_pessoa(self) -> None:
        """00:30 UTC de 10/09 é 21:30 de 09/09 em Recife — o dia não pode virar."""
        from app.api.uso_store import dia_local

        momento = datetime(2026, 9, 10, 0, 30, tzinfo=UTC)
        assert dia_local(momento) == "2026-09-09"

    def test_meio_dia_utc_e_o_mesmo_dia(self) -> None:
        """12:00 UTC é 09:00 local — mesmo dia."""
        from app.api.uso_store import dia_local

        momento = datetime(2026, 9, 10, 12, 0, tzinfo=UTC)
        assert dia_local(momento) == "2026-09-10"


class TestAcumulador:
    def test_registros_da_mesma_chave_somam(self) -> None:
        """Dois heartbeats da mesma (usuario, dia, rota) viram um só balde."""
        from app.api.uso_store import Acumulador

        acc = Acumulador()
        acc.registrar("gabriel", "/pendencias", 60, 45, dia="2026-09-09")
        acc.registrar("gabriel", "/pendencias", 60, 30, dia="2026-09-09")

        dados = acc.drenar()
        assert len(dados) == 1
        tempo = next(iter(dados.values()))
        assert tempo.aberto_s == 120
        assert tempo.ativo_s == 75

    def test_usuarios_diferentes_nao_se_misturam(self) -> None:
        """Chave inclui o usuário — o tempo de um não entra no do outro."""
        from app.api.uso_store import Acumulador

        acc = Acumulador()
        acc.registrar("gabriel", "/caixa", 60, 60, dia="2026-09-09")
        acc.registrar("maria", "/caixa", 60, 60, dia="2026-09-09")

        assert len(acc.drenar()) == 2

    def test_drenar_esvazia_o_buffer(self) -> None:
        """Depois de drenar, o acumulador está vazio — nada é contado duas vezes."""
        from app.api.uso_store import Acumulador

        acc = Acumulador()
        acc.registrar("gabriel", "/caixa", 60, 60, dia="2026-09-09")
        acc.drenar()
        assert acc.drenar() == {}

    def test_espiar_nao_esvazia(self) -> None:
        """espiar() serve o número da sidebar sem consumir o buffer."""
        from app.api.uso_store import Acumulador

        acc = Acumulador()
        acc.registrar("gabriel", "/caixa", 60, 60, dia="2026-09-09")

        assert len(acc.espiar()) == 1
        assert len(acc.espiar()) == 1
        assert len(acc.drenar()) == 1


class TestFlushELeitura:
    def test_flush_grava_uma_linha_por_chave(self, tmp_path: Path) -> None:
        """Cada balde do acumulador vira uma linha no JSONL do mês."""
        from app.api.uso_store import Acumulador, escrever_flush

        acc = Acumulador()
        acc.registrar("gabriel", "/caixa", 300, 200, dia="2026-09-09")
        acc.registrar("gabriel", "/regras", 120, 90, dia="2026-09-09")

        assert escrever_flush(tmp_path, acc.drenar()) == 2
        linhas = (tmp_path / "2026-09.jsonl").read_text(encoding="utf-8").strip().split("\n")
        assert len(linhas) == 2

    def test_flush_vazio_nao_cria_arquivo(self, tmp_path: Path) -> None:
        """Sem uso registrado, não há arquivo — evita lixo de mês sem atividade."""
        from app.api.uso_store import escrever_flush

        assert escrever_flush(tmp_path, {}) == 0
        assert not (tmp_path / "2026-09.jsonl").exists()

    def test_ler_mes_soma_deltas_da_mesma_chave(self, tmp_path: Path) -> None:
        """Dois flushes da mesma chave somam na leitura — este é o contrato do delta."""
        from app.api.uso_store import Acumulador, escrever_flush, ler_mes

        for _ in range(2):
            acc = Acumulador()
            acc.registrar("gabriel", "/caixa", 300, 200, dia="2026-09-09")
            escrever_flush(tmp_path, acc.drenar())

        agregado = ler_mes(tmp_path, "2026-09", "gabriel")
        assert agregado[("2026-09-09", "/caixa")].aberto_s == 600
        assert agregado[("2026-09-09", "/caixa")].ativo_s == 400

    def test_ler_mes_ignora_outros_usuarios(self, tmp_path: Path) -> None:
        """A leitura é sempre de um usuário só."""
        from app.api.uso_store import Acumulador, escrever_flush, ler_mes

        acc = Acumulador()
        acc.registrar("gabriel", "/caixa", 300, 200, dia="2026-09-09")
        acc.registrar("maria", "/caixa", 999, 999, dia="2026-09-09")
        escrever_flush(tmp_path, acc.drenar())

        agregado = ler_mes(tmp_path, "2026-09", "gabriel")
        assert len(agregado) == 1
        assert agregado[("2026-09-09", "/caixa")].aberto_s == 300

    def test_ler_mes_inexistente_retorna_vazio(self, tmp_path: Path) -> None:
        """Mês sem arquivo não é erro — é ausência de uso."""
        from app.api.uso_store import ler_mes

        assert ler_mes(tmp_path, "2020-01", "gabriel") == {}

    def test_ler_mes_prefere_compactado_sobre_bruto(self, tmp_path: Path) -> None:
        """Existindo `.agg.jsonl`, a leitura ignora o `.jsonl` bruto do mesmo mês."""
        from app.api.uso_store import ler_mes

        bruto = {
            "usuario": "gabriel",
            "dia": "2026-09-09",
            "rota": "/caixa",
            "aberto_s": 111,
            "ativo_s": 111,
            "ts": "2026-09-09T10:00:00-03:00",
        }
        compactado = {
            "usuario": "gabriel",
            "dia": "2026-09-09",
            "rota": "/caixa",
            "aberto_s": 222,
            "ativo_s": 222,
        }
        (tmp_path / "2026-09.jsonl").write_text(json.dumps(bruto) + "\n", encoding="utf-8")
        (tmp_path / "2026-09.agg.jsonl").write_text(
            json.dumps(compactado) + "\n", encoding="utf-8"
        )

        agregado = ler_mes(tmp_path, "2026-09", "gabriel")
        assert agregado[("2026-09-09", "/caixa")].aberto_s == 222
        assert agregado[("2026-09-09", "/caixa")].ativo_s == 222

    def test_ler_mes_pula_linha_json_valido_mas_nao_objeto(self, tmp_path: Path) -> None:
        """JSON válido que não é objeto (lista, número, ...) é pulado sem estourar."""
        from app.api.uso_store import Acumulador, escrever_flush, ler_mes

        acc = Acumulador()
        acc.registrar("gabriel", "/caixa", 300, 200, dia="2026-09-09")
        escrever_flush(tmp_path, acc.drenar())

        caminho = tmp_path / "2026-09.jsonl"
        with caminho.open("a", encoding="utf-8") as arquivo:
            arquivo.write(json.dumps([1, 2, 3]) + "\n")
            arquivo.write(json.dumps(42) + "\n")
            arquivo.write(json.dumps("texto") + "\n")
            arquivo.write(json.dumps(None) + "\n")

        agregado = ler_mes(tmp_path, "2026-09", "gabriel")
        assert len(agregado) == 1
        assert agregado[("2026-09-09", "/caixa")].aberto_s == 300

    def test_ler_mes_pula_linha_com_bytes_invalidos_em_utf8(self, tmp_path: Path) -> None:
        """Bytes inválidos em UTF-8 no meio do arquivo não derrubam as demais linhas."""
        from app.api.uso_store import Acumulador, escrever_flush, ler_mes

        acc = Acumulador()
        acc.registrar("gabriel", "/caixa", 300, 200, dia="2026-09-09")
        acc.registrar("gabriel", "/regras", 100, 50, dia="2026-09-09")
        escrever_flush(tmp_path, acc.drenar())

        caminho = tmp_path / "2026-09.jsonl"
        conteudo = caminho.read_bytes()
        linhas = conteudo.splitlines()
        linhas.insert(1, b'{"usuario": "gabriel", \xff\xfe "dia": "2026-09-09"}')
        caminho.write_bytes(b"\n".join(linhas) + b"\n")

        agregado = ler_mes(tmp_path, "2026-09", "gabriel")
        assert len(agregado) == 2
        assert agregado[("2026-09-09", "/caixa")].aberto_s == 300
        assert agregado[("2026-09-09", "/regras")].aberto_s == 100
