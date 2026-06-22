# UX-08/09 — Filtro e deep-link por dimensão (Implementation Plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Filtrar Pendências por dimensão de pontuação e permitir clicar numa dimensão do score para abrir Pendências já filtrada.

**Architecture:** Backend mapeia a categoria de regra de cada pendência para a dimensão de pontuação (via `DIMENSION_CATEGORIES` já existente) e filtra; `GET /api/pendencias` ganha o param `dimensao`. Frontend ganha um seletor de dimensão no rail de Pendências e barras de score clicáveis que fazem deep-link com query param.

**Tech Stack:** Python/FastAPI/pandas (backend); React+TS+Vite, react-router (frontend).

## Global Constraints

- Vocabulário = as **5 dimensões de pontuação**: `Estrutura`, `Fechamento`, `IC_Dominio`, `PCASP_Completude`, `Temporal` (chaves de `DIMENSION_WEIGHTS`).
- Reusar o mapeamento existente (`DIMENSION_CATEGORIES` / `_CATEGORY_TO_DIMENSION` em `score_engine.py`) — não duplicar.
- Sem mudança de contrato existente; `dimensao` é param **opcional** (compatível com chamadas atuais).
- Python ≥ 3.11, `from __future__ import annotations`, docstrings PT. Frontend: padrões `samid-*`, efeito com `cancelled`.
- Verificação backend via `.venv/bin/python -m pytest|ruff|mypy`; frontend via `npm run lint|typecheck|build` (em `web/`) + checagem manual.

---

## File Structure

- Modify: `src/ranking_msc/engine/score_engine.py` — helper público `scoring_dimension(category) -> str | None`.
- Modify: `src/ranking_msc/outputs/aggregations.py` — `filter_pendencias` ganha `dimensao`.
- Modify: `app/api/routes/pendencias.py` — query param `dimensao`.
- Modify: `tests/test_aggregations.py` — teste do filtro por dimensão.
- Modify: `web/src/api/client.ts` — param `dimensao` em `pendencias`.
- Modify: `web/src/screens/Pendencias.tsx` — seletor de dimensão + leitura do query param.
- Modify: `web/src/screens/Home.tsx`, `web/src/screens/Executivo.tsx` — barras de dimensão clicáveis (deep-link).
- Modify: `doc/backlog.md` — marcar UX-08/09 concluídas.

---

### Task 1: Backend — filtro por dimensão de pontuação

**Files:**
- Modify: `src/ranking_msc/engine/score_engine.py`
- Modify: `src/ranking_msc/outputs/aggregations.py`
- Modify: `app/api/routes/pendencias.py`
- Test: `tests/test_aggregations.py`

**Interfaces:**
- Produces: `scoring_dimension(category: str) -> str | None` (score_engine); `filter_pendencias(..., dimensao: str | None = None)`; query param `dimensao` em `GET /api/pendencias`.

- [ ] **Step 1: Escrever teste que falha** — adicionar em `tests/test_aggregations.py`

```python
def test_filter_pendencias_por_dimensao_de_pontuacao() -> None:
    """Filtra por dimensão de score, mapeando a categoria da regra."""
    import pandas as pd
    from ranking_msc.outputs.aggregations import filter_pendencias

    df = pd.DataFrame(
        [
            {"regra_id": "R030", "dimensao": "Fechamento", "severidade": "ERRO",
             "conta_contabil": "111"},
            {"regra_id": "R020", "dimensao": "IC", "severidade": "ERRO",
             "conta_contabil": "222"},
            {"regra_id": "R045", "dimensao": "ND", "severidade": "ALERTA",
             "conta_contabil": "333"},
        ]
    )
    # "IC" e "ND" mapeiam para a dimensão de pontuação "IC_Dominio"
    out = filter_pendencias(df, dimensao="IC_Dominio")
    assert set(out["regra_id"]) == {"R020", "R045"}
    out2 = filter_pendencias(df, dimensao="Fechamento")
    assert set(out2["regra_id"]) == {"R030"}
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/bin/python -m pytest tests/test_aggregations.py::test_filter_pendencias_por_dimensao_de_pontuacao -q`
Expected: FAIL (`filter_pendencias` não aceita `dimensao`).

- [ ] **Step 3: Implementar**

Em `src/ranking_msc/engine/score_engine.py`, após a definição de `_CATEGORY_TO_DIMENSION`, adicionar:

```python
def scoring_dimension(category: str) -> str | None:
    """Mapeia a categoria de uma regra para a dimensão de pontuação (ou None)."""
    return _CATEGORY_TO_DIMENSION.get(category)
```

Em `src/ranking_msc/outputs/aggregations.py`, importar e estender o filtro:

```python
from ranking_msc.engine.score_engine import scoring_dimension
```

Na assinatura de `filter_pendencias`, adicionar `dimensao: str | None = None` (após `conta_contabil_prefix`), e antes do `return`:

```python
    if dimensao:
        df = df[df["dimensao"].astype(str).map(scoring_dimension) == dimensao]
```

> Atenção a import circular: `aggregations.py` já importa de `engine`? Se sim, mantenha o import no topo; se gerar ciclo, importe `scoring_dimension` dentro da função.

Em `app/api/routes/pendencias.py`, adicionar o query param e repassar:

```python
    dimensao: str | None = Query(None, description="Dimensão de pontuação (ex: Fechamento, IC_Dominio)"),
```

e na chamada:

```python
    filtered = filter_pendencias(
        df,
        regra_id=regra_id,
        severidade=severidade,
        conta_contabil_prefix=conta_prefix,
        dimensao=dimensao,
    )
```

- [ ] **Step 4: Rodar e ver passar**

Run: `.venv/bin/python -m pytest tests/test_aggregations.py -q && .venv/bin/python -m ruff check src/ app/ tests/test_aggregations.py && .venv/bin/python -m mypy src/ app/api/`
Expected: tudo verde.

- [ ] **Step 5: Commit**

```bash
git add src/ranking_msc/engine/score_engine.py src/ranking_msc/outputs/aggregations.py app/api/routes/pendencias.py tests/test_aggregations.py
git commit -m "UX-09: filter pendencias by scoring dimension (backend)"
```

---

### Task 2: Frontend UX-09 — seletor de dimensão em Pendências

**Files:**
- Modify: `web/src/api/client.ts`
- Modify: `web/src/screens/Pendencias.tsx`

**Interfaces:**
- Consumes: `GET /api/pendencias?dimensao=` (Task 1).

- [ ] **Step 1: Param no client** — em `web/src/api/client.ts`, no método `pendencias`, adicionar `dimensao` ao tipo de `params` e ao `qs`. O método já monta `qs(params)`; basta incluir `dimensao?: string` na assinatura do objeto de params:

```ts
  pendencias: (params: {
    siconfi: string;
    competencia: string;
    regra_id?: string;
    severidade?: string;
    conta_prefix?: string;
    dimensao?: string;
    offset?: number;
    limit?: number;
  }): Promise<PendenciasPage> =>
    fetchAuth(`${BASE}/pendencias${qs(params)}`).then((r) => jsonOrThrow<PendenciasPage>(r)),
```

> Confirmar o nome real do param de conta (`conta_prefix`) lendo o método atual antes de editar.

- [ ] **Step 2: Seletor de dimensão em `Pendencias.tsx`**

Adicionar a lista de dimensões no topo do arquivo:

```ts
const DIM_OPTIONS: { value: string; label: string }[] = [
  { value: '', label: 'Todas' },
  { value: 'Estrutura', label: 'Estrutura' },
  { value: 'Fechamento', label: 'Fechamento' },
  { value: 'IC_Dominio', label: 'IC / Domínio' },
  { value: 'PCASP_Completude', label: 'PCASP / Completude' },
  { value: 'Temporal', label: 'Temporal' },
];
```

Adicionar estado `const [filterDimensao, setFilterDimensao] = useState('');`, incluir `dimensao: filterDimensao || undefined` no objeto passado a `api.pendencias`, incluir `filterDimensao` nas deps do efeito de fetch, e em `resetFilters()` adicionar `setFilterDimensao('')`.

No rail de filtros (antes de "Regra"), adicionar:

```tsx
        <div className="samid-filter-group">
          <span className="samid-filter-lbl">Dimensão</span>
          <select
            className="samid-select"
            value={filterDimensao}
            onChange={(e) => handleFilterChange(setFilterDimensao)(e.target.value)}
          >
            {DIM_OPTIONS.map((o) => (
              <option key={o.value || 'todas'} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>
```

- [ ] **Step 3: Verificar**

Run (em `web/`): `npm run lint && npm run typecheck && npm run build`
Expected: verde.

- [ ] **Step 4: Commit**

```bash
git add web/src/api/client.ts web/src/screens/Pendencias.tsx
git commit -m "UX-09: dimension filter in Pendencias rail"
```

---

### Task 3: Frontend UX-08 — deep-link das barras de score

**Files:**
- Modify: `web/src/screens/Pendencias.tsx` (ler query param)
- Modify: `web/src/screens/Home.tsx`, `web/src/screens/Executivo.tsx` (barras clicáveis)

**Interfaces:**
- Consumes: o estado `filterDimensao` e `DIM_OPTIONS` (Task 2).

- [ ] **Step 1: Pendências inicializa o filtro pelo query param**

Em `Pendencias.tsx`, importar `useSearchParams` de `react-router-dom` e inicializar o estado a partir do param:

```tsx
import { Link, useSearchParams } from 'react-router-dom';
// ...
  const [searchParams] = useSearchParams();
  const [filterDimensao, setFilterDimensao] = useState(searchParams.get('dimensao') ?? '');
```

(substitui a inicialização vazia do Step da Task 2).

- [ ] **Step 2: Barras clicáveis no Home**

Em `web/src/screens/Home.tsx`, importar `useNavigate`:

```tsx
import { useNavigate } from 'react-router-dom';
```

No componente: `const navigate = useNavigate();`. Tornar cada `.samid-score-row` do breakdown clicável (no `.map` das dimensões do summary):

```tsx
                  <div
                    key={key}
                    className="samid-score-row"
                    role="button"
                    tabIndex={0}
                    style={{ cursor: 'pointer' }}
                    onClick={() => navigate(`/pendencias?dimensao=${encodeURIComponent(dim.dimension)}`)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') navigate(`/pendencias?dimensao=${encodeURIComponent(dim.dimension)}`);
                    }}
                  >
```

(substitui o `<div key={key} className="samid-score-row">` atual, mantendo os filhos.)

- [ ] **Step 3: Barras clicáveis no Executivo**

Mesmo padrão em `web/src/screens/Executivo.tsx`, no breakdown `Object.values(score.dimensions).map((dim) => ...)`: importar `useNavigate`, e tornar cada `.samid-score-row` clicável navegando para `/pendencias?dimensao=${encodeURIComponent(dim.dimension)}`.

- [ ] **Step 4: Verificar**

Run (em `web/`): `npm run lint && npm run typecheck && npm run build`
Expected: verde.

- [ ] **Step 5: Commit**

```bash
git add web/src/screens/Pendencias.tsx web/src/screens/Home.tsx web/src/screens/Executivo.tsx
git commit -m "UX-08: deep-link score dimension bars to filtered Pendencias"
```

---

### Task 4: Verificação manual + docs

**Files:**
- Modify: `doc/backlog.md`

- [ ] **Step 1: Validar no navegador**

Subir back/front, logar, processar ≥1 competência. Em Pendências, selecionar "Fechamento" no novo filtro → lista reduz às de Fechamento. No Início/Executivo, clicar na barra "Fechamento" → vai para Pendências já filtrada por Fechamento. Testar IC_Dominio (deve trazer pendências de IC, ND, FR… mapeadas).

- [ ] **Step 2: Marcar UX-08/09 concluídas no backlog**

Em `doc/backlog.md`, nas entradas `UX-09` e `UX-08`, marcar os checkboxes como `[x]` e anotar "CONCLUIDA".

- [ ] **Step 3: Commit**

```bash
git add doc/backlog.md
git commit -m "UX-08/09: mark done in backlog"
```

---

## Self-Review

- **Cobertura:** filtro backend por dimensão de score (Task 1, com mapeamento reusado), seletor frontend (Task 2), deep-link das barras + leitura de query param (Task 3), verificação + docs (Task 4). Vocabulário das 5 dimensões respeitado.
- **Placeholders:** nenhum — código completo nos steps.
- **Consistência de tipos:** `dimensao: str | None` no backend; `dimensao?: string` no client; valores = chaves de `DIMENSION_WEIGHTS`. `scoring_dimension` retorna `str | None`, usado em `.map(...)` no filtro.
