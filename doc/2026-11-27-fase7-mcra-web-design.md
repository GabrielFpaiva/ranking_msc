# Fase 7 — MCRA web compartilhado (design)

> Origem: reunião de 27/11/2026 com a equipe do Ranking MSC. Brainstorm com o Gabriel no mesmo dia.
> Status: rascunho para aprovação. Depois de aprovado, vira plano e tasks no ClickUp.

## 1. Intenção

Hoje o MCRA é um app desktop Windows: cada pessoa sobe a matriz no próprio PC e ninguém vê o
que o outro enviou. A equipe quer **um sistema só, na web, onde todos veem as mesmas matrizes**,
com histórico de quem enviou, a matriz homologada puxada direto do SICONFI, um jeito de marcar
pendência que não faz sentido, e mais visão do dado (balancete, histórico, CAPAG). Referência
visual e de funções: anoma.com.br (pré-visualização de documentos, visual) e falconrank.

## 2. Objetivos

1. Voltar a ser web, com dado compartilhado entre usuários.
2. Matriz **prévia** (CSV enviado pela equipe para testar antes do SICONFI) e matriz
   **homologada** (puxada da API do SICONFI), por mês e ano.
3. Registro de quem enviou e quando; poder apagar prévia; sobrepor prévia do mesmo mês/ano.
4. Ao carregar a prévia, perguntar ano e mês.
5. Botão "esse erro não faz sentido" (dispensar pendência).
6. Cada pendência com o código oficial da verificação do Ranking e a dimensão oficial (D1–D4).
7. Trazer para o motor as verificações do Ranking de municípios que ainda não temos.
8. Visualizar o balancete no sistema, pesquisável, com totalizador.
9. Histórico do ranking mês a mês.
10. Estimativa da CAPAG.
11. Tirar os botões de exportar PDF/Excel repetidos.

## 3. Não-objetivos

- Estados. O sistema atende só município.
- Nota oficial da CAPAG. É estimativa, marcada como tal.
- Manter o app desktop. Vai para `doc/legacy/`, como foi o Docker.
- Guardar várias prévias do mesmo mês. A nova substitui a anterior (o registro fica).

## 4. Anti-objetivos (falha mesmo funcionando)

- Um clique esconder erro real que o SICONFI vai cobrar.
- Dado sumir no reinício do servidor (o problema do Render free com disco local).
- Mostrar estimativa (CAPAG, verificação nova não calibrada) como se fosse número oficial.
- Mostrar dado velho do SICONFI como atual (regra que a tela de Entregas já segue).

## 5. Restrições

- **Custo zero:** Render free (API + front) e Supabase free (Postgres + Storage).
- Supabase free **pausa após 7 dias sem uso**; Render free tem cold start de ~13 s.
- A MSC prévia ainda não é pública e fica em servidor de terceiro. Sem dado pessoal, mas a
  Controladoria deve saber.
- Convenções do `CLAUDE.md` do projeto valem (dataclasses, exceções próprias, testes, ruff, mypy).
- O motor (regras, scoring) não muda de contrato: `read_msc_csv → normalize_ic → run_engine`.

## 6. Abordagens consideradas

| | Abordagem | Troca |
|---|---|---|
| A | Base primeiro (migrar tudo), depois funções | Cada coisa feita uma vez; semanas sem nada visível |
| B | Funções no desktop, migrar depois | Novidade rápida; prévia/dispensadas/histórico reescritos para o banco |
| **C** | **Três trilhas: sem-banco agora, base, funções sobre a base** | **Escolhida.** Riscos (API, CAPAG) testados antes de virar promessa; nada feito duas vezes |

Também consideradas para hospedagem: Render pago com disco (~US$ 7–10/mês, menor mudança) e
Render free sem persistência (só demo). Escolhido Render free + Supabase por custo zero.

## 7. O que foi decidido

### 7.1 Plataforma
- Render free roda a API FastAPI e serve o build do React.
- Supabase: **Postgres** para matrizes, registros de envio, resultados de regras, dispensadas,
  usuários e histórico; **Storage** para o CSV original da prévia.
- Excel e PDF gerados na hora a partir do banco (não são guardados).
- Login segue o JWT atual; usuários migram do `settings.yaml` para tabela no banco.
- Ping semanal para o Supabase não pausar (mesma ideia do keep-alive do Render).

### 7.2 Ciclo da matriz
- **Prévia:** upload do CSV. Usuário escolhe ano e mês; o sistema confere com a competência
  do CSV e recusa se não bater. Se já existe prévia do mesmo mês/ano, avisa ("já existe
  prévia de 10/2026 enviada por X em dd/mm, substituir?") e substitui. Grava quem e quando.
  Pode ser apagada. O registro de envio/substituição/exclusão fica no histórico.
- **Homologada:** puxada da API do SICONFI (`apidatalake.tesouro.gov.br`, endpoints
  `msc_patrimonial`, `msc_orcamentaria`, `msc_controle`) e convertida para o schema
  `FACT_MSC_COLUMNS`. Mesmas regras rodam nela. Não se apaga (voltaria na próxima busca).
- Tela por mês mostra prévia e homologada lado a lado, com score de cada uma.

**Resultado do spike F7-03 (27/11/2026): a API devolve exatamente o CSV homologado.**
João Pessoa (`id_ente=2507507`), 2025:

| Matriz | Parâmetros | Linhas API = CSV | Chamadas | Tempo |
|---|---|---|---|---|
| 12/2025 | `co_tipo_matriz=MSCC&me_referencia=12` | 28.847 (28.742 chaves) | 25 | 49 s |
| Encerramento (13) | `co_tipo_matriz=MSCE&me_referencia=12` | 21.725 | 24 | 39 s |

Comparação por chave (conta + ICs + tipo_valor + natureza): nenhuma chave só de um lado,
nenhum valor diferente. Notas para a F7-12:

- Uma chamada por classe (1–8) × `id_tv` (`beginning_balance`, `period_change`,
  `ending_balance`); `limit` 5000, paginar por `offset` enquanto `hasMore`.
- Campos → IC: `poder_orgao`→PO, `financeiro_permanente`→FP, `divida_consolidada`→DC,
  `fonte_recursos`→FR (4 dígitos, já com o dígito do exercício), `complemento_fonte`→CO,
  `natureza_receita`→NR, `natureza_despesa`→ND, `funcao`+`subfuncao`→FS, `ano_inscricao`→AI.
  `ano_fonte_recursos` repete o 1º dígito da FR; `educacao_saude` veio sempre vazio.
- O dado é igual, mas a **ordem das ICs** no CSV segue o leiaute por tipo de conta (ex.: receita
  usa PO, FR, CO, NR; despesa PO, FS, FR, CO, ND, AI). O adaptador precisa gravar nessa ordem,
  senão regras de leiaute (R033, R082) acusam erro que a matriz homologada não tem.
- ~40–50 s por matriz: buscar em segundo plano e mostrar a data da busca (cache).

### 7.3 Dispensar pendência
- Chave: **regra + conta**. Vale para sempre, em todos os meses, prévia e homologada.
- Motivo obrigatório; grava quem e quando. Qualquer usuário pode dispensar.
- Lista "Dispensadas", com desfazer.
- Score mostrado com e sem dispensadas. A lista serve de insumo para calibrar regras.

### 7.4 Verificações oficiais
- Tabela de-para: verificação oficial do Ranking de **municípios** (código tipo `D2_00034`,
  dimensão D1–D4, descrição) × regra nossa (`R082`). Montada do que o site do Ranking publica,
  revisada pela equipe antes de virar task.
- Pendência mostra o código e a dimensão oficiais, além da dimensão interna.
- Verificações sem regra nossa viram regras novas (fluxo da seção 4.1 do `CLAUDE.md`).
- "Ver onde": pendência leva à conta no visualizador do balancete.

### 7.5 Balancete
- Visualização da matriz (prévia ou homologada) no sistema: busca por conta e descrição,
  filtros, linhas de **total por classe e por grupo** (débito, crédito, saldo).
- Referência: a pré-visualização de documentos do anoma.

### 7.6 Histórico e CAPAG
- Histórico mês a mês (ver questão aberta 9.2 sobre o que exatamente se mostra).
- CAPAG estimada a partir da matriz, pelo método vigente (Portaria MF 1.583/2023). Parte dos
  indicadores vem de RREO/RGF; a estimativa precisa bater com a CAPAG oficial de João Pessoa
  antes de aparecer como nota. Amostras de RREO/RGF/DCA em `ref/amostras/`.

### 7.7 Limpeza
- Exportar Excel aparece em `Home.tsx` e `Pendencias.tsx`; Exportar PDF em `Home.tsx` e
  `TopBar.tsx`. Proposta: ficar só na `TopBar` (PDF e Excel), que já aparece em toda tela.

## 8. Trilhas (ordem)

1. **Sem depender do banco**
   - Tirar botões repetidos.
   - Montar a tabela de-para das verificações oficiais.
   - Spike API: puxar 12/2025 homologada e comparar o resultado das regras com o CSV que temos.
   - Spike CAPAG: calcular a estimativa para João Pessoa e comparar com a oficial.
2. **Base:** schema Postgres, Storage, camada de persistência no lugar dos Parquet/arquivos,
   usuários no banco, deploy Render + Supabase, keep-alive, desktop para `legacy`.
3. **Funções sobre a base:** prévia (ano/mês, sobrepor, quem enviou, apagar), homologada via
   API, dispensar, código oficial nas pendências, balancete com totalizador, histórico mensal,
   regras novas, CAPAG (se o spike confirmar), visual novo.

## 9. Questões abertas

1. ~~Visual~~ — decidido: telas na linha do anoma (fundo claro, cards com ícone, mais respiro,
   tipografia limpa). Identidade atual é vermelho JP `#E1251B` + charcoal `#1B1B1F`
   (`web/src/styles/tokens.css`). Decisão minha, a confirmar: manter o vermelho JP como acento
   (é a marca da Prefeitura) em vez de trocar para o verde-petróleo do anoma.
2. ~~Histórico~~ — decidido: é o **nosso score** de cada mês (prévia e homologada), não a
   posição oficial do Ranking do Tesouro.

Design aprovado pelo Gabriel em 27/11/2026.

## 10. Deixado para quem constrói

- Modelo de tabelas no Postgres e como trocar a leitura/escrita de snapshot sem mexer nas regras.
- Como paginar e cachear as chamadas da API do SICONFI.
- Dados que já existem nas instalações desktop: começar o banco vazio e reprocessar as
  amostras de `ref/amostras/` (decisão minha; ninguém usa o desktop em produção).
- Busca da homologada: botão "buscar no SICONFI" com cache e data da busca, sem agendamento
  (Render free não tem cron confiável) — decisão minha.
