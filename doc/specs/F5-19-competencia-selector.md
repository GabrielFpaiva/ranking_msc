# F5-19 — Seletor de Competência na TopBar

> **Data:** 2026-06-22
> **Task:** F5-19
> **Status:** design aprovado, aguardando revisão do spec
> **Origem:** feedback do Gabriel — depois de enviar vários meses, não há como trocar a competência ativa entre as telas (fica preso no último upload).

## Problema

Hoje a competência ativa (`siconfi`/`competencia` no store) só é definida no
upload (`setLastRun`). Não existe UI para alternar entre as competências já
enviadas — o usuário fica preso no último mês processado. O `GET /api/competencias`
e o `store.setCurrent()` já existem, mas nada na UI os liga.

## Objetivo

Adicionar um seletor de competência na TopBar que liste os meses já enviados (do
ente ativo) e troque a competência ativa, fazendo todas as telas refletirem a
escolha — sem mudança de backend nem de outras telas.

## Escopo e premissas

- **Apenas competência** (um ente por enquanto). O ente (`siconfi`) segue como
  rótulo read-only. Multi-ente é futuro: o store e a API já são chaveados por
  ente, então adicionar depois um seletor de ente ao lado é incremental, sem
  retrabalho.
- **Fora de escopo:** seletor de ente; mudanças no Comparar; qualquer backend.

## Arquitetura

Mudança contida em **`web/src/components/TopBar.tsx`** (+ CSS em
`web/src/index.css`/equivalente se necessário). Nenhuma outra tela muda: todas já
re-fetcham via `useEffect` em `[siconfi, competencia]`, então trocar a competência
no store propaga sozinho.

### Dados

- `api.competencias(siconfi)` → `Competencia[]` (`{siconfi, competencia, has_resultado}`),
  já ordenado por competência desc.
- `store.useMCRA()` fornece `siconfi`, `competencia`, `setCurrent(siconfi, competencia)`.

### Componente (na TopBar)

Substitui o chip estático `samid-competencia` (hoje linhas ~82-87) por:

- Rótulo `ENTE {siconfi}` (read-only, inalterado).
- Um `<select className="samid-select">` (mesmo estilo do Comparar) com uma
  `<option>` por competência (valor = `competencia`, label = a própria
  competência; ex.: `2026-01`).
- `value` = `competencia` ativa do store.
- `onChange` → `setCurrent(siconfi, novoValor)`.

### Estado local da TopBar

- `const [comps, setComps] = useState<Competencia[]>([])`.
- `useEffect` dispara `api.competencias(siconfi)` quando há `siconfi`; guarda em
  `comps`. Dependências: `[siconfi, competencia]` — assim um upload novo (que muda
  `competencia`) força a re-busca e o novo mês aparece na lista.
- Padrão de cancelamento com flag `cancelled` (igual ao resto do código).

### Estados de borda

- **Sem `siconfi`** (nunca houve upload / após reset): mantém o placeholder atual
  ("COMPETÊNCIA / —"), sem `<select>`.
- **`siconfi` presente mas lista vazia ou carregando:** mostra a competência ativa
  como texto (fallback), sem opções; popula quando a lista chegar.
- **Erro ao listar:** cai para o chip estático (texto), sem quebrar a TopBar; o
  erro de competências não precisa de mensagem visível (é secundário ao fluxo).
- Se a `competencia` ativa não estiver na lista retornada (ex.: dado removido no
  servidor), ela ainda aparece selecionada (adicionar como opção sintética ou
  exibir o valor atual), evitando um `<select>` com `value` órfão.

## Contratos / compatibilidade

- Nenhuma assinatura de API ou store muda. `setCurrent` já existe.
- Exportação Excel/PDF na TopBar continua usando `siconfi`/`competencia` do store
  (agora podendo refletir o mês escolhido no dropdown).

## Testes / verificação

Não há runner de teste unitário no frontend (só `lint`/`typecheck`/`build`).
Verificação:

1. `cd web && npm run lint && npm run typecheck && npm run build` — verde.
2. Manual via navegador (Playwright): subir 2+ competências, confirmar que o
   dropdown lista os meses, trocar o mês e ver Score/Pendências/Caixa atualizarem;
   confirmar placeholder quando não há competência (estado pós-reset).

## Critério de aceite

Com ≥1 competência enviada, a TopBar mostra um dropdown dos meses do ente ativo;
selecionar um mês troca a competência ativa e todas as telas refletem; sem
competência, mantém o placeholder atual; `npm run typecheck`/`build` verdes.
