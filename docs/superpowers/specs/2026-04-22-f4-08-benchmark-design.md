# F4-08 — Benchmark de performance do pipeline

**Data:** 2026-04-22
**Task:** F4-08 (fase4_plan.md)
**Estimativa:** 6h
**Dependências:** F4-04 (batch pipeline) — concluído

---

## 1. Objetivo

Medir o desempenho do pipeline `read_msc_csv → normalize_ic → run_engine`
com CSVs grandes (100k, 500k, 1M linhas) gerados sinteticamente,
produzindo `ref/benchmark_performance.md` como baseline pra guiar a F4-09
(otimização vetorizada com ≥50% de ganho).

**Não-objetivo:** validar corretude das regras (já coberto pela suite de 532 testes)
ou servir como gate de regressão no CI (decisão: fora da v1).

---

## 2. Decisões de escopo

| Tema | Decisão | Justificativa |
|---|---|---|
| Fonte dos dados | Sintético via gerador | Stress test, não precisa refletir distribuição real |
| O que medir | Tempo por etapa + memória pico + throughput | Guia F4-09 saber onde otimizar |
| Framework | Script standalone (`scripts/benchmark.py`) | Evita peso no pytest; entregável é documentação |
| Formato do relatório | Tabela geral + por etapa + top-5 regras lentas | Leitura rápida + ação imediata |
| Critério de aceitação | Baseline documentado (sem hard threshold) | Sem número prévio pra definir threshold honesto |
| IO (read_csv) | Incluído no benchmark | Pipeline real lê CSV; detecta surpresas de parse |

---

## 3. Arquitetura

```
scripts/benchmark.py                     # entrypoint CLI
src/ranking_msc/benchmark/
    __init__.py
    generator.py                         # gera CSV MSC sintético
    profiler.py                          # mede tempo/memória por etapa e por regra
    reporter.py                          # gera ref/benchmark_performance.md
tests/test_benchmark.py                  # testes dos 3 componentes
ref/benchmark_performance.md             # entregável (gerado pelo script)
```

**Fluxo:** CLI recebe tamanhos → pra cada tamanho, gera CSV → roda pipeline
instrumentado → coleta `BenchmarkResult` → reporter escreve markdown.

---

## 4. Componentes

### 4.1 `generator.py`

**Função principal:** `generate_csv(n_rows: int, path: Path, seed: int = 42) -> Path`

- Escreve CSV no mesmo formato dos reais de `ref/amostras/`:
  - Delimiter `;`
  - Line ending `\r` (Mac Classic)
  - Header na linha 2: `CONTA;IC1;TIPO1;...;IC6;TIPO6;Valor;Tipo_valor;Natureza_valor`
  - Linha 1: `<siconfi>;<competencia>` (ex: `9999999EX;2026-01`)
- Combinações `IC/TIPO` válidas: sorteadas de `ref/mapeamento_ic_tipo.csv`
- Contas contábeis: sorteadas de `ref/pcasp.csv` filtrando `nivel` analítico
- Valores: `np.random.uniform(-1e7, 1e7)` com seed fixo
- `Tipo_valor ∈ {beginning_balance, period_change, ending_balance}`
- `Natureza_valor ∈ {D, C}`
- Sem garantia de D=C balanceado — é stress test

### 4.2 `profiler.py`

Dataclasses (frozen):

```python
@dataclass(frozen=True)
class StageMetrics:
    name: str
    wall_seconds: float
    rss_delta_mb: float

@dataclass(frozen=True)
class RuleMetrics:
    rule_id: str
    wall_seconds: float
    issue_count: int
    failed: bool = False

@dataclass(frozen=True)
class BenchmarkResult:
    n_rows: int
    total_seconds: float
    peak_rss_mb: float
    throughput_rows_per_sec: float
    stages: list[StageMetrics]
    rules: list[RuleMetrics]
    failed: bool = False
    failure_reason: str | None = None
```

APIs:

- `measure(name: str)` — context manager; mede wall time (`time.perf_counter`)
  e RSS delta (`resource.getrusage(RUSAGE_SELF).ru_maxrss`)
- `instrument_rules()` — context manager que patcha `Rule.execute` temporariamente
  pra capturar `RuleMetrics` por regra; reverte no `__exit__`

**Nota sobre memória:** `ru_maxrss` é global ao processo (não por etapa).
Registramos RSS delta por etapa como aproximação e peak global como valor honesto.

### 4.3 `reporter.py`

**Função principal:** `write_report(results: list[BenchmarkResult], output_path: Path) -> None`

Layout do markdown gerado:

```markdown
# Benchmark de Performance

**Gerado em:** <data>
**Commit:** <git rev-parse HEAD>
**Python:** <version> · **pandas:** <version>
**Máquina:** <platform.processor()>

## Resumo geral

| Tamanho | Tempo total | Memória pico | Throughput |
|---|---|---|---|
| 100k | 12.3s | 450 MB | 8.1k rows/s |
| 500k | 68.1s | 1.8 GB | 7.3k rows/s |
| 1M | FAIL: OOM | — | — |

## Tempo por etapa

| Tamanho | read_csv | normalize_ic | run_engine |
|---|---|---|---|
| 100k | 1.2s | 3.4s | 7.7s |
| ... |

## Top-5 regras mais lentas

### 100k linhas
| Regra | Tempo | Pendências |
|---|---|---|
| R030 | 2.1s | 14 |
| ... |

### 500k linhas
| ... |
```

### 4.4 `scripts/benchmark.py`

CLI args:

- `--rows 100000 500000 1000000` (tamanhos a testar)
- `--seed 42`
- `--output ref/benchmark_performance.md`
- `--keep-csv` (preserva CSVs gerados em `data/benchmark/` pra inspeção)

Fluxo:

1. Pra cada tamanho: gera CSV em `data/benchmark/msc_<n>.csv`
2. Executa pipeline instrumentado (ver §5)
3. Captura `BenchmarkResult`
4. Em caso de `MemoryError` ou falha fatal: marca linha como FAIL e continua
5. Apaga `data/benchmark/` no final (exceto se `--keep-csv`)
6. Escreve relatório via `reporter.write_report()`

---

## 5. Data flow

```python
settings = load_settings()
context = EngineContext(
    competencia="2026-01",
    siconfi="9999999EX",
    settings=settings,
    usuario="benchmark",
)

for n in rows_list:
    csv_path = generator.generate_csv(n_rows=n, path=Path(f"data/benchmark/msc_{n}.csv"), seed=seed)

    try:
        with profiler.measure("total") as total:
            with profiler.measure("read_csv") as m_read:
                raw = read_msc_csv(csv_path)
            with profiler.measure("normalize_ic") as m_norm:
                df_norm = normalize_ic(raw.df)
            with profiler.instrument_rules() as rule_metrics:
                with profiler.measure("run_engine") as m_engine:
                    result = run_engine(df_norm, context)

        results.append(BenchmarkResult(
            n_rows=n,
            total_seconds=total.wall_seconds,
            peak_rss_mb=read_peak_rss_mb(),
            throughput_rows_per_sec=n / total.wall_seconds,
            stages=[m_read.to_stage(), m_norm.to_stage(), m_engine.to_stage()],
            rules=rule_metrics,
        ))
    except MemoryError:
        logger.error("OOM at n_rows=%s", n)
        results.append(BenchmarkResult(n_rows=n, ..., failed=True, failure_reason="OOM"))
    except Exception as exc:
        logger.error("Benchmark failure at n_rows=%s", n, exc_info=True)
        results.append(BenchmarkResult(..., failed=True, failure_reason=str(exc)))

reporter.write_report(results, output_path)
```

---

## 6. Error handling

| Cenário | Ação |
|---|---|
| `MemoryError` durante geração ou pipeline | Log `logger.error()`, marca `FAIL: OOM` na tabela, segue pro próximo tamanho |
| `RuleExecutionError` em regra específica | Capturado dentro de `instrument_rules()`; marca a regra com `failed=True`, continua as outras |
| `InputFormatError` no `read_msc_csv` | **Não captura** — bug no gerador, deve abortar |
| Disco cheio ao gerar CSV | Aborta, sem fallback |
| `KeyboardInterrupt` | Escreve relatório parcial com os tamanhos completados + linha "INTERROMPIDO" |

Nova exceção: `BenchmarkError(RankingMSCError)` em `src/ranking_msc/exceptions.py`
pra erros específicos do módulo (gerador não consegue sortear IC válido, etc).

---

## 7. Testing

**`tests/test_benchmark.py`** com três classes:

### 7.1 `TestGenerator`
- `test_generate_csv_schema_correto` — colunas, delimiter `;`, line ending `\r`
- `test_generate_csv_n_rows_correto` — gera 100 linhas, conta exatamente 100
- `test_generate_csv_determinístico_com_seed` — mesmo seed → mesmo conteúdo
- `test_generate_csv_ic_tipo_válidos` — `normalize_ic` não levanta no CSV gerado

### 7.2 `TestProfiler`
- `test_measure_retorna_stage_metrics` — context manager popula `wall_seconds` e `rss_delta_mb`
- `test_instrument_rules_decora_e_reverte` — patch dentro, original fora
- `test_benchmark_result_throughput_calculado` — divisão correta

### 7.3 `TestReporter`
- `test_write_report_gera_três_tabelas` — mock `BenchmarkResult`, output contém "Resumo geral", "Tempo por etapa", "Top-5 regras"
- `test_report_header_tem_commit_hash_e_data`

### 7.4 O que NÃO se testa
- Tempos absolutos (flaky por hardware)
- CLI end-to-end em tamanhos grandes (lento)

### 7.5 Smoke manual
```bash
python scripts/benchmark.py --rows 1000 --output /tmp/bench.md
```
Deve rodar em <5s.

### 7.6 Comandos de qualidade (CLAUDE.md §6)
```bash
pytest tests/test_benchmark.py -v
ruff check src/ranking_msc/benchmark/ tests/test_benchmark.py scripts/benchmark.py
mypy src/ranking_msc/benchmark/
```

---

## 8. Convenções seguidas (CLAUDE.md)

- [x] Python 3.11+, `from __future__ import annotations`, type hints em tudo
- [x] Dataclasses frozen pra DTOs (`StageMetrics`, `RuleMetrics`, `BenchmarkResult`)
- [x] Exceções de `ranking_msc.exceptions` (adiciona `BenchmarkError`)
- [x] `logger`, nunca `print()`
- [x] Docstrings em português
- [x] Inglês pra nomes de código; português pra conceitos e mensagens
- [x] Sem tocar em `app/web_app.py`
- [x] Caminhos via argumentos CLI, sem hardcode

---

## 9. Entregáveis

1. `src/ranking_msc/benchmark/` (módulo novo com 3 arquivos)
2. `scripts/benchmark.py` (CLI)
3. `tests/test_benchmark.py`
4. `ref/benchmark_performance.md` (gerado rodando o script em 100k/500k/1M)
5. Entrada nova em `src/ranking_msc/exceptions.py`: `BenchmarkError`
6. `.gitignore` atualizado pra ignorar `data/benchmark/` (se já não coberto)

---

## 10. Fora de escopo

- Hard thresholds de performance (CI gate) — decisão consciente pra v1
- Gráficos de escalabilidade (matplotlib) — baixo ROI pro tamanho atual do time
- Otimização das regras identificadas como lentas — isso é **F4-09**
- Benchmark de `write_snapshot_atomic` / `export_issues_excel` — fora do pipeline principal
- Benchmark do `compare_periods` / `report_consolidado` — podem virar F4-08b se relevante
