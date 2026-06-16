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
| Exportacoes | Concluido com decisao de escopo pendente | Excel de pendencias e PDF executivo; confirmar se o PDF tambem deve conter pendencias completas |
| Autenticacao | Concluido com decisao de modelo pendente | JWT multiusuario implementado; confirmar se artefatos devem ser compartilhados por ente ou isolados por usuario |
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
- [ ] backup.

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

---

## P1 - Revisao Tecnica Final

### TECH-01 - Revisar residuos documentais e comentarios obsoletos

- [x] remover comentarios antigos sobre semaforo futuro no executor, pois o lock por periodo ja existe;
- [x] atualizar `doc/governanca_documental.md`: refactor arquitetural `#98` ja foi concluido;
- [x] revisar referencias antigas a placeholders e ao Ranking Regional na documentacao ativa;
- [x] manter referencias historicas apenas nos documentos classificados como historicos.

### TECH-02 - Decidir escopo do Excel por categoria

A antiga task F3-16 ficou parcialmente aberta porque o Excel nao possui aba separada por categoria.

- [ ] confirmar com a equipe se a organizacao atual do Excel atende ao uso real;
- [ ] encerrar formalmente a necessidade ou abrir task especifica de melhoria.

### TECH-03 - Decidir isolamento multiusuario dos artefatos

A antiga task F0-07 previa namespacing por usuario em snapshots. Hoje o login JWT identifica quem executou, e o lock evita escrita concorrente, mas snapshots e relatorios permanecem compartilhados por `siconfi + competencia`.

- [ ] confirmar se usuarios da PMJP devem enxergar o mesmo conjunto institucional de artefatos;
- [ ] se houver isolamento por usuario, definir impacto em snapshots, relatorios, comparacoes, exportacoes e locks;
- [ ] encerrar formalmente o requisito antigo ou abrir task especifica de implementacao.

**Criterio de aceite:** modelo de visibilidade institucional documentado e sem ambiguidade para producao.

### TECH-04 - Decidir escopo do PDF de pendencias

A antiga task F0-06 previa `Visao Executiva (1 pagina) + Pendencias completas`. Hoje o PDF entrega a visao executiva e o Excel entrega as pendencias completas.

- [ ] confirmar se Excel completo + PDF executivo atende ao fluxo operacional;
- [ ] se necessario, definir se as pendencias entram no mesmo PDF ou em exportacao separada;
- [ ] encerrar formalmente o requisito antigo ou abrir task especifica de implementacao.

**Criterio de aceite:** formato final de distribuicao aprovado pela equipe usuaria.

---

## P2 - Treinamento e Entrega

### F5-10 - Treinamento e demonstracao

- [ ] preparar roteiro curto baseado no fluxo operacional;
- [ ] demonstrar login, upload, score, pendencias, regras, exportacoes, superavit e comparar;
- [ ] coletar duvidas e registrar ajustes finais realmente necessarios.

### F5-11 - Handoff operacional

- [ ] entregar manual do usuario e guia de operacao;
- [ ] registrar commit/versao publicada;
- [ ] confirmar rotina de backup, logs e atualizacao;
- [ ] definir responsaveis por suporte e escalonamento;
- [ ] encerrar formalmente a entrega.

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

Concluido: `GO-01` (config; falta validar no servidor real), `UX-01` a `UX-06` (`#113`), `GO-04` (`#114`; falta exercitar no ambiente alvo), `TECH-01` (`#112`), `GO-03` (smoke local; falta backup).

Restante:

1. `GO-02` - validacao contabil do Superavit com a equipe (dados reais da PMJP);
2. `TECH-02` a `TECH-04` - decisoes finais de escopo (Excel por categoria, multiusuario, PDF);
3. `GO-03` (backup) + validacao de `GO-01`/`GO-04` no ambiente alvo da PMJP;
4. `F5-10` - treinamento e demonstracao;
5. `F5-11` - handoff e encerramento.

---

## Referencias Ativas

- `README.md` - setup, comandos e superficie publica da API;
- `doc/manual_usuario.md` - fluxo de uso para equipe contabil;
- `doc/guia_operacao.md` - operacao, deploy, backup e troubleshooting;
- `doc/modelo_pontuacao.md` - regra de negocio do score;
- `doc/governanca_documental.md` - politica documental e arquitetura.
