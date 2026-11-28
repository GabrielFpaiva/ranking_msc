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

**Persistência (F7-05/F7-06, 28/11/2026).** Decisão do Gabriel: um armazenamento único que
todos usam, com a origem como campo (opção 2, em vez de trocar por dentro de `read_snapshot`).

- Schema em `src/ranking_msc/io/migrations/0001_schema_inicial.sql` (psycopg 3, SQL puro;
  `scripts/db_migrate.py` aplica). RLS ligado sem policy: o Supabase expõe `public` pela REST.
- `ranking_msc.io.store`: `MatrizRef(siconfi, competencia, origem)` e o contrato
  `SnapshotStore` (`save_msc`/`load_msc`, `save_resultado`/`load_resultado`, `load_rule_ids`,
  `list_refs`). `PostgresStore` quando há `DATABASE_URL`; `ParquetStore` sem banco (testes e
  CLI local; prévia no caminho antigo, homologada em `<ente>/homologada/<mês>/`).
- Motor: `EngineContext.get_store()` e `ref()`; R054/R083 leem o mês anterior da mesma origem.
- Gravar a prévia de novo apaga a anterior (cascade leva execução e pendências); cada matriz
  guarda só a última execução. O score de cada execução vai para `historico_score`, que
  sobrevive à matriz apagada.
- O CSV original no Storage fica para a F7-10 (upload da prévia), que precisa da chave
  `service_role`.

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

**Resultado do spike F7-04 (27/11/2026): a CAPAG sai da MSC — João Pessoa dá B+, igual à oficial.**
Fonte oficial: planilha "Capag Municípios 2026 - 01/09/2026" do Tesouro Transparente (CKAN
`capag-municipios`), aba "CAPAG Ano Base 2025". Dados da MSC: dezembro (MSCC, mês 12) de 2023,
2024 e 2025, puxados pela API (ver 7.2). Valores = `ending_balance`.

| Indicador | Fórmula | MSC | Oficial | Nota |
|---|---|---|---|---|
| I — Endividamento | DC / RCL | 0,260358 | 0,260358 | A |
| II — Poupança corrente | média 50/30/20 (ano, -1, -2) de despesa corrente / RCA | 0,891227 | 0,891227 | B |
| III — Liquidez relativa | (DCB − OF + insuficiência) / RCL | ≈0,03052 | 0,030504 | B |
| CAPAG | combinação (A, B, B) | B | B | |
| Com ICF Aicf | B → B+ | **B+** | **B+** | |

Como cada variável sai da MSC (exato, centavo a centavo, salvo onde indicado):

- **Despesa corrente (II):** contas `6221304` + `6221305` + `6221307` com ND começando em 3.
- **RCA:** `6212` com NR iniciada em 1 (receita corrente) + `6212` com NR iniciada em 7
  (intra) + deduções `6213` com NR iniciada em 1 (`6213101` = FUNDEB; demais = outras).
- **RCL:** receita corrente líquida de deduções (RCA sem intra) − contribuição do servidor ao
  RPPS (NR `1215…`) − compensação previdenciária (NR `19990301`, `19990302`) − rendimentos do
  RPPS (NR `13210401`). Bateu exato para JP; a lista de deduções precisa ser conferida no MDF
  antes de generalizar.
- **Dívida consolidada:** empréstimos e financiamentos (`2121`, `2122`, `2123`, `2221`, `2222`,
  `2223`, qualquer FP) + precatórios a partir de 05/05/2000 (`211110503`) + renegociação de
  dívidas com fornecedores (`213110103`, `223110103`). Para outros entes, entram também as
  demais contas de precatório e parcelamento — conferir no MDF.
- **DCB (caixa bruto, não vinculados):** `1111` exceto `11112` (conta única, espelhada em
  `218920106`), FR com código-base 500/501/502, PO do Executivo e RPPS (Legislativo `20231`
  fica fora: é o RGF do Executivo).
- **OF (obrigações financeiras, não vinculados):** RP liquidados não pagos de exercícios
  anteriores (`6321000` + `6313000`), RP liquidados não pagos do exercício (`6327000`),
  RP não processados de exercícios anteriores (`6311000`) — exatos; demais obrigações
  financeiras (`2188` + `2189` sem `218920106` + `214`) ficou ~R$ 81 mil abaixo do RGF
  (efeito de 0,002 p.p. no indicador). Insuficiência de caixa das fontes vinculadas não foi
  conferida (usar DCL negativa por fonte vinculada).

Faixas e combinação (tiradas das 5.570 linhas da planilha oficial):

- I: A < 60%, B < 100%, C ≥ 100%. II: A < 85%, B < 95%, C ≥ 95%. III: A ≥ 5%, B > 0, C ≤ 0.
- Final: (A,A,A), (A,A,B), (A,B,A) → A; (A,B,B), (B,A,A), (B,A,B), (B,B,A), (B,B,B),
  (C,A,A), (C,B,A), (C,B,B) → B; (C,C,C) → D; o resto → C.
- ICF do Ranking: Aicf sobe A → A+ e B → B+; Eicf torna "n.e." (não elegível). O ICF pode vir da
  nossa própria estimativa do Ranking (score), o que liga a F7-19 ao motor.

Para a F7-19: a estimativa usa três dezembros (dois anteriores vêm da API, sem upload) e deve
ter teste de regressão com os números oficiais de JP 2025 acima.

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
