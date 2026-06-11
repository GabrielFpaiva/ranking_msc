# Backlog Operacional - MCRA PMJP

> **Atualizado:** 2026-06-01
> **Fonte unica de planejamento corrente:** este arquivo
> **Estado atual:** motor concluido (`78/78` regras), Fase 4 encerrada e Fase 5 em fechamento operacional.
> **Ultima validacao completa:** `make validate` verde em 2026-06-01 (`979` testes aprovados, `1` ignorado, cobertura `95,56%`, lint, tipos e build frontend).

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
| Frontend oficial | Concluido com hardening visual pendente | React + FastAPI substituiu a interface Panel |
| Exportacoes | Concluido com decisao de escopo pendente | Excel de pendencias e PDF executivo; confirmar se o PDF tambem deve conter pendencias completas |
| Autenticacao | Concluido com decisao de modelo pendente | JWT multiusuario implementado; confirmar se artefatos devem ser compartilhados por ente ou isolados por usuario |
| Deploy | Concluido na aplicacao com publicacao pendente | Docker, compose e testes E2E prontos; definir reverse proxy e terminacao HTTP/TLS no ambiente alvo |
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
- [ ] validar login e `GET /api/health` no ambiente real.

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

A antiga task F0-08 citava `Docker + nginx`. O projeto entrega container e compose da aplicacao na porta `8000`, mas ainda nao define como a prefeitura publicara o servico.

Checklist:

- [ ] confirmar se a infraestrutura alvo ja possui reverse proxy institucional;
- [ ] definir terminacao HTTP/TLS, hostname e porta publica;
- [ ] decidir se nginx pertence a este repositorio ou a infraestrutura externa;
- [ ] documentar a configuracao adotada no guia de operacao;
- [ ] validar `/api/health`, login e upload atraves do endpoint publico.

**Criterio de aceite:** topologia de publicacao definida, documentada e exercitada no ambiente alvo.

---

## P1 - Hardening de Frontend e Usabilidade

### UX-01 - Limpar navegacao, acoes sem funcao e sessao

- [x] remover sublinhado dos links da sidebar;
- [ ] remover o botao `Reprocessar` (sem funcionalidade prevista para go-live);
- [ ] remover o botao de notificacao/sino (sem handler);
- [ ] auditar outros botoes com placeholder ou handler vazio no TopBar, Home, Pendencias, Executivo, Regras e drawers;
- [ ] exibir erro de exportacao no TopBar em vez de silenciar falhas com `.catch(() => undefined)`;
- [ ] adicionar botao `Sair` em local previsivel (TopBar);
- [ ] exibir o usuario logado junto da acao de sair;
- [ ] limpar token ao sair e redirecionar para `/login`;
- [ ] garantir que rotas protegidas nao continuem acessiveis apos logout.

**Criterio de aceite:** nenhuma acao visivel fica sem resposta funcional; usuario consegue sair sem limpar navegador manualmente.

### UX-02 - Tornar o fluxo principal autoexplicativo

- [ ] revisar textos de login, upload, score, pendencias, executivo e comparar;
- [ ] adicionar chamadas diretas para `Inicio` nos estados vazios;
- [ ] indicar visualmente linhas clicaveis para abrir regra ou conta;
- [ ] revisar mensagens de erro para linguagem operacional;
- [ ] validar o fluxo com pelo menos um usuario da equipe contabil.

**Criterio de aceite:** usuario consegue executar `login -> upload -> revisar pendencias -> exportar` sem orientacao paralela.

### UX-03 - Melhorar Pendencias

- [ ] implementar paginacao real usando `offset` e `limit`;
- [ ] mostrar intervalo exibido e total de resultados;
- [ ] preservar clareza dos filtros por severidade, regra e conta;
- [ ] validar tabela com grandes volumes de pendencias.

**Criterio de aceite:** usuario navega por todas as pendencias sem depender exclusivamente do Excel.

### UX-04 - Revisar responsividade minima

- [ ] adicionar breakpoints para sidebar, TopBar, grids e filtros;
- [ ] garantir uso aceitavel em notebook com largura reduzida;
- [ ] verificar tabelas, heatmap e drawers sem corte de conteudo.

**Criterio de aceite:** telas principais permanecem legiveis em notebook padrao e viewport reduzida acordada com a PMJP.

### UX-05 - Alinhar tela de login ao design MCRA

- [ ] substituir estilos inline pelo kit visual existente;
- [x] alinhar cores e tipografia base aos tokens SAMID;
- [ ] confirmar identificacao institucional;
- [ ] revisar feedback de credenciais invalidas e expiracao de sessao.

**Criterio de aceite:** login parece parte do mesmo produto e comunica falhas de forma clara.

### UX-06 - Padronizar mensagens de erro do frontend

**Problema observado:** mensagens de erro estao exibindo codigos tecnicos, como `401`, em vez de feedback claro para o usuario.

Checklist:

- [ ] mapear respostas comuns da API (`401`, `403`, `404`, `409`, `422`, `500`) para mensagens amigaveis;
- [ ] tratar credenciais invalidas, sessao expirada e falta de permissao com textos especificos;
- [ ] evitar exibir codigo bruto ou payload tecnico como mensagem principal;
- [ ] manter detalhe tecnico apenas em area secundaria/log quando util para suporte;
- [ ] aplicar o padrao nas telas de login, upload, exportacoes, consultas e comparacao.

**Criterio de aceite:** usuario ve mensagens operacionais claras e nenhum erro comum aparece apenas como codigo HTTP bruto.

---

## P1 - Revisao Tecnica Final

### TECH-01 - Revisar residuos documentais e comentarios obsoletos

- [ ] remover comentarios antigos sobre semaforo futuro no executor, pois o lock por periodo ja existe;
- [ ] atualizar `doc/governanca_documental.md`: refactor arquitetural `#98` ja foi concluido;
- [ ] revisar referencias antigas a placeholders e ao Ranking Regional na documentacao ativa;
- [ ] manter referencias historicas apenas nos documentos classificados como historicos.

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

1. `GO-01` - configuracao operacional real;
2. `GO-02` - validacao contabil do Superavit;
3. `UX-01` a `UX-05` - rodada unica de hardening visual e intuitividade;
4. `GO-04` - definir topologia de publicacao;
5. `TECH-01` a `TECH-04` - limpeza e decisoes finais de escopo;
6. `GO-03` - smoke test no ambiente alvo;
7. `F5-10` - treinamento;
8. `F5-11` - handoff e encerramento.

---

## Referencias Ativas

- `README.md` - setup, comandos e superficie publica da API;
- `doc/manual_usuario.md` - fluxo de uso para equipe contabil;
- `doc/guia_operacao.md` - operacao, deploy, backup e troubleshooting;
- `doc/modelo_pontuacao.md` - regra de negocio do score;
- `doc/governanca_documental.md` - politica documental e arquitetura.
