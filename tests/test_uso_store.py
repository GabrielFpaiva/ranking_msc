"""
Testes de app/api/uso_store.py — persistência e agregação do tempo de uso.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

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

    def test_ler_mes_pula_linha_com_aberto_s_nao_numerico(self, tmp_path: Path) -> None:
        """`aberto_s` não numérico não pode estourar fora do handler de linha ruim."""
        from app.api.uso_store import Acumulador, escrever_flush, ler_mes

        acc = Acumulador()
        acc.registrar("gabriel", "/caixa", 300, 200, dia="2026-09-09")
        escrever_flush(tmp_path, acc.drenar())

        caminho = tmp_path / "2026-09.jsonl"
        with caminho.open("a", encoding="utf-8") as arquivo:
            arquivo.write(
                json.dumps(
                    {
                        "usuario": "gabriel",
                        "dia": "2026-09-09",
                        "rota": "/caixa",
                        "aberto_s": "not-a-number",
                        "ativo_s": 10,
                    }
                )
                + "\n"
            )

        agregado = ler_mes(tmp_path, "2026-09", "gabriel")
        assert agregado[("2026-09-09", "/caixa")].aberto_s == 300


class TestCompactacao:
    def _semear(self, uso_dir: Path, ano_mes: str, dia: str, repeticoes: int) -> None:
        """Escreve N flushes iguais para um mês, simulando dias de uso."""
        from app.api.uso_store import Acumulador, escrever_flush

        for _ in range(repeticoes):
            acc = Acumulador()
            acc.registrar("gabriel", "/caixa", 300, 200, dia=dia)
            escrever_flush(uso_dir, acc.drenar())

    def test_compacta_uma_linha_por_chave_preservando_totais(self, tmp_path: Path) -> None:
        """10 deltas viram 1 linha, e a soma não muda."""
        from app.api.uso_store import compactar_meses_pendentes, ler_mes

        self._semear(tmp_path, "2026-08", "2026-08-14", 10)
        assert compactar_meses_pendentes(tmp_path, "2026-09") == ["2026-08"]

        linhas = (tmp_path / "2026-08.agg.jsonl").read_text(encoding="utf-8").strip().split("\n")
        assert len(linhas) == 1
        agregado = ler_mes(tmp_path, "2026-08", "gabriel")
        assert agregado[("2026-08-14", "/caixa")].aberto_s == 3000

    def test_compactacao_descarta_o_bruto(self, tmp_path: Path) -> None:
        """O arquivo de deltas é removido — é dado pessoal sem valor de auditoria."""
        from app.api.uso_store import compactar_meses_pendentes

        self._semear(tmp_path, "2026-08", "2026-08-14", 3)
        compactar_meses_pendentes(tmp_path, "2026-09")

        assert not (tmp_path / "2026-08.jsonl").exists()
        assert (tmp_path / "2026-08.agg.jsonl").exists()

    def test_nao_compacta_o_mes_corrente(self, tmp_path: Path) -> None:
        """O mês em curso ainda recebe escrita — compactá-lo perderia dado."""
        from app.api.uso_store import compactar_meses_pendentes

        self._semear(tmp_path, "2026-09", "2026-09-09", 3)
        assert compactar_meses_pendentes(tmp_path, "2026-09") == []
        assert (tmp_path / "2026-09.jsonl").exists()

    def test_alcanca_meses_pendentes_antigos(self, tmp_path: Path) -> None:
        """Servidor fora do ar por meses não pode deixar mês bruto para trás."""
        from app.api.uso_store import compactar_meses_pendentes

        self._semear(tmp_path, "2026-06", "2026-06-10", 2)
        self._semear(tmp_path, "2026-07", "2026-07-10", 2)
        self._semear(tmp_path, "2026-08", "2026-08-10", 2)

        assert compactar_meses_pendentes(tmp_path, "2026-09") == ["2026-06", "2026-07", "2026-08"]

    def test_e_idempotente(self, tmp_path: Path) -> None:
        """Rodar duas vezes não recompacta nem duplica."""
        from app.api.uso_store import compactar_meses_pendentes

        self._semear(tmp_path, "2026-08", "2026-08-14", 3)
        compactar_meses_pendentes(tmp_path, "2026-09")
        assert compactar_meses_pendentes(tmp_path, "2026-09") == []

    def test_nao_deixa_tmp_para_tras(self, tmp_path: Path) -> None:
        """A escrita é atômica: nenhum .tmp sobrevive a uma compactação bem-sucedida."""
        from app.api.uso_store import compactar_meses_pendentes

        self._semear(tmp_path, "2026-08", "2026-08-14", 3)
        compactar_meses_pendentes(tmp_path, "2026-09")
        assert list(tmp_path.glob("*.tmp")) == []

    def test_linha_malformada_e_pulada_mas_o_resto_compacta(self, tmp_path: Path) -> None:
        """Uma linha corrompida no bruto não impede a compactação das demais."""
        from app.api.uso_store import compactar_meses_pendentes, ler_mes

        self._semear(tmp_path, "2026-08", "2026-08-14", 3)

        caminho = tmp_path / "2026-08.jsonl"
        with caminho.open("a", encoding="utf-8") as arquivo:
            arquivo.write('{"usuario": "gabriel", "dia": "2026-08-14"}\n')  # falta rota/valores

        assert compactar_meses_pendentes(tmp_path, "2026-09") == ["2026-08"]

        agregado = ler_mes(tmp_path, "2026-08", "gabriel")
        assert agregado[("2026-08-14", "/caixa")].aberto_s == 900

    def test_linha_malformada_nao_bloqueia_a_remocao_do_bruto(self, tmp_path: Path) -> None:
        """Uma linha ruim não pode deixar o mês bruto para trás para sempre."""
        from app.api.uso_store import compactar_meses_pendentes

        self._semear(tmp_path, "2026-08", "2026-08-14", 2)

        caminho = tmp_path / "2026-08.jsonl"
        with caminho.open("a", encoding="utf-8") as arquivo:
            arquivo.write("isto nao e json\n")

        compactar_meses_pendentes(tmp_path, "2026-09")
        assert not (tmp_path / "2026-08.jsonl").exists()
        assert (tmp_path / "2026-08.agg.jsonl").exists()

    def test_remove_bruto_orfao_de_compactacao_interrompida_sem_tocar_no_agregado(
        self, tmp_path: Path
    ) -> None:
        """Crash entre o replace() e o unlink() não deve travar o mês para sempre."""
        from app.api.uso_store import compactar_meses_pendentes

        agregado_bom = json.dumps(
            {
                "usuario": "gabriel",
                "dia": "2026-08-14",
                "rota": "/caixa",
                "aberto_s": 3000,
                "ativo_s": 2000,
            }
        ) + "\n"
        (tmp_path / "2026-08.agg.jsonl").write_text(agregado_bom, encoding="utf-8")
        (tmp_path / "2026-08.jsonl").write_text(
            json.dumps(
                {
                    "usuario": "gabriel",
                    "dia": "2026-08-14",
                    "rota": "/caixa",
                    "aberto_s": 300,
                    "ativo_s": 200,
                    "ts": "2026-08-14T10:00:00-03:00",
                }
            )
            + "\n",
            encoding="utf-8",
        )

        assert compactar_meses_pendentes(tmp_path, "2026-09") == []

        assert not (tmp_path / "2026-08.jsonl").exists()
        assert (tmp_path / "2026-08.agg.jsonl").read_text(encoding="utf-8") == agregado_bom

    def test_compacta_ignorando_linha_com_aberto_s_nao_numerico(self, tmp_path: Path) -> None:
        """`aberto_s` não numérico não pode travar a compactação nem sobreviver a ela."""
        from app.api.uso_store import compactar_meses_pendentes, ler_mes

        self._semear(tmp_path, "2026-08", "2026-08-14", 3)

        caminho = tmp_path / "2026-08.jsonl"
        with caminho.open("a", encoding="utf-8") as arquivo:
            arquivo.write(
                json.dumps(
                    {
                        "usuario": "gabriel",
                        "dia": "2026-08-14",
                        "rota": "/caixa",
                        "aberto_s": "not-a-number",
                        "ativo_s": 10,
                    }
                )
                + "\n"
            )

        assert compactar_meses_pendentes(tmp_path, "2026-09") == ["2026-08"]

        assert not (tmp_path / "2026-08.jsonl").exists()
        agregado = ler_mes(tmp_path, "2026-08", "gabriel")
        assert agregado[("2026-08-14", "/caixa")].aberto_s == 900


class TestCache:
    def test_mes_fechado_e_servido_do_cache(self, tmp_path: Path) -> None:
        """Removido o arquivo, o mês fechado continua respondendo — veio do cache."""
        from app.api.uso_store import Acumulador, agregado_do_mes, escrever_flush, limpar_cache

        limpar_cache()
        acc = Acumulador()
        acc.registrar("gabriel", "/caixa", 300, 200, dia="2026-08-14")
        escrever_flush(tmp_path, acc.drenar())

        primeiro = agregado_do_mes(tmp_path, "2026-08", "gabriel", ano_mes_corrente="2026-09")
        assert primeiro[("2026-08-14", "/caixa")].aberto_s == 300

        (tmp_path / "2026-08.jsonl").unlink()
        segundo = agregado_do_mes(tmp_path, "2026-08", "gabriel", ano_mes_corrente="2026-09")
        assert segundo[("2026-08-14", "/caixa")].aberto_s == 300

    def test_mes_corrente_nunca_e_cacheado(self, tmp_path: Path) -> None:
        """O mês em curso ainda recebe escrita — cachear mostraria número velho."""
        from app.api.uso_store import Acumulador, agregado_do_mes, escrever_flush, limpar_cache

        limpar_cache()
        acc = Acumulador()
        acc.registrar("gabriel", "/caixa", 300, 200, dia="2026-09-09")
        escrever_flush(tmp_path, acc.drenar())
        agregado_do_mes(tmp_path, "2026-09", "gabriel", ano_mes_corrente="2026-09")

        acc = Acumulador()
        acc.registrar("gabriel", "/caixa", 100, 50, dia="2026-09-09")
        escrever_flush(tmp_path, acc.drenar())

        atual = agregado_do_mes(tmp_path, "2026-09", "gabriel", ano_mes_corrente="2026-09")
        assert atual[("2026-09-09", "/caixa")].aberto_s == 400

    def test_cache_nao_mistura_usuarios(self, tmp_path: Path) -> None:
        """A chave do cache inclui o usuário."""
        from app.api.uso_store import Acumulador, agregado_do_mes, escrever_flush, limpar_cache

        limpar_cache()
        acc = Acumulador()
        acc.registrar("gabriel", "/caixa", 300, 200, dia="2026-08-14")
        acc.registrar("maria", "/caixa", 999, 999, dia="2026-08-14")
        escrever_flush(tmp_path, acc.drenar())

        agregado_do_mes(tmp_path, "2026-08", "gabriel", ano_mes_corrente="2026-09")
        de_maria = agregado_do_mes(tmp_path, "2026-08", "maria", ano_mes_corrente="2026-09")
        assert de_maria[("2026-08-14", "/caixa")].aberto_s == 999

    def test_retorno_do_cache_e_a_mesma_referencia_entre_chamadas(self, tmp_path: Path) -> None:
        """`agregado_do_mes` devolve o dict por referência — quem chama não pode mutar."""
        from app.api.uso_store import Acumulador, agregado_do_mes, escrever_flush, limpar_cache

        limpar_cache()
        acc = Acumulador()
        acc.registrar("gabriel", "/caixa", 300, 200, dia="2026-08-14")
        escrever_flush(tmp_path, acc.drenar())

        primeiro = agregado_do_mes(tmp_path, "2026-08", "gabriel", ano_mes_corrente="2026-09")
        segundo = agregado_do_mes(tmp_path, "2026-08", "gabriel", ano_mes_corrente="2026-09")
        assert primeiro is segundo


class TestIntervalo:
    def test_dia_e_o_proprio_dia(self) -> None:
        """Escala 'dia' começa e termina no mesmo dia."""
        from app.api.uso_store import intervalo

        assert intervalo("dia", "2026-09-09") == ("2026-09-09", "2026-09-09")

    def test_semana_vai_de_segunda_a_domingo(self) -> None:
        """2026-09-09 é quarta; a semana é 07 (seg) a 13 (dom)."""
        from app.api.uso_store import intervalo

        assert intervalo("semana", "2026-09-09") == ("2026-09-07", "2026-09-13")

    def test_semana_a_partir_de_um_domingo(self) -> None:
        """Domingo pertence à semana que começou na segunda anterior."""
        from app.api.uso_store import intervalo

        assert intervalo("semana", "2026-09-13") == ("2026-09-07", "2026-09-13")

    def test_semana_cruza_virada_de_mes(self) -> None:
        """2026-09-02 é quarta; a semana começa em 2026-08-31 (segunda) e
        termina em 2026-09-06 (domingo) — a virada de agosto para setembro
        cai no meio da semana. O endpoint de histórico (task futura) precisa
        buscar dois meses quando a semana selecionada cruza essa fronteira.
        """
        from app.api.uso_store import intervalo

        assert intervalo("semana", "2026-09-02") == ("2026-08-31", "2026-09-06")

    def test_mes_cobre_do_primeiro_ao_ultimo_dia(self) -> None:
        """Setembro tem 30 dias."""
        from app.api.uso_store import intervalo

        assert intervalo("mes", "2026-09-09") == ("2026-09-01", "2026-09-30")

    def test_mes_de_fevereiro_bissexto(self) -> None:
        """2028 é bissexto — fevereiro termina em 29."""
        from app.api.uso_store import intervalo

        assert intervalo("mes", "2028-02-10") == ("2028-02-01", "2028-02-29")

    def test_escala_desconhecida_levanta_valueerror(self) -> None:
        """Escala fora de 'dia'/'semana'/'mes' levanta ValueError."""
        from app.api.uso_store import intervalo

        with pytest.raises(ValueError):
            intervalo("ano", "2026-09-09")

    def test_saida_e_sempre_canonica_mesmo_com_entrada_nao_canonica(self) -> None:
        """A saída é sempre YYYY-MM-DD canônico, mesmo se `ref` não for.

        `date.fromisoformat` aceita variantes além de "YYYY-MM-DD" (ex.:
        "20260909" sem hífens). Remover a normalização da saída quebra o
        filtro `inicio <= dia <= fim` da rota de histórico, que compara
        strings direto contra o `dia` gravado no JSONL — uma saída não
        canônica faz essa comparação falhar em silêncio, devolvendo "sem uso"
        para um período com dados.
        """
        from app.api.uso_store import intervalo

        assert intervalo("dia", "20260909") == ("2026-09-09", "2026-09-09")
        assert intervalo("semana", "20260909") == intervalo("semana", "2026-09-09")
        assert intervalo("mes", "20260909") == intervalo("mes", "2026-09-09")


class TestAgregadoDoPeriodo:
    def _gravar(self, uso_dir: Path, dia: str, rota: str, aberto_s: int, ativo_s: int) -> None:
        """Grava direto no store, como se um flush já tivesse acontecido."""
        from app.api.uso_store import Acumulador, escrever_flush

        acc = Acumulador()
        acc.registrar("gabriel", rota, aberto_s, ativo_s, dia=dia)
        escrever_flush(uso_dir, acc.drenar())

    def test_semana_que_comeca_no_mes_anterior_traz_os_dois_meses(self, tmp_path: Path) -> None:
        """O caso do bug: fusão que só olhava `fim` perdia o mês de `inicio`.

        Semana de 2026-08-31 (segunda) a 2026-09-06 (domingo), com `ref` em
        setembro — o início da semana cai em agosto. `2026-08` é mês fechado
        (hoje é 2026-09-09) e por isso passa pelo cache — a chave do cache
        inclui `tmp_path`, então não há necessidade de `limpar_cache()` aqui.
        """
        from app.api.uso_store import agregado_do_periodo

        self._gravar(tmp_path, "2026-08-31", "/caixa", 1000, 800)
        self._gravar(tmp_path, "2026-09-06", "/caixa", 500, 400)

        agregado, inicio, fim = agregado_do_periodo(tmp_path, "semana", "2026-09-02", "gabriel")

        assert inicio == "2026-08-31"
        assert fim == "2026-09-06"
        assert agregado[("2026-08-31", "/caixa")].aberto_s == 1000
        assert agregado[("2026-09-06", "/caixa")].aberto_s == 500

    def test_semana_que_termina_no_mes_seguinte_traz_os_dois_meses(self, tmp_path: Path) -> None:
        """Espelho do caso acima: `ref` no fim do mês, semana estende para o mês seguinte."""
        from app.api.uso_store import agregado_do_periodo

        self._gravar(tmp_path, "2026-08-31", "/caixa", 1000, 800)
        self._gravar(tmp_path, "2026-09-06", "/caixa", 500, 400)

        agregado, inicio, fim = agregado_do_periodo(tmp_path, "semana", "2026-08-31", "gabriel")

        assert inicio == "2026-08-31"
        assert fim == "2026-09-06"
        assert agregado[("2026-08-31", "/caixa")].aberto_s == 1000
        assert agregado[("2026-09-06", "/caixa")].aberto_s == 500

    def test_periodo_dentro_de_um_so_mes_carrega_so_um_mes(self, tmp_path: Path) -> None:
        """Sem cruzar fronteira de mês, o agregado vem só do mês de `ref`.

        `agregado_do_periodo` devolve o mês inteiro — a filtragem para a
        janela de `escala` acontece na camada de cima (a rota). Aqui só
        confirmamos que os dados do mês de `ref` chegam corretos e que nenhum
        outro mês foi envolvido.
        """
        from app.api.uso_store import agregado_do_periodo

        self._gravar(tmp_path, "2026-09-07", "/caixa", 3600, 3000)
        self._gravar(tmp_path, "2026-09-09", "/caixa", 1800, 1500)

        agregado, inicio, fim = agregado_do_periodo(tmp_path, "semana", "2026-09-09", "gabriel")

        assert inicio == "2026-09-07"
        assert fim == "2026-09-13"
        assert agregado[("2026-09-07", "/caixa")].aberto_s == 3600
        assert agregado[("2026-09-09", "/caixa")].aberto_s == 1800

    def test_escala_mes(self, tmp_path: Path) -> None:
        """Escala 'mes' cobre o mês inteiro de `ref`."""
        from app.api.uso_store import agregado_do_periodo

        self._gravar(tmp_path, "2026-09-01", "/caixa", 100, 80)
        self._gravar(tmp_path, "2026-09-30", "/caixa", 200, 160)

        agregado, inicio, fim = agregado_do_periodo(tmp_path, "mes", "2026-09-15", "gabriel")

        assert inicio == "2026-09-01"
        assert fim == "2026-09-30"
        assert agregado[("2026-09-01", "/caixa")].aberto_s == 100
        assert agregado[("2026-09-30", "/caixa")].aberto_s == 200

    def test_escala_dia(self, tmp_path: Path) -> None:
        """Escala 'dia' resolve para o próprio dia, início igual a fim."""
        from app.api.uso_store import agregado_do_periodo

        self._gravar(tmp_path, "2026-09-09", "/caixa", 600, 500)
        self._gravar(tmp_path, "2026-09-10", "/caixa", 999, 999)

        agregado, inicio, fim = agregado_do_periodo(tmp_path, "dia", "2026-09-09", "gabriel")

        assert inicio == fim == "2026-09-09"
        assert set(agregado) == {("2026-09-09", "/caixa"), ("2026-09-10", "/caixa")}

    def test_devolve_dict_novo_nao_a_referencia_do_cache(self, tmp_path: Path) -> None:
        """O dict devolvido é novo — inserir/remover chave nele não afeta o cache.

        `2026-08` é mês fechado em relação ao `ano_mes_corrente` real do
        processo (hoje é 2026-09-09) — `agregado_do_mes` devolve, para ele, o
        mesmo dict guardado em `_CACHE_MES`. `agregado_do_periodo` monta o
        combinado com `dict(...)`/`.update(...)`, então o dict em si é novo.

        Isso não estende à mutação de atributo de um `TempoUso` dentro do
        dict: a cópia é rasa, então os `TempoUso` de um mês fechado ainda são
        os mesmos objetos do cache — exatamente a mesma ressalva que
        `agregado_do_mes` já documenta. A rota nunca escreve em `tempo.*`, só
        lê, então isso nunca é exercitado em produção; não é reconfirmado
        aqui para não sugerir que seria seguro fazer.
        """
        from app.api.uso_store import agregado_do_mes, agregado_do_periodo

        self._gravar(tmp_path, "2026-08-14", "/caixa", 300, 200)

        cache_direto = agregado_do_mes(tmp_path, "2026-08", "gabriel", ano_mes_corrente="2026-09")
        agregado, _, _ = agregado_do_periodo(tmp_path, "dia", "2026-08-14", "gabriel")

        assert agregado is not cache_direto
        del agregado[("2026-08-14", "/caixa")]
        assert ("2026-08-14", "/caixa") in cache_direto


class TestAgregadoDoAno:
    def _gravar(self, uso_dir: Path, dia: str, rota: str, aberto_s: int, ativo_s: int) -> None:
        """Grava direto no store, como se um flush já tivesse acontecido."""
        from app.api.uso_store import Acumulador, escrever_flush

        acc = Acumulador()
        acc.registrar("gabriel", rota, aberto_s, ativo_s, dia=dia)
        escrever_flush(uso_dir, acc.drenar())

    def test_ano_sem_dado_devolve_doze_meses_zerados_em_ordem(self, tmp_path: Path) -> None:
        """Ano sem nenhum registro ainda devolve os doze meses, todos a zero."""
        from app.api.uso_store import agregado_do_ano

        resultado = agregado_do_ano(tmp_path, 2025, "gabriel")

        assert [ano_mes for ano_mes, _ in resultado] == [f"2025-{mes:02d}" for mes in range(1, 13)]
        assert all(tempo.aberto_s == 0 and tempo.ativo_s == 0 for _, tempo in resultado)

    def test_dados_em_dois_meses_aparecem_com_totais_exatos(self, tmp_path: Path) -> None:
        """Dois meses com dado somam certo; os outros dez continuam a zero."""
        from app.api.uso_store import agregado_do_ano

        self._gravar(tmp_path, "2025-03-10", "/caixa", 100, 80)
        self._gravar(tmp_path, "2025-03-15", "/pendencias", 50, 40)
        self._gravar(tmp_path, "2025-11-01", "/caixa", 200, 150)

        resultado = dict(agregado_do_ano(tmp_path, 2025, "gabriel"))

        assert resultado["2025-03"].aberto_s == 150
        assert resultado["2025-03"].ativo_s == 120
        assert resultado["2025-11"].aberto_s == 200
        assert resultado["2025-11"].ativo_s == 150
        assert resultado["2025-01"].aberto_s == 0
        assert resultado["2025-06"].aberto_s == 0

    def test_dado_de_outro_ano_nao_vaza(self, tmp_path: Path) -> None:
        """Registro de 2024 não aparece ao consultar 2025."""
        from app.api.uso_store import agregado_do_ano

        self._gravar(tmp_path, "2024-12-31", "/caixa", 999, 999)

        resultado = dict(agregado_do_ano(tmp_path, 2025, "gabriel"))

        assert all(tempo.aberto_s == 0 and tempo.ativo_s == 0 for tempo in resultado.values())

    def test_dado_de_outro_usuario_nao_vaza(self, tmp_path: Path) -> None:
        """Registro de outro usuário não entra no agregado de gabriel."""
        from app.api.uso_store import Acumulador, agregado_do_ano, escrever_flush

        acc = Acumulador()
        acc.registrar("maria", "/caixa", 500, 400, dia="2025-05-05")
        escrever_flush(tmp_path, acc.drenar())

        resultado = dict(agregado_do_ano(tmp_path, 2025, "gabriel"))

        assert all(tempo.aberto_s == 0 and tempo.ativo_s == 0 for tempo in resultado.values())

    def test_nao_mutila_o_cache_de_mes_fechado(self, tmp_path: Path) -> None:
        """Chamar duas vezes não dobra o total nem corrompe o cache de meses fechados.

        `agregado_do_mes` devolve, para mês fechado, o dict por referência
        guardado em `_CACHE_MES`. `agregado_do_ano` precisa somar em objetos
        `TempoUso` novos — se somasse direto nos objetos do cache, a segunda
        chamada devolveria o dobro do total real.
        """
        from app.api.uso_store import agregado_do_ano

        self._gravar(tmp_path, "2025-07-04", "/caixa", 100, 80)

        primeiro = dict(agregado_do_ano(tmp_path, 2025, "gabriel"))
        segundo = dict(agregado_do_ano(tmp_path, 2025, "gabriel"))

        assert primeiro["2025-07"].aberto_s == 100
        assert segundo["2025-07"].aberto_s == 100

    def test_por_rota_traz_segundos_de_cada_rota_do_mes(self, tmp_path: Path) -> None:
        """Duas rotas no mesmo mês aparecem as duas em `por_rota`, com segundos exatos."""
        from app.api.uso_store import agregado_do_ano

        self._gravar(tmp_path, "2025-03-10", "/caixa", 100, 80)
        self._gravar(tmp_path, "2025-03-15", "/pendencias", 50, 40)

        resultado = dict(agregado_do_ano(tmp_path, 2025, "gabriel"))

        assert resultado["2025-03"].por_rota == {"/caixa": 100, "/pendencias": 50}

    def test_soma_de_por_rota_bate_com_aberto_s_do_mes(self, tmp_path: Path) -> None:
        """A soma dos valores de `por_rota` é sempre o `aberto_s` do mês."""
        from app.api.uso_store import agregado_do_ano

        self._gravar(tmp_path, "2025-03-10", "/caixa", 100, 80)
        self._gravar(tmp_path, "2025-03-12", "/caixa", 40, 30)
        self._gravar(tmp_path, "2025-03-15", "/pendencias", 50, 40)

        resultado = dict(agregado_do_ano(tmp_path, 2025, "gabriel"))

        mes = resultado["2025-03"]
        assert sum(mes.por_rota.values()) == mes.aberto_s

    def test_mes_sem_uso_tem_por_rota_vazio(self, tmp_path: Path) -> None:
        """Mês sem nenhum registro devolve `por_rota` vazio, não ausente."""
        from app.api.uso_store import agregado_do_ano

        self._gravar(tmp_path, "2025-03-10", "/caixa", 100, 80)

        resultado = dict(agregado_do_ano(tmp_path, 2025, "gabriel"))

        assert resultado["2025-01"].por_rota == {}


class TestSobreporBuffer:
    def test_soma_entrada_do_buffer_dentro_do_periodo(self) -> None:
        """Balde do buffer dentro de `[inicio, fim]` entra na chave certa."""
        from app.api.uso_store import ChaveUso, TempoUso, sobrepor_buffer

        agregado = {("2026-09-09", "/caixa"): TempoUso(aberto_s=100, ativo_s=80)}
        buffer = {ChaveUso("gabriel", "2026-09-09", "/caixa"): TempoUso(aberto_s=60, ativo_s=45)}

        resultado = sobrepor_buffer(agregado, buffer, "gabriel", "2026-09-07", "2026-09-13")

        assert resultado[("2026-09-09", "/caixa")].aberto_s == 160
        assert resultado[("2026-09-09", "/caixa")].ativo_s == 125

    def test_cria_chave_nova_quando_o_disco_ainda_nao_tem_a_rota(self) -> None:
        """Rota só presente no buffer (ainda não gravada) ganha entrada nova."""
        from app.api.uso_store import ChaveUso, TempoUso, sobrepor_buffer

        buffer = {ChaveUso("gabriel", "2026-09-09", "/uso"): TempoUso(aberto_s=30, ativo_s=20)}

        resultado = sobrepor_buffer({}, buffer, "gabriel", "2026-09-09", "2026-09-09")

        assert resultado[("2026-09-09", "/uso")].aberto_s == 30
        assert resultado[("2026-09-09", "/uso")].ativo_s == 20

    def test_ignora_buffer_de_outro_usuario(self) -> None:
        """Balde de outro usuário não vaza para o agregado consultado."""
        from app.api.uso_store import ChaveUso, TempoUso, sobrepor_buffer

        buffer = {ChaveUso("maria", "2026-09-09", "/caixa"): TempoUso(aberto_s=999, ativo_s=999)}

        resultado = sobrepor_buffer({}, buffer, "gabriel", "2026-09-09", "2026-09-09")

        assert resultado == {}

    def test_ignora_buffer_fora_do_periodo(self) -> None:
        """Balde de um dia fora de `[inicio, fim]` não entra — mesmo do usuário certo."""
        from app.api.uso_store import ChaveUso, TempoUso, sobrepor_buffer

        buffer = {ChaveUso("gabriel", "2026-08-20", "/caixa"): TempoUso(aberto_s=500, ativo_s=400)}

        resultado = sobrepor_buffer({}, buffer, "gabriel", "2026-09-01", "2026-09-30")

        assert resultado == {}

    def test_nao_muta_o_agregado_recebido_nem_seus_tempouso(self) -> None:
        """A entrada original permanece intacta — o resultado é uma estrutura nova.

        Este é o cuidado crítico do defeito: `agregado` pode ser (ou derivar
        rasamente de) o dict cacheado por referência em `_CACHE_MES` para um
        mês fechado. Mutar um `TempoUso` dali corromperia o cache para toda
        chamada futura, silenciosamente, até o próximo restart.
        """
        from app.api.uso_store import ChaveUso, TempoUso, sobrepor_buffer

        tempo_original = TempoUso(aberto_s=100, ativo_s=80)
        agregado = {("2026-09-09", "/caixa"): tempo_original}
        buffer = {ChaveUso("gabriel", "2026-09-09", "/caixa"): TempoUso(aberto_s=60, ativo_s=45)}

        resultado = sobrepor_buffer(agregado, buffer, "gabriel", "2026-09-09", "2026-09-09")

        assert tempo_original.aberto_s == 100
        assert tempo_original.ativo_s == 80
        assert resultado[("2026-09-09", "/caixa")] is not tempo_original

    def test_buffer_vazio_devolve_copia_equivalente(self) -> None:
        """Sem contribuição do buffer, os valores originais são preservados."""
        from app.api.uso_store import TempoUso, sobrepor_buffer

        agregado = {("2026-09-09", "/caixa"): TempoUso(aberto_s=100, ativo_s=80)}

        resultado = sobrepor_buffer(agregado, {}, "gabriel", "2026-09-09", "2026-09-09")

        assert resultado[("2026-09-09", "/caixa")].aberto_s == 100
        assert resultado is not agregado


class TestAgregadoDoPeriodoComBuffer:
    def test_buffer_do_dia_corrente_entra_no_periodo(self, tmp_path: Path) -> None:
        """`agregado_do_periodo` soma o buffer quando ele cai dentro do período pedido."""
        from app.api.uso_store import ChaveUso, TempoUso, agregado_do_periodo

        buffer = {ChaveUso("gabriel", "2026-09-09", "/uso"): TempoUso(aberto_s=45, ativo_s=30)}

        agregado, inicio, fim = agregado_do_periodo(
            tmp_path, "dia", "2026-09-09", "gabriel", buffer=buffer
        )

        assert inicio == fim == "2026-09-09"
        assert agregado[("2026-09-09", "/uso")].aberto_s == 45

    def test_sem_buffer_comportamento_e_identico_ao_anterior(self, tmp_path: Path) -> None:
        """`buffer=None` (default) não sobrepõe nada — compatível com os testes já existentes."""
        from app.api.uso_store import agregado_do_periodo

        agregado, _, _ = agregado_do_periodo(tmp_path, "dia", "2026-09-09", "gabriel")

        assert agregado == {}


class TestAgregadoDoAnoComBuffer:
    def _gravar(self, uso_dir: Path, dia: str, rota: str, aberto_s: int, ativo_s: int) -> None:
        from app.api.uso_store import Acumulador, escrever_flush

        acc = Acumulador()
        acc.registrar("gabriel", rota, aberto_s, ativo_s, dia=dia)
        escrever_flush(uso_dir, acc.drenar())

    def test_buffer_do_mes_corrente_soma_no_mes_certo(self, tmp_path: Path) -> None:
        """Balde do buffer entra só no mês a que o dia pertence."""
        from app.api.uso_store import ChaveUso, TempoUso, agregado_do_ano

        buffer = {ChaveUso("gabriel", "2025-03-10", "/uso"): TempoUso(aberto_s=45, ativo_s=30)}

        resultado = dict(agregado_do_ano(tmp_path, 2025, "gabriel", buffer=buffer))

        assert resultado["2025-03"].aberto_s == 45
        assert resultado["2025-03"].por_rota == {"/uso": 45}
        assert resultado["2025-04"].aberto_s == 0

    def test_buffer_de_outro_usuario_nao_vaza_no_ano(self, tmp_path: Path) -> None:
        """Mesma checagem de `sobrepor_buffer`, agora através de `agregado_do_ano`."""
        from app.api.uso_store import ChaveUso, TempoUso, agregado_do_ano

        buffer = {ChaveUso("maria", "2025-03-10", "/uso"): TempoUso(aberto_s=999, ativo_s=999)}

        resultado = dict(agregado_do_ano(tmp_path, 2025, "gabriel", buffer=buffer))

        assert resultado["2025-03"].aberto_s == 0

    def test_mes_fechado_servido_do_cache_nao_e_corrompido_pela_sobreposicao(
        self, tmp_path: Path
    ) -> None:
        """Chamar duas vezes com buffer não dobra o total do mês fechado.

        `2025-07` é mês fechado em relação ao relógio real do processo — vem
        do cache em `_CACHE_MES`. Se `sobrepor_buffer` mutasse os `TempoUso`
        do cache em vez de devolver objetos novos, a segunda chamada veria o
        total já inflado pela primeira sobreposição e dobraria de novo.
        """
        from app.api.uso_store import ChaveUso, TempoUso, agregado_do_ano

        self._gravar(tmp_path, "2025-07-04", "/caixa", 100, 80)
        buffer = {ChaveUso("gabriel", "2025-07-04", "/caixa"): TempoUso(aberto_s=50, ativo_s=40)}

        primeiro = dict(agregado_do_ano(tmp_path, 2025, "gabriel", buffer=buffer))
        segundo = dict(agregado_do_ano(tmp_path, 2025, "gabriel", buffer=buffer))

        assert primeiro["2025-07"].aberto_s == 150
        assert segundo["2025-07"].aberto_s == 150
