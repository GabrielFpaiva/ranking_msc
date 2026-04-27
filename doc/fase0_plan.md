# Fase 0 — Frontend MCRA PMJP (React + FastAPI)

**Status:** Em andamento (F0-00.A e F0-00.B concluídos)
**Depende de:** Fase 4 (motor estável: 35 regras, score_engine, compare_periods, snapshots/Excel/log)
**Referência do handoff visual:** `psb/03 - Resources/SAMID Design System (1)/handoff/`

---

## Contexto

A interface antiga é Panel (Python) em `app/web_app.py` — um SPA single-page
com Tabs (Status Geral / Regras / Pendências + placeholders Fase 5). O design
não suporta drawers slide-in, heatmap denso clicável, animações, roteamento
por URL, fontes específicas (Inter Tight + Inter + JetBrains Mono) nem
fidelidade pixel-perfect com o handoff MCRA.

A Fase 0 substitui essa camada por **SPA Vite + React 18 + TypeScript** (em
`web/`) consumindo o motor via **FastAPI** (em `app/api/`). O motor Python
permanece intocado — só ganha dois novos módulos de agregação (`outputs/aggregations.py`
e `outputs/contas.py`) que são puros e testáveis isoladamente.

**Arquitetura:**

```
┌────────────────┐   HTTP/JSON    ┌──────────────────────┐
│  React SPA     │ ─────────────► │  FastAPI (app/api)   │
│  (web/)        │                │  ↓ chama direto      │
│  build → dist  │ ◄───────────── │  src/ranking_msc/*   │
└────────────────┘                └──────────────────────┘
```

Em **dev**: Vite (`localhost:5173`) + uvicorn (`localhost:8000`) com proxy.
Em **prod**: `uvicorn app.api.main:app` serve `/api/*` + `web/dist/` estático.

---

## Tasks F0-00 (fatias) — Bootstrap completo

| ID | Fatia | Descrição | Prioridade | Horas | Depende de | Status |
|---|---|---|---|---|---|---|
| F0-00.A | Scaffold | Vite+React+TS, tokens 1:1, layout shell (Sidebar+TopBar), 10 rotas placeholder, FastAPI shell + healthcheck. | Crítica | 8 | — | **Concluído** (commit 64fb6ee) |
| F0-00.B | Run + Pendências + Score | `POST /api/run`, `GET /api/competencias`, `/api/score`, `/api/score-history`, `/api/pendencias`. Home (upload→score→6m→top 8) e Pendências (filtros) wired ao motor real. `outputs/aggregations.py` parte 1. | Crítica | 12 | F0-00.A | **Concluído** (commit 8626586 · 20 testes API) |
| F0-00.C | Regras + Drawers | `GET /api/rules`, `/api/rules/:id`, `/api/heatmap`, `/api/rule-history/:id`, `/api/contas/:codigo`. Tela Regras (heatmap 35×6 + tabela). Drawer Regra (descrição, fórmula, ocorrências). Drawer Conta (saldos + classificadores PCASP). Estado global de drawer via Context. `outputs/aggregations.py` parte 2 (heatmap, rule_history). | Crítica | 14 | F0-00.B | A Fazer |
| F0-00.D | Caixa / Passivos / Superávit | `GET /api/caixa`, `/api/passivos`, `/api/superavit`. Telas equivalentes wired à MSC normalizada (filtragem por prefixo de conta, agregação por banco/FR). Para Superávit (resultado financeiro por FR), expor 501 "a ser implementado" se a derivação ainda não estiver no motor. `outputs/contas.py` novo. | Alta | 10 | F0-00.B | A Fazer |
| F0-00.E | Visões (Executivo, Comparar, Ranking, Execução) | `GET /api/compare?a=&b=` (wrap `compare_periods`), `/api/log?execucao_id=`, `/api/recommendations`. Telas Executivo (hero score + ações), Comparar (diff 2 colunas), Ranking (banner "fonte regional não integrada"), Execução (pipeline + log). | Alta | 10 | F0-00.B | A Fazer |
| F0-00.F | Polish + cutover Panel | `GET /api/exports/excel`. Botão "Exportar PDF" disabled (defer F0-06). Renomear `app/web_app.py` → `app/web_app_legacy.py`. Atualizar README com novo "como rodar". Validação visual contra os 12 PNGs. a11y básica (focus ring, alt, contraste AA). Smoke test de 10 rotas + 2 drawers. PR único squash. | Alta | 6 | F0-00.C, F0-00.D, F0-00.E | A Fazer |

**Total estimado:** ~60 horas

---

## Tasks F0-01+ (fora desta entrega)

Itens identificados durante a fase mas que ficam fora do escopo de F0-00.
Cada um vira PR próprio quando priorizado.

| ID | Task | Descrição | Depende de | Prioridade |
|---|---|---|---|---|
| F0-01 | Lint + build TS no CI | Adicionar GitHub Action para `cd web && npm ci && npm run lint && npm run build` no PR template. | F0-00.F | Alta |
| F0-02 | Recommendations engine | Lógica para derivar "ações recomendadas" (heurísticas a partir de top regras + dimensão fraca + tendência). | F0-00.E | Média |
| F0-03 | Ranking Regional — fonte de dados | Definir e plugar dataset de outros entes (planilha SICONFI, API STN ou import manual de CSVs) para popular `/api/ranking`. | F0-00.E | Baixa |
| F0-04 | Superávit financeiro por FR | Implementar derivação contábil (resultado financeiro = ativo financeiro − passivo financeiro por FR). | F0-00.D | Média |
| F0-05 | Panel cutover definitivo | Remover `app/web_app_legacy.py` + dependências `panel`, `plotly`, `bokeh` do `pyproject.toml`. | F0-00.F + 1-2 sprints de validação | Alta |
| F0-06 | Exportar PDF | Geração HTML→PDF com `weasyprint` ou `reportlab` para a Visão Executiva (1 página) + Pendências completas. | F0-00.F | Alta |
| F0-07 | Autenticação multiusuário | Login + token JWT + namespacing por usuário em snapshots. Substitui o hardcoded `usuario="sistema"`. | F0-00.F | Alta (produção) |
| F0-08 | Deploy (Docker + nginx) | Dockerfile multi-stage (build do web + uvicorn + Python deps), compose com volume persistente para `data/`. | F0-07 | Alta (produção) |

---

## Convenções de fatia

- **1 fatia = 1 commit interno** com mensagem `F0-00.X: descrição`.
- **Squash final** no merge: `F0-00: implement MCRA PMJP frontend (React + FastAPI, replacing Panel)`.
- Cada fatia deve passar `pytest`, `ruff check src/ tests/ app/`, `mypy src/ app/api/`, `cd web && npm run lint && npm run build`.
- Onde o motor não tem capacidade ainda: **endpoint retorna 501** com payload
  `{"detail": "a ser implementado", "code": "not_implemented", "see": "F0-XX"}`,
  e o front renderiza banner com a referência da task.

---

## Critério de aceite

- [ ] 10 rotas navegáveis pela sidebar (`/inicio` · `/executivo` · `/execucao` · `/regras` · `/pendencias` · `/caixa` · `/passivos` · `/superavit` · `/comparar` · `/ranking`).
- [ ] 2 drawers globais (regra + conta) abrem por click em qualquer tela; ESC e overlay fecham.
- [ ] Sidebar dark + canvas claro fiel aos screenshots; 3 famílias de fonte carregadas.
- [ ] Upload de CSV real → score, top regras, pendências, snapshot Excel — tudo persistido.
- [ ] Comparar competências real via `compare_periods`.
- [ ] Topbar exibe competência ativa (vinda do último run); chip de SICONFI.
- [ ] `pytest` ≥ 600 verdes, `ruff` + `mypy` + `tsc` + `eslint` + `vite build` limpos.
- [ ] README atualizado com o novo "como rodar".
- [ ] Panel preservado como `web_app_legacy.py` por 1-2 sprints.
