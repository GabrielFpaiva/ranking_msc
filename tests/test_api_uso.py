"""
Testes das rotas de tempo de uso (app/api/routes/uso.py).

A fixture de sessão _bypass_auth_for_api_tests (tests/conftest.py) substitui
get_current_user por "test-user" — por isso nenhum teste aqui monta um JWT.
"""

from __future__ import annotations

import pytest
from app.api.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


@pytest.fixture(autouse=True)
def _estado_limpo() -> None:
    """Zera acumulador, cache e arquivos entre testes.

    O acumulador e o cache são globais ao processo, e o diretório de uso é
    compartilhado pela fixture de sessão _hermetic_settings. Sem esta limpeza,
    o que um teste grava vaza para o próximo e as asserções de total viram
    dependentes da ordem de execução.
    """
    from app.api.deps import absolute_uso_dir
    from app.api.uso_store import ACUMULADOR, limpar_cache

    ACUMULADOR.drenar()
    limpar_cache()

    uso_dir = absolute_uso_dir()
    if uso_dir.is_dir():
        for arquivo in uso_dir.iterdir():
            if arquivo.is_file():
                arquivo.unlink()


class TestHeartbeat:
    def test_heartbeat_valido_retorna_204(self) -> None:
        """Batida bem formada é aceita sem corpo de resposta."""
        resposta = client.post(
            "/api/uso/heartbeat",
            json={"rota": "/pendencias", "aberto_s": 60, "ativo_s": 45},
        )
        assert resposta.status_code == 204

    def test_heartbeat_alimenta_o_acumulador(self) -> None:
        """O que entra pela rota aparece no buffer, atrelado ao usuário do token."""
        from app.api.uso_store import ACUMULADOR

        client.post(
            "/api/uso/heartbeat",
            json={"rota": "/caixa", "aberto_s": 60, "ativo_s": 60},
        )
        buffer = ACUMULADOR.espiar()
        assert len(buffer) == 1
        chave = next(iter(buffer))
        assert chave.usuario == "test-user"
        assert chave.rota == "/caixa"

    def test_rota_desconhecida_e_rejeitada(self) -> None:
        """Allowlist: o cliente não escreve rota arbitrária no JSONL."""
        resposta = client.post(
            "/api/uso/heartbeat",
            json={"rota": "/../../etc/passwd", "aberto_s": 60, "ativo_s": 60},
        )
        assert resposta.status_code == 422

    def test_segundos_acima_do_teto_sao_rejeitados(self) -> None:
        """Ninguém se dá 40 horas de uso com um curl."""
        resposta = client.post(
            "/api/uso/heartbeat",
            json={"rota": "/caixa", "aberto_s": 144000, "ativo_s": 144000},
        )
        assert resposta.status_code == 422

    def test_segundos_negativos_sao_rejeitados(self) -> None:
        """Delta negativo faria o contador andar para trás."""
        resposta = client.post(
            "/api/uso/heartbeat",
            json={"rota": "/caixa", "aberto_s": -60, "ativo_s": -60},
        )
        assert resposta.status_code == 422


class TestUsoHoje:
    def test_sem_uso_retorna_zeros(self) -> None:
        """Usuário que nunca abriu o app não quebra a sidebar."""
        resposta = client.get("/api/uso/hoje")
        assert resposta.status_code == 200
        assert resposta.json() == {"aberto_s": 0, "ativo_s": 0}

    def test_soma_o_buffer_ainda_nao_gravado(self) -> None:
        """O número da sidebar não pode ficar 5 minutos atrasado esperando o flush."""
        client.post(
            "/api/uso/heartbeat",
            json={"rota": "/caixa", "aberto_s": 60, "ativo_s": 45},
        )
        client.post(
            "/api/uso/heartbeat",
            json={"rota": "/regras", "aberto_s": 30, "ativo_s": 20},
        )

        corpo = client.get("/api/uso/hoje").json()
        assert corpo["aberto_s"] == 90
        assert corpo["ativo_s"] == 65


class TestUsoHistorico:
    def _gravar(self, dia: str, rota: str, aberto_s: int, ativo_s: int) -> None:
        """Grava direto no store, como se um flush já tivesse acontecido."""
        from app.api.deps import absolute_uso_dir
        from app.api.uso_store import Acumulador, escrever_flush

        acc = Acumulador()
        acc.registrar("test-user", rota, aberto_s, ativo_s, dia=dia)
        escrever_flush(absolute_uso_dir(), acc.drenar())

    def test_escala_semana_soma_so_a_semana(self) -> None:
        """Segunda a domingo — o dia de fora não entra no total."""
        self._gravar("2026-09-07", "/caixa", 3600, 3000)
        self._gravar("2026-09-09", "/caixa", 1800, 1500)
        self._gravar("2026-09-20", "/caixa", 9999, 9999)

        corpo = client.get("/api/uso/historico?escala=semana&ref=2026-09-09").json()
        assert corpo["inicio"] == "2026-09-07"
        assert corpo["fim"] == "2026-09-13"
        assert corpo["total_aberto_s"] == 5400
        assert corpo["total_ativo_s"] == 4500

    def test_dias_cobrem_o_mes_inteiro_com_zeros(self) -> None:
        """O front desenha as semanas do mês sem fazer várias requisições."""
        self._gravar("2026-09-09", "/caixa", 1800, 1500)

        corpo = client.get("/api/uso/historico?escala=semana&ref=2026-09-09").json()
        assert len(corpo["dias"]) == 30
        assert corpo["dias"][0]["dia"] == "2026-09-01"
        assert corpo["dias"][0]["aberto_s"] == 0
        assert corpo["dias"][8]["dia"] == "2026-09-09"
        assert corpo["dias"][8]["aberto_s"] == 1800

    def test_rotas_vem_ordenadas_por_tempo_desc(self) -> None:
        """A tela 'Por tela' mostra a mais usada primeiro."""
        self._gravar("2026-09-09", "/caixa", 600, 500)
        self._gravar("2026-09-09", "/pendencias", 3600, 3000)
        self._gravar("2026-09-09", "/regras", 1200, 900)

        corpo = client.get("/api/uso/historico?escala=dia&ref=2026-09-09").json()
        assert [item["rota"] for item in corpo["rotas"]] == ["/pendencias", "/regras", "/caixa"]

    def test_escala_invalida_e_rejeitada(self) -> None:
        """Query param fora do enum não chega ao store."""
        resposta = client.get("/api/uso/historico?escala=decada&ref=2026-09-09")
        assert resposta.status_code == 422

    def test_ref_malformada_e_rejeitada(self) -> None:
        """Data inválida vira 422, não 500."""
        resposta = client.get("/api/uso/historico?escala=dia&ref=09/09/2026")
        assert resposta.status_code == 422

    def test_por_rota_traz_as_duas_rotas_do_dia_com_segundos_exatos(self) -> None:
        """Um dia com duas rotas reporta as duas em `por_rota`, sem colapsar no total."""
        self._gravar("2026-09-09", "/caixa", 600, 500)
        self._gravar("2026-09-09", "/pendencias", 300, 200)

        corpo = client.get("/api/uso/historico?escala=dia&ref=2026-09-09").json()
        dia_09 = next(item for item in corpo["dias"] if item["dia"] == "2026-09-09")

        assert dia_09["por_rota"] == {"/caixa": 600, "/pendencias": 300}

    def test_soma_de_por_rota_bate_com_aberto_s_do_dia(self) -> None:
        """A soma dos valores de `por_rota` é sempre o `aberto_s` daquele dia."""
        self._gravar("2026-09-09", "/caixa", 600, 500)
        self._gravar("2026-09-09", "/pendencias", 300, 200)
        self._gravar("2026-09-09", "/regras", 100, 90)

        corpo = client.get("/api/uso/historico?escala=dia&ref=2026-09-09").json()
        dia_09 = next(item for item in corpo["dias"] if item["dia"] == "2026-09-09")

        assert sum(dia_09["por_rota"].values()) == dia_09["aberto_s"]

    def test_dia_sem_uso_tem_por_rota_vazio(self) -> None:
        """Dia zero-preenchido do calendário mensal vem com `por_rota` vazio."""
        self._gravar("2026-09-09", "/caixa", 600, 500)

        corpo = client.get("/api/uso/historico?escala=dia&ref=2026-09-09").json()
        dia_10 = next(item for item in corpo["dias"] if item["dia"] == "2026-09-10")

        assert dia_10["por_rota"] == {}

    def test_ref_e_normalizada_na_resposta(self) -> None:
        """`ref=20260909` (ISO básico) não pode voltar diferente de `inicio`/`fim`.

        `date.fromisoformat` aceita variantes não canônicas; se a resposta
        ecoasse a string recebida, `ref` destoaria de `inicio`/`fim` — que
        `intervalo()` sempre canonicaliza — dentro do mesmo payload.
        """
        corpo = client.get("/api/uso/historico?escala=dia&ref=20260909").json()
        assert corpo["ref"] == "2026-09-09"
        assert corpo["inicio"] == "2026-09-09"
        assert corpo["fim"] == "2026-09-09"

    def test_semana_cruzando_mes_soma_os_dois_lados_mas_dias_e_so_do_mes_de_ref(self) -> None:
        """Semana de 31/08 a 06/09/2026 (segunda a domingo), ref em setembro.

        Os totais e `rotas` somam os dois lados da fronteira; `dias` continua
        cobrindo só o mês de `ref` (setembro) — sem barra para 31/08, embora
        aquele dia entre na soma. Ver docstring do endpoint.
        """
        self._gravar("2026-08-31", "/caixa", 1000, 800)
        self._gravar("2026-09-06", "/caixa", 500, 400)

        corpo = client.get("/api/uso/historico?escala=semana&ref=2026-09-02").json()
        assert corpo["inicio"] == "2026-08-31"
        assert corpo["fim"] == "2026-09-06"
        assert corpo["total_aberto_s"] == 1500
        assert corpo["total_ativo_s"] == 1200
        assert corpo["rotas"] == [{"rota": "/caixa", "aberto_s": 1500, "ativo_s": 1200}]

        dias_do_payload = [item["dia"] for item in corpo["dias"]]
        assert "2026-08-31" not in dias_do_payload
        assert dias_do_payload[0] == "2026-09-01"
        assert dias_do_payload[-1] == "2026-09-30"
        dia_06 = next(item for item in corpo["dias"] if item["dia"] == "2026-09-06")
        assert dia_06["aberto_s"] == 500


class TestUsoHistoricoComBuffer:
    """DEFEITO 1: `/historico` (e `/anual`, na classe abaixo) discordavam de
    `/hoje` porque só liam disco — o buffer em memória (até 5 minutos de
    heartbeats ainda não gravados) só entrava em `/hoje`. Estes testes
    exercitam a rota de verdade via heartbeat real, sem flush manual."""

    def test_heartbeat_nao_gravado_aparece_no_historico_do_dia(self) -> None:
        """Um heartbeat que ainda só está no buffer já aparece em `/historico`."""
        from app.api.uso_store import dia_local

        client.post(
            "/api/uso/heartbeat",
            json={"rota": "/uso", "aberto_s": 40, "ativo_s": 30},
        )

        hoje = dia_local()
        corpo = client.get(f"/api/uso/historico?escala=dia&ref={hoje}").json()

        assert corpo["total_aberto_s"] == 40
        assert corpo["total_ativo_s"] == 30
        dia_de_hoje = next(item for item in corpo["dias"] if item["dia"] == hoje)
        assert dia_de_hoje["aberto_s"] == 40

    def test_hoje_e_historico_do_mesmo_dia_batem(self) -> None:
        """Trava o defeito: sidebar (`/hoje`) e tela (`/historico`) não podem discordar.

        Grava um pouco em disco (flush já ocorrido) e deixa outro pouco só no
        buffer — as duas rotas precisam somar disco + buffer da mesma forma.
        """
        from app.api.deps import absolute_uso_dir
        from app.api.uso_store import Acumulador, dia_local, escrever_flush

        hoje = dia_local()
        acc = Acumulador()
        acc.registrar("test-user", "/caixa", 300, 200, dia=hoje)
        escrever_flush(absolute_uso_dir(), acc.drenar())

        client.post(
            "/api/uso/heartbeat",
            json={"rota": "/pendencias", "aberto_s": 60, "ativo_s": 45},
        )

        corpo_hoje = client.get("/api/uso/hoje").json()
        corpo_historico = client.get(f"/api/uso/historico?escala=dia&ref={hoje}").json()

        assert corpo_hoje["aberto_s"] == corpo_historico["total_aberto_s"] == 360
        assert corpo_hoje["ativo_s"] == corpo_historico["total_ativo_s"] == 245

    def test_buffer_de_outro_usuario_nao_aparece_no_historico(self) -> None:
        """Balde de outro usuário no buffer não vaza para quem consulta."""
        from app.api.uso_store import ACUMULADOR, dia_local

        hoje = dia_local()
        ACUMULADOR.registrar("outro-usuario", "/caixa", 500, 400, dia=hoje)

        corpo = client.get(f"/api/uso/historico?escala=dia&ref={hoje}").json()

        assert corpo["total_aberto_s"] == 0
        assert corpo["total_ativo_s"] == 0

    def test_buffer_fora_do_periodo_consultado_nao_entra(self) -> None:
        """Heartbeat de hoje não aparece ao consultar um dia diferente do mês."""
        from app.api.uso_store import dia_local

        hoje = dia_local()
        client.post(
            "/api/uso/heartbeat",
            json={"rota": "/uso", "aberto_s": 40, "ativo_s": 30},
        )

        primeiro_dia_do_mes = f"{hoje[:7]}-01"
        if primeiro_dia_do_mes == hoje:
            pytest.skip("hoje já é o primeiro dia do mês — não há outro dia para comparar")

        corpo = client.get(f"/api/uso/historico?escala=dia&ref={primeiro_dia_do_mes}").json()
        assert corpo["total_aberto_s"] == 0


class TestFlushDoCicloDeVida:
    def test_flush_agora_grava_e_esvazia_o_buffer(self) -> None:
        """A função chamada pelo lifespan drena o acumulador para o disco."""
        from app.api.deps import absolute_uso_dir
        from app.api.main import _flush_agora
        from app.api.uso_store import ACUMULADOR, dia_local

        client.post(
            "/api/uso/heartbeat",
            json={"rota": "/caixa", "aberto_s": 60, "ativo_s": 45},
        )
        _flush_agora()

        assert ACUMULADOR.espiar() == {}
        arquivo = absolute_uso_dir() / f"{dia_local()[:7]}.jsonl"
        assert arquivo.exists()
        assert "test-user" in arquivo.read_text(encoding="utf-8")

    def test_shutdown_do_testclient_dispara_flush(self) -> None:
        """Sair do contexto do TestClient encerra o lifespan sem deixar dado no ar."""
        from app.api.uso_store import ACUMULADOR

        with TestClient(app) as cliente:
            cliente.post(
                "/api/uso/heartbeat",
                json={"rota": "/regras", "aberto_s": 60, "ativo_s": 45},
            )
            assert ACUMULADOR.espiar() != {}

        assert ACUMULADOR.espiar() == {}

    def test_ano_mes_corrente_e_lido_antes_de_drenar_o_acumulador(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Trava a ordem exigida: o relógio é lido uma vez, antes do drenar.

        Reproduz por que a ordem importa (ver docstring de `_flush_agora`):
        se alguém mover a leitura de `dia_local()` para depois de
        `ACUMULADOR.drenar()` — ou chamá-la de novo depois —, um heartbeat
        que chegasse entre o drenar e a meia-noite real acabaria carimbado
        com o mês antigo, mas seria compactado sob um `ano_mes_corrente` já
        do mês novo; o próximo flush gravaria esse retardatário num
        `<mes-antigo>.jsonl` novo ao lado do `.agg.jsonl` já compactado
        daquele mês, que a próxima varredura de compactação apaga como lixo
        de crash — dado perdido em silêncio, sem exceção e sem log.

        Em vez de tentar reproduzir a corrida de fato (dependeria de cronometrar
        threads reais na virada do relógio), este teste finge ser um "linter de
        ordem": instrumenta `dia_local` (como importado em `app.api.main`) e
        `Acumulador.drenar` para registrar em que ordem são chamados, e exige
        que `dia_local` apareça exatamente uma vez, antes de `drenar`. Qualquer
        reordenação futura de `_flush_agora` que viole isso — mover a leitura
        do relógio para depois do drenar, ou lê-lo de novo depois — quebra
        esta asserção mesmo sem executar de fato na virada do mês.
        """
        from app.api import main as main_module
        from app.api.uso_store import ACUMULADOR

        ordem: list[str] = []

        dia_local_original = main_module.dia_local

        def dia_local_espiao(*args: object, **kwargs: object) -> str:
            ordem.append("dia_local")
            return dia_local_original(*args, **kwargs)  # type: ignore[arg-type]

        classe_acumulador = type(ACUMULADOR)
        drenar_original = classe_acumulador.drenar

        def drenar_espiao(self: object) -> dict[object, object]:
            ordem.append("drenar")
            return drenar_original(self)  # type: ignore[arg-type]

        monkeypatch.setattr(main_module, "dia_local", dia_local_espiao)
        monkeypatch.setattr(classe_acumulador, "drenar", drenar_espiao)

        main_module._flush_agora()

        assert ordem.count("dia_local") == 1
        assert ordem.index("dia_local") < ordem.index("drenar")


class TestUsoAnual:
    def _gravar(
        self, dia: str, rota: str, aberto_s: int, ativo_s: int, usuario: str = "test-user"
    ) -> None:
        """Grava direto no store, como se um flush já tivesse acontecido."""
        from app.api.deps import absolute_uso_dir
        from app.api.uso_store import Acumulador, escrever_flush

        acc = Acumulador()
        acc.registrar(usuario, rota, aberto_s, ativo_s, dia=dia)
        escrever_flush(absolute_uso_dir(), acc.drenar())

    def test_ano_sem_dado_devolve_doze_meses_zerados_em_ordem(self) -> None:
        """Ano sem nenhum uso ainda devolve os doze meses, todos a zero, em ordem."""
        resposta = client.get("/api/uso/anual?ano=2025")
        assert resposta.status_code == 200
        corpo = resposta.json()

        assert corpo["ano"] == 2025
        assert corpo["total_aberto_s"] == 0
        assert corpo["total_ativo_s"] == 0
        assert [item["mes"] for item in corpo["meses"]] == [
            f"2025-{mes:02d}" for mes in range(1, 13)
        ]
        assert all(item["aberto_s"] == 0 and item["ativo_s"] == 0 for item in corpo["meses"])

    def test_dados_em_dois_meses_aparecem_nos_meses_certos_com_totais_exatos(self) -> None:
        """Uso em março e novembro aparece só nesses dois meses, com o total certo."""
        self._gravar("2025-03-10", "/caixa", 100, 80)
        self._gravar("2025-03-15", "/pendencias", 50, 40)
        self._gravar("2025-11-01", "/caixa", 200, 150)

        corpo = client.get("/api/uso/anual?ano=2025").json()
        por_mes = {item["mes"]: item for item in corpo["meses"]}

        assert por_mes["2025-03"]["aberto_s"] == 150
        assert por_mes["2025-03"]["ativo_s"] == 120
        assert por_mes["2025-11"]["aberto_s"] == 200
        assert por_mes["2025-11"]["ativo_s"] == 150
        assert por_mes["2025-01"]["aberto_s"] == 0
        assert corpo["total_aberto_s"] == 350
        assert corpo["total_ativo_s"] == 270

    def test_dado_de_outro_ano_nao_vaza(self) -> None:
        """Uso registrado em 2024 não aparece ao consultar 2025."""
        self._gravar("2024-12-31", "/caixa", 999, 999)

        corpo = client.get("/api/uso/anual?ano=2025").json()
        assert corpo["total_aberto_s"] == 0
        assert corpo["total_ativo_s"] == 0

    def test_dado_de_outro_usuario_nao_vaza(self) -> None:
        """Uso de outro usuário não aparece no ano consultado pelo usuário do token."""
        self._gravar("2025-05-05", "/caixa", 500, 400, usuario="outro-usuario")

        corpo = client.get("/api/uso/anual?ano=2025").json()
        assert corpo["total_aberto_s"] == 0
        assert corpo["total_ativo_s"] == 0

    def test_ano_nao_numerico_e_rejeitado(self) -> None:
        """Query param que não parseia como int vira 422, não 500."""
        resposta = client.get("/api/uso/anual?ano=abacate")
        assert resposta.status_code == 422

    def test_ano_absurdo_no_passado_e_rejeitado(self) -> None:
        """1900 é anterior a qualquer dado real do app."""
        resposta = client.get("/api/uso/anual?ano=1900")
        assert resposta.status_code == 422

    def test_ano_absurdo_no_futuro_e_rejeitado(self) -> None:
        """3000 não tem como ter dado nenhum."""
        resposta = client.get("/api/uso/anual?ano=3000")
        assert resposta.status_code == 422

    def test_meses_sao_sempre_01_a_12_em_ordem_independente_de_onde_ha_dado(self) -> None:
        """Mesmo com dado só em dezembro, a lista continua 01..12 em ordem."""
        self._gravar("2025-12-25", "/caixa", 10, 5)

        corpo = client.get("/api/uso/anual?ano=2025").json()
        assert [item["mes"] for item in corpo["meses"]] == [
            f"2025-{mes:02d}" for mes in range(1, 13)
        ]

    def test_por_rota_traz_as_duas_rotas_do_mes_com_segundos_exatos(self) -> None:
        """Um mês com duas rotas reporta as duas em `por_rota`, sem colapsar no total."""
        self._gravar("2025-03-10", "/caixa", 100, 80)
        self._gravar("2025-03-15", "/pendencias", 50, 40)

        corpo = client.get("/api/uso/anual?ano=2025").json()
        por_mes = {item["mes"]: item for item in corpo["meses"]}

        assert por_mes["2025-03"]["por_rota"] == {"/caixa": 100, "/pendencias": 50}

    def test_soma_de_por_rota_bate_com_aberto_s_do_mes(self) -> None:
        """A soma dos valores de `por_rota` é sempre o `aberto_s` daquele mês."""
        self._gravar("2025-03-10", "/caixa", 100, 80)
        self._gravar("2025-03-12", "/caixa", 40, 30)
        self._gravar("2025-03-15", "/pendencias", 50, 40)

        corpo = client.get("/api/uso/anual?ano=2025").json()
        por_mes = {item["mes"]: item for item in corpo["meses"]}

        assert sum(por_mes["2025-03"]["por_rota"].values()) == por_mes["2025-03"]["aberto_s"]

    def test_mes_sem_uso_tem_por_rota_vazio(self) -> None:
        """Mês sem nenhum registro devolve `por_rota` vazio."""
        self._gravar("2025-03-10", "/caixa", 100, 80)

        corpo = client.get("/api/uso/anual?ano=2025").json()
        por_mes = {item["mes"]: item for item in corpo["meses"]}

        assert por_mes["2025-01"]["por_rota"] == {}

    def test_heartbeat_nao_gravado_aparece_no_ano_corrente(self) -> None:
        """DEFEITO 1: `/anual` também precisa enxergar o buffer do mês corrente."""
        from app.api.uso_store import dia_local

        hoje = dia_local()
        ano_corrente = int(hoje[:4])
        mes_corrente = hoje[:7]

        client.post(
            "/api/uso/heartbeat",
            json={"rota": "/uso", "aberto_s": 40, "ativo_s": 30},
        )

        corpo = client.get(f"/api/uso/anual?ano={ano_corrente}").json()
        por_mes = {item["mes"]: item for item in corpo["meses"]}

        assert por_mes[mes_corrente]["aberto_s"] == 40
        assert por_mes[mes_corrente]["ativo_s"] == 30

    def test_buffer_de_outro_usuario_nao_aparece_no_ano(self) -> None:
        """Balde de outro usuário no buffer não vaza para o ano consultado."""
        from app.api.uso_store import ACUMULADOR, dia_local

        hoje = dia_local()
        ano_corrente = int(hoje[:4])
        ACUMULADOR.registrar("outro-usuario", "/caixa", 500, 400, dia=hoje)

        corpo = client.get(f"/api/uso/anual?ano={ano_corrente}").json()
        assert corpo["total_aberto_s"] == 0
