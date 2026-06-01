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
| Exportacoes | Concluido | Excel de pendencias e PDF executivo |
| Autenticacao | Concluido tecnicamente | JWT multiusuario; falta configurar credenciais reais no ambiente operacional |
| Deploy | Concluido tecnicamente | Docker, compose e testes E2E de deploy |
| Superavit por FR | Concluido tecnicamente | Falta validacao contabil com dados reais da PMJP |
| Ranking Regional | Fora do fechamento | Depende de base comparativa externa ainda nao definida |

---

## P0 - Bloqueadores Para Go-Live

### GO-01 - Preparar configuracao operacional real

**Objetivo:** publicar um `config/settings.yaml` valido no servidor da prefeitura.

Checklist:

- [ ] recriar o arquivo operacional a partir de `config/settings.yaml.example`;
- [ ] habilitar as `78` regras atuais;
- [ ] remover campos legados como `allowed_users`;
- [ ] gerar `security.secret_key` segura;
- [ ] cadastrar ao menos um usuario com hash bcrypt;
- [ ] confirmar `app.esfera`, paths, permissoes e volumes Docker;
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

- [ ] login;
- [ ] upload de CSV MSC real;
- [ ] score e banda;
- [ ] pendencias e filtros;
- [ ] detalhe de regra e conta;
- [ ] exportacao Excel;
- [ ] exportacao PDF;
- [ ] superavit por FR;
- [ ] comparacao entre competencias;
- [ ] lock de processamento concorrente para o mesmo ente e competencia;
- [ ] backup e leitura dos logs.

**Criterio de aceite:** fluxo completo executado no ambiente alvo sem erro bloqueador.

---

## P1 - Hardening de Frontend e Usabilidade

### UX-01 - Limpar navegacao e acoes sem funcao

- [x] remover sublinhado dos links da sidebar;
- [ ] implementar logout e exibir o usuario autenticado;
- [ ] remover ou implementar o botao `Reprocessar`;
- [ ] remover ou implementar o sino de notificacoes;
- [ ] exibir erro de exportacao no TopBar em vez de silenciar falhas.

**Criterio de aceite:** nenhuma acao visivel parece clicavel sem produzir resultado compreensivel.

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
- [ ] alinhar cores, tipografia e identificacao institucional;
- [ ] revisar feedback de credenciais invalidas e expiracao de sessao.

**Criterio de aceite:** login parece parte do mesmo produto e comunica falhas de forma clara.

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
4. `TECH-01` e `TECH-02` - limpeza e decisao final de escopo;
5. `GO-03` - smoke test no ambiente alvo;
6. `F5-10` - treinamento;
7. `F5-11` - handoff e encerramento.

---

## Referencias Ativas

- `README.md` - setup, comandos e superficie publica da API;
- `doc/manual_usuario.md` - fluxo de uso para equipe contabil;
- `doc/guia_operacao.md` - operacao, deploy, backup e troubleshooting;
- `doc/modelo_pontuacao.md` - regra de negocio do score;
- `doc/governanca_documental.md` - politica documental e arquitetura.
