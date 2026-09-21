# Ranking MSC — Motor de Validação Contábil

Aplicação interna para validação da Matriz de Saldos Contábeis (MSC) conforme regras do Ranking SICONFI. Motor Python + interface React/TypeScript (SPA) + FastAPI, entregue como aplicativo desktop instalado na máquina de cada pessoa da equipe da prefeitura.

**Repositório:** <https://github.com/GabrielFpaiva/ranking_msc>

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
git clone https://github.com/GabrielFpaiva/ranking_msc.git
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

### Setup no Windows (sem `make`)

No PowerShell, os mesmos passos do `bootstrap` manualmente:

```powershell
git clone https://github.com/GabrielFpaiva/ranking_msc.git
cd ranking_msc

# Ambiente Python
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"

# Dependências do frontend (se o PowerShell bloquear `npm`, use `npm.cmd`)
cd web; npm.cmd install; cd ..

# Config e diretórios de dados (não sobrescreve settings.yaml existente)
if (-not (Test-Path config\settings.yaml)) { Copy-Item config\settings.yaml.example config\settings.yaml }
New-Item -ItemType Directory -Force data\snapshots, data\reports, data\logs
```

Para rodar em dev no Windows:

```powershell
# Terminal 1 — backend
.\.venv\Scripts\python.exe -m uvicorn app.api.main:app --reload --port 8000

# Terminal 2 — frontend
cd web; npm.cmd run dev
```

### Alternativa com uv

O repositório versiona `uv.lock`. Com o [uv](https://docs.astral.sh/uv/) instalado, o ambiente Python pode ser criado com uma única linha (substitui venv + pip do bootstrap; frontend, config e diretórios continuam como acima):

```bash
uv sync --extra dev
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

### Build unificado local (verificação antes de empacotar)

```bash
# Build do frontend
make frontend-build

# Servidor local (front + API unificados)
.venv/bin/python -m uvicorn app.api.main:app --host 127.0.0.1 --port 8000
```

O FastAPI serve `web/dist/` como estático em `/` e as rotas em `/api/*`. Serve
para conferir o build completo antes de empacotar — a entrega real para a
equipe da prefeitura é o instalador desktop (ver seção seguinte), não este
processo rodando exposto em rede.

### Distribuição (aplicativo desktop)

A entrega para a equipe da prefeitura é um instalador Windows,
`MCRA-Setup-<versão>.exe`, gerado pelo workflow `Release desktop` do GitHub
Actions a partir de uma tag `v*` (ou disparo manual). O workflow só anexa o
instalador como artefato da execução (`upload-artifact`), para baixar na aba
Actions; ele não cria Release no GitHub. O instalador instala o
aplicativo em Arquivos de Programas, cria atalho no menu iniciar e na área de
trabalho, e verifica/instala o Edge WebView2 se faltar.

```bash
# Uma vez: instala pywebview e PyInstaller (extra "desktop"), que os dois alvos exigem
pip install -e ".[desktop]"

# Rodar o aplicativo desktop em desenvolvimento, sem gerar instalador
make desktop-run

# Empacotar localmente (sem passar pelo CI)
make desktop-build
```

Dados e configuração de cada pessoa ficam em `%LOCALAPPDATA%\MCRA` — cada
máquina tem os seus, não existe cópia central.

O executável não é assinado: o Windows SmartScreen mostra aviso na primeira
execução, e o antivírus corporativo pode bloquear. Isso precisa ser testado
numa máquina real da prefeitura antes de qualquer distribuição ampla.

### Docker Compose (aposentado)

A publicação via Docker Compose (`docker compose up`, `make docker-up`) foi
aposentada em 21/09/2026 — a entrega deixou de ser hospedada e passou a ser
o instalador desktop acima. O material (compose, Dockerfile, nginx) está
preservado em `doc/legacy/`.

### Configuração e variáveis de ambiente

#### Arquivo `config/settings.yaml`

O arquivo real de configuração é `config/settings.yaml`.
Se ele não existir:

- `make bootstrap` copia `config/settings.yaml.example`;
- no aplicativo desktop, o próprio aplicativo cria `%LOCALAPPDATA%\MCRA\config\settings.yaml` no primeiro arranque, a partir de um template embutido;
- o material de container Docker (aposentado em 21/09/2026) também fazia isso — ver `doc/legacy/`.

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
  secret_key: "change-me-in-production"
  algorithm: "HS256"
  access_token_expire_minutes: 480
  users:
    - username: "admin"
      hashed_password: "$2b$12$SUBSTITUA_PELO_HASH_REAL"
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
| `security` | `secret_key` | sim* | `change-me-in-production` | chave de assinatura JWT (`HS256`) |
| `security` | `algorithm` | não | `HS256` | algoritmo JWT usado no encode/decode |
| `security` | `access_token_expire_minutes` | não | `480` | expiração do access token |
| `security` | `users` | sim* | `[]` | usuários autorizados (username + hash bcrypt) |

\* Em dev puro (sem login), `secret_key` padrão + `users=[]` é aceito com warning.
Em uso autenticado, é obrigatório configurar chave forte e ao menos um usuário.

No aplicativo desktop os três usuários da equipe já vêm cadastrados no
instalador; as senhas são entregues pessoalmente pelo responsável técnico. O
que segue vale para quem roda a API fora do instalador (desenvolvimento
local), onde nenhum caminho exige gerar hash na mão:

1. **Navegador (recomendado)** — com o app no ar e nenhum usuário configurado,
   a tela de login vira "Primeiro acesso" e cria o administrador ali mesmo
   (`POST /api/auth/setup`, que tranca após o primeiro usuário existir).
2. **CLI** — `python scripts/create_user.py --username admin` (senha pedida no
   prompt; hash bcrypt e `secret_key` seguro gerados automaticamente).

O caminho via variáveis de ambiente e Docker Compose foi aposentado em
21/09/2026 junto com o material em `doc/legacy/`.

Observações importantes:

- `config/settings.yaml` real não deve ser commitado.
- **Paths do `settings.yaml`** — a resolução depende do campo e do contexto:
  - `paths.snapshots_dir`, `paths.reports_dir` e `paths.logs_dir` são resolvidos a partir da **raiz do projeto** pelos scripts CLI (via `_cli_helpers._resolve_project_path()`) e pela API web (via `deps.py`).
  - `paths.ref_dir` **não** passa por `_resolve_project_path()`: as regras chamam `load_pcasp(settings.paths.ref_dir)` e o `ref_loader._resolve_reference_path()` usa `Path(ref_dir).expanduser().resolve()`, que resolve relativo ao **cwd**. Em execuções de `run_pipeline.py`/`run_batch.py` disparadas fora da raiz do repositório (cron, systemd), `./ref` pode apontar para o diretório errado. Para evitar isso, configure `paths.ref_dir` com caminho absoluto no `settings.yaml` de produção.
- **Paths explícitos da CLI** (`--config`, `--output-dir`, `--snapshots-dir`) são resolvidos a partir do **cwd** (`Path.cwd()`), não da raiz do projeto. Isso é relevante quando os scripts são invocados de fora da raiz do repositório (ex: cron, systemd). Veja `scripts/_cli_helpers.py` e `scripts/compare_periods.py` para detalhes da resolução.
- Em `scripts/run_pipeline.py` e `scripts/run_batch.py`, `--output-dir` sobrescreve os diretórios `snapshots/`, `reports/` e `logs/` sob um novo diretório base.
- Em `scripts/compare_periods.py`, `--output-dir` controla apenas o diretório de saída do Excel consolidado; a leitura de snapshots continua vindo de `settings.paths.snapshots_dir` ou de `--snapshots-dir`, e os logs continuam em `settings.paths.logs_dir`.

#### Variáveis de ambiente

Variáveis efetivamente suportadas hoje:

| Variável | Onde funciona | Default | Efeito |
|---|---|---|---|
| `PORT` | mecanismo do entrypoint Docker, aposentado em 21/09/2026 — ver `doc/legacy/` | `8000` | porta do `uvicorn` no entrypoint (sem uso no fluxo atual) |
| `RANKING_MSC_CONFIG` | API web (`app/api/deps.py::get_config_path()`) e loader Python quando `load_settings()` é chamado sem path explícito | `config/settings.yaml` | escolhe o `settings.yaml` da API (o aplicativo desktop depende disso), do uso programático sem path explícito e da CLI `scripts/benchmark.py` |

Limitações atuais de resolução de config:

- `app/api/deps.py::get_config_path()` usa `RANKING_MSC_CONFIG` quando definida e, sem ela, `PROJECT_ROOT / config/settings.yaml`; é assim que o aplicativo desktop aponta a API para `%LOCALAPPDATA%\MCRA\config\settings.yaml`;
- `scripts/run_pipeline.py`, `scripts/run_batch.py` e `scripts/compare_periods.py` resolvem `config/settings.yaml` ou `--config` antes de chamar `load_settings()`;
- `scripts/benchmark.py` chama `load_settings()` sem path explícito e, portanto, **respeita** `RANKING_MSC_CONFIG`;
- portanto, a variável `RANKING_MSC_CONFIG` **altera** a configuração da API web e de `scripts/benchmark.py`, mas **não** o comportamento padrão dessas três CLIs operacionais;
- para mudar a configuração da API fora do instalador (dev/self-hosted manual), edite `config/settings.yaml` na raiz do projeto; no aplicativo desktop, edite `%LOCALAPPDATA%\MCRA\config\settings.yaml`;
- para mudar a configuração de `run_pipeline.py`, `run_batch.py` e `compare_periods.py`, use `--config /caminho/para/settings.yaml`.

#### Dev vs aplicativo desktop vs Docker (aposentado)

| Ambiente | Como a config é resolvida | Paths de dados mais comuns | Observações |
|---|---|---|---|
| Dev local | `config/settings.yaml` na raiz do repo | `./data/*` | `make bootstrap` já cria tudo |
| CLI local | `config/settings.yaml` ou `--config` | `./data/*`, `--output-dir/*` (pipeline/batch) ou diretório custom de Excel consolidado (compare) | `compare_periods` usa `--snapshots-dir`; `benchmark.py` é a exceção que respeita `RANKING_MSC_CONFIG` |
| Aplicativo desktop | `%LOCALAPPDATA%\MCRA\config\settings.yaml`, criado pelo aplicativo no primeiro arranque (via `RANKING_MSC_CONFIG`) | `%LOCALAPPDATA%\MCRA\data\*` | sem servidor central; cada máquina tem os seus |
| Docker Compose | `/app/config/settings.yaml` via volume | `/app/data/*` mapeado de `./data` | aposentado em 21/09/2026 — ver `doc/legacy/` |

#### Checklist mínimo antes de distribuir uma versão

- `config/settings.yaml` (ou o template embutido do instalador) revisado para o ente correto (`app.esfera`);
- diretórios de `snapshots`, `reports` e `logs` com permissão de escrita;
- volume de `./config` e `./data` montado, se ainda usar o material Docker legado;
- `ref/` presente no artefato de instalação;
- instalador testado numa máquina real da prefeitura (SmartScreen, antivírus corporativo, WebView2);
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
│       ├── rules/               # 78 regras, uma por arquivo (R001–R093)
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
│   ├── guia_operacao.md         # Operação local, validações e troubleshooting
│   ├── manual_usuario.md        # Fluxo de uso para equipe contábil
│   ├── modelo_pontuacao.md      # Especificação do score
│   ├── handoff.md               # Handoff operacional (entrega formal)
│   ├── roteiro_treinamento.md   # Roteiro de demonstração/treinamento
│   └── atas/                    # Atas de reunião (PDF)
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
| `doc/manual_usuario.md` | Fluxo de uso, telas e exportações para a equipe contábil |
| `doc/guia_operacao.md` | Setup, execução, validações, logs e rotina de sustentação |
| `doc/modelo_pontuacao.md` | Regra de negócio do score |
| `doc/handoff.md` | Handoff operacional — entrega formal para operação |
| `doc/roteiro_treinamento.md` | Roteiro de demonstração e treinamento |
| `doc/atas/` | Atas de reunião do projeto (PDF) |

---

## Endpoints da API

| Método | Rota | Descrição |
|---|---|---|
| POST | `/api/auth/token` | Login OAuth2 password flow (retorna JWT) |
| GET | `/api/auth/me` | Retorna usuário autenticado |
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
| GET | `/api/exports/pdf` | Download do relatório executivo em PDF |
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
