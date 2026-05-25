# Ranking MSC — Motor de Validação Contábil

Aplicação web interna para validação da Matriz de Saldos Contábeis (MSC) conforme regras do Ranking SICONFI. Motor Python + interface React/TypeScript (SPA) + FastAPI, para uso na intranet da prefeitura.

---

## Descrição do Projeto

### O que faz

O Ranking MSC recebe o CSV mensal da MSC, aplica regras de validação e produz:

- **Pendências detalhadas** por regra, conta contábil e severidade.
- **Score de conformidade** para a competência processada.
- **Relatórios Excel** com evidências para correção.
- **Snapshots Parquet** para histórico e dashboards.
- **Logs estruturados** (JSON Lines) para auditoria.

### Arquitetura

```
┌────────────────┐   HTTP/JSON    ┌──────────────────────┐
│  React SPA     │ ─────────────► │  FastAPI (app/api)   │
│  (web/)        │                │  ↓ chama direto      │
│  build → dist  │ ◄───────────── │  src/ranking_msc/*   │
└────────────────┘                └──────────────────────┘
```

Em **dev**: Vite (`localhost:5173`) + uvicorn (`localhost:8000`) com proxy.
Em **prod**: `uvicorn app.api.main:app` serve `/api/*` + `web/dist/` estático.

### Fluxo de dados

1. **Upload** — Usuário envia CSV MSC via interface web.
2. **Leitura** — `reader_msc.py` extrai metadados (competência, SICONFI) e produz DataFrame bruto.
3. **Normalização** — `ic_normalize.py` expande colunas IC/TIPO nos 9 atributos: PO, FP, DC, FS, FR, CO, NR, ND, AI.
4. **Execução** — `executor.py` carrega regras habilitadas do YAML, executa cada uma e consolida pendências.
5. **Saída** — Snapshots Parquet são gravados atomicamente; relatórios Excel ficam disponíveis para download; logs vão para arquivo JSON Lines.

---

## Como rodar

### Pré-requisitos

- Python 3.11+
- Node.js 18+ e npm
- `make`

### Setup local

```bash
# Clonar e entrar no repositório
cd ranking_msc

# Bootstrap único: venv + deps Python + deps frontend + config + diretórios
make bootstrap
```

O target `bootstrap` faz:

- cria `.venv`
- instala o pacote Python em modo editável com `[dev]`
- instala as dependências do frontend em `web/`
- cria `config/settings.yaml` se ele ainda não existir
- cria `data/snapshots`, `data/reports` e `data/logs`

Se você mover o projeto de pasta e a `.venv` parar de funcionar, recrie-a com:

```bash
rm -rf .venv
make bootstrap
```

### Rodar em desenvolvimento (frontend + backend)

**Terminal 1 — Backend FastAPI:**

```bash
make dev-backend
```

**Terminal 2 — Frontend React (Vite):**

```bash
make dev-frontend
```

Acesse `http://localhost:5173` no navegador. O Vite faz proxy de `/api/*` para o backend na porta 8000.

### Rodar em produção

```bash
# Build do frontend
make frontend-build

# Servidor (front + API unificados)
.venv/bin/python -m uvicorn app.api.main:app --host 0.0.0.0 --port 8000
```

O FastAPI serve `web/dist/` como estático em `/` e as rotas em `/api/*`.

### Rodar com Docker Compose

Pré-requisito: Docker com `docker compose` disponível.

```bash
# Sobe a stack local já com build
docker compose up --build

# Ou via Makefile
make docker-up
```

A aplicação fica acessível em `http://localhost:8000`, servindo:

- frontend React já buildado em `/`
- API FastAPI em `/api/*`

Volumes montados por padrão:

- `./data:/app/data`
- `./config:/app/config`

Comportamento do container:

- se `config/settings.yaml` não existir, o entrypoint copia `config/settings.yaml.example`;
- diretórios `data/snapshots`, `data/reports` e `data/logs` são criados automaticamente.

Para derrubar a stack:

```bash
docker compose down
# ou
make docker-down
```

### Configuração e variáveis de ambiente

#### Arquivo `config/settings.yaml`

O arquivo real de configuração é `config/settings.yaml`.
Se ele não existir:

- `make bootstrap` copia `config/settings.yaml.example`;
- o container também copia `config/settings.yaml.example` no startup.

Estrutura suportada hoje:

```yaml
app:
  title: "Ranking MSC — Validação Contábil"
  debug: false
  esfera: "municipal"

paths:
  data_dir: "./data"
  snapshots_dir: "./data/snapshots"
  reports_dir: "./data/reports"
  logs_dir: "./data/logs"
  ref_dir: "./ref"

rules:
  enabled: ["R001", "R002", "..."]
  fail_fast: false

security:
  max_concurrent_jobs: 3
  allowed_users: []
```

Campos e efeito operacional:

| Seção | Campo | Obrigatório | Default | Efeito |
|---|---|---|---|---|
| `app` | `title` | não | `Ranking MSC` | título lógico da aplicação |
| `app` | `debug` | não | `false` | flag de debug da app |
| `app` | `esfera` | não | `municipal` | base para regras como `R039` |
| `paths` | `data_dir` | não | `./data` | diretório raiz lógico de dados |
| `paths` | `snapshots_dir` | não | `./data/snapshots` | leitura e escrita de snapshots |
| `paths` | `reports_dir` | não | `./data/reports` | saída dos relatórios Excel |
| `paths` | `logs_dir` | não | `./data/logs` | destino do `ranking_msc.jsonl` |
| `paths` | `ref_dir` | não | `./ref` | tabelas de referência do motor |
| `rules` | `enabled` | não | `[]` | lista de regras executadas |
| `rules` | `fail_fast` | não | `false` | interrompe no primeiro erro fatal |
| `security` | `max_concurrent_jobs` | não | `3` | reservado para hardening multiusuário |
| `security` | `allowed_users` | não | `[]` | reservado para auth/autorização futura |

Observações importantes:

- `config/settings.yaml` real não deve ser commitado.
- Caminhos relativos são resolvidos a partir da raiz do projeto `/app` no container e da raiz do repositório em dev local.
- Em CLI (`scripts/run_pipeline.py`, `scripts/run_batch.py`, `scripts/compare_periods.py`), `--output-dir` sobrescreve os diretórios `snapshots/`, `reports/` e `logs/` sob um novo diretório base.

#### Variáveis de ambiente

Variáveis efetivamente suportadas hoje:

| Variável | Onde funciona | Default | Efeito |
|---|---|---|---|
| `PORT` | container / `docker-compose` | `8000` | porta do `uvicorn` no entrypoint |
| `RANKING_MSC_CONFIG` | loader Python quando `load_settings()` é chamado sem path explícito | `config/settings.yaml` | troca o arquivo de configuração usado por scripts/uso programático |

Limitação atual da API FastAPI:

- `app/api/deps.py` carrega explicitamente `PROJECT_ROOT / config/settings.yaml`;
- portanto, a variável `RANKING_MSC_CONFIG` **não altera** a configuração da API web hoje;
- para mudar a configuração do servidor web, use o arquivo `config/settings.yaml` montado no volume `./config:/app/config`.

#### Dev vs produção vs Docker

| Ambiente | Como a config é resolvida | Paths de dados mais comuns | Observações |
|---|---|---|---|
| Dev local | `config/settings.yaml` na raiz do repo | `./data/*` | `make bootstrap` já cria tudo |
| CLI local | `config/settings.yaml` ou `--config` | `./data/*` ou `--output-dir/*` | útil para batch e compare |
| Docker Compose | `/app/config/settings.yaml` via volume | `/app/data/*` mapeado de `./data` | `PORT=8000` por padrão |
| Produção sem compose | arquivo local `config/settings.yaml` | conforme `paths.*` | garantir permissão de escrita em logs/reports/snapshots |

#### Checklist mínimo de produção

Antes de subir em ambiente operacional, confirme:

- `config/settings.yaml` presente e revisado para o ente correto (`app.esfera`);
- diretórios de `snapshots`, `reports` e `logs` com permissão de escrita;
- volume de `./config` e `./data` montado, se usar Docker;
- `ref/` presente no artefato de deploy;
- porta exposta compatível com o reverse proxy ou intranet;
- `make validate` verde na revisão que será publicada.

### Validar localmente

```bash
make validate
```

Esse comando executa:

- `ruff check src/ tests/ app/`
- `mypy src/ app/api/`
- `pytest --cov=ranking_msc --cov-report=term-missing --cov-fail-under=80`
- `cd web && npm run lint`
- `cd web && npm run typecheck`
- `cd web && npm run build`

### Comandos avulsos

```bash
make lint
make typecheck
make test
make frontend-lint
make frontend-typecheck
make frontend-build
```

### CI

O repositório executa GitHub Actions em PRs e pushes para `main` com os checks abaixo:

- `pytest`
- `ruff check src tests app`
- `mypy src app/api`
- `npm run build`
- `npm run lint`

---

## Estrutura de diretórios

```
ranking_msc/
├── app/
│   ├── api/                    # FastAPI (ponto de entrada web)
│   │   ├── main.py             # App FastAPI, rotas, CORS, static mount
│   │   ├── deps.py             # Dependências (settings, logger, paths)
│   │   ├── schemas.py          # Modelos Pydantic (contrato JSON)
│   │   └── routes/             # Módulos de rota (run, score, rules, etc.)
├── web/                        # Frontend React + TypeScript + Vite
│   ├── src/
│   │   ├── api/client.ts       # Wrapper fetch → FastAPI
│   │   ├── screens/            # 10 telas (Home, Executivo, Regras, etc.)
│   │   ├── components/         # Componentes reutilizáveis (ScoreBadge, Sev, etc.)
│   │   ├── store/              # Context providers (MCRA, Drawer)
│   │   └── styles/             # CSS global + tokens
│   └── package.json
├── config/
│   ├── settings.yaml           # Config real (NÃO versionado)
│   └── settings.yaml.example   # Template de config
├── src/
│   └── ranking_msc/
│       ├── __init__.py
│       ├── schemas.py           # Constantes de colunas dos DataFrames
│       ├── exceptions.py        # Exceções customizadas
│       ├── config/settings.py   # Loader de YAML → dataclasses
│       ├── engine/
│       │   ├── executor.py      # Motor principal (EngineContext, EngineResult)
│       │   ├── score_engine.py  # Cálculo de score por dimensão/banda
│       │   └── compare_periods.py  # Diff de score entre competências
│       ├── rules/               # Uma regra por arquivo (R003..R054)
│       ├── io/
│       │   ├── reader_msc.py    # Leitura do CSV MSC
│       │   └── ref_loader.py    # Carregamento de tabelas de referência
│       ├── transform/
│       │   └── ic_normalize.py  # Normalização IC → 9 atributos
│       └── outputs/
│           ├── snapshot.py      # Escrita Parquet atômica
│           ├── reports.py       # Exportação Excel
│           ├── aggregations.py  # Agregações para a API (heatmap, ranking, recomendações)
│           └── logs.py          # Logging JSON Lines
├── tests/                       # ~50 arquivos de teste
├── ref/                         # Tabelas de referência (PCASP, domínios)
├── data/                        # Outputs gerados (gitignored)
├── doc/
│   ├── backlog.md               # Backlog consolidado e status atual
│   ├── fase0_plan.md            # Referência das pendências F0-03/F0-04
│   └── modelo_pontuacao.md      # Especificação do score
├── .claude/                     # Automação/skills locais do fluxo Claude
├── pyproject.toml
├── README.md
└── .gitignore
```

---

## Guia de Extensão — Como adicionar uma nova regra

Adicionar uma regra nova não requer refatoração. Basta 3 passos:

### Passo 1: Criar o arquivo da regra

Crie `src/ranking_msc/rules/r<NNN>.py` (ex: `r099.py`):

```python
"""Regra R099 — Verifica XYZ."""

import pandas as pd

from ranking_msc.engine.executor import EngineContext
from ranking_msc.rules.base import Rule, register_rule


@register_rule
class R099(Rule):
    rule_id = "R099"
    rule_name = "Verificação de XYZ"
    dimensao = "Fechamento"  # ou "PCASP", "Temporal", "Domínio"…

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        issues = []
        # Sua lógica aqui
        return self.build_issues(issues)
```

### Passo 2: Importar no `__init__` das regras

```python
from ranking_msc.rules.r099 import R099  # noqa: F401
```

### Passo 3: Habilitar no settings.yaml

```yaml
rules:
  enabled:
    - "R099"
```

---

## Onde ficam as coisas

| O quê | Onde |
|---|---|
| Tabelas de referência (PCASP, domínios) | `ref/` |
| Snapshots Parquet | `data/snapshots/<SICONFI>/<YYYY-MM>/` |
| Relatórios Excel | `data/reports/` |
| Logs de execução | `data/logs/ranking_msc.jsonl` |
| Config da aplicação | `config/settings.yaml` |

---

## Documentação ativa

| Documento | Uso |
|---|---|
| `README.md` | Visão geral, setup, comandos e superfície pública da API |
| `CLAUDE.md` | Convenções operacionais permanentes do repositório |
| `doc/backlog.md` | Status consolidado, pendências e prioridades |
| `doc/modelo_pontuacao.md` | Regra de negócio do score |
| `doc/governanca_documental.md` | Política documental e revisão de aderência arquitetural |
| `doc/fase0_plan.md` | Registro histórico da entrega de bootstrap/frontend |
| `doc/legacy_inventory.md` | Registro histórico da remoção do legado Panel |

---

## Endpoints da API

| Método | Rota | Descrição |
|---|---|---|
| POST | `/api/run` | Executa o pipeline sobre um CSV MSC |
| GET | `/api/competencias` | Lista competências disponíveis |
| GET | `/api/score` | Score de uma competência |
| GET | `/api/score-history` | Histórico de score (6 meses) |
| GET | `/api/pendencias` | Pendências paginadas com filtros |
| GET | `/api/rules` | Catálogo de regras |
| GET | `/api/rules/:id` | Detalhe de uma regra |
| GET | `/api/heatmap` | Heatmap regras × competências |
| GET | `/api/rule-history/:id` | Histórico de uma regra |
| GET | `/api/contas/:codigo` | Detalhe de uma conta contábil |
| GET | `/api/caixa` | Listagem de contas de caixa |
| GET | `/api/passivos` | Listagem de passivos |
| GET | `/api/superavit` | Resultado financeiro por FR |
| GET | `/api/compare` | Diff de score entre 2 competências |
| GET | `/api/recommendations` | Ações recomendadas (Executivo) |
| GET | `/api/log` | Tail do log JSONL |
| GET | `/api/exports/excel` | Download do relatório Excel |
| GET | `/api/health` | Healthcheck |

> `Ranking Regional` permanece fora da superfície pública até a integração de uma
> base benchmark externa comparável entre entes.

---

## Comandos rápidos

```bash
# Backend (dev)
uvicorn app.api.main:app --reload --port 8000

# Frontend (dev)
cd web && npm run dev

# Pipeline completo via CLI
python scripts/run_pipeline.py --csv ref/amostras/msc_2025-11.csv

# Testes
pytest

# Cenário E2E API-first do fluxo principal
pytest tests/test_e2e_main_flow.py

# Lint + type check
ruff check src/ tests/ app/
mypy src/ app/api/
cd web && npx tsc --noEmit && npx eslint src/
```
