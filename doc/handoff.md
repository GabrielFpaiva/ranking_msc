# Handoff Operacional - Ranking MSC

> Documento de entrega formal do Ranking MSC (MCRA PMJP) para operacao.
> Tarefa de backlog: F5-11.
> Status: em preenchimento (campos marcados como `<a definir>` dependem da PMJP).

---

## Objetivo

Registrar o que esta sendo entregue, a versao publicada, as rotinas de
operacao e os responsaveis, de modo que a equipe da PMJP opere e mantenha o
sistema de forma autonoma e o projeto possa ser encerrado formalmente.

---

## Artefatos entregues

| Artefato | Local | Conteudo |
|---|---|---|
| Codigo-fonte | repositorio Git (`main`) | Motor, API FastAPI e frontend React |
| Manual do usuario | `doc/manual_usuario.md` | Fluxo de uso para a equipe contabil |
| Guia de operacao | `doc/guia_operacao.md` | Instalacao, configuracao, backup, troubleshooting |
| Roteiro de treinamento | `doc/roteiro_treinamento.md` | Roteiro da demonstracao (F5-10) |
| Convite e FAQ | `doc/convite_treinamento.md`, `FAQ-MCRA.html` | Texto do e-mail aos usuarios; FAQ com GIFs gerado por `make faq-html` (regravar os GIFs: `make faq-gifs`, com backend e frontend de dev no ar) |
| Modelo de pontuacao | `doc/modelo_pontuacao.md` | Regra de negocio do score |

---

## Versao publicada

- Versao do pacote: `0.1.0` (`src/ranking_msc/__init__.py`).
- Estado funcional: `78/78` regras implementadas; score, historico, comparacao,
  exportacoes (Excel + PDF), autenticacao JWT e superavit por FR.
- Branch de referencia: `main` (commit no momento do handoff: `<a definir na distribuicao>`;
  ultimo commit conhecido: `74472b3`).
- Topologia de publicacao usada ate 21/09/2026 (nunca chegou a ser exercitada
  em ambiente real da PMJP): container da aplicacao isolado + nginx reverse
  proxy com TLS (`docker-compose.prod.yml`, mergeado em `#114`). Aposentada
  nessa data; o material fica em `doc/legacy/`.
- Topologia atual: instalador Windows por maquina (`MCRA-Setup-<versao>.exe`),
  gerado pelo workflow `Release desktop` do GitHub Actions. Sem servidor
  central; cada maquina guarda sua propria configuracao e dados em
  `%LOCALAPPDATA%\MCRA`.

> Ao distribuir uma nova versao do instalador para a PMJP, fixar aqui a versao
> (`<a definir>`) e a data.

---

## Ambiente e publicacao

Ate 21/09/2026 a entrega seria via Docker (`make prod-up`, app + nginx com
TLS). Essa topologia foi aposentada nessa data — a prefeitura nao provisionou
servidor, dominio nem certificado institucional — e o material correspondente
esta em `doc/legacy/`.

Hoje a entrega e um instalador Windows por maquina:

- Instalador: `MCRA-Setup-<versao>.exe`, gerado pelo workflow `Release desktop`
  do GitHub Actions. Instala em Arquivos de Programas e cria atalho no menu
  iniciar e na area de trabalho.
- O instalador verifica o Edge WebView2 e instala se estiver faltando.
- Login por e-mail e senha. Os usuarios iniciais ja vem cadastrados no
  instalador (a lista esta em `config/settings.desktop.yaml`); as senhas sao
  entregues pelo responsavel tecnico por um canal separado do convite
  (`doc/convite_treinamento.md`).
- Novos colaboradores entram por convite assinado (ver "Convites" no guia de
  operacao, `doc/guia_operacao.md`). As contas criadas por convite ficam no
  `settings.yaml` do computador: apagar esse arquivo apaga essas contas.
- O executavel nao e assinado: o Windows SmartScreen mostra aviso na primeira
  execucao, e o antivirus corporativo pode bloquear. Precisa ser testado numa
  maquina real da prefeitura antes do treinamento.
- Validacao de runtime exercitada localmente em 2026-06-16 (ainda na topologia
  hospedada, aposentada): `/api/health` 200, redirect 308, login JWT e upload
  `/api/run` OK. Falta repetir a validacao equivalente com o instalador numa
  maquina real da PMJP.

---

## Rotina operacional

Detalhada em `doc/guia_operacao.md` (secao "Rotina operacional"):

- **Inicio do dia:** confirmar que o aplicativo abre normalmente na maquina.
- **Depois de cada processamento:** conferir score, pendencias e relatorios gerados.
- **Fechamento mensal:** processar a competencia, exportar e arquivar os artefatos.

---

## Backup, logs e retencao

Detalhado em `doc/guia_operacao.md` (secao "Backup e retencao"):

- Backup diario de `%LOCALAPPDATA%\MCRA` em cada maquina (config + dados).
- Backup obrigatorio antes de qualquer atualizacao de versao.
- Reter os snapshots mensais usados em comparacoes e auditorias.
- Logs de execucao em JSON Lines (ver guia, "Saidas geradas").
- Como cada pessoa guarda os proprios dados, nao existe copia central.

> Dry-run de backup/restore (`config` + `data`) validado localmente em 2026-06-16
> (ainda na topologia hospedada, aposentada em 21/09/2026): arquivo `.tar.gz`
> gerado, restaurado em diretorio limpo e checksums conferindo em todos os
> arquivos. Falta repetir a validacao equivalente para `%LOCALAPPDATA%\MCRA`
> numa maquina real da PMJP (fecha o item de backup da GO-03).

---

## Atualizacao de versao

A nova versao chega como um novo instalador (`MCRA-Setup-<versao>.exe`, gerado
pelo workflow `Release desktop`). Cada pessoa baixa e executa o instalador na
propria maquina; ele reinstala o aplicativo em Arquivos de Programas e
preserva `%LOCALAPPDATA%\MCRA` (config e dados de cada pessoa nao sao
tocados). Fazer backup de `%LOCALAPPDATA%\MCRA` antes de instalar, por
seguranca.

Para quem mantem o codigo-fonte (nao o instalador), o procedimento de
atualizar um checkout local esta em `doc/guia_operacao.md`, secao
"Atualizacao de versao".

---

## Responsaveis

| Papel | Responsavel | Contato |
|---|---|---|
| Suporte de 1o nivel (operacao) | `<a definir>` | `<a definir>` |
| Suporte de 2o nivel (tecnico) | `<a definir>` | `<a definir>` |
| Escalonamento / decisoes de produto | `<a definir>` | `<a definir>` |
| Infraestrutura / TI (instalacao, backup por maquina) | `<a definir>` | `<a definir>` |

---

## Treinamento realizado

- Data da sessao: `<a definir>`
- Roteiro utilizado: `doc/roteiro_treinamento.md` (F5-10)
- Participantes: `<a definir>`
- Duvidas e ajustes registrados: `<a definir>`

---

## Pendencias para o encerramento formal

- [ ] GO-02 - validacao contabil do superavit por FR com a area contabil *(planilha de conferencia por FR ja disponivel como apoio)*
- [ ] Instalar numa maquina real da PMJP e validar login, envio de MSC e geracao de relatorio
- [ ] Confirmar que o antivirus da Prefeitura nao bloqueia o executavel
- [ ] Rotina de backup definida para `%LOCALAPPDATA%\MCRA` em cada maquina
- [ ] Responsaveis preenchidos e cientes
- [ ] F5-10 - treinamento realizado
- [ ] Versao do instalador distribuida registrada neste documento

> A entrega deixou de ser hospedada em 21/09/2026. Servidor, dominio e
> certificado institucional saem da lista; o material correspondente esta em
> `doc/legacy/`.

> Decisoes de escopo TECH-02/03/04 ja **encerradas** (registradas na governanca documental,
> hoje fora do repositorio de entrega); nao sao bloqueadores de encerramento.

---

## Aceite formal

| Campo | Valor |
|---|---|
| Responsavel pela aceitacao (PMJP) | `<a definir>` |
| Data do aceite | `<a definir>` |
| Observacoes | `<a definir>` |

Com todos os itens de pendencia resolvidos e o aceite registrado, a entrega
e considerada encerrada e o projeto migra para `04 - Archive/` no PSB.
