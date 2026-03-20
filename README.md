# Ranking MSC — Motor de Validação Contábil

Aplicação web interna para validação da Matriz de Saldos Contábeis (MSC) conforme regras do Ranking SICONFI. Desenvolvida em Python com Panel + Plotly para uso na intranet da prefeitura.

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
                    ┌────────────────────────┐
                    │   app/web_app.py        │  ← Interface Panel (navegador)
                    │   Upload CSV + Abas     │
                    └──────────┬─────────────┘
                               │
                    ┌──────────▼─────────────┐
                    │  io/reader_msc.py       │  ← Leitura e parse do CSV
                    └──────────┬─────────────┘
                               │
                    ┌──────────▼─────────────┐
                    │  transform/             │  ← Normalização IC → PO, FP, DC, FS, FR, CO, NR, ND, AI
                    │  ic_normalize.py        │
                    └──────────┬─────────────┘
                               │
                    ┌──────────▼─────────────┐
                    │  engine/executor.py     │  ← Motor: carrega regras, executa, consolida
                    │  EngineContext          │
                    │  EngineResult           │
                    └──────────┬─────────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
     ┌────────▼───────┐  ┌────▼─────┐  ┌───────▼────────┐
     │ rules/base.py  │  │ rules/   │  │ rules/         │
     │ Rule (ABC)     │  │ r082.py  │  │ r083.py …      │
     │ RULE_REGISTRY  │  └──────────┘  └────────────────┘
     └────────────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
     ┌────────▼───────┐  ┌────▼─────┐  ┌───────▼────────┐
     │ outputs/       │  │ outputs/ │  │ outputs/       │
     │ snapshot.py    │  │ reports  │  │ logs.py        │
     │ (Parquet)      │  │ (Excel)  │  │ (JSON Lines)   │
     └────────────────┘  └──────────┘  └────────────────┘
```

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
- (Recomendado) ambiente virtual

### Setup local

```bash
# Clonar e entrar no repositório
cd ranking_msc

# Criar ambiente virtual
python -m venv .venv
source .venv/bin/activate        # Linux/Mac
# .venv\Scripts\activate         # Windows

# Instalar pacote em modo editável + dependências de dev
pip install -e ".[dev]"

# Copiar config de exemplo
cp config/settings.yaml.example config/settings.yaml
# (Edite settings.yaml conforme necessário)

# Criar diretórios de dados
mkdir -p data/{snapshots,reports,logs}
```

### Rodar a aplicação (desenvolvimento)

```bash
panel serve app/web_app.py --show --autoreload
```

Acesse `http://localhost:5006/web_app` no navegador.

### Rodar no servidor (produção, multiusuário)

```bash
panel serve app/web_app.py \
    --address 0.0.0.0 \
    --port 5006 \
    --allow-websocket-origin="servidor.prefeitura.local" \
    --num-procs 2 \
    --static-dirs assets=./assets
```

### Rodar testes

```bash
pytest                    # todos os testes
pytest -v --tb=short      # verbose
pytest --cov=ranking_msc  # com cobertura
```

### Lint e type check

```bash
ruff check src/ tests/
mypy src/
```

---

## Estrutura de diretórios

```
ranking_msc/
├── app/
│   └── web_app.py              # Aplicação Panel (ponto de entrada web)
├── config/
│   ├── settings.yaml           # Config real (NÃO versionado)
│   └── settings.yaml.example   # Template de config
├── src/
│   └── ranking_msc/
│       ├── __init__.py
│       ├── schemas.py           # Constantes de colunas dos DataFrames
│       ├── exceptions.py        # Exceções customizadas
│       ├── config/
│       │   └── settings.py      # Loader de YAML → dataclasses
│       ├── engine/
│       │   └── executor.py      # Motor principal (EngineContext, EngineResult)
│       ├── rules/
│       │   ├── base.py          # Classe base Rule + RULE_REGISTRY
│       │   ├── r003.py          # Tipo_valor válido
│       │   ├── r004.py          # Natureza_valor válida
│       │   ├── r010.py          # Conta existe no PCASP
│       │   ├── r021.py          # PO válido
│       │   └── r030.py          # Fechamento patrimonial D=C
│       ├── io/
│       │   ├── reader_msc.py    # Leitura do CSV MSC
│       │   └── ref_loader.py    # Carregamento de tabelas de referência (PCASP, domínios)
│       ├── transform/
│       │   └── ic_normalize.py  # Normalização IC → PO, FP, DC, FS, FR, CO, NR, ND, AI
│       └── outputs/
│           ├── snapshot.py      # Escrita Parquet atômica
│           ├── reports.py       # Exportação Excel (abas: Resumo + Pendências)
│           └── logs.py          # Logging JSON Lines
├── tests/
│   ├── conftest.py              # Fixtures compartilhadas
│   ├── test_smoke.py            # Smoke tests
│   ├── test_reader.py           # io/reader_msc.py
│   ├── test_normalize.py        # transform/ic_normalize.py
│   ├── test_ref_loader.py       # io/ref_loader.py
│   ├── test_engine.py           # engine/executor.py
│   ├── test_rules.py            # regras genéricas
│   ├── test_r003_r004.py        # R003, R004
│   ├── test_r010.py             # R010
│   ├── test_r021.py             # R021
│   ├── test_r030.py             # R030
│   ├── test_mapeamento_ic_tipo.py
│   ├── test_snapshot.py         # outputs/snapshot.py
│   ├── test_reports.py          # outputs/reports.py
│   ├── test_logs.py             # outputs/logs.py
│   ├── test_integration.py      # Pipeline ponta a ponta
│   └── test_run_pipeline.py     # scripts/run_pipeline.py
├── doc/
│   └── fase3_plan.md            # Handoff e roadmap da Fase 3
├── data/
│   ├── snapshots/               # Parquet por competência (gitignored)
│   ├── reports/                 # Excel gerados (gitignored)
│   └── logs/                    # Logs JSON Lines (gitignored)
├── ref/                         # Tabelas de referência (PCASP, domínios, amostras)
│   ├── layout_msc.md            # Especificação do CSV MSC
│   ├── mapeamento_ic_tipo.csv   # Combinações IC/TIPO válidas
│   ├── regras_piloto.md         # Documentação das 5 regras piloto
│   ├── regras_catalogo.md       # Catálogo completo de regras
│   ├── resultados_piloto.md     # Resultados das execuções com dados reais
│   ├── pcasp.csv                # PCASP Estendido 2026
│   └── tabela_po/fr/co/fs/nd/nr.csv  # Tabelas de domínio por atributo
├── scripts/
│   └── run_pipeline.py          # CLI de execução do pipeline
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
        # Sua lógica aqui — filtre, compare, valide.
        issues = []

        # Exemplo: encontrou problema na conta 1.1.1
        # issues.append({
        #     "severidade": "ERRO",
        #     "conta_contabil": "1.1.1.0.0.00.00",
        #     "descricao": "Saldo inconsistente",
        #     "valor_esperado": "0.00",
        #     "valor_encontrado": "150.00",
        #     "competencia": context.competencia,
        # })

        return self.build_issues(issues)
```

### Passo 2: Importar no `__init__` das regras

Adicione em `src/ranking_msc/rules/__init__.py`:

```python
from ranking_msc.rules.r099 import R099  # noqa: F401
```

### Passo 3: Habilitar no settings.yaml

```yaml
rules:
  enabled:
    - "R099"   # ← adicionar aqui
```

Pronto. O executor já carregará a regra automaticamente.

---

## Onde ficam as coisas

| O quê | Onde |
|---|---|
| Tabelas de referência (PCASP, domínios) | `ref/` |
| Snapshots Parquet | `data/snapshots/<YYYY-MM>/` |
| Relatórios Excel | `data/reports/` |
| Logs de execução | `data/logs/ranking_msc.jsonl` |
| Config da aplicação | `config/settings.yaml` |

---

## Fase 2 — Concluída ✅

Todas as entregas da Fase 2 estão prontas. O pipeline roda de ponta a ponta com dados reais.

- [x] Estrutura de repositório e `pyproject.toml`
- [x] Settings YAML com loader e validação
- [x] Exceções customizadas e schemas de colunas
- [x] Classe base `Rule` com registro automático
- [x] Engine com `EngineContext` e `EngineResult`
- [x] `read_msc_csv()` — leitura e parse do CSV MSC real
- [x] `normalize_ic()` — 9 tipos IC (PO, FP, DC, FS, FR, CO, NR, ND, AI) conforme STN 642/2026
- [x] `ref_loader.py` — PCASP + tabelas de domínio com cache
- [x] Regras piloto: R003, R004, R010, R021, R030
- [x] Outputs: snapshot Parquet atômico, Excel (Resumo + Pendências), log JSON Lines
- [x] Scripts CLI (`run_pipeline.py`)
- [x] 190 testes passando (pytest), ruff e mypy limpos
- [x] Execução validada com CSVs reais (2025-11 e 2025-12 — SICONFI 2507507EX)

**Próximo:** ver [`doc/fase3_plan.md`](doc/fase3_plan.md) para o roadmap da Fase 3.

### Comandos rápidos

```bash
# Rodar pipeline completo via CLI
python scripts/run_pipeline.py --csv ref/amostras/msc_2025-11.csv

# Rodar app local
panel serve app/web_app.py --show --autoreload

# Rodar testes
pytest

# Lint
ruff check src/ tests/

# Type check
mypy src/
```
