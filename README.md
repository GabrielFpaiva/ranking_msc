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
- (Recomendado) ambiente virtual

### Setup local

```bash
# Clonar e entrar no repositório
cd ranking_msc

# Criar ambiente virtual Python
python -m venv .venv
source .venv/bin/activate        # Linux/Mac
# .venv\Scripts\activate         # Windows

# Instalar pacote em modo editável + dependências de dev
pip install -e ".[dev]"

# Copiar config de exemplo
cp config/settings.yaml.example config/settings.yaml

# Criar diretórios de dados
mkdir -p data/{snapshots,reports,logs}

# Instalar dependências do frontend
cd web && npm install && cd ..
```

### Rodar em desenvolvimento (frontend + backend)

**Terminal 1 — Backend FastAPI:**

```bash
source .venv/bin/activate
uvicorn app.api.main:app --reload --port 8000
```

**Terminal 2 — Frontend React (Vite):**

```bash
cd web
npm run dev
```

Acesse `http://localhost:5173` no navegador. O Vite faz proxy de `/api/*` para o backend na porta 8000.

### Rodar em produção

```bash
# Build do frontend
cd web && npm run build && cd ..

# Servidor (front + API unificados)
uvicorn app.api.main:app --host 0.0.0.0 --port 8000
```

O FastAPI serve `web/dist/` como estático em `/` e as rotas em `/api/*`.

### Rodar testes

```bash
pytest                    # todos os testes
pytest -v --tb=short      # verbose
pytest --cov=ranking_msc  # com cobertura
```

### Lint e type check

```bash
# Python
ruff check src/ tests/ app/
mypy src/ app/api/

# TypeScript / Frontend
cd web
npx tsc --noEmit
npx eslint src/
npm run build
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
| `README.md` | Visão geral, setup e comandos |
| `CLAUDE.md` | Convenções operacionais do repositório |
| `doc/backlog.md` | Status consolidado, pendências e prioridades |
| `doc/fase0_plan.md` | Referência das entregas/pêndencias do frontend |
| `doc/modelo_pontuacao.md` | Regra de negócio do score |

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
| GET | `/api/superavit` | Superávit financeiro (501 — F0-04) |
| GET | `/api/compare` | Diff de score entre 2 competências |
| GET | `/api/recommendations` | Ações recomendadas (Executivo) |
| GET | `/api/log` | Tail do log JSONL |
| GET | `/api/ranking` | Ranking Regional (501 — F0-03) |
| GET | `/api/exports/excel` | Download do relatório Excel |
| GET | `/api/health` | Healthcheck |

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

# Lint + type check
ruff check src/ tests/ app/
mypy src/ app/api/
cd web && npx tsc --noEmit && npx eslint src/
```
