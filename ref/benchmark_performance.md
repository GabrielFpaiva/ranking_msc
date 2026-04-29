# Benchmark de Performance

**Gerado em:** 2026-04-29 18:45 UTC
**Commit:** c334b24
**Python:** 3.12.3 · **pandas:** 3.0.2
**Máquina:** x86_64

## Resumo geral

| Tamanho | Tempo total | Memória pico | Throughput |
|---|---|---|---|
| 100k | 12.4s | 460 MB | 8040.9 rows/s |
| 500k | 30.4s | 782 MB | 16431.1 rows/s |
| 1M | 48.8s | 1492 MB | 20489.9 rows/s |

## Tempo por etapa

| Tamanho | read_csv | normalize_ic | run_engine |
|---|---|---|---|
| 100k | 3.5s | 4.9s | 4.1s |
| 500k | 17.2s | 7.6s | 5.6s |
| 1M | 35.2s | 7.9s | 5.7s |

## Top-5 regras mais lentas

### 100k linhas

| Regra | Tempo | Pendências | Status |
|---|---|---|---|
| R081 | 1.12s | 113712 | ✅ |
| R020 | 0.91s | 3691 | ✅ |
| R031 | 0.66s | 60058 | ✅ |
| R060 | 0.14s | 14345 | ✅ |
| R070 | 0.13s | 2529 | ✅ |

### 500k linhas

| Regra | Tempo | Pendências | Status |
|---|---|---|---|
| R081 | 1.70s | 176411 | ✅ |
| R031 | 1.00s | 91267 | ✅ |
| R020 | 0.94s | 2577 | ✅ |
| R032 | 0.28s | 27831 | ✅ |
| R070 | 0.26s | 6053 | ✅ |

### 1M linhas

| Regra | Tempo | Pendências | Status |
|---|---|---|---|
| R081 | 1.68s | 177440 | ✅ |
| R031 | 0.98s | 91781 | ✅ |
| R020 | 0.96s | 2558 | ✅ |
| R032 | 0.38s | 39359 | ✅ |
| R070 | 0.24s | 6119 | ✅ |

