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
| Guia de operacao | `doc/guia_operacao.md` | Deploy, backup, troubleshooting, reverse proxy |
| Roteiro de treinamento | `doc/roteiro_treinamento.md` | Roteiro da demonstracao (F5-10) |
| Modelo de pontuacao | `doc/modelo_pontuacao.md` | Regra de negocio do score |

---

## Versao publicada

- Versao do pacote: `0.1.0` (`src/ranking_msc/__init__.py`).
- Estado funcional: `78/78` regras implementadas; score, historico, comparacao,
  exportacoes (Excel + PDF), autenticacao JWT e superavit por FR.
- Branch de referencia: `main` (commit no momento do handoff: `<a definir no deploy>`;
  ultimo commit conhecido: `74472b3`).
- Topologia de publicacao: container da aplicacao isolado + nginx reverse proxy
  com TLS (`docker-compose.prod.yml`, mergeado em `#114`).

> Ao publicar no servidor da PMJP, fixar aqui o commit exato (`git rev-parse HEAD`)
> e a data de publicacao.

---

## Ambiente e publicacao

- Execucao via Docker: `make prod-up` sobe app + nginx (gera o certificado se faltar).
- App nao exposto diretamente no host; acesso somente via nginx (HTTP redireciona
  para HTTPS).
- Substituir o certificado self-signed pelo certificado institucional antes do
  go-live (ver `doc/guia_operacao.md`, secao "Publicacao com reverse proxy").
- Validacao de runtime ja exercitada localmente em 2026-06-16: `/api/health` 200,
  redirect 308, login JWT e upload `/api/run` OK. Falta exercitar no ambiente alvo.

---

## Rotina operacional

Detalhada em `doc/guia_operacao.md` (secao "Rotina operacional"):

- **Inicio do dia:** confirmar que a aplicacao esta no ar e respondendo.
- **Depois de cada processamento:** conferir score, pendencias e relatorios gerados.
- **Fechamento mensal:** processar a competencia, exportar e arquivar os artefatos.

---

## Backup, logs e retencao

Detalhado em `doc/guia_operacao.md` (secao "Backup e retencao"):

- Backup diario dos diretorios `config` e `data`.
- Backup obrigatorio antes de qualquer atualizacao de versao.
- Reter os snapshots mensais usados em comparacoes e auditorias.
- Logs de execucao em JSON Lines (ver guia, "Saidas geradas").

> Dry-run de backup/restore (`config` + `data`) validado localmente em 2026-06-16:
> arquivo `.tar.gz` gerado, restaurado em diretorio limpo e checksums conferindo
> em todos os arquivos. Falta confirmar com a TI da PMJP a rotina automatizada do
> servidor alvo e validar uma restauracao de teste la (fecha o item de backup da GO-03).

---

## Atualizacao de versao

Procedimento em `doc/guia_operacao.md` (secao "Atualizacao de versao"):
parar o stack, backup de `config` e `data`, atualizar o repositorio, instalar
dependencias se necessario, rodar validacoes e subir novamente.

---

## Responsaveis

| Papel | Responsavel | Contato |
|---|---|---|
| Suporte de 1o nivel (operacao) | `<a definir>` | `<a definir>` |
| Suporte de 2o nivel (tecnico) | `<a definir>` | `<a definir>` |
| Escalonamento / decisoes de produto | `<a definir>` | `<a definir>` |
| Infraestrutura / TI (servidor, backup, certificado) | `<a definir>` | `<a definir>` |

---

## Treinamento realizado

- Data da sessao: `<a definir>`
- Roteiro utilizado: `doc/roteiro_treinamento.md` (F5-10)
- Participantes: `<a definir>`
- Duvidas e ajustes registrados: `<a definir>`

---

## Pendencias para o encerramento formal

- [ ] GO-02 - validacao contabil do superavit por FR com a area contabil *(planilha de conferencia por FR ja disponivel como apoio)*
- [ ] GO-01 / GO-04 - validar login, `/api/health` e upload no servidor da PMJP
- [ ] GO-03 - validar rotina de backup (e restauracao) no ambiente alvo *(dry-run local OK)*
- [ ] Certificado TLS institucional instalado no lugar do self-signed
- [ ] Senha de producao forte definida (substituir credenciais de teste)
- [ ] Responsaveis preenchidos e cientes
- [ ] F5-10 - treinamento realizado

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
