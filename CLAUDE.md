# CLAUDE.md — Contexto Operacional do `ranking_msc`

> Este arquivo é o **contexto permanente** do projeto. Leia-o inteiro antes de
> implementar qualquer task. Ele garante consistência entre sessões, devs e sprints.

---

## 1. O que é este projeto

**ranking_msc** é um motor de validação contábil da MSC (Matriz de Saldos Contábeis)
para o Ranking SICONFI. Aplicação interna da prefeitura, multiusuário, com
**motor Python + FastAPI + React/TypeScript**.

O pipeline principal é:

```
CSV MSC → read_msc_csv() → normalize_ic() → run_engine(regras) → snapshot + Excel + log
```

O estado de referência do projeto fica em `doc/backlog.md`.

Resumo atual:

- 73 de 78 regras implementadas
- API FastAPI em `app/api/`
- frontend React/Vite em `web/`
- Panel mantido apenas como legado em `app/web_app_legacy.py`
- backlog ativo: F4-18, gap estrutural R0010/R0011 e Fase 5

---

## 2. Estrutura do repositório

```
ranking_msc/
├── app/
│   ├── api/                        # API FastAPI
│   └── web_app_legacy.py           # Interface Panel (legado)
├── config/settings.yaml            # Config local (NÃO versionado)
├── config/settings.yaml.example    # Template versionado
├── scripts/
│   ├── run_pipeline.py             # CLI de execução individual
│   ├── run_batch.py                # CLI batch multi-competência
│   ├── compare_periods.py          # CLI de comparação temporal
│   └── _cli_helpers.py             # Helpers compartilhados dos CLIs
├── src/ranking_msc/
│   ├── __init__.py                 # __version__
│   ├── schemas.py                  # Colunas dos DataFrames (contratos de dados)
│   ├── exceptions.py               # Exceções customizadas
│   ├── config/settings.py          # Loader YAML → dataclasses
│   ├── engine/executor.py          # Motor: EngineContext, EngineResult, run_engine()
│   ├── rules/
│   │   ├── base.py                 # Rule ABC + RULE_REGISTRY + @register_rule
│   │   ├── r082.py                 # Uma regra por arquivo
│   │   └── ...
│   ├── io/
│   │   ├── reader_msc.py           # Leitura CSV → RawMSC
│   │   └── ref_loader.py           # Carregar tabelas de referência (PCASP, domínios)
│   ├── transform/
│   │   └── ic_normalize.py         # IC/TIPO → PO, FR, CO, NR, ND, FS
│   └── outputs/
│       ├── snapshot.py             # Parquet atômico por competência
│       ├── reports.py              # Excel de pendências
│       └── logs.py                 # Logger JSON Lines
├── tests/
│   ├── test_smoke.py               # Imports e sanidade básica
│   ├── test_reader.py              # Testes de io/reader_msc.py
│   ├── test_normalize.py           # Testes de transform/
│   ├── test_engine.py              # Testes de engine/executor.py
│   ├── test_snapshot.py            # Testes de outputs/snapshot.py
│   ├── test_reports.py             # Testes de outputs/reports.py
│   ├── test_rules.py               # Testes das regras piloto
│   ├── test_integration.py         # Pipeline ponta a ponta
│   └── conftest.py                 # Fixtures compartilhadas
├── ref/                            # Tabelas de referência (PCASP, domínios, amostras CSV)
│   ├── amostras/                   # CSVs MSC reais para testes
│   ├── layout_msc.md               # Documentação do layout do CSV
│   ├── mapeamento_ic_tipo.csv      # IC × TIPO → colunas complementares
│   └── regras_piloto.md            # Documentação das 5 regras piloto
├── data/                           # Outputs gerados (gitignored)
│   ├── snapshots/<YYYY-MM>/        # Parquet por competência
│   ├── reports/                    # Excel gerados
│   └── logs/                       # ranking_msc.jsonl
├── web/                            # Frontend React + TS + Vite
├── pyproject.toml
├── README.md
├── CLAUDE.md                       # ← ESTE ARQUIVO
└── .gitignore
```

**Regra de ouro:** se não sabe onde colocar algo, pergunte antes de criar pasta nova.

---

## 3. Convenções de código

### 3.1 Linguagem e nomes

| Elemento | Idioma | Exemplo |
|---|---|---|
| Nomes de variáveis, funções, classes | Inglês | `run_engine()`, `EngineResult` |
| Conceitos de negócio (campos/colunas) | Português | `competencia`, `severidade`, `conta_contabil` |
| Docstrings e comentários | Português | `"""Executa todas as regras habilitadas."""` |
| Mensagens de erro/log para o usuário | Português | `"Coluna 'conta_contabil' ausente no CSV"` |
| Mensagens internas/debug | Inglês ou PT | À escolha, mas consistente no módulo |

### 3.2 Estilo

- **Python 3.11+** — use union types (`str | None`), não `Optional[str]`
- **Type hints em tudo** — parâmetros, retornos, atributos de dataclass
- **`from __future__ import annotations`** no topo de todo arquivo (lazy evaluation)
- **PEP8** com line length 100 (configurado no `pyproject.toml` via ruff)
- **Imports agrupados:** stdlib → terceiros → locais, separados por linha em branco
- **Sem `import *`** — sempre imports explícitos

### 3.3 Dataclasses para tudo que é "estrutura de dados"

```python
from __future__ import annotations
from dataclasses import dataclass, field

@dataclass
class AlgumaCoisa:
    """Docstring obrigatória explicando o propósito."""
    campo_obrigatorio: str
    campo_opcional: int = 0
    lista: list[str] = field(default_factory=list)
```

- Use `frozen=True` para configurações e DTOs imutáveis
- Use `field(default_factory=...)` para mutáveis (listas, dicts)
- **Nunca** use dicts soltos para representar dados estruturados — crie dataclass

### 3.4 Exceções

- **Sempre** use exceções de `ranking_msc.exceptions` — nunca `raise Exception("...")`
- Escolha a mais específica: `InputFormatError`, `SnapshotError`, `RuleExecutionError`...
- Mensagem em português, descritiva, com contexto:

```python
# ✅ BOM
raise InputFormatError(
    f"Coluna obrigatória 'conta_contabil' ausente no CSV. "
    f"Colunas encontradas: {list(df.columns)}"
)

# ❌ RUIM
raise Exception("Coluna faltando")
```

- Se precisar de nova exceção, herde de `RankingMSCError` e adicione em `exceptions.py`

### 3.5 Logging

- **Nunca** use `print()` — use o logger:

```python
import logging
logger = logging.getLogger("ranking_msc")

logger.info("Processando competência %s", competencia)
logger.warning("Combinação IC=%s TIPO=%s desconhecida", ic, tipo)
logger.error("Falha ao gravar snapshot", exc_info=True)
```

- Para logs de execução (auditoria), use o helper:

```python
from ranking_msc.outputs.logs import log_execucao
log_execucao(logger, execucao_id=ctx.execucao_id, competencia="2024-01", status="OK")
```

- Campos extras via `extra={}` aparecem no JSON Lines automaticamente
- Nunca logue dados sensíveis (senhas, tokens) — não temos hoje, mas previna

### 3.6 Docstrings

Todo arquivo, classe e função pública DEVE ter docstring. Formato:

```python
def minha_funcao(df: pd.DataFrame, competencia: str) -> pd.DataFrame:
    """Resumo em uma linha (verbo no imperativo).

    Explicação mais longa se necessário, em português.

    Args:
        df: DataFrame com colunas de FACT_MSC_COLUMNS.
        competencia: mês de referência no formato "YYYY-MM".

    Returns:
        DataFrame transformado com colunas X, Y, Z adicionadas.

    Raises:
        InputFormatError: se colunas obrigatórias faltam.
    """
```

---

## 4. Padrões de implementação

### 4.1 Como implementar uma nova REGRA

Este é o caso mais frequente. Siga **exatamente** estes passos:

**Passo 1 — Criar arquivo** `src/ranking_msc/rules/r<NNN>.py`:

```python
"""
Regra R<NNN> — <Nome descritivo>.

Dimensão: <Fechamento | PCASP | Domínio | Orçamentária | Temporal>
Severidade padrão: <ERRO | ALERTA>

Lógica:
    <Descrever em 2-3 linhas o que a regra verifica>

Referência:
    <Manual STN página X / documentação SICONFI>
"""

from __future__ import annotations

import pandas as pd

from ranking_msc.engine.executor import EngineContext
from ranking_msc.rules.base import Rule, register_rule


@register_rule
class R<NNN>(Rule):
    rule_id = "R<NNN>"
    rule_name = "<Nome curto>"
    dimensao = "<Dimensão>"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """<Resumo do que verifica>."""
        issues: list[dict[str, object]] = []

        # --- LÓGICA DA REGRA ---
        # 1. Filtrar/agrupar o DataFrame conforme necessário
        # 2. Aplicar a condição de validação
        # 3. Para cada violação encontrada, adicionar ao issues:
        #
        # issues.append({
        #     "severidade": "ERRO",
        #     "conta_contabil": row["conta_contabil"],
        #     "descricao": "Débito ≠ Crédito na conta X",
        #     "valor_esperado": str(valor_esperado),
        #     "valor_encontrado": str(valor_encontrado),
        #     "competencia": context.competencia,
        # })

        return self.build_issues(issues)
```

**Passo 2 — Registrar** em `src/ranking_msc/rules/__init__.py`:

```python
from ranking_msc.rules.r<NNN> import R<NNN>  # noqa: F401
```

**Passo 3 — Habilitar** em `config/settings.yaml`:

```yaml
rules:
  enabled:
    - "R<NNN>"
```

**Passo 4 — Criar teste** em `tests/test_rules.py` (ou arquivo próprio se complexo):

```python
class TestR<NNN>:
    def test_dados_corretos_sem_pendencia(self, sample_df, engine_context):
        """Dados válidos → nenhuma pendência."""
        rule = R<NNN>()
        result = rule.execute(sample_df, engine_context)
        assert len(result) == 0

    def test_dados_incorretos_gera_pendencia(self, sample_df_com_erro, engine_context):
        """Dados com violação → pendência com severidade ERRO."""
        rule = R<NNN>()
        result = rule.execute(sample_df_com_erro, engine_context)
        assert len(result) > 0
        assert result.iloc[0]["severidade"] == "ERRO"
        assert result.iloc[0]["regra_id"] == "R<NNN>"
```

**Checklist da regra:**
- [ ] `@register_rule` no decorator da classe
- [ ] `rule_id`, `rule_name`, `dimensao` preenchidos
- [ ] `execute()` retorna DataFrame via `self.build_issues()`
- [ ] Nunca levanta exceção silenciosamente — se der erro, deixa propagar ou loga
- [ ] Docstring com explicação da lógica
- [ ] Import em `rules/__init__.py`
- [ ] ID adicionado em `settings.yaml`
- [ ] Pelo menos 2 testes (positivo + negativo)
- [ ] Colunas de texto de tabelas de referência normalizadas com `.str.strip()` antes de comparação (ex: `nivel`, `status`, `nat_saldo`)

### 4.2 Como adicionar uma nova coluna ao schema

Se o CSV real tem uma coluna que não está em `FACT_MSC_COLUMNS`:

1. Adicionar em `src/ranking_msc/schemas.py` com comentário explicando
2. Atualizar `io/reader_msc.py` para mapear a coluna do CSV original
3. Atualizar testes que validam colunas
4. Se a coluna é usada por regras, documentar em `ref/layout_msc.md`

**Nunca** adicione coluna direto no reader sem atualizar o schema — o schema é o contrato.

### 4.3 Como adicionar um novo módulo

Se precisar de um módulo que não existe (ex: um novo transform):

1. Criar o arquivo em `src/ranking_msc/<subpacote>/<modulo>.py`
2. Docstring no topo explicando propósito
3. Type hints em tudo
4. Exceções de `ranking_msc.exceptions`
5. Criar teste correspondente em `tests/`
6. **Não** criar subpacotes novos sem necessidade — preferir adicionar a um existente

### 4.4 Padrão de leitura de tabelas de referência

Use `io/ref_loader.py` para qualquer tabela externa (PCASP, domínios, fontes):

```python
# Padrão: função que lê + cache em variável de módulo
_CACHE_PCASP: pd.DataFrame | None = None

def load_pcasp(ref_dir: str = "ref") -> pd.DataFrame:
    """Carrega tabela PCASP. Usa cache em memória após primeira leitura."""
    global _CACHE_PCASP
    if _CACHE_PCASP is not None:
        return _CACHE_PCASP
    path = Path(ref_dir) / "pcasp.csv"
    if not path.exists():
        raise ConfigError(f"Tabela PCASP não encontrada: {path}")
    _CACHE_PCASP = pd.read_csv(path, dtype=str)
    return _CACHE_PCASP
```

- Sempre `dtype=str` para códigos contábeis (evita 001 virar 1)
- Cache simples em variável de módulo (sem framework)
- Exceção `ConfigError` se arquivo ausente

---

## 5. Padrões de teste

### 5.1 Estrutura

- Um arquivo de teste por módulo: `test_reader.py` testa `io/reader_msc.py`
- Exceção: regras podem ficar agrupadas em `test_rules.py` se forem simples
- Teste de integração separado: `test_integration.py`

### 5.2 Fixtures (conftest.py)

Fixtures compartilhadas ficam em `tests/conftest.py`:

```python
import pytest
import pandas as pd
from ranking_msc.config.settings import Settings
from ranking_msc.engine.executor import EngineContext


@pytest.fixture
def settings() -> Settings:
    """Settings padrão para testes."""
    return Settings()


@pytest.fixture
def engine_context(settings: Settings) -> EngineContext:
    """EngineContext padrão para testes de regra."""
    return EngineContext(
        competencia="2024-01",
        siconfi="250400",
        settings=settings,
        usuario="teste",
    )


@pytest.fixture
def sample_msc_df() -> pd.DataFrame:
    """DataFrame MSC mínimo e válido para testes."""
    return pd.DataFrame({
        "competencia": ["2024-01"],
        "siconfi": ["250400"],
        "conta_contabil": ["1.1.1.1.1.01.00"],
        # ... adicionar conforme FACT_MSC_COLUMNS
    })
```

### 5.3 Nomes de teste

```python
def test_<oque>_<condicao>_<resultado_esperado>():
    """Docstring curta em português."""
```

Exemplos:
- `test_read_csv_valido_retorna_rawmsc()`
- `test_read_csv_sem_coluna_obrigatoria_levanta_inputformaterror()`
- `test_normalize_ic_desconhecido_loga_warning()`

### 5.4 Rodar testes

```bash
pytest                           # tudo
pytest tests/test_reader.py -v   # só um módulo
pytest -k "test_r082"            # por nome
pytest --cov=ranking_msc         # com cobertura
```

---

## 6. Fluxo de trabalho com Git

### Branches

- `main` — sempre estável, testes passando
- `feat/F2-XX-descricao` — uma branch por task do backlog
- Merge via PR com pelo menos revisão visual do outro dev

### Commits

Formato: `F<N>-XX: short description in English` (uma linha só, máximo ~72 caracteres)

```
F3-03: implement read_msc_csv() with real CSV
F3-12: rule R082 - debit = credit closing check
F3-18: end-to-end pipeline integration test
```

**Regras de commit:**
- Mensagem curta e direta **em inglês** — **nunca** mensagem multi-linha ou detalhada
- **Nunca** adicionar `Co-Authored-By` ou tags extras
- Um commit por task, exceto se a task for muito grande

### Antes de commitar

```bash
pytest                         # testes passam?
ruff check src/ tests/ app/    # lint ok?
mypy src/ app/api/             # tipos ok?
```

---

## 7. Decisões técnicas já tomadas

| Decisão | Escolha | Motivo |
|---|---|---|
| Layout do projeto | `src/` layout | Evita imports acidentais do diretório raiz |
| Modelos de dados | `dataclasses` | Simples, stdlib, type hints nativos |
| Config | YAML + dataclasses `frozen` | Legível, imutável após load |
| Exceções | Hierarquia própria sob `RankingMSCError` | Captura seletiva, mensagens claras |
| Logging | `logging` stdlib + JSON Lines | Thread-safe, parseable, sem dependência |
| Snapshots | Parquet via pyarrow | Compacto, tipado, rápido para DataFrames |
| Relatórios | Excel via openpyxl | Familiar para o analista da prefeitura |
| Regras | Classe ABC + Registry + decorator | Extensível sem modificar engine |
| Testes | pytest | Padrão da indústria, fixtures, boa UX |
| Lint | ruff | Rápido, substitui flake8+isort+pyupgrade |
| Web | FastAPI + React/Vite | API fina, SPA separada e build estático |

---

## 8. O que NÃO fazer

- **Não usar `print()`** — use `logger`
- **Não usar dicts genéricos** para dados estruturados — crie dataclass
- **Não usar `raise Exception()`** — use exceção específica de `exceptions.py`
- **Não hardcodar caminhos** — use `settings.paths.*`
- **Não hardcodar lista de colunas** — use constantes de `schemas.py`
- **Não criar lógica de regra dentro do engine** — cada regra é um arquivo em `rules/`
- **Não ignorar type hints** — tudo tipado, mypy deve passar
- **Não commitar `config/settings.yaml`** — só o `.example` vai pro repo
- **Não commitar dados de `data/`** — está no `.gitignore`
- **Não criar dependências desnecessárias** — discutir antes de adicionar pacote
- **Não tratar `app/web_app_legacy.py` como superfície principal** — a interface oficial é FastAPI + React
- **Não comparar colunas de texto de tabelas de referência sem `.str.strip()`** — `load_pcasp()` e outros loaders não normalizam colunas como `nivel`, `status`, `nat_saldo`; sempre use `.assign(col=lambda x: x[col].str.strip())` no `assign` do merge antes de filtrar

---

## 9. Referência rápida — imports mais usados

```python
# Config
from ranking_msc.config.settings import load_settings, Settings

# Engine
from ranking_msc.engine.executor import EngineContext, EngineResult, run_engine

# Regras
from ranking_msc.rules.base import Rule, register_rule, RULE_REGISTRY

# I/O
from ranking_msc.io.reader_msc import read_msc_csv, RawMSC
from ranking_msc.io.ref_loader import load_pcasp  # quando existir

# Transform
from ranking_msc.transform.ic_normalize import normalize_ic

# Outputs
from ranking_msc.outputs.snapshot import write_snapshot_atomic, read_snapshot
from ranking_msc.outputs.reports import export_issues_excel
from ranking_msc.outputs.logs import setup_logging, log_execucao

# Schemas e exceções
from ranking_msc.schemas import FACT_MSC_COLUMNS, FACT_RESULTADO_REGRAS_COLUMNS
from ranking_msc.exceptions import InputFormatError, SnapshotError, RuleExecutionError
```

---

## 10. Checklist para qualquer task

Antes de marcar uma task como concluída, verificar:

- [ ] Código segue as convenções deste arquivo (nomes, tipos, docstrings)
- [ ] Exceções são de `ranking_msc.exceptions`
- [ ] Logging via `logger`, não `print()`
- [ ] Schema usado de `ranking_msc.schemas` (não hardcoded)
- [ ] Caminhos de diretório via `settings.paths` (não hardcoded)
- [ ] Testes escritos (positivo + negativo)
- [ ] `pytest` passa
- [ ] `ruff check src/ tests/ app/` sem erros
- [ ] `mypy src/ app/api/` sem erros
- [ ] Docstrings em português em toda função/classe pública
- [ ] Se é regra: segue o padrão da seção 4.1 completo
