# Benchmark de Performance

**Gerado em:** 2026-04-27 16:06 UTC
**Commit:** 8c7e651
**Python:** 3.12.3 · **pandas:** 3.0.2
**Máquina:** x86_64

## Resumo geral

| Tamanho | Tempo total | Memória pico | Throughput |
|---|---|---|---|
| 100k | 28.7s | 424 MB | 3482.2 rows/s |
| 500k | 53.6s | 805 MB | 9335.5 rows/s |
| 1M | 70.5s | 1477 MB | 14174.5 rows/s |

## Tempo por etapa

| Tamanho | read_csv | normalize_ic | run_engine |
|---|---|---|---|
| 100k | 4.0s | 7.0s | 17.7s |
| 500k | 20.3s | 8.4s | 24.9s |
| 1M | 37.7s | 8.0s | 24.8s |

## Top-5 regras mais lentas

### 100k linhas

| Regra | Tempo | Pendências | Status |
|---|---|---|---|
| R081 | 7.76s | 113712 | ✅ |
| R031 | 2.96s | 60058 | ✅ |
| R060 | 1.41s | 14345 | ✅ |
| R020 | 0.68s | 3691 | ✅ |
| R024 | 0.49s | 6119 | ✅ |

### 500k linhas

| Regra | Tempo | Pendências | Status |
|---|---|---|---|
| R081 | 12.58s | 176411 | ✅ |
| R031 | 4.27s | 91267 | ✅ |
| R060 | 2.04s | 22398 | ✅ |
| R032 | 0.90s | 27831 | ✅ |
| R020 | 0.61s | 2577 | ✅ |

### 1M linhas

| Regra | Tempo | Pendências | Status |
|---|---|---|---|
| R081 | 12.12s | 177440 | ✅ |
| R031 | 4.10s | 91781 | ✅ |
| R060 | 2.02s | 22524 | ✅ |
| R032 | 1.32s | 39359 | ✅ |
| R020 | 0.62s | 2558 | ✅ |

