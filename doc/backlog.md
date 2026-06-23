# Backlog Operacional - MCRA PMJP

> **Atualizado:** 2026-06-16
> **Fonte unica de planejamento corrente:** este arquivo
> **Estado atual:** motor concluido (`78/78` regras), Fase 4 encerrada e Fase 5 em fechamento operacional. Hardening de frontend mergeado (`#113`, UX-01 a UX-06) e topologia de publicacao nginx + TLS mergeada (`#114`, GO-04). Restam validacoes no ambiente alvo da PMJP, decisoes de escopo (TECH-02/03/04) e treinamento/handoff (F5-10/F5-11).
> **Ultima validacao completa:** `make validate` verde em 2026-06-01 (`979` testes aprovados, `1` ignorado, cobertura `95,56%`, lint, tipos e build frontend).
> **Validacao de runtime (local):** stack de producao (`make prod-up`) exercitada em 2026-06-16 — HTTPS `/api/health` 200, redirect 308, app isolado do host, auth imposta (401 sem token), login JWT e upload `/api/run` (pipeline 78 regras, score/banda/pendencias) OK.

---

## Regra de Uso

Este backlog contem somente trabalho aberto ou decisoes ainda necessarias para concluir a entrega.
Historico de implementacao deve ser consultado no Git e nos documentos classificados como historicos.
Nao reabrir tarefas concluidas sem registrar um bug, uma nova necessidade ou uma decisao operacional explicita.

---

## Estado Consolidado

| Frente | Estado | Observacao |
|---|---|---|
| Motor MSC | Concluido | `78/78` regras implementadas e registradas |
| Score e historico | Concluido | Score `0-100`, bandas `A-E`, historico e comparacao entre competencias |
| Frontend oficial | Concluido | React + FastAPI substituiu a interface Panel; hardening visual mergeado (`#113`) |
| Exportacoes | Concluido | Excel completo (com abas por dimensao) + PDF executivo; escopo encerrado (TECH-02/04) |
| Autenticacao | Concluido | JWT multiusuario; modelo institucional compartilhado definido e encerrado (TECH-03) |
| Deploy | Concluido; publicacao definida | Docker, compose e E2E prontos; topologia nginx + TLS definida, documentada e mergeada (`#114`); falta exercitar no ambiente alvo da PMJP |
| Superavit por FR | Concluido tecnicamente | Falta validacao contabil com dados reais da PMJP |
| Ranking Regional | Fora do fechamento | Depende de base comparativa externa ainda nao definida |

---

## P0 - Bloqueadores Para Go-Live

### GO-01 - Preparar configuracao operacional real

**Objetivo:** publicar um `config/settings.yaml` valido no servidor da prefeitura.

Checklist:

- [x] recriar o arquivo operacional a partir de `config/settings.yaml.example`;
- [x] habilitar as `78` regras atuais;
- [x] remover campos legados como `allowed_users`;
- [x] gerar `security.secret_key` segura;
- [x] cadastrar ao menos um usuario com hash bcrypt;
- [x] confirmar `app.esfera`, paths, permissoes e volumes Docker;
- [ ] validar login e `GET /api/health` no ambiente real *(validado localmente em 2026-06-16; pendente no servidor da PMJP)*.

**Criterio de aceite:** aplicacao sobe sem warnings de configuracao, login funciona e a API informa as regras esperadas.

### GO-02 - Validar Superavit por FR com a area contabil

**Objetivo:** confirmar que a derivacao implementada representa corretamente a leitura esperada pela PMJP.

Checklist:

- [ ] processar uma competencia real da PMJP;
- [ ] comparar manualmente ativo financeiro, passivo financeiro e resultado por FR;
- [ ] confirmar o tratamento de contas `Financeiro/Permanente`;
- [ ] registrar aceite ou abrir task de ajuste da regra contabil.

> Material de apoio gerado: planilha de conferencia por FR (uma linha por FR,
> totais e coluna de conferencia manual), produzida via `GET /api/superavit`. A
> validacao contabil em si permanece com a equipe.

**Criterio de aceite:** equipe contabil valida uma competencia real ou existe task corretiva documentada antes do go-live.

### GO-03 - Executar smoke test operacional

Checklist:

- [x] login;
- [x] upload de CSV MSC real;
- [x] score e banda;
- [x] pendencias e filtros;
- [x] detalhe de regra e conta;
- [x] exportacao Excel;
- [x] exportacao PDF;
- [x] superavit por FR;
- [x] comparacao entre competencias;
- [x] lock de processamento concorrente para o mesmo ente e competencia;
- [x] leitura dos logs;
- [ ] backup *(dry-run de backup/restore de `config`+`data` validado localmente em 2026-06-16 — tar.gz + restauracao com checksums conferindo; falta exercitar no servidor da PMJP)*.

**Criterio de aceite:** fluxo completo executado no ambiente alvo sem erro bloqueador.

### GO-04 - Definir topologia de publicacao

A antiga task F0-08 citava `Docker + nginx`. **Mergeado em `#114`:** `docker-compose.prod.yml` com nginx reverse proxy + TLS, app isolado do host (porta `8000` apenas interna), `make gen-cert`/`prod-up`, healthcheck e redirect HTTP->HTTPS; topologia documentada no `doc/guia_operacao.md`.

Checklist:

- [ ] confirmar se a infraestrutura alvo ja possui reverse proxy institucional;
- [x] definir terminacao HTTP/TLS, hostname e porta publica;
- [x] decidir se nginx pertence a este repositorio ou a infraestrutura externa *(decisao: nginx no repo via `docker-compose.prod.yml`)*;
- [x] documentar a configuracao adotada no guia de operacao;
- [x] validar `/api/health`, login e upload atraves do endpoint publico *(exercitado localmente em 2026-06-16; revalidar no ambiente alvo)*.

**Criterio de aceite:** topologia de publicacao definida, documentada e exercitada no ambiente alvo.

---

## P1 - Hardening de Frontend e Usabilidade

**Concluido em `#113` (UX-01 a UX-06).** Entregue: navegacao/sessao limpas com logout e usuario logado no TopBar; fluxo principal autoexplicativo; paginacao real de pendencias; responsividade minima; tela de login alinhada ao design MCRA; e padronizacao de mensagens de erro (sem codigos HTTP brutos). Historico detalhado no Git.

### F5-19 - Seletor de competencia na TopBar — CONCLUIDA

Dropdown na TopBar lista as competencias enviadas do ente ativo e troca a
competencia ativa (`store.setCurrent`), com todas as telas refletindo via
`useEffect([siconfi, competencia])`. Apenas competencia (um ente); o ente segue
read-only — multi-ente fica para o futuro (store/API ja chaveados por ente).
Estado vazio mantem o placeholder. So frontend (`web/src/components/TopBar.tsx`).
Spec/plano em `doc/specs/` e `doc/plans/`.

---

## P1 - Revisao Tecnica Final

### TECH-01 - Revisar residuos documentais e comentarios obsoletos

- [x] remover comentarios antigos sobre semaforo futuro no executor, pois o lock por periodo ja existe;
- [x] atualizar `doc/governanca_documental.md`: refactor arquitetural `#98` ja foi concluido;
- [x] revisar referencias antigas a placeholders e ao Ranking Regional na documentacao ativa;
- [x] manter referencias historicas apenas nos documentos classificados como historicos.

### TECH-02 - Escopo do Excel por categoria — ENCERRADA

Decisao: **implementar abas por dimensao**. O Excel passou a ter uma aba por
dimensao com pendencias (alem de Resumo/Pendencias/Saldo Devedor/Score). Ver
`src/ranking_msc/outputs/reports.py` e `doc/governanca_documental.md` §7.

- [x] decidir organizacao do Excel;
- [x] implementar abas por dimensao (`F5-13`);
- [x] registrar decisao na governanca.

### TECH-03 - Isolamento multiusuario dos artefatos — ENCERRADA

Decisao: **modelo institucional compartilhado** (sem isolamento por usuario). O
JWT identifica quem executou; o lock impede escrita concorrente. Requisito antigo
F0-07 (namespacing por usuario) encerrado. Justificativa em
`doc/governanca_documental.md` §7.

### TECH-04 - Escopo do PDF de pendencias — ENCERRADA

Decisao: **manter a divisao** PDF executivo (1 pagina) + Excel completo. Requisito
antigo F0-06 (pendencias completas no PDF) encerrado. Ver
`doc/governanca_documental.md` §7.

### F5-18 - Relatorios exportados branded — CONCLUIDA

PDF executivo reescrito com `reportlab` (identidade MCRA navy/dourado, 1 pagina:
faixa de marca, score em destaque, barras por dimensao, historico e cards de
recomendacao; acentos PT-BR corretos) e Excel re-estilizado (capa "Visao Geral",
cabecalho navy/branco, bordas, bandas alinhadas a paleta). Paleta centralizada em
`src/ranking_msc/outputs/brand.py`. Nova dependencia `reportlab>=4.0` (wheel pura,
sem libs de sistema). Contratos publicos (`export_issues_excel`,
`render_executive_pdf`, `write_executive_pdf`) inalterados. Spec/plano em
`doc/specs/` e `doc/plans/`.

> Formato contabil (R$) nas colunas de valor foi descartado: `valor_esperado`/
> `valor_encontrado` sao textuais nas pendencias, entao nao se aplica.

---

## P2 - Treinamento e Entrega

### F5-10 - Treinamento e demonstracao

- [x] preparar roteiro curto baseado no fluxo operacional *(`doc/roteiro_treinamento.md`)*;
- [ ] demonstrar login, upload, score, pendencias, regras, exportacoes, superavit e comparar *(demo ao vivo com a equipe da PMJP ainda pendente)*;
- [ ] coletar duvidas e registrar ajustes finais realmente necessarios.

**Dry-run local (2026-06-22):** fluxo completo das 9 etapas do roteiro validado no app local (amostra `msc_2026-01.csv`, competencia 2026-01, score 76,4/banda C, 945 pendencias, 78 regras / 0 erro). Login, upload+execucao, score, pendencias (filtro ERRO 945->278), catalogo de 78 regras, exportacoes (Excel + PDF executivo de 1 pagina), superavit por FR, comparar (2025-13 -> 2026-01: -12,03 pts / +489 pendencias) e logout (rota protegida bloqueada) OK, zero erros de console. Evidencias em `doc/demo-evidence/`. Achados nao bloqueantes: formatacao `-R$ 0,00` (zero negativo) em saldos nulos; badge "73 regras" no Executivo (regras com pontuacao/pendencia) pode confundir vs. 78 do catalogo. Falta apenas a demo ao vivo com a equipe.

### F5-11 - Handoff operacional

Documento base: `doc/handoff.md` (criado; campos dependentes da PMJP marcados como `<a definir>`).

- [x] entregar manual do usuario e guia de operacao *(referenciados no handoff)*;
- [ ] registrar commit/versao publicada *(v0.1.0 / main; fixar o commit exato no deploy)*;
- [ ] confirmar rotina de backup, logs e atualizacao *(documentada; validar no ambiente alvo)*;
- [ ] definir responsaveis por suporte e escalonamento;
- [ ] encerrar formalmente a entrega.

---

## Backlog de Evolucao — Reuniao Bruno (2026-06-22)

Itens levantados em reuniao com o Bruno. Capturados via briefing; nao bloqueiam
o go-live atual. Itens 1 e 2 sao UX pequenas e relacionadas; o item 3 e um epico.

### UX-09 - Filtro por dimensao em Pendencias — CONCLUIDA

**Objetivo:** permitir filtrar a tela de Pendencias por dimensao/tipo de problema,
alem dos filtros atuais (Severidade, Regra, Conta).

- [x] backend: `GET /api/pendencias` aceita `dimensao` (mapeia a categoria da regra
      para a dimensao de pontuacao via `scoring_dimension`/`DIMENSION_CATEGORIES`);
- [x] frontend: seletor de dimensao no rail de `Pendencias.tsx` (5 dimensoes de score);
- [x] teste do filtro (backend) + verificacao manual.

Decisao: vocabulario sao as **5 dimensoes de pontuacao** (Estrutura, Fechamento,
IC_Dominio, PCASP_Completude, Temporal), coerente com as barras de score.

### UX-08 - Deep-link dimensao -> Pendencias filtradas — CONCLUIDA

**Objetivo:** clicar numa dimensao no score (Home/Executivo) abre Pendencias **ja
filtrada** por aquela dimensao.

- [x] linhas de dimensao do breakdown clicaveis (Home e Executivo);
- [x] navega para `/pendencias?dimensao=<dim>`; `Pendencias.tsx` le o query param;
- [x] o filtro vem pre-selecionado e a lista ja aparece filtrada.

Verificado: clicar "Fechamento" leva a Pendencias mostrando so as de Fechamento.

### EPIC-EDIT - Correcao assistida da MSC no sistema

**Objetivo:** corrigir pendencias editando os dados da MSC dentro do sistema,
reprocessar para ver o impacto, e exportar a MSC corrigida para reenvio ao SICONFI.

Decisoes do briefing (2026-06-22):

- **O que edita:** depende da regra/pendencia. Clicar na pendencia abre a linha da
  MSC daquela conta com o(s) campo(s) relevante(s) destacado(s) — pode ser um
  **valor** (saldo) ou um **classificador** (IC, ND, FS, FR...), conforme o que a
  regra apontou.
- **Persistencia:** original do upload fica **imutavel**; edicoes vao para uma
  **copia de trabalho** da MSC (por ente/competencia). Edicao em lote.
- **Revalidacao:** botao **"Reprocessar"** re-roda o pipeline sobre a copia de
  trabalho e atualiza pendencias/score (nao ao vivo por celula).
- **Entregavel final:** **exportar a MSC corrigida** (layout SICONFI) para reenvio.

Pontos em aberto (resolver no design do epico):

- mapear, por regra, qual(is) campo(s) sao editaveis para "consertar" aquela
  pendencia;
- trilha de auditoria (quem editou o que — modelo institucional, JWT ja identifica
  o usuario; ver `TECH-03`); revert/reset para o original; versionamento da copia
  de trabalho;
- validacao dos valores editados antes de aceitar; concorrencia (lock por
  ente/competencia ja existe);
- garantir que o CSV exportado bate exatamente com o layout MSC do SICONFI.

> Este epico precisa do seu proprio ciclo spec -> plano -> implementacao (e
> provavelmente ser quebrado em sub-tarefas) antes de codar.

---

## Fora do Fechamento Atual

Estes itens nao bloqueiam a entrega e nao devem disputar prioridade com go-live, UX ou treinamento.

| ID | Item | Condicao para iniciar |
|---|---|---|
| FUT-01 | Ranking Regional | obter e validar base comparativa externa de outros entes |
| FUT-02 | Recommendations engine avancado | aprovar novas heuristicas apos uso real da versao atual |
| FUT-03 | Refinamentos adicionais de Superavit | abrir somente se a validacao contabil exigir nova regra |

---

## Ordem Recomendada de Execucao

Concluido: `GO-01` (config; falta validar no servidor real), `UX-01` a `UX-06` (`#113`), `GO-04` (`#114`; falta exercitar no ambiente alvo), `TECH-01` (`#112`), `TECH-02`/`TECH-03`/`TECH-04` (decisoes de escopo encerradas), `GO-03` (smoke local; falta backup).

Restante:

1. `GO-02` - validacao contabil do Superavit com a equipe (dados reais da PMJP);
2. `GO-03` (backup) + validacao de `GO-01`/`GO-04` no ambiente alvo da PMJP;
3. `F5-10` - treinamento e demonstracao;
4. `F5-11` - handoff e encerramento.

---

## Referencias Ativas

- `README.md` - setup, comandos e superficie publica da API;
- `doc/manual_usuario.md` - fluxo de uso para equipe contabil;
- `doc/guia_operacao.md` - operacao, deploy, backup e troubleshooting;
- `doc/modelo_pontuacao.md` - regra de negocio do score;
- `doc/governanca_documental.md` - politica documental e arquitetura.
